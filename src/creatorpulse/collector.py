"""Orchestration loop. No HTTP knowledge, no SQL knowledge — the loop's per-pair try/except
isolates one source's failure from the rest of the run (D-15/RUN-01), and the outer
try/finally guarantees a runs row even when the job dies part way through (D-16/DATA-03)."""

import dataclasses
import logging
import sqlite3
from datetime import UTC, datetime

from creatorpulse.config import Creator
from creatorpulse.db import upsert_metric, write_run_failures, write_run_row
from creatorpulse.models import RunFailure, RunResult
from creatorpulse.sources import FETCHERS

logger = logging.getLogger("creatorpulse")


def collect_once(conn: sqlite3.Connection, creators: list[Creator]) -> RunResult:
    metric_date = datetime.now(UTC).date()  # RUN-05 — computed once, threaded through
    started_at = datetime.now(UTC)
    rows_written = 0
    failure_count = 0
    failures: list[RunFailure] = []

    try:
        for creator in creators:
            for source_name, identifier in creator.sources.items():
                fetch = FETCHERS.get(source_name)
                if fetch is None:
                    logger.info(
                        "skip creator=%s source=%s reason=no_fetcher_registered",
                        creator.id,
                        source_name,
                    )
                    continue  # D-09/D-10 — a skip is neither a row nor a failure

                try:
                    record = fetch(identifier, metric_date)
                except Exception as exc:  # D-15 — one boundary per (creator, source) pair
                    failure_count += 1
                    cause = type(exc).__name__
                    message = str(exc)
                    logger.error(
                        "fetch failed creator=%s source=%s cause=%s: %s",
                        creator.id,
                        source_name,
                        cause,
                        message,
                    )
                    failures.append(
                        RunFailure(
                            creator_id=creator.id,
                            source=source_name,
                            cause=cause,
                            message=message,
                        )
                    )
                    continue  # no cross-pair state, no short-circuit (D-15)

                record = dataclasses.replace(record, creator_id=creator.id)
                # A write failure here is systemic, not per-source: deliberately outside the
                # per-pair boundary above, so it propagates through the finally below instead
                # of being counted as one more source failure (D-16).
                upsert_metric(conn, record)
                rows_written += 1
    finally:
        finished_at = datetime.now(UTC)
        # If either write raises here, it replaces the exception in flight — Python's
        # documented behavior, and the correct outcome: an unwritable database is the more
        # important error to surface.
        run_id = write_run_row(conn, started_at, finished_at, rows_written, failure_count)
        write_run_failures(conn, run_id, failures)

    return RunResult(
        rows_written=rows_written, failure_count=failure_count, failures=tuple(failures)
    )
