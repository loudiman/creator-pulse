"""creatorpulse console-script entry point and subcommand dispatch."""

import argparse
import logging
import sys
import time
from pathlib import Path

from creatorpulse.collector import collect_once
from creatorpulse.config import ValidationError, load_creators, load_raw, resolve_paths, validate
from creatorpulse.db import connect

logger = logging.getLogger("creatorpulse")


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

    Why this matters operationally: systemd marks a unit `failed` on any non-zero exit.
    Returning 1 for a run that wrote most of its rows would leave `systemctl --failed`
    permanently red once a single creator hiccups, and a smoke alarm that is always on is
    one nobody looks at. Phase 7's narrated cold-start demo would show red while working.
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
    elapsed = time.monotonic() - start
    logger.info("Run complete in %.2f seconds", elapsed)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creatorpulse")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--config", type=Path, default=None)

    subparsers.add_parser("sync")
    subparsers.add_parser("bot")

    args = parser.parse_args(argv)

    configure_logging()

    if args.command == "collect":
        config_path, db_path = resolve_paths()
        if args.config is not None:
            config_path = args.config.resolve()
        return run_collect(config_path, db_path)
    if args.command == "sync":
        logger.warning("sync is not implemented yet; Phase 4 fills it in")
        return 3
    if args.command == "bot":
        logger.warning("bot is not implemented yet; Phase 6 fills it in")
        return 3
    return 1


if __name__ == "__main__":
    sys.exit(main())
