"""Tests for sheets.py — the end-to-end Dashboard slice against a temp database and a mocked
worksheet.

Fixtures only, no live network calls. The worksheet double is built as Mock(spec=gspread.Worksheet)
and client construction is intercepted via monkeypatch, the same idiom tests/test_sources.py uses
for requests.get. This file never calls service_account or open_by_key.
"""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import gspread
import pytest
from gspread.utils import ValueInputOption

from creatorpulse.db import connect, upsert_metric
from creatorpulse.models import MetricRecord
from creatorpulse.sheets import (
    DELTA_PLACEHOLDER,
    HEADERS,
    build_dashboard_rows,
    fetch_latest_rows,
    sync,
)


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


def _worksheet() -> Mock:
    return Mock(spec=gspread.Worksheet)


def test_sync_writes_dashboard_once_latest_row_only_ordered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    # c1 has two metric_dates — only the later one's views/collected_at may reach the Sheet.
    upsert_metric(
        conn,
        _record(
            creator_id="c1",
            metric_date=date(2026, 1, 1),
            followers=100,
            views=200,
            collected_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        ),
    )
    upsert_metric(
        conn,
        _record(
            creator_id="c1",
            metric_date=date(2026, 1, 2),
            followers=150,
            views=250,
            collected_at=datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC),
        ),
    )
    # c2 has no followers on this platform at all — must render blank, not zero.
    upsert_metric(
        conn,
        _record(
            creator_id="c2",
            metric_date=date(2026, 1, 2),
            followers=None,
            views=50,
            collected_at=datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC),
        ),
    )

    ws = _worksheet()
    monkeypatch.setattr("creatorpulse.sheets._open_worksheet", lambda *a, **kw: ws)

    row_count = sync(conn, "SHEETID", Path("/fake/keyfile.json"))

    assert ws.update.call_count == 1
    ws.clear.assert_not_called()

    call = ws.update.call_args
    values, range_name = call.args
    assert values[0] == HEADERS
    assert len(values[0]) == 6
    assert all(len(row) == 6 for row in values)

    # Ordered by creator_id then source: c1 first, c2 second.
    assert values[1][0] == "c1"
    assert values[1][3] == 250  # the later date's views, not the earlier date's 200
    assert values[1][5] == "2026-01-02T12:00:00+00:00"
    assert values[2][0] == "c2"
    assert values[2][2] == ""  # NULL followers renders blank, never a substituted zero

    assert range_name == f"A1:F{len(values)}"
    assert range_name.startswith("A1:F")  # last column letter is F, a literal, never computed
    assert call.kwargs["value_input_option"] == ValueInputOption.user_entered

    assert row_count == 2  # data rows only — the header does not inflate the count


def test_sync_against_empty_metrics_table_still_writes_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    ws = _worksheet()
    monkeypatch.setattr("creatorpulse.sheets._open_worksheet", lambda *a, **kw: ws)

    row_count = sync(conn, "SHEETID", Path("/fake/keyfile.json"))

    assert ws.update.call_count == 1
    ws.clear.assert_not_called()
    values, range_name = ws.update.call_args.args
    assert values == [HEADERS]
    assert range_name == "A1:F1"
    assert row_count == 0


def test_null_followers_renders_blank_and_zero_renders_zero(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="null-case", followers=None))
    upsert_metric(conn, _record(creator_id="zero-case", followers=0))

    values = build_dashboard_rows(fetch_latest_rows(conn))
    by_creator = {row[0]: row for row in values[1:]}

    assert by_creator["null-case"][2] == ""
    assert by_creator["zero-case"][2] == 0


# --- 04-02 Task 1: the baseline row arrives in the same read ---------------------------


def test_baseline_present_returns_previous_day_views(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=4200))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    rows = fetch_latest_rows(conn)

    assert len(rows) == 1
    assert rows[0][0] == "c1"
    assert rows[0][5] == 4200


def test_baseline_absent_single_row_returns_one_tuple_with_none(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    rows = fetch_latest_rows(conn)

    assert len(rows) == 1
    assert rows[0][0] == "c1"
    assert rows[0][5] is None


def test_baseline_gap_two_days_back_returns_none_not_the_gap_row(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 3), views=1000))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    rows = fetch_latest_rows(conn)

    assert len(rows) == 1
    assert rows[0][5] is None
    assert rows[0][5] != 1000


def test_baseline_resolves_across_month_boundary(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 2, 28), views=100))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 3, 1), views=150))

    rows = fetch_latest_rows(conn)

    assert rows[0][5] == 100


def test_baseline_resolves_across_leap_day(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2028, 2, 29), views=100))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2028, 3, 1), views=150))

    rows = fetch_latest_rows(conn)

    assert rows[0][5] == 100


def test_baseline_row_with_null_views_returns_none(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=None))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    rows = fetch_latest_rows(conn)

    assert rows[0][5] is None


def test_baseline_row_with_zero_views_returns_zero_not_none(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=0))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    rows = fetch_latest_rows(conn)

    assert rows[0][5] == 0


# --- 04-02 Task 2: one conditional expression, and the seven cases that pin it down ----


def test_delta_present_both_sides_non_null_puts_the_difference_in_column_e(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=4200))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    values = build_dashboard_rows(fetch_latest_rows(conn))

    assert values[1][4] == 800
    assert values[1][4] != DELTA_PLACEHOLDER


def test_delta_no_baseline_row_puts_the_marker_and_row_still_appears(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    values = build_dashboard_rows(fetch_latest_rows(conn))

    assert len(values) == 2  # header + one data row -- the row did not vanish
    assert values[1][0] == "c1"
    assert values[1][4] == DELTA_PLACEHOLDER


def test_delta_gap_two_days_back_puts_the_marker_not_the_two_day_difference(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 3), views=1000))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    values = build_dashboard_rows(fetch_latest_rows(conn))

    assert values[1][4] == DELTA_PLACEHOLDER
    assert values[1][4] != 4000  # 5000 - 1000, the widened-lookback answer this forbids


def test_delta_month_and_leap_day_boundaries_produce_the_real_difference(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="month", metric_date=date(2026, 2, 28), views=100))
    upsert_metric(conn, _record(creator_id="month", metric_date=date(2026, 3, 1), views=150))
    upsert_metric(conn, _record(creator_id="leap", metric_date=date(2028, 2, 29), views=100))
    upsert_metric(conn, _record(creator_id="leap", metric_date=date(2028, 3, 1), views=150))

    values = build_dashboard_rows(fetch_latest_rows(conn))
    by_creator = {row[0]: row for row in values[1:]}

    assert by_creator["month"][4] == 50
    assert by_creator["leap"][4] == 50


def test_delta_zero_renders_as_zero_not_the_marker(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=5000))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    values = build_dashboard_rows(fetch_latest_rows(conn))

    assert values[1][4] == 0
    assert values[1][4] != DELTA_PLACEHOLDER


def test_delta_negative_renders_negative_unchanged(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=1000))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=900))

    values = build_dashboard_rows(fetch_latest_rows(conn))

    assert values[1][4] == -100


def test_delta_today_views_null_with_non_null_baseline_puts_the_marker(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=4200))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=None))

    values = build_dashboard_rows(fetch_latest_rows(conn))

    assert values[1][4] == DELTA_PLACEHOLDER


def test_delta_baseline_views_null_with_non_null_today_puts_the_marker(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=None))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    values = build_dashboard_rows(fetch_latest_rows(conn))

    assert values[1][4] == DELTA_PLACEHOLDER


def test_delta_zero_baseline_versus_null_baseline_adjacency(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="zero-base", metric_date=date(2026, 8, 4), views=0))
    upsert_metric(conn, _record(creator_id="zero-base", metric_date=date(2026, 8, 5), views=700))
    upsert_metric(conn, _record(creator_id="null-base", metric_date=date(2026, 8, 5), views=700))

    values = build_dashboard_rows(fetch_latest_rows(conn))
    by_creator = {row[0]: row for row in values[1:]}

    assert by_creator["zero-base"][4] == 700  # real subtraction against a real zero
    assert by_creator["null-base"][4] == DELTA_PLACEHOLDER


def test_delta_column_type_is_int_never_bool_str_or_float(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=4200))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    values = build_dashboard_rows(fetch_latest_rows(conn))
    cell = values[1][4]

    assert isinstance(cell, int)
    assert not isinstance(cell, bool)


def test_sync_write_range_never_names_column_g(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 4), views=4200))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 8, 5), views=5000))

    ws = _worksheet()
    monkeypatch.setattr("creatorpulse.sheets._open_worksheet", lambda *a, **kw: ws)

    sync(conn, "SHEETID", Path("/fake/keyfile.json"))

    values, range_name = ws.update.call_args.args
    assert "G" not in range_name
    assert values[0] == HEADERS
    assert all(len(row) == 6 for row in values)
