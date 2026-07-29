"""Hand-run fixture recorder — never invoked by pytest.

Fetches a public URL and saves the body into tests/fixtures/{source}/{case}.{ext}. Generic
fetch-and-save only: no platform knowledge, no parsing, no browser automation. Run by hand;
`[tool.pytest.ini_options]` testpaths is scoped to tests/, so this script is never collected.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests

_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_TIMEOUT_SECONDS = 30
FIXTURES_ROOT = (Path(__file__).resolve().parent.parent / "tests" / "fixtures").resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a fixture file from a public URL.")
    parser.add_argument("--source", required=True, help="fixture subdirectory, e.g. youtube")
    parser.add_argument("--case", required=True, help="scenario name, e.g. channel_ok")
    parser.add_argument("--url", required=True, help="public URL to fetch")
    parser.add_argument("--ext", default="json", help="file extension (default: json)")
    args = parser.parse_args(argv)

    for label, value in (("--source", args.source), ("--case", args.case)):
        if not _NAME_RE.match(value):
            print(f"invalid {label}: {value!r} (must match ^[a-z0-9_]+$)", file=sys.stderr)
            return 2

    target = (FIXTURES_ROOT / args.source / f"{args.case}.{args.ext}").resolve()
    if FIXTURES_ROOT not in target.parents:
        print(f"refusing to write outside fixtures root: {target}", file=sys.stderr)
        return 2

    response = requests.get(args.url, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(response.text, encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
