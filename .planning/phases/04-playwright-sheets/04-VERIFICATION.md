---
phase: 04-playwright-sheets
verified: 2026-08-06T02:00:00Z
status: human_needed
score: 2/5 must-haves verified
behavior_unverified: 3
overrides_applied: 0
behavior_unverified_items:
  - truth: "ROADMAP criterion 1 — the author opens the real Google Sheet after a real run and sees one Dashboard row per creator-source pair with the latest snapshot and its day-over-day delta on views, follower figures labelled coarse"
    test: "Run `creatorpulse sync` against a database holding at least two consecutive days of rows, cross-check the Dashboard's A-D/F cells against a `sqlite3` query over `metrics`, and eyeball column E (Δ Views) for right-alignment"
    expected: "Sheet rows match the database cell-for-cell, C1 reads 'Followers (coarse)', and a row with a real computed delta renders right-aligned (proves USER_ENTERED/number, not text)"
    why_human: "The live Sheet currently holds only single-date synthetic rows (kaicenat, pokimane, xqc per 04-02-SUMMARY) — no pair yet has a real two-day delta to display, and rendering/alignment is a Google Sheets UI fact no mock or grep can see. 04-UAT.md entry 1 is `result: pending`."
  - truth: "ROADMAP criterion 2 — a creator with no prior-day row shows `—` for delta, not a number computed against zero, using the live `mkbhd` orphan as the concrete instance"
    test: "Run `creatorpulse sync`, open the Dashboard, read the `mkbhd`/`youtube` row's column E"
    expected: "Column E reads the em-dash marker, not a number and not blank"
    why_human: "Reading one specific rendered cell on a real Sheet is not something a unit test (which only proves the Python array is correct) can substitute for. 04-UAT.md entry 2 is `result: pending`."
  - truth: "ROADMAP criterion 4 — a Sheet not shared with the service account fails with a message naming the exact `client_email` to share it with"
    test: "Point CREATORPULSE_SHEET_ID at a deliberately unshared spreadsheet and run `creatorpulse sync`, or un-share/re-share-as-Viewer/re-share-as-Editor the live Sheet per 04-03's own manual verification step"
    expected: "A named `SheetNotShared` failure containing the real client_email address and the word 'Editor'; the process exits non-zero"
    why_human: "The seven fixture cases in tests/test_sheets.py prove the exception logic against mocked PermissionError/APIError/SpreadsheetNotFound objects — they cannot prove gspread 6.2.1 actually raises those shapes against a real unshared Google Sheet. 04-UAT.md entry 4 is `result: pending`, and 04-03-SUMMARY's own coverage table (D8) marks this human_judgment: true, verification: []."
---

# Phase 4: Playwright & Sheets Verification Report

**Phase Goal:** The ops team gets a Sheet they can actually read
**Verified:** 2026-08-06T02:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Criterion 1: real Sheet shows one row per (creator, source) pair, latest snapshot + day-over-day delta on views, followers labelled coarse | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Code path fully implemented and unit-tested (`fetch_latest_rows`, `build_dashboard_rows`, 29/29 tests in `tests/test_sheets.py` pass). Live Sheet currently holds only single-date synthetic rows (04-02-SUMMARY) — no consecutive-day pair exists yet to exercise a real delta or the right-alignment eye-check. `04-UAT.md` entry 1: `result: pending`. |
| 2 | Criterion 2: a creator (the live `mkbhd` orphan) with no prior-day row shows `—`, never a number computed against zero | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `LEFT JOIN` guarantees the row survives with no baseline (`test_delta_no_baseline_row_puts_the_marker_and_row_still_appears` passes). Live confirmation that the real `mkbhd` row on the real Sheet reads `—` is still outstanding — `04-UAT.md` entry 2: `result: pending`. |
| 3 | ROADMAP criterion 3: the human-edited Status column (G) survives a real sync round-trip | ✓ VERIFIED | Structurally proven (`test_sync_write_range_never_names_column_g`, range literal `A1:F{n+1}`) **and** live-proven: 04-01's own human-check typed a marker into G2 on the real Sheet, ran `creatorpulse sync`, and confirmed the marker survived (04-01-SUMMARY coverage D4, `human_judgment: true`, `status: pass`). |
| 4 | Criterion 4: an unshared Sheet fails with a named `SheetNotShared` error naming the real `client_email` and "Editor" | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `sheets.py` implements the `PermissionError`→`SpreadsheetNotFound`→`APIError(403)` preflight plus a write-time 403 arm; 7 fixture cases in `tests/test_sheets.py` cover every branch against mocks and all pass. Never exercised against a real unshared Google Sheet — `04-UAT.md` entry 4: `result: pending`; `04-03-SUMMARY.md`'s own coverage table (D8) already marks this `human_judgment: true`, `verification: []`. |
| 5 | SHEET-05: exactly one batched `Worksheet.update` call per sync, never per-cell, never `.clear()` | ✓ VERIFIED | `ws.update.call_count == 1` and `ws.clear.assert_not_called()` are asserted and pass in multiple tests (`test_sync_writes_dashboard_once_latest_row_only_ordered`, `test_sync_against_empty_metrics_table_still_writes_header`). This behavior does not depend on a real external Sheet — it is exercised end-to-end against a `Mock(spec=gspread.Worksheet)`, which is sufficient proof for a call-count/argument-shape assertion. |

**Score:** 2/5 truths verified (3 present + wired + unit-tested, behavior against the real Google Sheet not yet exercised)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/creatorpulse/sheets.py` | HEADERS, LATEST_ROWS_SQL, fetch_latest_rows, build_dashboard_rows, _open_worksheet, sync, SheetNotShared, SheetsKeyfileUnusable | ✓ VERIFIED | All symbols present, substantive (191 lines, real SQL/logic, not a stub), and exercised by 29 passing tests |
| `src/creatorpulse/config.py` | `resolve_sheets_config()` alongside unchanged `resolve_paths()` | ✓ VERIFIED | Present, additive, `resolve_paths()` untouched |
| `src/creatorpulse/cli.py` | `run_sync()`, `sync` subcommand, `run_collect()` sync attachment | ✓ VERIFIED | Both entry points present and wired; `cli.py` diff for 04-03 is additions-only (verified structurally in 04-03-SUMMARY and consistent with current file content) |
| `.env.example` | `CREATORPULSE_SHEET_ID=`, `CREATORPULSE_SHEETS_KEYFILE=` blank vars | ✓ VERIFIED (per 04-01-SUMMARY; file access restricted in this session but no test or gate flags it missing) | — |
| `tests/test_sheets.py` | end-to-end + delta + failure-branch test suite | ✓ VERIFIED | 29 tests, all pass, covering happy path, NULL/zero/negative delta matrix, and 7 failure branches |
| `.planning/phases/04-playwright-sheets/COVERAGE.md` | Google Sheets API v4 capability matrix | ✓ VERIFIED | `api-coverage-verify-pre` gate: `passed: true`, `error_count: 0`, 34 capabilities (7 INTEGRATE, 27 OPT-OUT) |
| `.planning/phases/04-playwright-sheets/04-UAT.md` | 4 pending entries matching ROADMAP criteria 1-4 | ✓ VERIFIED (as a scaffold) | Exactly 4 `### N.` entries present, matching ROADMAP wording; all `result: pending` — this is the honest, undischarged state, not a gap in the document itself |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `cli.py` | `sheets.py` | `sheets.sync(...)` calls in both `run_collect` and `run_sync` | ✓ WIRED | Confirmed by direct read of `cli.py` |
| `cli.py` | `config.py` | `resolve_sheets_config()` called before opening anything | ✓ WIRED | Confirmed |
| `cli.py` | `db.py` | `connect(db_path, create=False)` on the sync reader path | ✓ WIRED | Confirmed, used in both entry points |
| `sheets.py` | `idx_metrics_creator_date` | `date(m.metric_date, '-1 day')` join keyed on `(creator_id, metric_date)` | ✓ WIRED | Confirmed in `LATEST_ROWS_SQL` |
| `sheets.py` (`open_by_key`, `update`) | `SheetNotShared` / `SheetsKeyfileUnusable` | ordered except arms, `PermissionError` first | ✓ WIRED | Confirmed by reading the module; arm order verified (`except PermissionError` precedes the two `gspread.exceptions.*` arms) |
| `COVERAGE.md` | `api-coverage-verify-pre` gate | single `| capability | decision | reason |` table | ✓ WIRED | Gate run directly: `passed: true`, `error_count: 0` |
| `04-UAT.md` | ROADMAP §Phase 4 success criteria | `### N.` headings carrying criterion wording | ✓ WIRED | 4 headings confirmed matching ROADMAP text |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `.venv/Scripts/python.exe -m pytest -q` | `93 passed in 1.58s` | ✓ PASS |
| Sheets-specific suite passes | `.venv/Scripts/python.exe -m pytest tests/test_sheets.py -v` | `29 passed` (all named cases: baseline resolution, delta matrix, failure branches, range-never-names-G) | ✓ PASS |
| `ruff check .` | `.venv/Scripts/python.exe -m ruff check .` | `All checks passed!` | ✓ PASS |
| `mypy src/` | `.venv/Scripts/python.exe -m mypy src/` | `Success: no issues found in 10 source files` | ✓ PASS |
| `ruff format --check .` | `.venv/Scripts/python.exe -m ruff format --check .` | `2 files would be reformatted` — both are `.planning/` markdown docs (`04-PATTERNS.md`, `04-REVIEW.md`), not source/test files touched by any of this phase's `files_modified` lists | ⚠️ WARNING (non-blocking, see Anti-Patterns) |
| Coverage gate | `node gsd-core/bin/gsd-tools.cjs check api-coverage-verify-pre .planning/phases/04-playwright-sheets --raw` | `"passed": true, "error_count": 0, counts: {surface:34, integrate:7, optout:27}` | ✓ PASS |
| Live Sheet round-trip (real data) | manual, per ROADMAP "Definition of Green" | Partially done in a prior session (04-01: header/right-alignment/G2-survival); real two-consecutive-day delta and real `SheetNotShared` never exercised | ? SKIP — routed to Human Verification |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|--------------|--------|----------|
| SHEET-01 | 04-01, 04-02, 04-04 | Dashboard shows one row per creator-source pair, latest snapshot + delta | ✓ SATISFIED (code) / pending (live) | Code + tests confirm; live cross-check is UAT entry 1, pending |
| SHEET-02 | 04-01, 04-02, 04-04 | Delta on views; followers/subscribers labelled coarse | ✓ SATISFIED (code) / pending (live) | `Followers (coarse)` header confirmed in `HEADERS`; NULL-vs-0 test passes |
| SHEET-03 | 04-02, 04-04 | No-prior-day row shows `—`, never a number against assumed zero | ✓ SATISFIED (code) / pending (live, mkbhd) | `test_delta_no_baseline_row_puts_the_marker_and_row_still_appears` passes |
| SHEET-04 | — | History tab | CUT 2026-08-05 (ROADMAP §Cut Order item 3, moved to V2-SHEET-01) | Correctly excluded from Phase 4 scope per REQUIREMENTS.md and ROADMAP.md; not a gap |
| SHEET-05 | 04-01, 04-04 | Batched writes, one call per tab per run | ✓ SATISFIED | `call_count == 1`, `.clear()` never called, asserted and passing |
| SHEET-06 | 04-01, 04-02, 04-03, 04-04 | Human-edited Status column survives a sync | ✓ SATISFIED (code + live) | Structural test + live G2-marker proof (04-01) |
| SHEET-07 | 04-03, 04-04 | Unshared Sheet fails naming `client_email`, not a raw 403 | ✓ SATISFIED (code) / pending (live) | 7 fixture cases pass; live proof is UAT entry 4, pending |

No orphaned requirements: the union of `requirements:` across 04-01 through 04-04 is exactly `{SHEET-01, SHEET-02, SHEET-03, SHEET-05, SHEET-06, SHEET-07}`, matching the phase's declared requirement IDs precisely.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.planning/phases/04-playwright-sheets/04-PATTERNS.md` | — | `ruff format --check .` flags this planning doc | ℹ️ Info | Pre-existing since 04-01 (documented in every SUMMARY as out-of-scope); not a source/test file in any plan's `files_modified` |
| `.planning/phases/04-playwright-sheets/04-REVIEW.md` | — | `ruff format --check .` flags this planning doc (a Python code fence inside a markdown code-review report) | ℹ️ Info | New since the code-review pass; same category as above — a planning artifact, not phase-owned source. Neither file affects `ruff check .`, `mypy src/`, or `pytest`, which are the CLAUDE.md-mandated green-gate commands (`ruff format --check` is a plan-level extra, not a CLAUDE.md requirement) |
| `src/creatorpulse/config.py:61-73` | CR-01 (04-REVIEW.md) | Malformed/empty `creators.yaml` crashes with an unhandled `AttributeError`/`yaml.YAMLError` instead of the documented exit code 2 | ℹ️ Info (pre-existing, Phase 3 code, advisory per task's own known_context) | Not introduced by any Phase 4 plan (Phase 4 only added `resolve_sheets_config()` to this file); flagged by code review as advisory, non-blocking per GSD convention. Does not affect any SHEET-* must-have |
| `src/creatorpulse/sheets.py:159` | WR-02 (04-REVIEW.md) | No dedicated handling for `gspread.exceptions.WorksheetNotFound` (missing "Dashboard" tab) — propagates as a raw traceback, uncaught by `cli.py`'s except clause | ℹ️ Info | Real residual gap adjacent to SHEET-07's intent, but not claimed by any plan's must-haves (04-03 scoped exactly to `PermissionError`/`SpreadsheetNotFound`/`APIError(403)`). Worth a follow-up, not a blocker for this phase's stated must-haves |
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK` markers found in any file this phase modified | — | Clean |

## Human Verification Required

### 1. Real Sheet row/value cross-check and the right-alignment eye-check (ROADMAP criterion 1)

**Test:** Seed or wait for two consecutive days of real/seeded rows, run `creatorpulse sync`, cross-check the Dashboard's A-D/F cells against a `sqlite3` query over `metrics`, and look at column E on a row with a real delta.
**Expected:** Every cell matches the database; column E renders right-aligned (a number), confirming `value_input_option=USER_ENTERED` worked, not left-aligned text.
**Why human:** The live Sheet currently holds only single-date synthetic rows — there is no real delta yet to look at, and cell alignment is a rendering fact only visible in the Google Sheets UI.

### 2. The `mkbhd` orphan shows `—` on the real Sheet (ROADMAP criterion 2)

**Test:** After a real sync, open the Dashboard and read the `mkbhd`/`youtube` row's column E.
**Expected:** The em-dash marker, not a number, not blank.
**Why human:** Reading one specific rendered cell on the real Sheet UI is what closes this, not a mock-based unit test.

### 3. `SheetNotShared` against a real unshared Sheet, naming the real `client_email` (ROADMAP criterion 4)

**Test:** Point `CREATORPULSE_SHEET_ID` at a deliberately unshared spreadsheet (or un-share the live one), run `creatorpulse sync`, and paste the failure text verbatim; then re-share as Viewer only and confirm it fails a second time at the write; then re-share as Editor and confirm success.
**Expected:** A named error containing the real service-account `client_email` and the word "Editor"; non-zero exit in the unshared/Viewer cases, exit 0 once shared as Editor.
**Why human:** The unit tests prove the exception-handling *logic* against mocked gspread exception shapes; they cannot prove gspread 6.2.1 actually raises `PermissionError`/`APIError(403)` in these exact real-world shapes against Google's live API. `04-03-SUMMARY.md`'s own coverage table already flags this item as `human_judgment: true`, unverified.

## Gaps Summary

No code, test, or artifact gap was found: every plan's stated must-haves are implemented, wired, and covered by passing automated tests (93/93 full suite, 29/29 `test_sheets.py`), the four-command gate is green on all source/test files this phase touches, and the `COVERAGE.md` gate passes. `SHEET-04` (History tab) and `SRC-03` (TikTok) are correctly and deliberately absent — a documented cut, not an oversight, and not treated as a gap here.

What is genuinely outstanding is the phase's own **Definition of Green manual gate** (ROADMAP.md §"Definition of Green": "a human-observed end-to-end run against real data... reaching the real Google Sheet from Phase 4"). `04-UAT.md` itself — written by this same phase's own 04-04 plan — honestly records all four ROADMAP criteria as `result: pending`, three of which (1, 2, 4) remain unexercised against real Sheet data: no consecutive-day delta exists live yet, the `mkbhd` `—`-cell hasn't been read on the real Sheet, and `SheetNotShared` has never fired against a real unshared spreadsheet. Criterion 3 (Status column survival) is the one exception — it was already exercised live during 04-01 and recorded as passing.

This is not a code defect and not something a re-plan would fix; it is a live-environment verification step that requires droplet/service-account access, exactly as `04-UAT.md`'s own `blocked_reason` states. Per the verification methodology, three unexercised, present-and-wired truths route to `human_needed` rather than `passed` — the honest status given the phase's own manual-gate contract is not yet fully discharged.

---

_Verified: 2026-08-06T02:00:00Z_
_Verifier: Claude (gsd-verifier)_
