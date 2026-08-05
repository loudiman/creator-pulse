---
phase: 04-playwright-sheets
plan: 02
subsystem: sheets-sync
tags: [sqlite, gspread, date-arithmetic, tdd]

requires:
  - phase: 04-playwright-sheets
    provides: "04-01's sheets.py module (HEADERS, LATEST_ROWS_SQL, LatestRow, fetch_latest_rows, build_dashboard_rows, sync) and its live-verified Dashboard write path"
provides:
  - "LATEST_ROWS_SQL extended with a left join to metrics AS prev on date(m.metric_date, '-1 day'), keyed on idx_metrics_creator_date"
  - "LatestRow widened to a 6-tuple carrying the baseline views"
  - "build_dashboard_rows computes column E as views - prev_views when both are non-NULL, DELTA_PLACEHOLDER otherwise"
  - "17 new fixture cases in tests/test_sheets.py pinning the baseline resolution and the delta matrix to specific values"
affects: [04-03, 04-04, phase-5-apps-script]

tech-stack:
  added: []
  patterns:
    - "SQLite date(col, '-1 day') for exact-previous-day baseline joins, never Python string-slicing on ISO dates"
    - "is None guards on both operands of a nullable subtraction, never a truthiness fallback (NULL-vs-0 rule)"

key-files:
  created: []
  modified:
    - src/creatorpulse/sheets.py
    - tests/test_sheets.py

key-decisions:
  - "The plan anticipated one 04-01 assertion pinning column E to DELTA_PLACEHOLDER that would need amending to a real number. No such assertion exists in tests/test_sheets.py as written by 04-01 -- confirmed via grep for DELTA_PLACEHOLDER before starting, zero hits. No line was amended or deleted; this is recorded per the plan's own instruction to quote any deleted/amended line verbatim, and here there is none."
  - "build_dashboard_rows' loop unpack widened to 6 names in Task 1's commit (as _prev_views, unused) so the full pytest suite stayed green between Task 1 and Task 2, then renamed to prev_views and wired into the conditional expression in Task 2 -- splits the RED/GREEN cycle per task without breaking the full-suite gate in between."

patterns-established:
  - "Baseline-then-delta pairing: a nullable join column travels through an unused unpack slot for one commit, then gets consumed in the next -- keeps each TDD task's own full-suite gate green without smuggling ahead of its RED case."

requirements-completed: [SHEET-01, SHEET-02, SHEET-03, SHEET-06]

coverage:
  - id: D1
    description: "LATEST_ROWS_SQL left-joins to metrics AS prev on (creator_id, source, date(metric_date, '-1 day')) -- a pair with no baseline row still reaches the Dashboard"
    requirement: SHEET-01
    verification:
      - kind: unit
        ref: "tests/test_sheets.py -k baseline (7 fetch-layer cases: present, absent, gap, month, leap, null-baseline, zero-baseline)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Column E computes views - prev_views as a Python int exactly when both sides are non-NULL; DELTA_PLACEHOLDER otherwise, including zero-vs-null adjacency, negative deltas, and either-side-NULL"
    requirement: SHEET-03
    verification:
      - kind: unit
        ref: "tests/test_sheets.py -k delta (10 cases covering present/absent/gap/month/leap/zero/negative/null-today/null-baseline/zero-vs-null/type)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The single Worksheet.update range never names column G, proven structurally in the suite rather than by source grep alone"
    requirement: SHEET-06
    verification:
      - kind: unit
        ref: "tests/test_sheets.py::test_sync_write_range_never_names_column_g"
        status: pass
    human_judgment: false
  - id: D4
    description: "Column E right-aligned on a live Sheet row with a real delta (PITFALLS.md §5 visual check)"
    verification: []
    human_judgment: true
    rationale: "Cell alignment can only be confirmed by looking at the actual Google Sheet UI, and the live Sheet currently holds only single-date synthetic seed rows (no consecutive-day pair), so the check cannot even run yet -- BLOCKED per the plan's own instruction, not a pass. Requires a human to run creatorpulse sync after two consecutive days of real or seeded rows exist, for 04-04 to paste into 04-UAT.md."

duration: ~35min
completed: 2026-08-06
status: complete
---

# Phase 4 Plan 2: Strict Day-Over-Day Delta on Views Summary

**Column E stops being a placeholder: `LATEST_ROWS_SQL` gains a left join to the exact previous-day row via SQLite's own `date()` function, and `build_dashboard_rows` computes `views - prev_views` as a real int whenever both sides are non-NULL, `—` otherwise -- with 17 new fixture cases pinning every NULL/zero/negative/gap/boundary state to a specific expected value.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2 (both `type="auto" tdd="true"`)
- **Files modified:** 2 (`src/creatorpulse/sheets.py`, `tests/test_sheets.py`)

## Accomplishments
- `LATEST_ROWS_SQL` extended with one `LEFT JOIN metrics AS prev` on `(creator_id, source, date(metric_date, '-1 day'))` -- an index seek against `idx_metrics_creator_date`, not a scan; the existing `MAX(m2.metric_date)` latest-snapshot subquery and `ORDER BY` are untouched
- `LatestRow` widened to a 6-tuple; `fetch_latest_rows`'s body unchanged, only the type it returns widened
- `build_dashboard_rows` column E: `DELTA_PLACEHOLDER if views is None or prev_views is None else views - prev_views` -- one conditional expression, no helper function, no post-processing
- 17 new fixture cases appended to `tests/test_sheets.py`: 7 fetch-layer baseline cases (present, absent-single-row, two-day gap, month boundary, leap day, NULL baseline, zero baseline) and 10 delta-matrix cases (present, absent-row-still-appears, gap-not-widened, month+leap difference, zero-renders-zero, negative-unclamped, NULL-today, NULL-baseline, zero-vs-null adjacency, int-type, range-never-names-G)
- Both tasks followed RED (failing cases against the prior shape) then GREEN (the one-line/one-join fix) as separate commits

## Task Commits

1. **Task 1: The baseline row arrives in the same read** - RED `3940253` (test), GREEN `d6497f9` (feat)
2. **Task 2: One conditional expression, and the seven cases that pin it down** - RED `801e97e` (test), GREEN `4f2fb3e` (feat)

**Plan metadata:** this commit (docs: complete 04-02)

## Files Created/Modified
- `src/creatorpulse/sheets.py` - `LATEST_ROWS_SQL` gains the left join and comment naming `idx_metrics_creator_date`; `LatestRow` widened to 6 slots; `build_dashboard_rows`'s loop unpack and column-E expression updated
- `tests/test_sheets.py` - 17 new bare `def test_x(...)` cases appended, following 04-01's established style (no classes, no conftest, seeded via `db.upsert_metric` with real `MetricRecord` instances, worksheet injected via the existing `_worksheet()`/monkeypatch idiom)

## Decisions Made
- The plan's anticipated "sanctioned amendment" (loosening/changing a 04-01 assertion that pins column E to `DELTA_PLACEHOLDER`) does not apply: grepped `tests/test_sheets.py` for `DELTA_PLACEHOLDER` before starting Task 2 and found zero hits in 04-01's original file. No line was amended or deleted for this reason; recorded here per the plan's instruction to name the amendment even if none was needed.
- Split the `LatestRow` unpack widening across the two tasks' commits: Task 1's GREEN commit renames the loop's fifth-position variable set to accept the new 6th slot as `_prev_views` (unused), keeping the full `pytest` gate green immediately after Task 1 without pre-empting Task 2's behavior. Task 2 then renames it to `prev_views` and wires it into the conditional expression.

## Deviations from Plan

None - plan executed exactly as written. No Rule 1-4 auto-fixes were needed; both tasks' `<action>` sections described the change precisely and it applied cleanly.

## Issues Encountered

Re-running the four-command gate surfaced the same pre-existing, out-of-scope `ruff format --check .` failure 04-01's closeout already documented: `.planning/phases/04-playwright-sheets/04-PATTERNS.md` (a planning doc, not touched by this plan) fails formatting. Not a regression from this plan's task commits -- `ruff format --check src/creatorpulse/sheets.py tests/test_sheets.py` (the two files this plan actually touches) passes clean, and `ruff check .`, `mypy src/`, and `pytest` (85 passed) all pass clean on the full repo.

One acceptance-criterion grep (`round\(|float\(|abs\(|:,\}|%d` returning 0) has a false-positive hit: `logger.info("Wrote %d data rows to %s", ...)` in `sync()` is a pre-existing 04-01 logging line, not delta post-processing. The delta expression itself (`views - prev_views`) contains none of `round`/`float`/`abs`/format-spec/`%d`. Recorded as a criterion-wording gap, not a violation -- the grep pattern is broader than the property it means to test.

## User Setup Required

None new. Same env vars and service-account setup 04-01 already established.

## Next Phase Readiness

- `04-03` (SheetNotShared/`client_email` preflight, D-07 log-then-re-raise, `run_collect` attachment) has its call sites already in place from 04-01 and is unaffected by this plan's changes.
- `04-04`'s `04-UAT.md` should record the Task 2 human-check as **BLOCKED**, not pass: the live Sheet holds only single-date synthetic seed rows (kaicenat, pokimane, xqc), so no pair yet has a real baseline to display, and the right-alignment check cannot run until two consecutive days of rows exist.
- The Dashboard's row set, column count, single batched write, and `A1:F` range boundary are all unchanged and now additionally proven by a suite assertion (`test_sync_write_range_never_names_column_g`) rather than by source grep alone.

---
*Phase: 04-playwright-sheets*
*Completed: 2026-08-06*
