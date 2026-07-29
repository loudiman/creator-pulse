"""creatorpulse console-script entry point and subcommand dispatch."""

import argparse
import logging
import sys
import time
from pathlib import Path

from creatorpulse.config import DEFAULT_CONFIG_PATH, load_creators

logger = logging.getLogger("creatorpulse")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def run_collect(config_path: Path) -> int:
    start = time.monotonic()
    logger.info("Starting collect run using config %s", config_path)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        return 1
    creators = load_creators(config_path)
    logger.info("Loaded %d creators", len(creators))
    logger.warning("Collector body is not implemented yet; Phase 3 fills it in")
    elapsed = time.monotonic() - start
    logger.info("Run complete in %.2f seconds", elapsed)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creatorpulse")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)

    subparsers.add_parser("sync")
    subparsers.add_parser("bot")

    args = parser.parse_args(argv)

    configure_logging()

    if args.command == "collect":
        return run_collect(args.config)
    if args.command == "sync":
        logger.warning("sync is not implemented yet; Phase 4 fills it in")
        return 3
    if args.command == "bot":
        logger.warning("bot is not implemented yet; Phase 6 fills it in")
        return 3
    return 1


if __name__ == "__main__":
    sys.exit(main())
