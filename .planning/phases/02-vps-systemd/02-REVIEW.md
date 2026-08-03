---
phase: 02-vps-systemd
reviewed: 2026-08-04T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - src/creatorpulse/cli.py
  - src/creatorpulse/config.py
  - tests/test_paths.py
  - .env.example
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-08-04T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Small, deliberate diff: `resolve_paths()` added to `config.py`, `db_path` threaded through
`cli.py`'s `run_collect()`, `.env.example` committed with blank secret placeholders. Core
contract (env-var precedence, empty-string-as-unset, repo/cwd-relative fallback) is correctly
implemented and well covered by `tests/test_paths.py`. `.env.example` contains no real values
and no `CREATORPULSE_*` path entries, consistent with the phase contract; `.gitignore` correctly
excludes `.env`/`*.env` while allowlisting `.env.example`.

Two gaps found: the new `--config` CLI-override branch in `main()` (part of this diff) has zero
test coverage, and the pre-existing `config_path.exists()` check doesn't distinguish files from
directories, so a misconfigured path that happens to point at a directory produces an unhandled
traceback instead of the intended clean logged error — undermining the "first log line explains
what happened" design goal this phase is built around. No critical/security issues found; the
documented cwd-vs-repo-relative default behavior is excluded per phase instructions.

## Warnings

### WR-01: `--config` CLI override branch has no test coverage

**File:** `src/creatorpulse/cli.py:50-54`
**Issue:** This diff changed `main()`'s dispatch logic for `collect`: it now calls
`resolve_paths()` unconditionally and then overrides `config_path` when `args.config is not
None`. `tests/test_paths.py` thoroughly covers `resolve_paths()` in isolation and covers
`run_collect()` given already-resolved paths, but nothing in the test suite invokes `main()` or
exercises the `args.config is not None` branch. This is the actual new wiring in this diff (not
just `resolve_paths()` itself) and it is currently unverified by any test — a future refactor of
`main()` could silently break the manual `--config` override with nothing failing red.
**Fix:**
```python
def test_main_config_flag_overrides_resolved_path(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("CREATORPULSE_CONFIG", raising=False)
    monkeypatch.delenv("CREATORPULSE_DB", raising=False)
    config_path = tmp_path / "creators.yaml"
    config_path.write_text(CREATORS_YAML, encoding="utf-8")

    exit_code = main(["collect", "--config", str(config_path)])

    assert exit_code == 0
```

### WR-02: Directory (or other non-file) config path crashes instead of failing cleanly

**File:** `src/creatorpulse/cli.py:25-28`
**Issue:** `run_collect()` guards only with `config_path.exists()`, which is `True` for
directories. If `CREATORPULSE_CONFIG` (or `--config`) is accidentally pointed at a directory —
a plausible operator typo, e.g. `/etc/creatorpulse` instead of `/etc/creatorpulse/creators.yaml`
— the existence check passes, and `load_creators()` → `path.read_text()` raises an unhandled
`IsADirectoryError` that propagates out of `main()` as a raw traceback. The process still exits
non-zero, but this contradicts the explicit design intent of this phase: a single clean log line
telling the operator exactly what went wrong. Pre-existing code untouched by this diff's `+/-`
lines, but directly adjacent to (and now more load-bearing because of) the paths this phase
surfaces in the first log line.
**Fix:**
```python
if not config_path.is_file():
    logger.error("Config file not found: %s", config_path)
    return 1
```

## Info

### IN-01: Inconsistent empty-string handling between env vars and `--config`

**File:** `src/creatorpulse/cli.py:52-53` vs `src/creatorpulse/config.py:28-29`
**Issue:** `resolve_paths()` deliberately treats an empty `CREATORPULSE_CONFIG`/`CREATORPULSE_DB`
as unset (`if config_env else DEFAULT_CONFIG_PATH`). The `--config` CLI flag has no equivalent
normalization: `args.config is not None` is `True` even for `Path("")`, so `--config ""` would
silently override to `Path("").resolve()` (the cwd) rather than falling back to the default,
diverging from the "empty means unset" contract established for the env-var path.
**Fix:** Treat a falsy/empty `args.config` the same as unset: `if args.config:` instead of
`if args.config is not None:`.

### IN-02: Unreachable `return 1` at end of `main()`

**File:** `src/creatorpulse/cli.py:61`
**Issue:** `subparsers = parser.add_subparsers(dest="command", required=True)` means argparse
raises and exits before `args.command` can be anything other than `"collect"`, `"sync"`, or
`"bot"`. The final `return 1` can never execute.
**Fix:** Remove the trailing `return 1`, or replace with `raise AssertionError("unreachable")` to
make the intent explicit if kept for mypy exhaustiveness.

### IN-03: No guard against whitespace-only env values in `resolve_paths()`

**File:** `src/creatorpulse/config.py:28-29`
**Issue:** `if config_env else DEFAULT_CONFIG_PATH` only catches falsy values (`None`, `""`). A
value of `" "` (a stray space from a hand-edited `EnvironmentFile`) is truthy and becomes
`Path(" ")`, producing a confusing resolved path rather than falling back to the default. Low
likelihood given systemd `EnvironmentFile` authoring, but cheap to close.
**Fix:** `config_env = (os.environ.get("CREATORPULSE_CONFIG") or "").strip() or None`, same for
`db_env`.

---

_Reviewed: 2026-08-04T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
