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

from creatorpulse import collector
from creatorpulse.collector import collect_once
from creatorpulse.config import Creator, load_creators
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


# --- 03-05: failure isolation, the crash guarantee, and idempotency -------------------------
#
# These tests drive collect_once() through a fake in-memory fetcher registry — two distinct
# source keys, never the real YouTube fetcher — so they need no credential and no fixture.
# 03-03 (Twitch) is deferred; nothing below depends on it.


def _ok_record(source: str, metric_date: date) -> MetricRecord:
    return MetricRecord(
        creator_id="",  # filled in by collect_once
        source=source,
        metric_date=metric_date,
        followers=1,
        views=2,
        likes=None,
        video_count=3,
        is_live=None,
        collected_at=datetime.now(UTC),
    )


def test_one_source_failure_does_not_abort_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def ok_fetch(identifier: str, metric_date: date) -> MetricRecord:
        return _ok_record("source_a", metric_date)

    def fail_fetch(identifier: str, metric_date: date) -> MetricRecord:
        raise ValueError("boom")

    monkeypatch.setitem(collector.FETCHERS, "source_a", ok_fetch)
    monkeypatch.setitem(collector.FETCHERS, "source_b", fail_fetch)

    creators = [Creator(id="c1", name="C1", sources={"source_a": "id1", "source_b": "id2"})]
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    with caplog.at_level("INFO", logger="creatorpulse"):
        result = collect_once(conn, creators)

    assert result.rows_written == 1
    assert result.failure_count == 1
    fail_lines = [r.getMessage() for r in caplog.records if "fetch failed" in r.getMessage()]
    assert len(fail_lines) == 1
    assert "creator=c1" in fail_lines[0]
    assert "source=source_b" in fail_lines[0]
    assert "ValueError" in fail_lines[0]


def test_one_failing_source_fails_every_creator_no_short_circuit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_fetch(identifier: str, metric_date: date) -> MetricRecord:
        raise ValueError("boom")

    monkeypatch.setitem(collector.FETCHERS, "source_a", fail_fetch)

    creators = [
        Creator(id="c1", name="C1", sources={"source_a": "id1"}),
        Creator(id="c2", name="C2", sources={"source_a": "id2"}),
        Creator(id="c3", name="C3", sources={"source_a": "id3"}),
    ]
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    result = collect_once(conn, creators)

    assert result.failure_count == 3  # no cross-pair state, no short-circuit (D-15)
    assert result.rows_written == 0


def test_two_failing_sources_on_one_creator_produce_two_log_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fail_fetch(identifier: str, metric_date: date) -> MetricRecord:
        raise ValueError("broke")

    monkeypatch.setitem(collector.FETCHERS, "source_a", fail_fetch)
    monkeypatch.setitem(collector.FETCHERS, "source_b", fail_fetch)

    creators = [Creator(id="c1", name="C1", sources={"source_a": "id1", "source_b": "id2"})]
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    with caplog.at_level("INFO", logger="creatorpulse"):
        result = collect_once(conn, creators)

    assert result.failure_count == 2
    fail_lines = [r.getMessage() for r in caplog.records if "fetch failed" in r.getMessage()]
    assert len(fail_lines) == 2
    assert any("source=source_a" in line for line in fail_lines)
    assert any("source=source_b" in line for line in fail_lines)


def test_failure_with_empty_message_still_names_creator_and_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fail_fetch(identifier: str, metric_date: date) -> MetricRecord:
        raise KeyError()  # str(KeyError()) == "" — an empty message on purpose

    monkeypatch.setitem(collector.FETCHERS, "source_a", fail_fetch)

    creators = [Creator(id="c1", name="C1", sources={"source_a": "id1"})]
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    with caplog.at_level("INFO", logger="creatorpulse"):
        result = collect_once(conn, creators)

    assert result.failure_count == 1
    fail_lines = [r.getMessage() for r in caplog.records if "fetch failed" in r.getMessage()]
    assert len(fail_lines) == 1
    assert "creator=c1" in fail_lines[0]
    assert "source=source_a" in fail_lines[0]
    assert "KeyError" in fail_lines[0]  # the type names the failure even with no message


def test_processing_order_matches_file_order_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []

    def counting_fetch(identifier: str, metric_date: date) -> MetricRecord:
        calls.append(identifier)
        if identifier == "id1":
            raise ValueError("first fails")
        return _ok_record("source_a", metric_date)

    monkeypatch.setitem(collector.FETCHERS, "source_a", counting_fetch)

    creators = [
        Creator(id="c1", name="C1", sources={"source_a": "id1"}),
        Creator(id="c2", name="C2", sources={"source_a": "id2"}),
        Creator(id="c3", name="C3", sources={"source_a": "id3"}),
    ]
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    with caplog.at_level("INFO", logger="creatorpulse"):
        result = collect_once(conn, creators)

    assert calls == ["id1", "id2", "id3"]  # second and third still ran, in file order
    assert result.failure_count == 1
    assert result.rows_written == 2
    fail_lines = [r.getMessage() for r in caplog.records if "fetch failed" in r.getMessage()]
    assert len(fail_lines) == 1
    assert "creator=c1" in fail_lines[0]


def test_registry_miss_produces_skip_and_no_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    creators = [Creator(id="c1", name="C1", sources={"source_unregistered": "id1"})]
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    with caplog.at_level("INFO", logger="creatorpulse"):
        result = collect_once(conn, creators)

    assert result.rows_written == 0
    assert result.failure_count == 0
    skip_lines = [r.getMessage() for r in caplog.records if "skip" in r.getMessage()]
    assert len(skip_lines) == 1
    assert "source=source_unregistered" in skip_lines[0]


def test_all_rows_from_one_run_share_metric_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def ok_fetch(identifier: str, metric_date: date) -> MetricRecord:
        return _ok_record("source_a", metric_date)

    monkeypatch.setitem(collector.FETCHERS, "source_a", ok_fetch)

    creators = [
        Creator(id="c1", name="C1", sources={"source_a": "id1"}),
        Creator(id="c2", name="C2", sources={"source_a": "id2"}),
    ]
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    collect_once(conn, creators)

    conn.row_factory = sqlite3.Row
    dates = {row["metric_date"] for row in conn.execute("SELECT metric_date FROM metrics")}
    assert len(dates) == 1  # RUN-05 — every row from one run carries the same metric_date


def test_runs_row_written_on_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def ok_fetch(identifier: str, metric_date: date) -> MetricRecord:
        return _ok_record("source_a", metric_date)

    monkeypatch.setitem(collector.FETCHERS, "source_a", ok_fetch)
    monkeypatch.setitem(collector.FETCHERS, "source_b", ok_fetch)

    real_upsert = collector.upsert_metric
    call_count = {"n": 0}

    def flaky_upsert(conn: sqlite3.Connection, record: MetricRecord) -> None:
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise sqlite3.OperationalError("disk full")
        real_upsert(conn, record)

    monkeypatch.setattr(collector, "upsert_metric", flaky_upsert)

    creators = [Creator(id="c1", name="C1", sources={"source_a": "id1", "source_b": "id2"})]
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    with pytest.raises(sqlite3.OperationalError):
        collect_once(conn, creators)

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    assert row["rows_written"] == 1  # one pair succeeded before the crash — not zero, not two
    assert row["failure_count"] == 0


def test_idempotent_rerun_same_day(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> "_FixedDateTime":
            return fixed_now  # type: ignore[return-value]

    monkeypatch.setattr(collector, "datetime", _FixedDateTime)

    def ok_fetch(identifier: str, metric_date: date) -> MetricRecord:
        return _ok_record("source_a", metric_date)

    monkeypatch.setitem(collector.FETCHERS, "source_a", ok_fetch)

    creators = [Creator(id="c1", name="C1", sources={"source_a": "id1"})]
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    collect_once(conn, creators)
    collect_once(conn, creators)

    metrics_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    runs_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert metrics_count == 1  # same metric_date both times — upsert, not duplicate
    assert runs_count == 2  # deliberately no value-equality assertion — a real re-fetch can differ
