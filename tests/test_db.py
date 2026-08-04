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

from creatorpulse.db import DatabaseNotInitialized, connect, upsert_metric
from creatorpulse.models import MetricRecord


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
