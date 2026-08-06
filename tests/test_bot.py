"""Tests for bot.py's pure formatters, config.py's resolve_discord_config(), and cli.py's
D-08/D-09 failure-alert path (build_alert_text, _post_alert, and their two call sites in
run_collect) — against a temp SQLite database, following tests/test_sheets.py's pattern
one-for-one. No discord.py is imported here and nothing here is mocked beyond requests.post
and sheets.sync; the gateway, the task loop, and command registration are untested by design
(D-20) and that gap is recorded in 06-VALIDATION.md rather than papered over.
"""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from creatorpulse import collector
from creatorpulse.bot import build_digest_text, format_percent, percent_change
from creatorpulse.cli import _post_alert, build_alert_text, run_collect
from creatorpulse.config import DiscordConfigError, resolve_discord_config
from creatorpulse.db import DELTA_PLACEHOLDER, connect, upsert_metric
from creatorpulse.models import MetricRecord, RunFailure
from creatorpulse.sheets import SheetNotShared


def _record(**overrides: Any) -> MetricRecord:
    base: dict[str, Any] = {
        "creator_id": "c1",
        "source": "youtube",
        "metric_date": date(2026, 1, 1),
        "followers": 100,
        "views": 200,
        "likes": None,
        "video_count": 5,
        "is_live": None,
        "collected_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return MetricRecord(**base)


_ALL_DISCORD_VARS = (
    "DISCORD_BOT_TOKEN",
    "DISCORD_CHANNEL_ID",
    "DISCORD_GUILD_ID",
    "DISCORD_WEBHOOK_URL",
)


def _set_all_discord_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "sekrit-token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "111")
    monkeypatch.setenv("DISCORD_GUILD_ID", "222")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")


# --- config: resolve_discord_config() ---------------------------------------------------


@pytest.mark.parametrize("missing_var", _ALL_DISCORD_VARS)
def test_config_missing_variable_raises_naming_that_variable(
    monkeypatch: pytest.MonkeyPatch, missing_var: str
) -> None:
    for var in _ALL_DISCORD_VARS:
        monkeypatch.delenv(var, raising=False)
    _set_all_discord_vars(monkeypatch)
    monkeypatch.delenv(missing_var, raising=False)

    with pytest.raises(DiscordConfigError) as exc_info:
        resolve_discord_config()

    assert missing_var in str(exc_info.value)


def test_config_channel_id_not_an_integer_raises_naming_the_variable_and_quoting_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_all_discord_vars(monkeypatch)
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "not-a-number")

    with pytest.raises(DiscordConfigError) as exc_info:
        resolve_discord_config()

    message = str(exc_info.value)
    assert "DISCORD_CHANNEL_ID" in message
    assert "not-a-number" in message


def test_config_guild_id_not_an_integer_raises_naming_the_variable_and_quoting_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_all_discord_vars(monkeypatch)
    monkeypatch.setenv("DISCORD_GUILD_ID", "also-not-a-number")

    with pytest.raises(DiscordConfigError) as exc_info:
        resolve_discord_config()

    message = str(exc_info.value)
    assert "DISCORD_GUILD_ID" in message
    assert "also-not-a-number" in message


def test_config_error_messages_never_contain_the_token_or_webhook_url_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_all_discord_vars(monkeypatch)
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "not-a-number")

    with pytest.raises(DiscordConfigError) as exc_info:
        resolve_discord_config()

    message = str(exc_info.value)
    assert "sekrit-token" not in message
    assert "https://discord.example/webhook" not in message


# --- percent_change() / format_percent() ------------------------------------------------


def test_percent_change_positive_pair_returns_the_ratio() -> None:
    assert percent_change(1200, 1000) == 0.2


def test_percent_change_zero_baseline_returns_none() -> None:
    assert percent_change(1000, 0) is None


def test_percent_change_missing_today_value_returns_none() -> None:
    assert percent_change(None, 1000) is None


def test_percent_change_missing_baseline_value_returns_none() -> None:
    assert percent_change(1000, None) is None


def test_percent_change_zero_today_against_nonzero_baseline_returns_negative_one() -> None:
    assert percent_change(0, 1000) == -1.0


def test_format_percent_renders_one_decimal_place_with_an_explicit_sign() -> None:
    assert format_percent(0.2544) == "+25.4%"


# --- build_digest_text() -----------------------------------------------------------------


def test_digest_text_orders_rows_by_absolute_percent_change_descending(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    # +10%
    upsert_metric(conn, _record(creator_id="small", metric_date=date(2026, 8, 4), views=1000))
    upsert_metric(conn, _record(creator_id="small", metric_date=date(2026, 8, 5), views=1100))
    # +50%
    upsert_metric(conn, _record(creator_id="big", metric_date=date(2026, 8, 4), views=1000))
    upsert_metric(conn, _record(creator_id="big", metric_date=date(2026, 8, 5), views=1500))
    # -30%
    upsert_metric(conn, _record(creator_id="neg", metric_date=date(2026, 8, 4), views=1000))
    upsert_metric(conn, _record(creator_id="neg", metric_date=date(2026, 8, 5), views=700))

    text = build_digest_text(conn, datetime(2026, 8, 5, 8, 15, tzinfo=UTC))
    lines = text.splitlines()[1:]

    assert [line.split(" / ")[0] for line in lines] == ["big", "neg", "small"]


def test_digest_text_places_row_with_no_computable_percent_after_every_row_that_has_one(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(
        conn, _record(creator_id="has-baseline", metric_date=date(2026, 8, 4), views=1000)
    )
    upsert_metric(
        conn, _record(creator_id="has-baseline", metric_date=date(2026, 8, 5), views=1200)
    )
    upsert_metric(conn, _record(creator_id="no-baseline", metric_date=date(2026, 8, 5), views=500))

    text = build_digest_text(conn, datetime(2026, 8, 5, 8, 15, tzinfo=UTC))
    lines = text.splitlines()[1:]

    assert lines[0].startswith("has-baseline")
    assert lines[1].startswith("no-baseline")


def test_digest_text_renders_delta_placeholder_for_missing_and_zero_baseline(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="no-baseline", metric_date=date(2026, 8, 5), views=500))
    upsert_metric(conn, _record(creator_id="zero-baseline", metric_date=date(2026, 8, 4), views=0))
    upsert_metric(
        conn, _record(creator_id="zero-baseline", metric_date=date(2026, 8, 5), views=700)
    )

    text = build_digest_text(conn, datetime(2026, 8, 5, 8, 15, tzinfo=UTC))
    by_creator = {line.split(" ", 1)[0]: line for line in text.splitlines()[1:]}

    assert f"(Δ {DELTA_PLACEHOLDER})" in by_creator["no-baseline"]
    assert f"(Δ {DELTA_PLACEHOLDER})" in by_creator["zero-baseline"]


def test_digest_text_on_empty_database_returns_an_explicit_message_not_an_empty_string(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    text = build_digest_text(conn, datetime(2026, 8, 5, 8, 15, tzinfo=UTC))

    assert text != ""
    assert "No rows recorded yet" in text


# --- build_alert_text() ------------------------------------------------------------------

_TWO_FAILURES = (
    RunFailure(creator_id="c1", source="youtube", cause="ValueError", message="boom"),
    RunFailure(creator_id="c2", source="youtube", cause="KeyError", message="missing"),
)
_ONE_FAILURE = (RunFailure(creator_id="c1", source="youtube", cause="ValueError", message="boom"),)


def test_alert_text_two_failures_names_both_creators_sources_causes_messages() -> None:
    text = build_alert_text(_TWO_FAILURES)

    assert "c1" in text and "c2" in text
    assert text.count("youtube") == 2
    assert "ValueError" in text and "boom" in text
    assert "KeyError" in text and "missing" in text


def test_alert_text_one_failure_header_says_one_not_two() -> None:
    text = build_alert_text(_ONE_FAILURE)

    header = text.splitlines()[0]
    assert "1" in header
    assert "2" not in header


# --- run_collect() alert call sites (D-08/D-09) -------------------------------------------

_CREATORS_YAML = """\
creators:
  - id: c1
    name: C1
    sources:
      youtube: "@handle1"
"""


def _write_creators_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "creators.yaml"
    path.write_text(_CREATORS_YAML, encoding="utf-8")
    return path


def _stub_sheets_sync_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make run_collect's Sheets step a no-op success, so alert-path assertions about the
    D-08 call site are not entangled with the D-09 call site."""
    monkeypatch.setenv("CREATORPULSE_SHEET_ID", "fake-sheet-id")
    monkeypatch.setenv("CREATORPULSE_SHEETS_KEYFILE", str(Path("fake-keyfile.json").resolve()))
    monkeypatch.setattr("creatorpulse.sheets.sync", lambda conn, sheet_id, keyfile: 0)


def _fake_204_response() -> Mock:
    resp = Mock(spec=requests.Response)
    resp.status_code = 204
    resp.text = ""
    return resp


def test_run_collect_with_one_failure_calls_alert_path_exactly_once_and_still_returns_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    _stub_sheets_sync_success(monkeypatch)

    def fail_fetch(identifier: str, metric_date: date) -> MetricRecord:
        raise ValueError("boom")

    monkeypatch.setitem(collector.FETCHERS, "youtube", fail_fetch)

    posts: list[str] = []

    def fake_post(url: str, json: dict[str, Any], timeout: int) -> Mock:
        posts.append(json["content"])
        return _fake_204_response()

    monkeypatch.setattr("creatorpulse.cli.requests.post", fake_post)

    exit_code = run_collect(_write_creators_yaml(tmp_path), tmp_path / "creatorpulse.db")

    assert exit_code == 0
    assert len(posts) == 1
    assert "1 failure" in posts[0]


def test_run_collect_with_zero_failures_does_not_call_the_alert_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    _stub_sheets_sync_success(monkeypatch)

    def ok_fetch(identifier: str, metric_date: date) -> MetricRecord:
        return MetricRecord(
            creator_id="",
            source="youtube",
            metric_date=date(2026, 1, 1),
            followers=1,
            views=2,
            likes=None,
            video_count=3,
            is_live=None,
            collected_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    monkeypatch.setitem(collector.FETCHERS, "youtube", ok_fetch)

    posts: list[str] = []

    def fake_post(url: str, json: dict[str, Any], timeout: int) -> Mock:
        posts.append(json["content"])
        return _fake_204_response()

    monkeypatch.setattr("creatorpulse.cli.requests.post", fake_post)

    exit_code = run_collect(_write_creators_yaml(tmp_path), tmp_path / "creatorpulse.db")

    assert exit_code == 0
    assert posts == []


def test_post_alert_with_webhook_url_unset_logs_warning_naming_that_variable_and_returns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    with caplog.at_level("WARNING", logger="creatorpulse"):
        _post_alert("some alert text")  # must not raise

    assert any("DISCORD_WEBHOOK_URL" in r.getMessage() for r in caplog.records)


def test_post_alert_whose_post_raises_connection_error_logs_and_returns_without_raising(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")

    def raise_connection_error(url: str, json: dict[str, Any], timeout: int) -> requests.Response:
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr("creatorpulse.cli.requests.post", raise_connection_error)

    with caplog.at_level("ERROR", logger="creatorpulse"):
        _post_alert("some alert text")  # must not raise

    assert any("alert POST raised" in r.getMessage() for r in caplog.records)


def test_run_collect_sheets_failure_and_broken_webhook_still_propagates_sheet_not_shared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    monkeypatch.setenv("CREATORPULSE_SHEET_ID", "fake-sheet-id")
    monkeypatch.setenv("CREATORPULSE_SHEETS_KEYFILE", str(Path("fake-keyfile.json").resolve()))

    def ok_fetch(identifier: str, metric_date: date) -> MetricRecord:
        return MetricRecord(
            creator_id="",
            source="youtube",
            metric_date=date(2026, 1, 1),
            followers=1,
            views=2,
            likes=None,
            video_count=3,
            is_live=None,
            collected_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    monkeypatch.setitem(collector.FETCHERS, "youtube", ok_fetch)

    def raise_sheet_not_shared(conn: Any, sheet_id: str, keyfile: Path) -> int:
        raise SheetNotShared("not shared")

    monkeypatch.setattr("creatorpulse.sheets.sync", raise_sheet_not_shared)

    def raise_connection_error(url: str, json: dict[str, Any], timeout: int) -> requests.Response:
        raise requests.ConnectionError("webhook is also down")

    monkeypatch.setattr("creatorpulse.cli.requests.post", raise_connection_error)

    with pytest.raises(SheetNotShared):
        run_collect(_write_creators_yaml(tmp_path), tmp_path / "creatorpulse.db")


def test_post_alert_never_logs_the_webhook_url_value(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    webhook_url = "https://discord.example/webhook/secret-token"
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", webhook_url)

    def raise_connection_error(url: str, json: dict[str, Any], timeout: int) -> requests.Response:
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr("creatorpulse.cli.requests.post", raise_connection_error)

    with caplog.at_level("DEBUG", logger="creatorpulse"):
        _post_alert("some alert text")

    assert all(webhook_url not in r.getMessage() for r in caplog.records)
