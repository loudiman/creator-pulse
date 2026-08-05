---
phase: 04-playwright-sheets
reviewed: 2026-08-06T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/creatorpulse/sheets.py
  - src/creatorpulse/config.py
  - src/creatorpulse/cli.py
  - tests/test_sheets.py
  - tests/test_config.py
  - tests/test_paths.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-08-06T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

`sheets.py` is the strongest file in this set: the two-try-block split around
`gspread.service_account()` vs. `client.open_by_key()` is correct and does exactly what its
docstring claims — a bare `PermissionError` from an unshared Sheet is never conflated with an
`OSError` from a bad key file, because each is caught in its own try block, and `PermissionError`
is only ever caught in the second one. The NULL-vs-0 rule (D-08/SHEET's core correctness
requirement) is implemented correctly in `build_dashboard_rows` — `None` renders blank, `0`
renders as `0`, and delta math checks `is None` explicitly rather than falling back on
truthiness. No `COALESCE`/`or 0` pattern was found anywhere in the metric path.

The real gaps are one config-loading crash path that breaks the phase's own documented exit-code
contract, a validation gap that lets non-string source identifiers slip past `validate()`, a
missing-worksheet-tab failure mode `sheets.py`'s otherwise-thorough error handling doesn't cover,
and a couple of DB-connection leaks on exception paths in `cli.py`.

## Critical Issues

### CR-01: Malformed creators.yaml crashes with an unhandled exception instead of the documented exit code 2

**File:** `src/creatorpulse/config.py:61-65` and `src/creatorpulse/config.py:68-73`, exercised via `src/creatorpulse/cli.py:64-70`

**Issue:** `run_collect()`'s docstring promises: "2  creators.yaml failed validation — nothing
opened, nothing fetched (CFG-03, D-11)." The implementation only delivers that contract for
inputs where `yaml.safe_load` returns a `dict` whose `"creators"` key is present. Two realistic
inputs break it:

1. `load_raw()` does `data: dict[str, Any] = yaml.safe_load(text)` with no check that the
   result actually is a dict — the annotation is asserted, not verified. An **empty
   `creators.yaml`** (very plausible on first-time setup, e.g. `touch creators.yaml` or an
   accidentally-cleared file) makes `yaml.safe_load` return `None`. A top-level YAML *list*
   (someone drops the `creators:` key and pastes a bare list) makes it return a `list`.
2. `validate(raw)` immediately does `raw.get("creators")` (config.py:71) with no `isinstance`
   guard. `None.get(...)` and `list.get(...)` both raise `AttributeError`, which is not a
   `ValidationError` and is therefore **not caught** by `run_collect()`'s
   `except ValidationError:` (cli.py:66-70). The exception propagates out of `run_collect()`
   and out of `main()` as a raw traceback — not exit code 2, no `field=...` log lines, and no
   `runs` row.

A YAML syntax error (unbalanced quotes, bad indentation) hits the same gap one call earlier:
`yaml.safe_load` raises `yaml.YAMLError`, which is also not caught anywhere in `run_collect()`.

Both are plausible operator mistakes on a config file that the project's own hard rules
describe as human-authored and expected to "fail loudly at startup" — but the failure here is
loud in the wrong way (an unhandled traceback under whatever process wraps the systemd timer),
not the clean, aggregated `field=` problem list CFG-03 promises.

**Fix:**
```python
# config.py
def load_raw(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValidationError([f"creator=<missing> field=<file>: not valid YAML ({exc})"]) from exc
    if not isinstance(data, dict):
        raise ValidationError(["creator=<missing> field=<file>: top level is not a mapping"])
    return data
```
This keeps `run_collect()`'s existing `except ValidationError:` block as the single catch site —
no change needed in `cli.py`. (`validate()`'s own `raw.get("creators")` guard already handles a
present-but-non-list `creators` key; this closes the gap one level up, at the file-parse
boundary.)

## Warnings

### WR-01: `validate()`'s "empty identifier" check accepts non-string source values

**File:** `src/creatorpulse/config.py:99-100`

**Issue:**
```python
if not str(identifier).strip():
    problems.append(f"creator={label} field=sources.{platform}: empty identifier")
```
This only catches the empty-string case. A YAML value of `null` (i.e. `youtube:` with nothing
after the colon — an easy typo) parses to `None`, and `str(None).strip()` is `"None"` — truthy —
so it passes validation as if it were a real identifier. The same is true for an unquoted numeric
handle (`twitch: 123456` parses as an `int`, `str(123456)` is non-empty) or any other non-string
YAML scalar/collection. `load_creators()` (config.py:106-117) then stores the raw, un-stringified
value straight into `Creator.sources: dict[str, str]` (config.py:27), silently violating that
type contract. The failure only surfaces later, per-source, as an opaque
`fetch failed creator=... cause=AttributeError: ...` in `collect_once()`'s per-pair catch
(collector.py:38-46) — instead of a `field=sources.youtube: empty identifier`-style message at
config-validation time, which is exactly the fail-fast guarantee CFG-03 is meant to provide.

**Fix:**
```python
if not isinstance(identifier, str) or not identifier.strip():
    problems.append(f"creator={label} field=sources.{platform}: empty identifier")
```

### WR-02: `sheets.py` has no handling for a missing "Dashboard" worksheet tab

**File:** `src/creatorpulse/sheets.py:159` (inside `_open_worksheet`, `src/creatorpulse/sheets.py:112-159`)

**Issue:** `spreadsheet.worksheet(DASHBOARD_TAB)` raises `gspread.exceptions.WorksheetNotFound`
when the target Sheet does not have a tab literally named "Dashboard" (renamed tab, or a fresh
spreadsheet that still only has "Sheet1"). Every other Sheets failure mode in this module —
unshared sheet, Viewer-only share, bad key file, deleted spreadsheet, transient 4xx/5xx — gets a
dedicated, explained exception (`SheetNotShared` / `SheetsKeyfileUnusable`) per the module's own
stated goal of preventing misdiagnosis (SHEET-07). `WorksheetNotFound` is not one of the excepts
in `_open_worksheet`, so it propagates straight through `sync()` and past `cli.py`'s
`except (SheetNotShared, SheetsKeyfileUnusable, gspread.exceptions.APIError)` (cli.py:90) — it
is not an `APIError` subclass — surfacing as a raw traceback with none of the "share it with
this address as Editor"-style guidance the rest of the module provides. No test in
`test_sheets.py` exercises this path either.

**Fix:**
```python
try:
    return spreadsheet.worksheet(DASHBOARD_TAB)
except gspread.exceptions.WorksheetNotFound as exc:
    raise SheetNotShared(
        f"Sheet {sheet_id} has no {DASHBOARD_TAB!r} tab — create it (or rename the tab) "
        "before running sync"
    ) from exc
```
(Reusing `SheetNotShared` may not be the right name for this case — a distinct exception class
communicates the actual problem better — but either way `cli.py`'s except clause needs it added.)

### WR-03: `run_collect()` leaks the Sheets DB connection when `sheets.sync()` raises

**File:** `src/creatorpulse/cli.py:79-96`

**Issue:**
```python
try:
    resolved = resolve_sheets_config()
    if resolved is None:
        raise SheetsKeyfileUnusable(...)
    sheet_id, keyfile = resolved
    sheets_conn = connect(db_path, create=False)
    sheets.sync(sheets_conn, sheet_id, keyfile)
    sheets_conn.close()
except (SheetNotShared, SheetsKeyfileUnusable, gspread.exceptions.APIError) as exc:
    logger.error(...)
    raise
```
`sheets_conn.close()` only runs on the success path. Every documented failure mode of
`sheets.sync()` (unshared sheet, bad keyfile, Viewer-only share, transient API error) raises
before reaching that line, so `sheets_conn` is left open and the code re-raises without closing
it. It doesn't crash the process (which exits right after), but it does mean the connection
object outlives the function on every error path, and any caller that catches this re-raised
exception without the process actually exiting (e.g. a test, or a future long-lived wrapper)
accumulates open connections. The same shape of problem exists for the outer `conn` used by
`collect_once()` (cli.py:74-76): if anything after the upserts but before `conn.close()`
(cli.py:76) throws, `conn` is never closed either.

**Fix:**
```python
sheet_id, keyfile = resolved
with connect(db_path, create=False) as sheets_conn:
    sheets.sync(sheets_conn, sheet_id, keyfile)
```
`sqlite3.Connection` supports the context-manager protocol for commit/rollback but not
auto-close; use `contextlib.closing()` if `connect()` doesn't return something that closes
itself:
```python
from contextlib import closing

with closing(connect(db_path, create=False)) as sheets_conn:
    sheets.sync(sheets_conn, sheet_id, keyfile)
```

### WR-04: `run_sync()` handles Sheets failures inconsistently with `run_collect()`

**File:** `src/creatorpulse/cli.py:103-130`

**Issue:** `run_collect()` wraps its Sheets sync call and logs a clear, contextual error message
before re-raising (cli.py:90-96). `run_sync()` (the `creatorpulse sync` subcommand) calls
`sheets.sync(conn, sheet_id, keyfile)` (cli.py:125) with no equivalent try/except at all — a
`SheetNotShared`, `SheetsKeyfileUnusable`, or `gspread.exceptions.APIError` from the exact same
underlying call produces a bare traceback under `sync` but a clean logged message under
`collect`. Both subcommands exit non-zero either way (matching the "non-zero exit marks the unit
failed" intent), so this isn't a correctness bug, but it's an avoidable inconsistency in operator-
facing output for what is otherwise presented as the same failure surface. `run_sync()` also
shares WR-03's leak: `conn.close()` (cli.py:126) is skipped if `sheets.sync()` raises.

**Fix:** Mirror `run_collect()`'s except clause (log the same style of message, then re-raise),
and close `conn` in a `finally`/`with closing(...)` regardless of outcome.

## Info

### IN-01: `main()`'s final `return 1` is unreachable

**File:** `src/creatorpulse/cli.py:133-158`

**Issue:** `subparsers = parser.add_subparsers(dest="command", required=True)` (cli.py:135)
only registers `collect`, `sync`, and `bot` (cli.py:137-141), and `required=True` means argparse
itself rejects any other/missing subcommand before `main()`'s body runs. The `if/elif/elif`
chain (cli.py:147-157) already returns inside every one of the three branches, so the trailing
`return 1` (cli.py:158) can never execute.

**Fix:** Either delete the dead `return 1`, or replace the `if` chain with an assertion that
documents the invariant, e.g. `raise AssertionError(f"unhandled command {args.command!r}")`.

### IN-02: `entry.get("id")`/`entry.get("name")` conflate a falsy-but-present value with "missing"

**File:** `src/creatorpulse/config.py:78-79`

**Issue:** `str(entry.get("id") or "").strip()` and the equivalent for `name` use `or ""`, which
treats any falsy value — not just `None`/absent — as missing. A YAML `id: 0` (or `id: false`)
would report as "missing or not a lowercase ASCII slug" rather than being evaluated on its actual
value. Low real-world likelihood for a creator slug, but it's the same falsy-vs-missing
conflation this codebase's own hard rules call out explicitly (NULL vs 0) as a correctness rule
elsewhere in the metric path — worth the same discipline here.

**Fix:** `str(entry.get("id", "")).strip()` (falls back only when the key is absent, not when
present-but-falsy).

---

_Reviewed: 2026-08-06T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
