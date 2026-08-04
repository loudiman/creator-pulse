"""Orchestration loop. No HTTP knowledge, no SQL knowledge — this task's loop is the happy
path and the skip path; the per-pair try/except and the try/finally runs-row guarantee on a
mid-run raise are 03-05's work."""

import dataclasses
import logging
import sqlite3
from datetime import UTC, datetime

from creatorpulse.config import Creator
from creatorpulse.db import upsert_metric, write_run_row
from creatorpulse.models import RunResult
from creatorpulse.sources import FETCHERS

logger = logging.getLogger("creatorpulse")


def collect_once(conn: sqlite3.Connection, creators: list[Creator]) -> RunResult:
    metric_date = datetime.now(UTC).date()  # RUN-05 — computed once, threaded through
    started_at = datetime.now(UTC)
    rows_written = 0
    failure_count = 0

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
            record = fetch(identifier, metric_date)
            record = dataclasses.replace(record, creator_id=creator.id)
            upsert_metric(conn, record)
            rows_written += 1

    finished_at = datetime.now(UTC)
    write_run_row(conn, started_at, finished_at, rows_written, failure_count)
    return RunResult(rows_written=rows_written, failure_count=failure_count)
