"""SQL-layer tests for db.py — DDL, upsert idempotency, prior-date immutability, the
NULL-versus-zero round trip, and the create=False read path.

Fixtures only, no live network calls, no credential. Builds MetricRecord objects directly
and talks to a tmp_path database.
"""

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from creatorpulse.db import (
    CREATOR_TREND_SQL,
    DatabaseNotInitialized,
    connect,
    fetch_creator_trend,
    fetch_known_creators,
    fetch_last_run,
    fetch_run_failures,
    upsert_metric,
    write_run_failures,
    write_run_row,
)
from creatorpulse.models import MetricRecord, RunFailure


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


def test_connect_create_true_creates_file_and_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "creatorpulse.db"
    assert not db_path.exists()

    conn = connect(db_path, create=True)

    assert db_path.exists()
    table_names = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"metrics", "runs"} <= table_names


def test_connect_create_true_idempotent_second_call_keeps_data(tmp_path: Path) -> None:
    db_path = tmp_path / "creatorpulse.db"
    conn1 = connect(db_path, create=True)
    upsert_metric(conn1, _record())
    conn1.close()

    conn2 = connect(db_path, create=True)  # idempotent — must not drop the row or the table
    row_count = conn2.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    table_count = conn2.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='metrics'"
    ).fetchone()[0]
    assert row_count == 1
    assert table_count == 1


def test_connect_create_false_missing_file_raises_and_creates_nothing(tmp_path: Path) -> None:
    db_path = tmp_path / "does_not_exist.db"

    with pytest.raises(DatabaseNotInitialized):
        connect(db_path, create=False)

    assert not db_path.exists()  # the call created nothing


def test_create_false_raises_on_missing_table(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    db_path.touch()  # a real file, a valid empty SQLite database, no tables at all

    with pytest.raises(DatabaseNotInitialized, match="metrics"):
        connect(db_path, create=False)

    # The connection opened on the way in must be closed on the way out — a lingering
    # handle leaves the file locked on Windows, so this unlink is itself part of the proof.
    db_path.unlink()


def test_connect_create_false_succeeds_and_reads_writer_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "creatorpulse.db"
    writer = connect(db_path, create=True)
    upsert_metric(writer, _record())
    writer.close()

    reader = connect(db_path, create=False)
    count = reader.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    assert count == 1
    reader.close()


def test_connect_both_branches_set_wal_and_busy_timeout(tmp_path: Path) -> None:
    db_path = tmp_path / "creatorpulse.db"
    writer = connect(db_path, create=True)
    assert writer.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert writer.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    writer.close()

    reader = connect(db_path, create=False)
    assert reader.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert reader.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    reader.close()


def test_upsert_same_key_updates_not_duplicates(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(followers=100))
    upsert_metric(conn, _record(followers=200))

    row_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    assert row_count == 1

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM metrics").fetchone()
    assert row["followers"] == 200  # the second call's values win


def test_upsert_different_date_does_not_touch_prior_row(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(metric_date=date(2026, 1, 1), followers=111))

    conn.row_factory = sqlite3.Row
    before = dict(
        conn.execute("SELECT * FROM metrics WHERE metric_date = ?", ("2026-01-01",)).fetchone()
    )

    upsert_metric(conn, _record(metric_date=date(2026, 1, 2), followers=222))

    after_row = conn.execute(
        "SELECT * FROM metrics WHERE metric_date = ?", ("2026-01-01",)
    ).fetchone()
    assert after_row is not None
    assert dict(after_row) == before  # byte-identical — same values, same collected_at

    total = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    assert total == 2


def test_upsert_empty_creator_id_raises_and_writes_nothing(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    with pytest.raises(ValueError):
        upsert_metric(conn, _record(creator_id=""))

    count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    assert count == 0


def test_none_metric_is_sql_null_and_zero_is_not(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="null-case", followers=None))
    upsert_metric(conn, _record(creator_id="zero-case", followers=0))

    null_is_null = conn.execute(
        "SELECT followers IS NULL FROM metrics WHERE creator_id = ?", ("null-case",)
    ).fetchone()[0]
    zero_is_null = conn.execute(
        "SELECT followers IS NULL FROM metrics WHERE creator_id = ?", ("zero-case",)
    ).fetchone()[0]
    assert null_is_null == 1
    assert zero_is_null == 0


def test_stored_null_and_zero_round_trip_distinct(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(views=0, likes=None))

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM metrics").fetchone()

    # Four separate identity checks, never a truthiness check — 0 is falsy, and `not
    # row["views"]` would pass while the row was wrong.
    assert row["views"] == 0
    assert row["views"] is not None
    assert row["likes"] is None
    assert row["likes"] != 0


def test_reader_can_read_while_writer_has_open_transaction(tmp_path: Path) -> None:
    db_path = tmp_path / "creatorpulse.db"
    writer = connect(db_path, create=True)
    writer.execute(
        "INSERT INTO metrics "
        "(creator_id, source, metric_date, followers, views, likes, video_count, is_live, "
        " collected_at) "
        "VALUES ('c1', 'youtube', '2026-01-01', 1, 2, NULL, 3, NULL, '2026-01-01T00:00:00')"
    )  # deliberately not committed — an open transaction

    reader = connect(db_path, create=False)
    count = reader.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    assert count == 0  # WAL: the writer's uncommitted row is invisible, but no lock error

    writer.commit()
    reader.close()
    writer.close()


def test_write_run_row_returns_rowid_not_none(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    finished = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)

    first_id = write_run_row(conn, started, finished, 1, 0)
    second_id = write_run_row(conn, started, finished, 1, 0)

    assert first_id == 1
    assert second_id == 2


def test_write_run_failures_empty_sequence_writes_nothing_and_does_not_raise(
    tmp_path: Path,
) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    finished = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    run_id = write_run_row(conn, started, finished, 0, 0)

    write_run_failures(conn, run_id, [])

    count = conn.execute("SELECT COUNT(*) FROM run_failures").fetchone()[0]
    assert count == 0


def test_fetch_last_run_on_empty_runs_table_returns_none(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    assert fetch_last_run(conn) is None


def test_fetch_last_run_after_three_runs_returns_the_newest_one(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    write_run_row(conn, started, datetime(2026, 1, 1, 0, 1, tzinfo=UTC), 1, 0)
    write_run_row(conn, started, datetime(2026, 1, 2, 0, 1, tzinfo=UTC), 2, 0)
    newest_finished = datetime(2026, 1, 3, 0, 1, tzinfo=UTC)
    newest_id = write_run_row(conn, started, newest_finished, 3, 0)

    last_run = fetch_last_run(conn)

    assert last_run is not None
    assert last_run[0] == newest_id
    assert last_run[2] == newest_finished.isoformat()


def test_write_run_failures_round_trip_matches_run_id(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    finished = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    run_id = write_run_row(conn, started, finished, 0, 1)
    failure = RunFailure(creator_id="c1", source="youtube", cause="ValueError", message="boom")

    write_run_failures(conn, run_id, [failure])

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM run_failures").fetchone()
    assert row["run_id"] == run_id
    assert row["creator_id"] == "c1"
    assert row["source"] == "youtube"
    assert row["cause"] == "ValueError"
    assert row["message"] == "boom"


def test_fetch_run_failures_returns_only_rows_for_that_run_id(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    older_run = write_run_row(conn, started, started, 0, 1)
    newer_run = write_run_row(conn, started, started, 0, 1)
    write_run_failures(
        conn,
        older_run,
        [RunFailure(creator_id="a", source="youtube", cause="X", message="old")],
    )
    write_run_failures(
        conn,
        newer_run,
        [RunFailure(creator_id="b", source="youtube", cause="Y", message="new")],
    )

    failures = fetch_run_failures(conn, newer_run)

    assert len(failures) == 1
    assert failures[0] == ("b", "youtube", "Y", "new")


def test_fetch_run_failures_on_run_with_no_failures_returns_empty_list(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    run_id = write_run_row(conn, started, started, 0, 0)

    assert fetch_run_failures(conn, run_id) == []


def test_fetch_known_creators_on_empty_database_returns_empty_list(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)

    assert fetch_known_creators(conn) == []


def test_fetch_known_creators_returns_distinct_ids_alphabetical(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="xqc", metric_date=date(2026, 1, 1)))
    upsert_metric(conn, _record(creator_id="kaicenat", metric_date=date(2026, 1, 1)))
    # A second source row for the same creator must not duplicate the id in the list.
    upsert_metric(
        conn, _record(creator_id="kaicenat", source="twitch", metric_date=date(2026, 1, 1))
    )

    assert fetch_known_creators(conn) == ["kaicenat", "xqc"]


def test_fetch_creator_trend_orders_newest_first_within_each_source(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 1, 1), views=100))
    upsert_metric(conn, _record(creator_id="c1", metric_date=date(2026, 1, 2), views=200))
    upsert_metric(conn, _record(creator_id="other", metric_date=date(2026, 1, 1), views=999))

    rows = fetch_creator_trend(conn, "c1")

    assert rows == [
        ("youtube", "2026-01-02", 200),
        ("youtube", "2026-01-01", 100),
    ]


def test_fetch_creator_trend_groups_two_sources_separately(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="c1", source="youtube", metric_date=date(2026, 1, 1)))
    upsert_metric(conn, _record(creator_id="c1", source="twitch", metric_date=date(2026, 1, 1)))

    rows = fetch_creator_trend(conn, "c1")

    sources = {source for source, _metric_date, _views in rows}
    assert sources == {"youtube", "twitch"}


def test_creator_trend_sql_binds_creator_id_not_interpolated() -> None:
    assert "?" in CREATOR_TREND_SQL
    assert "%" not in CREATOR_TREND_SQL
    assert "{" not in CREATOR_TREND_SQL
