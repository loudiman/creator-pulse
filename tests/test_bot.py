"""Tests for bot.py's pure formatters, config.py's resolve_discord_config(), and cli.py's
D-08/D-09 failure-alert path (build_alert_text, _post_alert, and their two call sites in
run_collect) — against a temp SQLite database, following tests/test_sheets.py's pattern
one-for-one. No discord.py is imported here and nothing here is mocked beyond requests.post
and sheets.sync; the gateway, the task loop, and command registration are untested by design
(D-20) and that gap is recorded in 06-VALIDATION.md rather than papered over.
"""

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from creatorpulse import collector
from creatorpulse.bot import (
    MOVER_FLAG,
    TREND_LIMIT,
    build_digest_text,
    build_trend_text,
    format_percent,
    percent_change,
    staleness_hours,
)
from creatorpulse.cli import _post_alert, build_alert_text, run_collect
from creatorpulse.config import DiscordConfigError, resolve_discord_config
from creatorpulse.db import (
    DELTA_PLACEHOLDER,
    connect,
    upsert_metric,
    write_run_failures,
    write_run_row,
)
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


def _drop_flag_prefix(line: str) -> str:
    """Every mover row carries a fixed 2-char lead-in — MOVER_FLAG+space when flagged, two
    blank spaces otherwise (bot.py's column-alignment rule). Strip it before reading the
    creator_id back out of a row in a test."""
    return line[2:]


def _line_for(text: str, creator_id: str) -> str:
    for line in text.splitlines():
        if f"{creator_id} /" in line:
            return line
    raise AssertionError(f"no digest line found for creator_id={creator_id!r}: {text!r}")


def test_digest_text_orders_rows_by_absolute_percent_change_descending(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    write_run_row(conn, now, now, 3, 0)  # fresh run — no staleness banner to skip over
    # +10%
    upsert_metric(conn, _record(creator_id="small", metric_date=date(2026, 8, 4), views=1000))
    upsert_metric(conn, _record(creator_id="small", metric_date=date(2026, 8, 5), views=1100))
    # +50%
    upsert_metric(conn, _record(creator_id="big", metric_date=date(2026, 8, 4), views=1000))
    upsert_metric(conn, _record(creator_id="big", metric_date=date(2026, 8, 5), views=1500))
    # -30%
    upsert_metric(conn, _record(creator_id="neg", metric_date=date(2026, 8, 4), views=1000))
    upsert_metric(conn, _record(creator_id="neg", metric_date=date(2026, 8, 5), views=700))

    text = build_digest_text(conn, now)
    lines = text.splitlines()[1:4]  # header, then exactly the 3 mover rows

    assert [_drop_flag_prefix(line).split(" / ")[0] for line in lines] == ["big", "neg", "small"]


def test_digest_text_places_row_with_no_computable_percent_after_every_row_that_has_one(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    write_run_row(conn, now, now, 2, 0)
    upsert_metric(
        conn, _record(creator_id="has-baseline", metric_date=date(2026, 8, 4), views=1000)
    )
    upsert_metric(
        conn, _record(creator_id="has-baseline", metric_date=date(2026, 8, 5), views=1200)
    )
    upsert_metric(conn, _record(creator_id="no-baseline", metric_date=date(2026, 8, 5), views=500))

    text = build_digest_text(conn, now)
    lines = text.splitlines()[1:3]

    assert _drop_flag_prefix(lines[0]).startswith("has-baseline")
    assert _drop_flag_prefix(lines[1]).startswith("no-baseline")


def test_digest_text_renders_delta_placeholder_for_missing_and_zero_baseline(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    write_run_row(conn, now, now, 2, 0)
    upsert_metric(conn, _record(creator_id="no-baseline", metric_date=date(2026, 8, 5), views=500))
    upsert_metric(conn, _record(creator_id="zero-baseline", metric_date=date(2026, 8, 4), views=0))
    upsert_metric(
        conn, _record(creator_id="zero-baseline", metric_date=date(2026, 8, 5), views=700)
    )

    text = build_digest_text(conn, now)
    by_creator = {_drop_flag_prefix(line).split(" ", 1)[0]: line for line in text.splitlines()[1:3]}

    assert f"(Δ {DELTA_PLACEHOLDER})" in by_creator["no-baseline"]
    assert f"(Δ {DELTA_PLACEHOLDER})" in by_creator["zero-baseline"]
    # No baseline, or a zero baseline, is never flagged — a missing comparison is not a move
    # and a division by zero is not a gain (D-12).
    assert MOVER_FLAG not in by_creator["no-baseline"]
    assert MOVER_FLAG not in by_creator["zero-baseline"]


def test_digest_text_on_no_runs_row_but_metrics_present_shows_could_not_determine_banner(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=500))

    text = build_digest_text(conn, datetime(2026, 8, 5, 8, 15, tzinfo=UTC))
    lines = text.splitlines()

    assert "could not determine" in lines[1].lower()
    assert any("c1" in line for line in lines[2:])


# --- ±20% flag boundary (BOT-02, D-10) ----------------------------------------------------


def _seed_pair(conn: sqlite3.Connection, creator_id: str, prev_views: int, views: int) -> None:
    upsert_metric(
        conn, _record(creator_id=creator_id, metric_date=date(2026, 8, 4), views=prev_views)
    )
    upsert_metric(conn, _record(creator_id=creator_id, metric_date=date(2026, 8, 5), views=views))


def test_digest_flag_pair_at_exactly_positive_threshold_is_not_flagged(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    write_run_row(conn, now, now, 1, 0)
    _seed_pair(conn, "at-threshold", 1000, 1200)  # exactly +20%

    text = build_digest_text(conn, now)

    assert MOVER_FLAG not in _line_for(text, "at-threshold")


def test_digest_flag_pair_one_step_over_positive_threshold_is_flagged(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    write_run_row(conn, now, now, 1, 0)
    _seed_pair(conn, "over-threshold", 1000, 1201)  # +20.1%

    text = build_digest_text(conn, now)

    assert MOVER_FLAG in _line_for(text, "over-threshold")


def test_digest_flag_pair_at_exactly_negative_threshold_is_not_flagged(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    write_run_row(conn, now, now, 1, 0)
    _seed_pair(conn, "at-negative-threshold", 1000, 800)  # exactly -20%

    text = build_digest_text(conn, now)

    assert MOVER_FLAG not in _line_for(text, "at-negative-threshold")


def test_digest_flag_pair_one_step_over_negative_threshold_is_flagged(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    write_run_row(conn, now, now, 1, 0)
    _seed_pair(conn, "over-negative-threshold", 1000, 799)  # -20.1%

    text = build_digest_text(conn, now)

    assert MOVER_FLAG in _line_for(text, "over-negative-threshold")


def test_digest_flag_reads_the_unrounded_float_not_the_rounded_display_text(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    write_run_row(conn, now, now, 1, 0)
    _seed_pair(conn, "rounds-but-flags", 10000, 12004)  # +20.04% -> displays +20.0%

    text = build_digest_text(conn, now)
    line = _line_for(text, "rounds-but-flags")

    assert "+20.0%" in line
    assert MOVER_FLAG in line


# --- staleness banner (D-04, D-17) ---------------------------------------------------------


def test_staleness_hours_at_exactly_26_reads_fresh_and_digest_has_no_stale_banner(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    finished = datetime(2026, 8, 4, 6, 15, tzinfo=UTC)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)  # exactly 26 hours later
    write_run_row(conn, finished, finished, 0, 0)

    assert staleness_hours(finished.isoformat(), now) == 26.0

    text = build_digest_text(conn, now)
    assert "STALE" not in text


def test_staleness_one_minute_past_26_hours_emits_stale_banner_naming_timestamp_and_age(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    finished = datetime(2026, 8, 4, 6, 14, tzinfo=UTC)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)  # 26h 1min later
    write_run_row(conn, finished, finished, 0, 0)

    text = build_digest_text(conn, now)

    assert "STALE" in text
    assert finished.isoformat() in text


# --- digest failures section (BOT-01, D-06) -------------------------------------------------


def test_digest_text_two_failures_names_both_creators_sources_and_causes(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    run_id = write_run_row(conn, now, now, 0, 2)
    write_run_failures(
        conn,
        run_id,
        [
            RunFailure(creator_id="c1", source="youtube", cause="ValueError", message="boom"),
            RunFailure(creator_id="c2", source="youtube", cause="KeyError", message="missing"),
        ],
    )

    text = build_digest_text(conn, now)

    assert "c1" in text and "c2" in text
    assert "ValueError" in text and "boom" in text
    assert "KeyError" in text and "missing" in text
    assert "Failures this run: 2" in text


def test_digest_text_clean_run_ends_with_explicit_no_failures_line(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    write_run_row(conn, now, now, 0, 0)

    text = build_digest_text(conn, now)

    assert "Failures this run: none" in text


def test_digest_text_names_only_the_newer_runs_failures_never_an_older_runs(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    now = datetime(2026, 8, 5, 8, 15, tzinfo=UTC)
    older_run = write_run_row(conn, now, now, 0, 1)
    write_run_failures(
        conn,
        older_run,
        [RunFailure(creator_id="stale-fail", source="youtube", cause="X", message="old")],
    )
    newer_run = write_run_row(conn, now, now, 0, 1)
    write_run_failures(
        conn,
        newer_run,
        [RunFailure(creator_id="fresh-fail", source="youtube", cause="Y", message="new")],
    )

    text = build_digest_text(conn, now)

    assert "fresh-fail" in text
    assert "stale-fail" not in text


def test_digest_text_with_no_runs_row_has_no_failures_section(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    text = build_digest_text(conn, datetime(2026, 8, 5, 8, 15, tzinfo=UTC))

    assert "Failures this run" not in text
    assert "could not determine" in text.lower()


def test_digest_text_on_empty_database_returns_an_explicit_message_not_an_empty_string(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    text = build_digest_text(conn, datetime(2026, 8, 5, 8, 15, tzinfo=UTC))

    assert text != ""
    assert "No rows recorded yet" in text


# --- build_trend_text() (BOT-04, D-15/D-16) -----------------------------------------------


def _seed_days(
    conn: sqlite3.Connection, creator_id: str, source: str, days: list[tuple[date, int | None]]
) -> None:
    for metric_date, views in days:
        upsert_metric(
            conn,
            _record(creator_id=creator_id, source=source, metric_date=metric_date, views=views),
        )


def test_creator_trend_matches_mixed_case_name(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(conn, "kaicenat", "youtube", [(date(2026, 8, 5), 100)])

    text = build_trend_text(conn, "KaiCenat")

    assert "kaicenat / youtube" in text
    assert "No creator named" not in text


def test_creator_trend_matches_whitespace_padded_name(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(conn, "kaicenat", "youtube", [(date(2026, 8, 5), 100)])

    text = build_trend_text(conn, "  kaicenat  ")

    assert "kaicenat / youtube" in text


def test_creator_trend_does_not_match_a_substring_of_a_known_slug(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(conn, "kaicenat", "youtube", [(date(2026, 8, 5), 100)])

    text = build_trend_text(conn, "kai")

    assert "No creator named" in text
    assert "kaicenat" in text  # named in the known-slugs list, not matched


def test_creator_trend_dotted_capital_i_does_not_match(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(conn, "kaicenat", "youtube", [(date(2026, 8, 5), 100)])

    text = build_trend_text(conn, "KAİCENAT")

    assert "No creator named" in text


def test_creator_trend_unknown_name_lists_known_slugs(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(conn, "kaicenat", "youtube", [(date(2026, 8, 5), 100)])
    _seed_days(conn, "xqc", "youtube", [(date(2026, 8, 5), 200)])

    text = build_trend_text(conn, "nobody")

    assert "nobody" in text
    assert "kaicenat" in text
    assert "xqc" in text


def test_creator_trend_empty_database_says_no_creators_recorded_yet(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    text = build_trend_text(conn, "anyone")

    assert "no creators recorded" in text.lower()
    assert "anyone" not in text  # not an empty-list rendering of the unknown-name reply


def test_creator_trend_single_day_creator_renders_one_line_with_delta_placeholder(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(conn, "kaicenat", "youtube", [(date(2026, 8, 5), 100)])

    text = build_trend_text(conn, "kaicenat")
    day_lines = [line for line in text.splitlines() if line.strip().startswith("2026-")]

    assert len(day_lines) == 1
    assert f"(Δ {DELTA_PLACEHOLDER})" in day_lines[0]


def test_creator_trend_three_days_renders_three_lines_newest_first_oldest_placeholder(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(
        conn,
        "kaicenat",
        "youtube",
        [
            (date(2026, 8, 3), 100),
            (date(2026, 8, 4), 150),
            (date(2026, 8, 5), 200),
        ],
    )

    text = build_trend_text(conn, "kaicenat")
    day_lines = [line for line in text.splitlines() if line.strip().startswith("2026-")]

    assert len(day_lines) == 3
    assert day_lines[0].strip().startswith("2026-08-05")
    assert day_lines[-1].strip().startswith("2026-08-03")
    assert f"(Δ {DELTA_PLACEHOLDER})" in day_lines[-1]


def test_creator_trend_more_than_seven_days_renders_exactly_seven_lines(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    days = [(date(2026, 8, 1 + i), 100 + i) for i in range(10)]
    _seed_days(conn, "kaicenat", "youtube", days)

    text = build_trend_text(conn, "kaicenat")
    day_lines = [line for line in text.splitlines() if line.strip().startswith("2026-")]

    assert len(day_lines) == TREND_LIMIT
    # The oldest line shown carries the em dash even though an older row exists beyond
    # the seven-row cut — the delta is computed within the window, not against history.
    assert f"(Δ {DELTA_PLACEHOLDER})" in day_lines[-1]


def test_creator_trend_two_sources_render_in_separate_blocks(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(conn, "kaicenat", "youtube", [(date(2026, 8, 5), 100)])
    _seed_days(conn, "kaicenat", "twitch", [(date(2026, 8, 5), 50)])

    text = build_trend_text(conn, "kaicenat")

    assert "kaicenat / youtube" in text
    assert "kaicenat / twitch" in text


def test_creator_trend_null_views_renders_blank_and_next_day_carries_placeholder(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(
        conn,
        "kaicenat",
        "youtube",
        [
            (date(2026, 8, 4), None),
            (date(2026, 8, 5), 200),
        ],
    )

    text = build_trend_text(conn, "kaicenat")
    lines_by_date = {
        line.strip().split(":")[0]: line
        for line in text.splitlines()
        if line.strip().startswith("2026-")
    }

    null_day = lines_by_date["2026-08-04"]
    newer_day = lines_by_date["2026-08-05"]
    # views_text is blank on NULL, not the digit "0" — split off the part between the date's
    # colon and the literal word "views".
    views_part = null_day.split(":", 1)[1].split("views")[0].strip()
    assert views_part == ""
    assert f"(Δ {DELTA_PLACEHOLDER})" in null_day
    # The newer day's baseline (the NULL row) is missing — never a delta against nothing.
    assert f"(Δ {DELTA_PLACEHOLDER})" in newer_day


def test_creator_trend_name_with_quote_and_sql_fragment_returns_unknown_reply(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    _seed_days(conn, "kaicenat", "youtube", [(date(2026, 8, 5), 100)])

    text = build_trend_text(conn, "foo'; DROP TABLE metrics; --")  # must not raise

    assert "No creator named" in text
    # The database is untouched — the metrics table still answers normally.
    assert conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] == 1


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
