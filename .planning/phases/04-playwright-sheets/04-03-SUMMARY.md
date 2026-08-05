---
phase: 04-playwright-sheets
plan: 03
subsystem: sheets-sync
tags: [gspread, error-handling, cli, tdd]

requires:
  - phase: 04-playwright-sheets
    provides: "04-01's sheets.py module (_open_worksheet, sync) and 04-02's delta computation, both still assuming the happy path"
provides:
  - "sheets.py: SheetNotShared, SheetsKeyfileUnusable exceptions; _client_email_from_keyfile helper; PermissionError/SpreadsheetNotFound/APIError preflight on open_by_key; a separate 403 arm on the write call"
  - "cli.py: run_collect() syncs the Sheet after collect_once's rows and runs row are committed, using its own create=False connection; a Sheets failure logs at ERROR then re-raises"
  - "7 new fixture cases in tests/test_sheets.py covering every named failure branch plus the transient-failure hedge"
affects: [04-04, phase-5-apps-script, phase-7-readme]

tech-stack:
  added: []
  patterns:
    - "Two separate try blocks for client construction vs open_by_key -- PermissionError is an OSError subclass, so a merged try would misreport an unshared Sheet as a key-file problem"
    - "gspread.exceptions.APIError.response.status_code == 403 as the sole signal that distinguishes a permission failure from a transient 5xx/429 -- never re-labelled otherwise"
    - "client_email read via one json.loads(...).get('client_email'), never any other field from the service-account JSON"

key-files:
  created: []
  modified:
    - src/creatorpulse/sheets.py
    - src/creatorpulse/cli.py
    - tests/test_sheets.py
    - tests/test_config.py
    - tests/test_paths.py

key-decisions:
  - "run_collect() treats a missing Sheets env-var pair the same as any other sync failure (raises SheetsKeyfileUnusable, caught by the same log-then-reraise arm) rather than silently skipping the sync -- consistent with D-07/PITFALLS.md §18(d)'s rule that a stale Dashboard must never be a quiet outcome. Not explicitly specified by the plan's <behavior> list; added as necessary since resolve_sheets_config() returns Optional and mypy strict forces the None case to be handled."
  - "3 pre-existing tests (test_config.py x2, test_paths.py x1) that call run_collect() directly now set CREATORPULSE_SHEET_ID/CREATORPULSE_SHEETS_KEYFILE and stub creatorpulse.cli.sheets.sync to a no-op. They predate this plan's dependency and broke because they never anticipated a Sheets call; no existing assertion was weakened."

patterns-established:
  - "A failure path introduced deep in a module can widen the fixture surface of unrelated call-site tests -- when a plan adds a mandatory dependency to an already-tested function, grep for every existing caller before declaring the gate green, not just the plan's own new test file."

requirements-completed: [SHEET-06, SHEET-07]

coverage:
  - id: D1
    description: "An unshared Sheet raises SheetNotShared naming client_email and Editor (PermissionError arm)"
    requirement: SHEET-07
    verification:
      - kind: unit
        ref: "tests/test_sheets.py::test_unshared_sheet_raises_sheet_not_shared_naming_client_email_and_editor"
        status: pass
    human_judgment: false
  - id: D2
    description: "A Viewer-only share raises SheetNotShared at the write call, naming client_email and Editor -- the case a preflight on open alone cannot see"
    requirement: SHEET-07
    verification:
      - kind: unit
        ref: "tests/test_sheets.py::test_viewer_only_share_raises_at_write_naming_client_email_and_editor"
        status: pass
    human_judgment: false
  - id: D3
    description: "A wrong or deleted spreadsheet id raises SheetNotShared naming CREATORPULSE_SHEET_ID"
    requirement: SHEET-07
    verification:
      - kind: unit
        ref: "tests/test_sheets.py::test_unknown_spreadsheet_id_raises_sheet_not_shared_naming_env_var"
        status: pass
    human_judgment: false
  - id: D4
    description: "A missing or malformed key file raises SheetsKeyfileUnusable naming the path and CREATORPULSE_SHEETS_KEYFILE before any network call"
    requirement: SHEET-07
    verification:
      - kind: unit
        ref: "tests/test_sheets.py::test_keyfile_absent_raises_before_any_network_call, test_keyfile_present_but_not_json_raises_before_any_network_call"
        status: pass
    human_judgment: false
  - id: D5
    description: "A transient 500/429 at open or write propagates as the original gspread.exceptions.APIError, unrelabelled"
    requirement: SHEET-07
    verification:
      - kind: unit
        ref: "tests/test_sheets.py::test_transient_api_failure_propagates_unrelabelled_at_open, test_transient_api_failure_propagates_unrelabelled_at_write"
        status: pass
    human_judgment: false
  - id: D6
    description: "run_collect() syncs the Sheet after collect_once's rows and runs row are committed; a Sheets failure logs at ERROR then re-raises, exiting non-zero, and never touches failure_count"
    requirement: SHEET-06
    verification:
      - kind: unit
        ref: "tests/test_sheets.py::test_run_collect_reraises_sheets_sync_failure_after_runs_row_committed"
        status: pass
    human_judgment: false
  - id: D7
    description: "The collect CLI surface, its existing log lines, and deploy/ are byte-identical to before this plan (cli.py diff is additions-only)"
    verification:
      - kind: other
        ref: "git diff HEAD -- src/creatorpulse/cli.py | grep -c '^-[^-]' == 0; git diff --name-only HEAD -- deploy/ | wc -l == 0"
        status: pass
    human_judgment: false
  - id: D8
    description: "SHEET-07's real-Sheet proof: un-share/re-share-as-Viewer/re-share-as-Editor against the live droplet Sheet, pasting the actual SheetNotShared text"
    verification: []
    human_judgment: true
    rationale: "Automated checks cannot exercise gspread's real 403/PermissionError responses against a live Sheet. This is 04-04's 04-UAT.md work, per ROADMAP's Definition of Green (manual gate from Phase 3 onward)."

duration: ~50min
completed: 2026-08-06
status: complete
---

# Phase 4 Plan 3: Name the Sheets Failures, and Attach the Second Entry Point Summary

**`sheets.py` gains `SheetNotShared`/`SheetsKeyfileUnusable` with a `PermissionError`-first preflight on `open_by_key` plus a separate 403 arm on the write call (catching the Viewer-only case a preflight alone can't see), and `run_collect()` now syncs the Dashboard after every collect run, logging and re-raising on failure without touching `failure_count` or any existing log line.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 3 (all `type="auto" tdd="true"`/`auto`)
- **Files modified:** 5 (`src/creatorpulse/sheets.py`, `src/creatorpulse/cli.py`, `tests/test_sheets.py`, `tests/test_config.py`, `tests/test_paths.py`)

## Accomplishments
- `sheets.py`: two new exceptions (`SheetNotShared`, `SheetsKeyfileUnusable`), a `_client_email_from_keyfile` helper reading exactly one field and nothing else, a client-construction try block separate from the `open_by_key` try block (so `PermissionError`, an `OSError` subclass, can never be misreported as a key-file problem), three ordered except arms on `open_by_key` (`PermissionError` → `SpreadsheetNotFound` → `APIError`), and a fourth `APIError` arm on the single `Worksheet.update` write call for the Viewer-not-Editor case
- `cli.py`: `run_collect()` resolves the Sheets config and calls `sheets.sync()` on its own `create=False` connection after the collector's rows and `runs` row are committed, wraps that in a try that logs at ERROR and re-raises, and gains one additive docstring line for the new exit path — the diff is additions-only, verified structurally
- `tests/test_sheets.py`: 7 new fixture cases — unshared Sheet, Viewer-only share (caught at write), unknown/deleted spreadsheet id, key file absent, key file malformed, transient 500 at open, transient 429 at write, plus `run_collect()`'s re-raise with `failure_count` proven untouched
- 3 pre-existing tests in `test_config.py`/`test_paths.py` updated with the now-required Sheets env vars and a stubbed `sheets.sync`, since `run_collect()` gained an unconditional new dependency they never anticipated

## Task Commits

1. **Task 1: Name the Sheets failures — SheetNotShared preflight and the key-file guard (D-08, SHEET-07)** - `f8dbc45` (feat, tdd)
2. **Task 2: The second entry point, and the failure policy (D-06, D-07, SHEET-06)** - `aac61c6` (feat, tdd)
3. **Fix: write-time 403 arm names client_email too** - `96f2b29` (fix — found while writing Task 3's case 2)
4. **Task 3: One fixture case per failure branch, and the four-command gate** - `a052546` (test)

**Plan metadata:** this commit (docs: complete 04-03)

## Files Created/Modified
- `src/creatorpulse/sheets.py` - `SheetNotShared`, `SheetsKeyfileUnusable`, `_client_email_from_keyfile`, the `open_by_key` preflight (3 ordered except arms), the write-call's 403 arm
- `src/creatorpulse/cli.py` - `run_collect()` calls `sheets.sync()` after the collector commits, log-then-reraise on failure, one additive docstring line
- `tests/test_sheets.py` - 7 new failure-branch cases plus `_write_keyfile`/`_api_error` helpers
- `tests/test_config.py`, `tests/test_paths.py` - 3 existing `run_collect()` callers given the Sheets env vars + a stubbed `sheets.sync`

## Decisions Made
- **Missing Sheets config in `run_collect()`:** treated as a sync failure (raises `SheetsKeyfileUnusable`, caught by the same ERROR-log-then-reraise arm) rather than silently skipping the sync. The plan's `<behavior>` section only described "Sheets sync raises" and "healthy Sheet" — it didn't name this branch — but `resolve_sheets_config()` returning `Optional` forces *some* handling under mypy strict, and skipping silently would recreate exactly the "quietly stale Dashboard" failure mode D-07/PITFALLS.md §18(d) exist to eliminate. In production this branch is dead code (env vars are confirmed set both locally and on the droplet).
- **Write-time 403 message also names `client_email`** (fix commit `96f2b29`): the initial Task 1 implementation of the Viewer-only arm named "Editor" but not the address to share with, which directly violates a must_haves truth ("the message still names client_email and Editor"). Caught while writing Task 3's case 2 and fixed before Task 3 ran.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Write-time 403 arm didn't name client_email**
- **Found during:** Task 3 (writing the Viewer-only-share fixture case)
- **Issue:** `sync()`'s write-call except arm raised `SheetNotShared` naming "Editor" but never the service-account address, contradicting the plan's own must_haves truth for the Viewer case.
- **Fix:** Added the same `_client_email_from_keyfile` lookup already used in the open-time arm.
- **Files modified:** `src/creatorpulse/sheets.py`
- **Verification:** `test_viewer_only_share_raises_at_write_naming_client_email_and_editor` asserts both the fake email and "Editor" are present.
- **Committed in:** `96f2b29`

**2. [Rule 3 - Blocking] 3 pre-existing `run_collect()` callers broke on the new Sheets dependency**
- **Found during:** Task 3's full-suite `pytest` run
- **Issue:** `test_run_collect_fourth_creator_needs_no_code_change`, `test_run_collect_returns_zero_when_a_source_failed_but_the_run_completed` (both `test_config.py`), and `test_run_collect_logs_both_resolved_paths` (`test_paths.py`) call `run_collect()` directly without setting `CREATORPULSE_SHEET_ID`/`CREATORPULSE_SHEETS_KEYFILE`. Task 2's change makes `run_collect()` unconditionally attempt a Sheets sync, so these pre-existing tests started raising `SheetsKeyfileUnusable` instead of returning 0.
- **Fix:** Added `monkeypatch.setenv` for both env vars and `monkeypatch.setattr("creatorpulse.cli.sheets.sync", lambda *a, **kw: 0)` to stub the sync as a no-op in all three tests. No existing assertion was changed — these tests validate collector/path-resolution behavior, not Sheets, and now provide the fixture the function requires.
- **Files modified:** `tests/test_config.py`, `tests/test_paths.py` (not in the plan's `files_modified` list)
- **Verification:** Full `pytest` suite green (93 passed) after the fix.
- **Committed in:** `a052546` (same commit as Task 3's own test additions)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both were necessary for the plan's own must_haves truths and for the whole-suite green gate. No scope creep — Rule 1/Rule 3 fixes only.

## Issues Encountered

None beyond the two deviations above. The pre-existing `.planning/phases/04-playwright-sheets/04-PATTERNS.md` `ruff format --check` failure (documented in 04-01's and 04-02's SUMMARYs, a planning doc unrelated to any task's `files_modified`) is still present and still out of scope; `ruff format --check` on every file this plan touched passes clean.

## User Setup Required

None new. Same two env vars 04-01 already established; this plan only makes their absence loud instead of silent.

## Next Phase Readiness

- SHEET-06 and SHEET-07 are code-complete: both entry points sync the Dashboard, and every named failure shape (`PermissionError`, Viewer-only 403, `SpreadsheetNotFound`, missing/malformed key file, transient 5xx/429) is covered by a fixture test.
- `04-04`'s `04-UAT.md` is what actually closes SHEET-07 (per this plan's own `<planner_assumptions>` flag) — the real-Sheet un-share/Viewer/Editor sequence against the droplet, pasting the actual `SheetNotShared` text. This plan's automated checks establish the code is correct; they cannot substitute for that human proof.
- `deploy/creatorpulse.service` and `deploy/creatorpulse.timer` are untouched (verified via `git diff --name-only HEAD -- deploy/` returning 0 after every task).
- This is the last plan in Phase 4 — the phase now proceeds to verification.

---
*Phase: 04-playwright-sheets*
*Completed: 2026-08-06*
