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


def connect(db_path: Path, *, create: bool) -> sqlite3.Connection:
    """Open db_path. create=True runs the idempotent DDL; create=False lands in 03-05."""
    if not create:
        raise NotImplementedError("connect(create=False) lands in 03-05")

    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(SCHEMA_DDL)
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
