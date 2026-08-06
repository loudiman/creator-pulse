"""Connection factory, schema DDL, metric upsert, and the runs writer — the only SQL module."""

import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from creatorpulse.models import MetricRecord, RunFailure

# Every surface that renders a metric shares this one em dash: the Sheet's Δ Views column and
# the Discord digest. It lives here rather than in sheets.py so a reader of the database layer
# never has to import the Google client to learn how "no comparison available" is spelled
# (D-13's rationale, applied to the constant as well as to the query).
DELTA_PLACEHOLDER = "—"

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

CREATE TABLE IF NOT EXISTS run_failures (
    run_id      INTEGER NOT NULL,  -- the runs.id row this failure belongs to
    creator_id  TEXT    NOT NULL,
    source      TEXT    NOT NULL,
    cause       TEXT    NOT NULL,  -- exception class name
    message     TEXT    NOT NULL
);
-- No index: a run has at most a handful of failure rows and the only read is by run_id —
-- omission recorded as deliberate, not forgotten. No UNIQUE constraint: the same
-- (run_id, creator_id, source) pair failing twice in one run cannot happen (D-15's per-pair
-- boundary runs each pair once), and a constraint that can never fire is untested code.
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

_WRITE_RUN_FAILURE = """
INSERT INTO run_failures (run_id, creator_id, source, cause, message)
VALUES (:run_id, :creator_id, :source, :cause, :message);
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


# The newest runs row, or none at all — what the digest banner (D-04) and, once 06-05 lands,
# /status (D-17) both need to answer "can these numbers be trusted". ORDER BY id, not
# finished_at: id is the AUTOINCREMENT insertion order and needs no string-timestamp compare.
LAST_RUN_SQL = """
SELECT id, started_at, finished_at, rows_written, failure_count
FROM runs
ORDER BY id DESC
LIMIT 1;
"""

LastRun = tuple[int, str, str, int, int]


def fetch_last_run(conn: sqlite3.Connection) -> LastRun | None:
    """The newest runs row, or None when no run has ever completed (an empty runs table)."""
    cursor = conn.execute(LAST_RUN_SQL)
    row: LastRun | None = cursor.fetchone()
    return row


# run_id is a bound parameter (the trailing ?), never interpolated — this is the query shape
# 06-05's user-supplied /creator lookup copies, so the discipline is established here on a
# trusted integer before it is applied to untrusted input (T-06-01).
RUN_FAILURES_SQL = """
SELECT creator_id, source, cause, message
FROM run_failures
WHERE run_id = ?
ORDER BY creator_id, source;
"""


def fetch_run_failures(conn: sqlite3.Connection, run_id: int) -> list[tuple[str, str, str, str]]:
    """Every failure row recorded for one run — never another run's, because run_id is bound."""
    cursor = conn.execute(RUN_FAILURES_SQL, (run_id,))
    rows: list[tuple[str, str, str, str]] = cursor.fetchall()
    return rows


# The distinct creator_id values ever recorded, alphabetical — the "known slugs" list D-15's
# unknown-name reply names. Built from what was collected, not from creators.yaml (Phase 4
# D-01's rule applied here too): a creator added to the config this morning genuinely has no
# rows yet, and saying so is honest.
KNOWN_CREATORS_SQL = """
SELECT DISTINCT creator_id
FROM metrics
ORDER BY creator_id;
"""


def fetch_known_creators(conn: sqlite3.Connection) -> list[str]:
    """Every creator_id the database holds at least one metric row for, alphabetical."""
    cursor = conn.execute(KNOWN_CREATORS_SQL)
    return [row[0] for row in cursor.fetchall()]


# creator_id is the trailing bound ?, never interpolated — this is the one query in the whole
# codebase whose input originates from a stranger typing in a Discord channel, bound for
# exactly that reason (T-06-01). The WHERE clause alone is what uses
# idx_metrics_creator_date; ordering by source is an in-memory sort over a handful of rows per
# creator, not a second index.
#
# D-16 named "one indexed read with LIMIT 7". A flat LIMIT 7 is only correct while a creator
# has exactly one source — creators.yaml already declares twitch and tiktok entries that will
# start producing rows the moment either is registered, at which point a flat limit silently
# interleaves two sources into three and a half days each. The read stays one indexed pass;
# the seven-row-per-source cut is applied in bot.build_trend_text instead of here.
CREATOR_TREND_SQL = """
SELECT source, metric_date, views
FROM metrics
WHERE creator_id = ?
ORDER BY source, metric_date DESC;
"""


def fetch_creator_trend(
    conn: sqlite3.Connection, creator_id: str
) -> list[tuple[str, str, int | None]]:
    """Every recorded (source, metric_date, views) row for one creator, newest first within
    each source. creator_id is bound as a parameter, never interpolated (T-06-01)."""
    cursor = conn.execute(CREATOR_TREND_SQL, (creator_id,))
    rows: list[tuple[str, str, int | None]] = cursor.fetchall()
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
) -> int:
    """Write one runs row and return its inserted id, so write_run_failures can attribute
    failure rows to this exact run without a second query (D-06)."""
    cursor = conn.execute(
        _WRITE_RUN_ROW,
        {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "rows_written": rows_written,
            "failure_count": failure_count,
        },
    )
    conn.commit()
    # sqlite3 types lastrowid as int | None because it is None before any insert; this INSERT
    # always produces one, so this names what happened rather than an inline type-ignore.
    if cursor.lastrowid is None:
        raise RuntimeError("write_run_row: INSERT produced no lastrowid")
    return cursor.lastrowid


def write_run_failures(
    conn: sqlite3.Connection, run_id: int, failures: Sequence[RunFailure]
) -> None:
    """Write one row per failure, attributed to run_id. An empty sequence writes nothing and
    commits nothing (D-06)."""
    if not failures:
        return
    conn.executemany(
        _WRITE_RUN_FAILURE,
        [
            {
                "run_id": run_id,
                "creator_id": failure.creator_id,
                "source": failure.source,
                "cause": failure.cause,
                "message": failure.message,
            }
            for failure in failures
        ],
    )
    conn.commit()
