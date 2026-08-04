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

    Exit codes: 0 clean run; 1 config file not found, or the run completed with failures;
    2 creators.yaml failed validation — nothing was opened, nothing was fetched (CFG-03, D-11).
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
    return 0 if result.failure_count == 0 else 1


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
