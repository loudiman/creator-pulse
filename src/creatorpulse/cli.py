"""creatorpulse console-script entry point and subcommand dispatch."""

import argparse
import logging
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import gspread
import requests

from creatorpulse import sheets
from creatorpulse.collector import collect_once
from creatorpulse.config import (
    ValidationError,
    load_creators,
    load_raw,
    resolve_paths,
    resolve_sheets_config,
    validate,
)
from creatorpulse.db import connect
from creatorpulse.models import RunFailure
from creatorpulse.sheets import SheetNotShared, SheetsKeyfileUnusable

logger = logging.getLogger("creatorpulse")

# D-09: 10 seconds is generous for a small JSON POST and short enough that an unreachable or
# hanging webhook cannot stall the collection run (T-06-07).
WEBHOOK_TIMEOUT_SECONDS = 10


def build_alert_text(failures: Sequence[RunFailure]) -> str:
    """Pure formatter for the immediate failure alert (D-08). Reads only the in-memory
    RunResult failures the caller already holds, never the database, so the alert and the
    runs row cannot disagree about the count (D-08). Formats values; does not truncate,
    redact, or reorder them."""
    count = len(failures)
    noun = "failure" if count == 1 else "failures"
    lines = [f"CreatorPulse run recorded {count} {noun}:"]
    for failure in failures:
        lines.append(
            f"{failure.creator_id} / {failure.source} — {failure.cause}: {failure.message}"
        )
    return "\n".join(lines)


def _post_alert(text: str) -> None:
    """POST text to the Phase 5 webhook (D-02). Swallows its own failures on purpose: a
    broken alert channel must never replace the real error it is reporting (D-09). Nothing
    here logs, formats, or re-raises the webhook URL itself — only the variable name."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or None
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL is not set; skipping alert")
        return
    try:
        response = requests.post(
            webhook_url,
            json={"content": text, "allowed_mentions": {"parse": []}},
            timeout=WEBHOOK_TIMEOUT_SECONDS,
        )
        if response.status_code >= 300:
            logger.error("alert POST failed status=%d body=%s", response.status_code, response.text)
    except requests.RequestException:
        logger.exception("alert POST raised; the error it was reporting still propagates")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def run_collect(config_path: Path, db_path: Path) -> int:
    """Run one collection.

    Exit codes say whether the run COMPLETED, not whether every source succeeded:
      0  the run completed — including runs where some (creator, source) pairs failed.
         Per-pair failures are reported in the `runs` row's failure_count and in the log,
         which is the channel Phase 6's /status and BOT-03 read. RUN-01 requires one
         failing source not to abort the run; reporting that run as a process failure
         would contradict it.
      1  config file not found — the run could not start.
      2  creators.yaml failed validation — nothing opened, nothing fetched (CFG-03, D-11).
      *  a run that DIES part way re-raises after its `runs` row is written (D-16), so the
         interpreter exits non-zero on its own. That is the case a non-zero code means.
      *  a Sheets sync failure (04-03, D-07) re-raises the same way, after the metric rows
         and the `runs` row are already committed — the process exits non-zero and systemd
         marks the unit failed, intended per PITFALLS.md §18(d): a Sheet quietly showing
         yesterday's numbers has no other symptom. The next day's timer run is the retry.

    Why this matters operationally: systemd marks a unit `failed` on any non-zero exit.
    Returning 1 for a run that wrote most of its rows would leave `systemctl --failed`
    permanently red once a single creator hiccups, and a smoke alarm that is always on is
    one nobody looks at. Phase 7's narrated cold-start demo would show red while working.

    A run with per-source failures still exits 0 after this Discord alert is added, exactly
    as before: the alert is the reporting channel, the exit code is not (D-07/D-08).
    """
    start = time.monotonic()
    logger.info("Starting collect run using config %s, database %s", config_path, db_path)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        return 1

    raw = load_raw(config_path)
    try:
        validate(raw)
    except ValidationError as exc:
        for problem in exc.problems:
            logger.error("%s", problem)
        return 2

    creators = load_creators(config_path)
    logger.info("Loaded %d creators", len(creators))
    conn = connect(db_path, create=True)
    result = collect_once(conn, creators)
    conn.close()
    logger.info("Run wrote %d rows with %d failures", result.rows_written, result.failure_count)
    if result.failure_count > 0:
        # Sent after collect_once() has returned and the runs row is committed — not from
        # inside the per-pair except — so one dead upstream API produces one message, not N
        # (D-08). A no_fetcher_registered skip is never in result.failures (D-07).
        _post_alert(build_alert_text(result.failures))

    try:
        resolved = resolve_sheets_config()
        if resolved is None:
            raise SheetsKeyfileUnusable(
                "Sheets configuration missing: set CREATORPULSE_SHEET_ID and "
                "CREATORPULSE_SHEETS_KEYFILE"
            )
        sheet_id, keyfile = resolved
        sheets_conn = connect(db_path, create=False)
        sheets.sync(sheets_conn, sheet_id, keyfile)
        sheets_conn.close()
    except (SheetNotShared, SheetsKeyfileUnusable, gspread.exceptions.APIError) as exc:
        logger.error(
            "Sheets sync failed — metric rows and the runs row are already committed; "
            "the next timer run is the retry: %s",
            exc,
        )
        # D-09: post, then re-raise, exactly as before. _post_alert swallows its own
        # failures, so there is no path by which a broken webhook replaces this exception.
        _post_alert(f"CreatorPulse Sheets sync failed: {type(exc).__name__}: {exc}")
        raise

    elapsed = time.monotonic() - start
    logger.info("Run complete in %.2f seconds", elapsed)
    return 0


def run_sync(db_path: Path) -> int:
    """Write the Dashboard tab from the database's current metrics.

    Exit codes:
      0  the sync completed and the Dashboard was written.
      1  the sheets configuration (CREATORPULSE_SHEET_ID / CREATORPULSE_SHEETS_KEYFILE) is
         absent, so the sync could not start — nothing was opened, nothing was written.
      *  an exception propagated (e.g. DatabaseNotInitialized, a gspread failure); a non-zero
         exit is what marks the unit failed and puts a traceback in the journal.
    """
    start = time.monotonic()
    resolved = resolve_sheets_config()
    if resolved is None:
        logger.error(
            "Sheets configuration missing: set CREATORPULSE_SHEET_ID and "
            "CREATORPULSE_SHEETS_KEYFILE in /etc/creatorpulse/creatorpulse.env"
        )
        return 1
    sheet_id, keyfile = resolved

    logger.info("Starting sync using database %s, sheet %s, keyfile %s", db_path, sheet_id, keyfile)
    conn = connect(db_path, create=False)
    row_count = sheets.sync(conn, sheet_id, keyfile)
    conn.close()
    logger.info("Sync wrote %d data rows", row_count)
    elapsed = time.monotonic() - start
    logger.info("Run complete in %.2f seconds", elapsed)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creatorpulse")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--config", type=Path, default=None)

    subparsers.add_parser("sync")
    bot_parser = subparsers.add_parser("bot")
    bot_parser.add_argument(
        "--digest-now",
        action="store_true",
        help="post one digest immediately after connecting, then keep the schedule",
    )

    args = parser.parse_args(argv)

    configure_logging()

    if args.command == "collect":
        config_path, db_path = resolve_paths()
        if args.config is not None:
            config_path = args.config.resolve()
        return run_collect(config_path, db_path)
    if args.command == "sync":
        _, db_path = resolve_paths()
        return run_sync(db_path)
    if args.command == "bot":
        _, db_path = resolve_paths()
        # Imported here, not at module top: the collector and sync commands must not pull
        # discord.py into their import graph, and a top-level import would do exactly that.
        from creatorpulse.bot import run_bot

        return run_bot(db_path, digest_now=args.digest_now)
    return 1


if __name__ == "__main__":
    sys.exit(main())
