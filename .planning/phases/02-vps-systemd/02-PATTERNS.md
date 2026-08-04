# Phase 2: VPS & systemd - Pattern Map

**Mapped:** 2026-07-31
**Files analyzed:** 4 (agent-writable) + 3 human-built (read-only reference, not mapped)
**Analogs found:** 4 / 4

## Scope note

Per the hard scope fence, only these are files-to-create/modify for pattern-mapping purposes:
- `src/creatorpulse/config.py` (extend) or a new `src/creatorpulse/paths.py`
- `src/creatorpulse/cli.py` (extend)
- `tests/test_paths.py` (new) or `tests/test_config.py` (extend)
- `.env.example` (new, names only)
- `.planning/phases/02-vps-systemd/02-UAT.md` (new)

`deploy/creatorpulse.service`, `deploy/creatorpulse.timer`, `docs/deploy.md` are **human-built —
not mapped**. No analog, no excerpt, no outline provided for them here.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/creatorpulse/config.py` (or new `paths.py`) — `resolve_paths()` | utility/config | request-response (env read → resolved value) | `src/creatorpulse/config.py` itself (existing `DEFAULT_CONFIG_PATH` + `load_creators`) | exact |
| `src/creatorpulse/cli.py` — `run_collect()` log line, `main()` wiring | controller (CLI entry) | request-response | `src/creatorpulse/cli.py` itself (existing `run_collect`/`main`) | exact |
| `tests/test_paths.py` (new) | test | transform (env state → assertion) | `tests/test_config.py` | role-match (same project test style; new file has no direct env-var precedent in repo) |
| `.env.example` | config | — | none in repo (new artifact) | no analog — see below |

## Pattern Assignments

### `src/creatorpulse/config.py` or `src/creatorpulse/paths.py` (utility, request-response)

**Analog:** `src/creatorpulse/config.py` (self — extend in place; this is the established pattern
for "small stdlib-only module with one constant + one function")

**Module docstring + imports pattern** (lines 1-7):
```python
"""Parse-only reader for creators.yaml. No validation — see Phase 3 CFG-03."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
```
Mirror: one-line module docstring stating scope/boundary, stdlib imports first, third-party after
a blank line. `resolve_paths()` needs only `import os` + `from pathlib import Path` — no third-party
import block at all.

**Module-level constant pattern** (line 9):
```python
DEFAULT_CONFIG_PATH = Path("creators.yaml")
```
Add `DEFAULT_DB_PATH = Path("creatorpulse.db")` (or a gitignored subdir per CONTEXT.md discretion)
alongside it, same style — bare `Path(...)` literal, no `os.path.join`.

**Function signature + docstring pattern** (lines 19-20):
```python
def load_creators(path: Path = DEFAULT_CONFIG_PATH) -> list[Creator]:
    """Read and parse creators.yaml into a list of Creator objects. Parse-only, no validation."""
```
`resolve_paths()` should match: full type annotations (mypy `strict = true` per Phase 1 D-05),
one-line docstring stating exactly what it does and does not do (RESEARCH.md's own draft already
follows this — see RESEARCH.md "Pattern 1" code block for the literal implementation to use,
verified against this file's existing style).

**No error handling / no try-except in this file** — `load_creators` lets `FileNotFoundError` and
`KeyError` propagate uncaught; `resolve_paths()` should do the same (`os.environ.get()` never
raises, `Path.resolve()` doesn't touch the filesystem). Consistent with this file's "parse-only, no
validation" stated boundary — do not add defensive code the analog doesn't have.

---

### `src/creatorpulse/cli.py` (controller/CLI, request-response)

**Analog:** `src/creatorpulse/cli.py` (self)

**Imports pattern** (lines 1-9):
```python
"""creatorpulse console-script entry point and subcommand dispatch."""

import argparse
import logging
import sys
import time
from pathlib import Path

from creatorpulse.config import DEFAULT_CONFIG_PATH, load_creators
```
Add `resolve_paths` (and `DEFAULT_DB_PATH` if needed) to the same `from creatorpulse.config import
...` line if `resolve_paths` stays in `config.py`; use a new `from creatorpulse.paths import
resolve_paths` line only if the discretion call goes the other way.

**Core pattern — `run_collect`** (lines 22-33):
```python
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
```
Change: add `db_path: Path` param, and change the first `logger.info` line to also print `db_path`
— RESEARCH.md's own worked example (Code Examples → "Resolved-path logging integrated into the
existing run_collect") is this exact diff, already checked against this file's real line numbers.
`db_path` is accepted and logged only, never opened — matches D-08/RUN-04 exactly and matches this
function's existing "log first, before any I/O that could raise" ordering (log line precedes the
`config_path.exists()` check).

**`main()` wiring pattern** (lines 36-58, esp. 40-41 and 50-51):
```python
collect_parser = subparsers.add_parser("collect")
collect_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
...
if args.command == "collect":
    return run_collect(args.config)
```
Change: `--config` default becomes `None` (sentinel for "use env/fallback"), and the `collect`
branch calls `resolve_paths()` first, then overrides with `args.config` only if the flag was passed
— see RESEARCH.md Code Examples → "main() wiring" for the literal 6-line diff. This preserves D-06's
requirement that the flag remains an interactive override, not the primary source.

**Logging setup — do not touch** (lines 14-19): `configure_logging()` is already correct per Phase
1 D-19/D-20 (stdout, `logging.basicConfig`, INFO level) — the new resolved-paths line rides this
existing config unchanged. No new handler, no structured/JSON logging.

---

### `tests/test_paths.py` (new) or extend `tests/test_config.py` (test, transform)

**Analog:** `tests/test_config.py`

**Full existing test file style** (lines 1-27, reproduced above):
- One-line module docstring restating "Fixtures only, no live network calls" per CLAUDE.md.
- Module-level constant for a fixture path resolved via `Path(__file__).resolve().parent.parent /
  "creators.yaml"` — not needed for the new tests (no fixture file), but same import shape:
  `from creatorpulse.config import Creator, load_creators` → new file uses `from creatorpulse.config
  import DEFAULT_CONFIG_PATH, DEFAULT_DB_PATH, resolve_paths` (adjust per actual module).
- Bare `def test_xxx() -> None:` functions, no test classes, no fixtures/conftest beyond what pytest
  ships — matches this repo's minimal style.

**New tests needed (from RESEARCH.md Pitfall D, already vetted against this project's exact
import names and pytest version 9.1.1)**:
```python
def test_resolve_paths_uses_env_vars_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CREATORPULSE_CONFIG", str(tmp_path / "creators.yaml"))
    monkeypatch.setenv("CREATORPULSE_DB", str(tmp_path / "creatorpulse.db"))
    config_path, db_path = resolve_paths()
    assert config_path == (tmp_path / "creators.yaml").resolve()
    assert db_path == (tmp_path / "creatorpulse.db").resolve()


def test_resolve_paths_falls_back_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CREATORPULSE_CONFIG", raising=False)
    monkeypatch.delenv("CREATORPULSE_DB", raising=False)
    config_path, db_path = resolve_paths()
    assert config_path == DEFAULT_CONFIG_PATH.resolve()
    assert db_path == DEFAULT_DB_PATH.resolve()
```
Add a third `caplog`-based test asserting `run_collect`'s log record contains both resolved absolute
path strings (RESEARCH.md Validation Architecture table, row 3) — no existing `caplog` test in the
repo to copy from; standard pytest `caplog` fixture usage, no project-specific pattern deviation
needed.

**Import note:** `import pytest` for the `pytest.MonkeyPatch` type annotation — check whether
`test_config.py` or any other repo test imports `pytest` directly; it currently does not (no
type-annotated fixtures used yet), so this is the first file in the repo to need it. Not a deviation
from convention, just the first instance.

---

### `.env.example` (config, no data flow — static file)

**No analog in repo.** This is a new artifact type. Follow D-14 literally: names only, blank values,
one line per variable, comment style at Claude's discretion. Suggested shape (plain `KEY=` lines,
optionally grouped with `#` comment headers per phase — YouTube/Twitch/Discord/Sheets), matching the
flat `KEY=value` shape `EnvironmentFile=` parsing expects (see RESEARCH.md "Pitfall B" for the
parsing rules this file's real counterpart at `/etc/creatorpulse/creatorpulse.env` must satisfy —
`.env.example` itself is not parsed by systemd, just a template for the human-typed file).

Variables to list (from CONTEXT.md D-14): YouTube API key, Twitch client id + secret, Discord bot
token, Discord webhook URL, Google service-account JSON path. `CREATORPULSE_CONFIG`/
`CREATORPULSE_DB` are **not** secrets and are NOT in this file — D-07 places them as `Environment=`
lines in the human-built unit, not in the `EnvironmentFile`.

## Shared Patterns

### stdlib-only, no new imports
**Source:** `src/creatorpulse/config.py`, `src/creatorpulse/cli.py` (both already stdlib +
PyYAML only)
**Apply to:** `resolve_paths()`, its tests — `os`, `pathlib`, `logging` stdlib only. No
python-dotenv, no config-object library (STACK.md already closed this question).

### `str | None` explicit handling for `os.environ.get()`
**Source:** RESEARCH.md Pattern 1 (verified against Phase 1 D-05's `mypy --strict` setting)
**Apply to:** `resolve_paths()` — annotate `os.environ.get(...)` results as `str | None` explicitly;
strict mode will otherwise flag implicit `Any`/`str` narrowing.

### Log-first-before-I/O ordering
**Source:** `src/creatorpulse/cli.py:24` (`run_collect`'s existing `logger.info` precedes the
`config_path.exists()` check)
**Apply to:** the new resolved-paths log line — must be the first thing `run_collect` does after
`configure_logging()`, before any `Path.exists()`/`open()` call, so a failing run still leaves the
path in `journalctl`.

### One-line module/function docstrings stating scope boundary
**Source:** `src/creatorpulse/config.py:1,20`
**Apply to:** every new function in this phase — state what it does and, where relevant, what it
deliberately does not do (mirrors "Parse-only reader... No validation").

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `.env.example` | config | static | First file of this kind in the repo; D-14 spec is prescriptive enough that no analog is needed. |
| `.planning/phases/02-vps-systemd/02-UAT.md` | doc/test-record | — | Analog exists at `.planning/phases/01-skeleton/01-UAT.md` (frontmatter + `## Tests`/`## Summary`/`## Gaps` structure, pasted-evidence style) — same repo, already reviewed above; follow that structure with one test entry per D-15 success criterion (5 pasted-output items) instead of the single fresh-clone walkthrough Phase 1 used. |

## Human-built — not mapped (read-only reference only)

Per hard scope fence, these are **not** files-to-create in this PATTERNS.md and carry no analog/
excerpt: `deploy/creatorpulse.service`, `deploy/creatorpulse.timer`, `docs/deploy.md`. They may be
read by the planner/executor if they exist on disk, but must never be drafted, outlined, or
templated by the agent.

## Metadata

**Analog search scope:** `src/creatorpulse/`, `tests/`, `.planning/phases/01-skeleton/`
**Files scanned:** `config.py`, `cli.py`, `tests/test_config.py`, `01-UAT.md`, `.gitignore` (referenced, not read this pass — already summarized in CONTEXT.md/RESEARCH.md)
**Pattern extraction date:** 2026-07-31
