---
phase: 04-playwright-sheets
plan: 01
subsystem: sheets-sync
tags: [gspread, sqlite, google-sheets, tracer]

requires:
  - phase: 03-collector-core-api-sources
    provides: metrics table with UNIQUE(creator_id, source, metric_date), idx_metrics_creator_date
provides:
  - creatorpulse.sheets module (HEADERS, LATEST_ROWS_SQL, fetch_latest_rows, build_dashboard_rows, _open_worksheet, sync)
  - config.resolve_sheets_config() (D-09 two-env-var contract)
  - cli.run_sync() and the sync subcommand, wired end to end
  - live Dashboard tab proven with real writes (SHEET-06)
affects: [04-02, 04-03, 04-04, phase-5-apps-script]

tech-stack:
  added: []
  patterns:
    - "sheets.py takes only a connection + two config values as input; never imports config/collector/sources (Internal Boundaries)"
    - "single batched Worksheet.update per sync, range literal 'A1:F{n}', USER_ENTERED, never .clear()"
    - "NULL followers/views render as empty string, never coalesced to 0"

key-files:
  created:
    - src/creatorpulse/sheets.py
    - tests/test_sheets.py
  modified:
    - src/creatorpulse/config.py
    - src/creatorpulse/cli.py
    - .env.example

key-decisions:
  - "Task 1 checkpoint resolved option-a: D-02/D-03 shipped as written, no code changes (confirmation gate only)"
  - "Task 2 human-check resolved verified: live Sheet confirmed header row, right-aligned Views column, G2 marker survives sync"
  - "Synthetic seed rows (kaicenat, pokimane, xqc, YouTube only) and the G2 'reviewing 2026-08-06' marker deliberately left in the live Sheet as proof, not cleared, per author instruction"

patterns-established:
  - "Tracer task proves the whole Sheets architecture (column layout, batched write, range boundary) against a live Sheet before any expansion plan touches it"

requirements-completed: [SHEET-01, SHEET-02, SHEET-05, SHEET-06]

coverage:
  - id: D1
    description: "creatorpulse sync reads latest (creator, source) snapshot rows from metrics and writes one header + N data rows to the Dashboard tab in a single batched update"
    requirement: SHEET-01
    verification:
      - kind: unit
        ref: "tests/test_sheets.py — end-to-end sync test (update called once, header row, 6-wide rows, latest-date-wins)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Column C header reads 'Followers (coarse)'; NULL followers/views render blank, 0 renders as 0, never merged"
    requirement: SHEET-02
    verification:
      - kind: unit
        ref: "tests/test_sheets.py -k null"
        status: pass
    human_judgment: false
  - id: D3
    description: "Exactly one Worksheet.update call per sync, no per-cell writes, USER_ENTERED value input"
    requirement: SHEET-05
    verification:
      - kind: unit
        ref: "tests/test_sheets.py — ws.update.call_count == 1 assertion"
        status: pass
    human_judgment: false
  - id: D4
    description: "Write range is literal A1:F{n}, tab never cleared, human-owned column G survives a real sync run against the live Sheet"
    requirement: SHEET-06
    verification:
      - kind: unit
        ref: "tests/test_sheets.py — range string and .clear()-never assertions"
        status: pass
      - kind: manual_procedural
        ref: "Live Sheet check 2026-08-06: header row A1:F1 correct, column D right-aligned, G2 marker 'reviewing 2026-08-06' survived a creatorpulse sync run"
        status: pass
    human_judgment: true
    rationale: "Column rendering (alignment) and cross-run cell survival can only be confirmed by a human looking at the actual Google Sheet UI — not observable from a mock in the test suite."

duration: (execution work done in prior session; this closeout session ~15min)
completed: 2026-08-06
status: complete
---

# Phase 4 Plan 1: Tracer — Two Env Vars to a Real Dashboard Write Summary

**`creatorpulse sync` reads latest per-(creator, source) metric rows from SQLite and writes them via one batched, USER_ENTERED `Worksheet.update` to a live Google Sheet's Dashboard tab, proven against the real Sheet — not just a mock.**

## Performance

- **Tasks:** 2 (Task 1 checkpoint:decision, Task 2 tracer)
- **Files modified:** 5 (`src/creatorpulse/config.py`, `src/creatorpulse/sheets.py`, `src/creatorpulse/cli.py`, `.env.example`, `tests/test_sheets.py`)

## Accomplishments
- New `creatorpulse.sheets` module: `HEADERS` (6 cols, D-03 frozen layout), `LATEST_ROWS_SQL` (correlated-subquery latest-snapshot query keyed on `idx_metrics_creator_date`), `fetch_latest_rows`, `build_dashboard_rows` (NULL-safe), `_open_worksheet` (narrowed to the `spreadsheets` scope only, no Drive), `sync` (one batched write, returns data row count)
- `config.resolve_sheets_config()` added alongside unchanged `resolve_paths()`, same empty-string-means-unset treatment, no default (D-09)
- `cli.run_sync()` wired into the `sync` subcommand; resolves sheets config before opening the database, fails loudly (non-zero, names both env vars) when unset, opens with `create=False`
- `.env.example` carries the two new blank vars; superseded Phase 2 `GOOGLE_SERVICE_ACCOUNT_FILE` placeholder removed
- Both plan checkpoints resolved and closed: Task 1's column-layout decision (option-a, no code change) and Task 2's live-Sheet human-check (verified)

## Task Commits

1. **Task 1: Freeze Dashboard column layout** — resolved via checkpoint decision `option-a`; no code commit (confirmation-only gate, D-02/D-03 already written that way)
2. **Task 2: Two env vars to a real Sheet — one path, end to end** - `5f7f86d` (feat, tracer, tdd)

**Plan metadata:** this commit (docs: complete 04-01)

## Files Created/Modified
- `src/creatorpulse/sheets.py` - new module: latest-snapshot query, header/NULL-safe row builder, narrowed-scope worksheet open, single batched sync write
- `src/creatorpulse/config.py` - `resolve_sheets_config()` added, additive only
- `src/creatorpulse/cli.py` - `run_sync()`, `sync` subcommand wired, `create=False` reader path
- `.env.example` - `CREATORPULSE_SHEET_ID=`, `CREATORPULSE_SHEETS_KEYFILE=` added; `GOOGLE_SERVICE_ACCOUNT_FILE` removed
- `tests/test_sheets.py` - end-to-end sync test (mocked worksheet) + NULL-vs-zero test

## Decisions Made
- Task 1 checkpoint: option-a — ship D-02 (one row per creator/source pair) and D-03 (7-column frozen layout, Status at G) exactly as already decided in `04-CONTEXT.md`. No code changes required; this was a confirmation gate on a one-way door before Task 2 wrote to a live Sheet.
- Task 2 human-check: verified against the real Sheet (https://docs.google.com/spreadsheets/d/1hP7rZqq9Z-QnYGCkt8uhNK1yiwF3dsM9e-T2sYQOqQI/edit) — header row correct, column D (`Views`) right-aligned confirming real numbers not text, column E's `—` placeholder left-aligned as expected, G2's `"reviewing 2026-08-06"` marker survived a `creatorpulse sync` run, proving SHEET-06 live.
- Author's explicit instruction: leave the 3 synthetic seed rows (kaicenat, pokimane, xqc — YouTube only) and the G2 marker in the Sheet as living proof. **These are not real collected metrics** — Phase 3's droplet UAT (still PARTIAL, see STATE.md Blockers) is what gates real numbers reaching this Dashboard. 04-02's executor should expect non-empty rows already present and not re-derive their origin.

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria gates (grep-based structural checks, `pytest tests/test_sheets.py -x`, the null-case test, the config/cli wiring checks) re-verified in this closeout session and pass.

## Issues Encountered

Re-running the four green gates during closeout surfaced one pre-existing, out-of-scope failure: `ruff format --check .` flags `.planning/phases/04-playwright-sheets/04-PATTERNS.md` (a planning doc, not touched by this plan's task commits — last touched by the plan-authoring commit `b4f91a8`). This is not part of `04-01`'s `files_modified` set and not a regression from Task 2's work; `ruff check .`, `mypy src/`, and `pytest` (67 passed) all pass clean. Left unfixed per this closeout's directed scope (docs/tracking only); flagging here rather than silently ignoring.

## User Setup Required

None new beyond what Task 1's `user_setup` block already required — the Google Cloud project, service account, spreadsheet, and droplet env file were already provisioned and verified in the prior session (see STATE.md decisions log, 2026-08-05 entries).

## Next Phase Readiness

- 04-02 (strict day-over-day delta on views) can build directly on `build_dashboard_rows`'s column-E placeholder and the existing test file.
- 04-03 (SheetNotShared / client_email preflight, D-07 log-then-re-raise, `run_collect` attachment) has its call sites already in place (`_open_worksheet`'s two adjacent calls, `sync`'s uncaught propagation).
- Live Sheet currently holds synthetic seed data only — not a blocker, but 04-04's `04-UAT.md` should record this distinction alongside Phase 3's still-PARTIAL real-data status.

---
*Phase: 04-playwright-sheets*
*Completed: 2026-08-06*
