"""End-to-end slice test for the tracer: creators.yaml -> registry -> a real YouTube parse ->
a real SQLite row -> a runs row.

Fixtures only, no live network calls. HTTP is faked with Mock(spec=requests.Response) patched
onto creatorpulse.sources.youtube.requests.get.
"""

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from creatorpulse.collector import collect_once
from creatorpulse.config import load_creators
from creatorpulse.db import connect, upsert_metric
from creatorpulse.models import MetricRecord
from creatorpulse.sources import youtube

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CREATORS_YAML = Path(__file__).resolve().parent.parent / "creators.yaml"


def _fake_response(fixture_path: Path, status_code: int = 200) -> Mock:
    resp = Mock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json.loads(fixture_path.read_text(encoding="utf-8"))
    resp.raise_for_status.return_value = None
    return resp


def test_end_to_end_collect_once_writes_metrics_and_one_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    ok_response = _fake_response(FIXTURES / "youtube" / "channel_ok.json")
    monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", lambda *a, **kw: ok_response)

    conn = connect(tmp_path / "creatorpulse.db", create=True)
    creators = load_creators(CREATORS_YAML)

    with caplog.at_level("INFO", logger="creatorpulse"):
        result = collect_once(conn, creators)

    registered_pairs = sum(1 for c in creators for s in c.sources if s == "youtube")
    assert result.rows_written == registered_pairs

    metrics_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    assert metrics_count == registered_pairs

    runs_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert runs_count == 1

    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT metric_date FROM metrics").fetchall()
    dates = {row["metric_date"] for row in rows}
    assert len(dates) == 1  # RUN-05 — every row from one run carries the same metric_date

    skip_lines = [
        r.getMessage()
        for r in caplog.records
        if "skip" in r.getMessage() and "source=tiktok" in r.getMessage()
    ]
    assert skip_lines  # D-09/D-10 — tiktok is known but unregistered, so it is skipped not failed


def test_idempotent_rerun_same_date_leaves_metrics_count_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    ok_response = _fake_response(FIXTURES / "youtube" / "channel_ok.json")
    monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", lambda *a, **kw: ok_response)

    conn = connect(tmp_path / "creatorpulse.db", create=True)
    creators = load_creators(CREATORS_YAML)

    collect_once(conn, creators)
    first_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]

    collect_once(conn, creators)
    second_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]

    assert second_count == first_count  # DATA-01/DATA-02 — upsert, not duplicate

    runs_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert runs_count == 2  # DATA-03 — runs is append-only, two runs is two rows


def test_row_at_earlier_metric_date_survives_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    ok_response = _fake_response(FIXTURES / "youtube" / "channel_ok.json")
    monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", lambda *a, **kw: ok_response)

    conn = connect(tmp_path / "creatorpulse.db", create=True)
    creators = load_creators(CREATORS_YAML)

    yesterday = datetime.now(UTC).date() - timedelta(days=1)  # UTC-based: collector's clock
    prior_record = MetricRecord(
        creator_id="xqc",
        source="youtube",
        metric_date=yesterday,
        followers=111,
        views=222,
        likes=None,
        video_count=333,
        is_live=None,
        collected_at=datetime.now(UTC),
    )
    upsert_metric(conn, prior_record)

    collect_once(conn, creators)

    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM metrics WHERE creator_id = ? AND source = ? AND metric_date = ?",
        ("xqc", "youtube", yesterday.isoformat()),
    ).fetchone()
    assert row is not None
    assert row["followers"] == 111  # DATA-04 — untouched by today's run
    assert row["views"] == 222


def test_youtube_hidden_subscriber_count_maps_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    fixture = FIXTURES / "youtube" / "channel_hidden_subs_derived.json"
    monkeypatch.setattr(
        "creatorpulse.sources.youtube.requests.get",
        lambda *a, **kw: _fake_response(fixture),
    )

    record = youtube.fetch("@somehandle", date(2026, 8, 4))

    assert record.followers is None  # D-03 rule 1 — never 0, even though flag+"0" is present


def test_youtube_hidden_subscriber_count_omitted_key_maps_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    fixture = FIXTURES / "youtube" / "channel_hidden_subs_omitted_derived.json"
    monkeypatch.setattr(
        "creatorpulse.sources.youtube.requests.get",
        lambda *a, **kw: _fake_response(fixture),
    )

    record = youtube.fetch("@somehandle", date(2026, 8, 4))

    assert record.followers is None  # proves subscriberCount is never read on the hidden path


def test_youtube_not_found_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    fixture = FIXTURES / "youtube" / "channel_not_found.json"
    monkeypatch.setattr(
        "creatorpulse.sources.youtube.requests.get",
        lambda *a, **kw: _fake_response(fixture),
    )

    with pytest.raises(youtube.ChannelNotFound):
        youtube.fetch("@doesnotexist", date(2026, 8, 4))


def test_youtube_missing_view_count_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    body = json.loads((FIXTURES / "youtube" / "channel_ok.json").read_text(encoding="utf-8"))
    del body["items"][0]["statistics"]["viewCount"]
    resp = Mock(spec=requests.Response)
    resp.status_code = 200
    resp.json.return_value = body
    resp.raise_for_status.return_value = None
    monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", lambda *a, **kw: resp)

    with pytest.raises(KeyError):
        youtube.fetch("@xQcOW", date(2026, 8, 4))
