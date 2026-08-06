"""Connection factory, schema DDL, metric upsert, and the runs writer — the only SQL module."""

import sqlite3
from datetime import datetime
from pathlib import Path

from creatorpulse.models import MetricRecord

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS metrics (
    creator_id    TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    metric_date   TEXT    NOT NULL,   -- ISO-8601 'YYYY-MM-DD'
    followers     INTEGER,            -- NULL = platform doesn't expose this metric
    views         INTEGER,
    likes         INTEGER,
    video_count   INTEGER,
    is_live       INTEGER,
    collected_at  TEXT    NOT NULL,   -- ISO-8601 UTC timestamp
    UNIQUE (creator_id, source, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_metrics_creator_date
    ON metrics (creator_id, metric_date);

CREATE TABLE IF NOT EXISTS runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT    NOT NULL,
    finished_at    TEXT    NOT NULL,
    rows_written   INTEGER NOT NULL,
    failure_count  INTEGER NOT NULL
);
"""

UPSERT_METRIC = """
INSERT INTO metrics
    (creator_id, source, metric_date, followers, views, likes, video_count, is_live,
     collected_at)
VALUES
    (:creator_id, :source, :metric_date, :followers, :views, :likes, :video_count, :is_live,
     :collected_at)
ON CONFLICT (creator_id, source, metric_date) DO UPDATE SET
    followers    = excluded.followers,
    views        = excluded.views,
    likes        = excluded.likes,
    video_count  = excluded.video_count,
    is_live      = excluded.is_live,
    collected_at = excluded.collected_at;
"""

_WRITE_RUN_ROW = """
INSERT INTO runs (started_at, finished_at, rows_written, failure_count)
VALUES (:started_at, :finished_at, :rows_written, :failure_count);
"""

# Correlated on (creator_id, metric_date), so this uses idx_metrics_creator_date. Rejected
# alternatives: SQLite's bare-column-with-MAX() shorthand is a SQLite quirk rather than
# standard SQL (the merge rule: nothing enters the repo the author cannot explain out loud);
# a separate DISTINCT-pairs query plus a per-pair lookup would be N+1 queries for the same
# answer. This one query yields the DISTINCT (creator_id, source) pairs D-01 names, plus each
# pair's latest snapshot, in one pass.
LATEST_ROWS_SQL = """
SELECT m.creator_id, m.source, m.followers, m.views, m.collected_at, prev.views
FROM metrics AS m
LEFT JOIN metrics AS prev
    -- keyed on (creator_id, metric_date): idx_metrics_creator_date's exact column pair
    ON prev.creator_id = m.creator_id
    AND prev.source = m.source
    AND prev.metric_date = date(m.metric_date, '-1 day')
WHERE m.metric_date = (
    SELECT MAX(m2.metric_date) FROM metrics AS m2
    WHERE m2.creator_id = m.creator_id AND m2.source = m.source
)
ORDER BY m.creator_id, m.source;
"""

LatestRow = tuple[str, str, int | None, int | None, str, int | None]


def fetch_latest_rows(conn: sqlite3.Connection) -> list[LatestRow]:
    """One indexed read of metrics: each (creator_id, source) pair's latest snapshot."""
    cursor = conn.execute(LATEST_ROWS_SQL)
    rows: list[LatestRow] = cursor.fetchall()
    return rows


class DatabaseNotInitialized(Exception):
    """Raised by connect(create=False) when the file or its metrics table is absent (D-04)."""


def connect(db_path: Path, *, create: bool) -> sqlite3.Connection:
    """Open db_path. create=True runs the idempotent DDL; create=False raises
    DatabaseNotInitialized rather than silently creating an empty database at the wrong path."""
    if create:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
    else:
        # sqlite3.connect raises OperationalError on a missing file under this read-only URI
        # — this is the "raise a named error" mechanism D-04 asks for (verified live,
        # 03-RESEARCH.md). as_posix() keeps a Windows path from producing backslashes in a URI.
        uri = f"file:{db_path.as_posix()}?mode=rw"
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        except sqlite3.OperationalError as exc:
            raise DatabaseNotInitialized(f"database file not found: {db_path}") from exc

    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")

    if create:
        conn.executescript(SCHEMA_DDL)
    else:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
        )
        if cursor.fetchone() is None:
            conn.close()  # close before raising — an open handle locks the file on Windows
            raise DatabaseNotInitialized(f"metrics table not found in {db_path}")

    return conn


def upsert_metric(conn: sqlite3.Connection, record: MetricRecord) -> None:
    if not record.creator_id:
        raise ValueError("MetricRecord.creator_id must not be empty")

    conn.execute(
        UPSERT_METRIC,
        {
            "creator_id": record.creator_id,
            "source": record.source,
            "metric_date": record.metric_date.isoformat(),
            "followers": record.followers,
            "views": record.views,
            "likes": record.likes,
            "video_count": record.video_count,
            "is_live": record.is_live,
            "collected_at": record.collected_at.isoformat(),
        },
    )
    conn.commit()


def write_run_row(
    conn: sqlite3.Connection,
    started_at: datetime,
    finished_at: datetime,
    rows_written: int,
    failure_count: int,
) -> None:
    conn.execute(
        _WRITE_RUN_ROW,
        {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "rows_written": rows_written,
            "failure_count": failure_count,
        },
    )
    conn.commit()
