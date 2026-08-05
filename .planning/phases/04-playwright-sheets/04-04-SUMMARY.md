---
phase: 04-playwright-sheets
plan: 04
subsystem: docs
tags: [gspread, coverage-matrix, uat-scaffold, google-sheets]

requires:
  - phase: 04-playwright-sheets
    provides: "04-01's live-verified Dashboard write path and 04-02's day-over-day delta, both cited as evidence sources in the UAT scaffold"
provides:
  - "COVERAGE.md — the Google Sheets API v4 / gspread 6.2.1 subtraction record: 7 INTEGRATE, 27 OPT-OUT, gate-verified"
  - "04-UAT.md — the four surviving Phase 4 ROADMAP criteria as pending human-verification entries with close-later commands"
affects: [phase-4-seal, phase-7-uat-closeout]

tech-stack:
  added: []
  patterns:
    - "Coverage matrix as single-header markdown table, parsed and validated by the api-coverage gate rather than eyeballed"
    - "UAT scaffold pattern from 02-UAT.md/03-UAT.md: pasted-command evidence, no screenshots, one shared blocker named once rather than per entry"

key-files:
  created:
    - .planning/phases/04-playwright-sheets/COVERAGE.md
    - .planning/phases/04-playwright-sheets/04-UAT.md
  modified: []

key-decisions:
  - "COVERAGE.md's PermissionError/APIError/SpreadsheetNotFound INTEGRATE row initially exceeded the 80-char capability cap by 1 char (gate caught it); shortened by dropping backtick wrapping around the exception names, no meaning lost"
  - "04-UAT.md's shared blocker text notes (without contradicting the PENDING status) that STATE.md's decision log records the underlying service-account/Sheet groundwork as already done in a prior session — the scaffold still ships all four entries pending, per the plan's explicit instruction, so the checklist stays usable in one sitting rather than assumed closed by this executor"

patterns-established:
  - "Coverage matrix authored against the gate's own parser rules (single header row, <=80/<=200 char cells, no pipes/newlines) and re-run through the gate before commit, not just visually inspected"

requirements-completed: [SHEET-01, SHEET-02, SHEET-03, SHEET-05, SHEET-06, SHEET-07]

coverage:
  - id: D1
    description: "COVERAGE.md enumerates the Google Sheets API v4 surface reachable through gspread 6.2.1: one markdown table, 7 INTEGRATE rows, 27 OPT-OUT rows, every OPT-OUT citing a written decision (D-NN, ROADMAP Cut Order, PITFALLS §N, STACK §6, REQUIREMENTS Out of Scope, or CLAUDE.md)"
    verification:
      - kind: other
        ref: "node gsd-core/bin/gsd-tools.cjs check api-coverage-verify-pre .planning/phases/04-playwright-sheets --raw"
        status: pass
    human_judgment: false
  - id: D2
    description: "04-UAT.md exists with exactly four ### N. entries carrying ROADMAP's own criterion wording, entry 1 with the PITFALLS §5 right-alignment eye-check, entry 2 naming mkbhd, entry 4 naming client_email and the PermissionError-first correction; all four result: pending with a shared blocker and close-later commands"
    verification:
      - kind: other
        ref: "awk '/^## Tests/{f=1;next} /^## /{f=0} f&&/^### [0-9]+\\./{n++} END{exit !(n==4)}' .planning/phases/04-playwright-sheets/04-UAT.md"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-08-06
status: complete
---

# Phase 4 Plan 4: Coverage Matrix and UAT Scaffold Summary

**Two documents, zero code: a Google Sheets API v4 subtraction record (7 INTEGRATE vs 27 OPT-OUT, every opt-out cited to a written decision) and a four-entry `04-UAT.md` scaffold, both gate-verified, so Phase 4 has its coverage accounting and its human-verification checklist ready before seal.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2 (both `type="auto"`)
- **Files modified:** 2 (both new — `COVERAGE.md`, `04-UAT.md`)

## Accomplishments
- `COVERAGE.md` — the Google Sheets API v4 / gspread 6.2.1 capability matrix, scoped to a daily one-way DB-to-Sheet view sync. `node gsd-core/bin/gsd-tools.cjs check api-coverage-verify-pre` reports `"passed": true`, `"error_count": 0`, `counts: {surface: 34, integrate: 7, optout: 27}`.
- Every `OPT-OUT` row cites a specific written decision: `append_rows` → SHEET-04 cut (ROADMAP §Cut Order item 3); `Worksheet.clear`/`batch_clear` → PITFALLS §6, D-04; any write reaching column G → D-03; `google-api-python-client` → STACK §6; the four Drive-scoped rows (`open`, `create`, `openall`, `share`) → D-09's narrowed `auth/spreadsheets` scope.
- `04-UAT.md` — four `### N.` entries matching ROADMAP's own Phase 4 criteria wording exactly, all `result: pending` behind one named shared blocker (no service account/spreadsheet access from this executor's vantage). Entry 1 carries the PITFALLS §5 right-alignment eye-check as an explicit sub-check; entry 2 names `mkbhd` as the live `—`-delta instance; entry 4 names `client_email` and the D-08 verified `PermissionError`-first correction.
- Both documents contain zero private-key material and no filled-in `CREATORPULSE_SHEET_ID=`/`CREATORPULSE_SHEETS_KEYFILE=` credential lines — verified by grep, not just by intent.

## Task Commits

1. **Task 1: Write COVERAGE.md — the Google Sheets API v4 subtraction record** - `0a89b97` (docs)
2. **Task 2: Write the 04-UAT.md scaffold — four pending criteria with their close-later commands** - `be5ab42` (docs)

**Plan metadata:** this commit (docs: complete 04-04)

## Files Created/Modified
- `.planning/phases/04-playwright-sheets/COVERAGE.md` - Google Sheets API v4 capability matrix: 7 INTEGRATE, 27 OPT-OUT, one `| capability | decision | reason |` table, a consequences bullet list, dated closing line
- `.planning/phases/04-playwright-sheets/04-UAT.md` - four pending UAT entries (frontmatter, `## Current Test`, `## Tests`, `## Summary`, `## Gaps`) matching ROADMAP's Phase 4 criteria 1–4

## Decisions Made
- Shortened the INTEGRATE row naming the preflight's exception surface (`PermissionError` / `APIError` / `SpreadsheetNotFound`) after the gate flagged it at 81 chars against an 80-char cap — dropped the wrapping backticks around the exception names rather than the content, no decision lost.
- Kept all four UAT entries `result: pending` as the plan directed, even though `STATE.md`'s decision log and `04-01-SUMMARY.md` record the underlying Google Cloud project, service account, and Sheet-sharing groundwork as already done in a prior session. The scaffold's `blocked_reason` names this explicitly rather than silently closing entries this executor cannot itself observe — the next session running the pasted commands closes all four in one sitting.

## Deviations from Plan

None — plan executed exactly as written. The one gate failure (capability cell 1 char over 80) was caught by the plan's own `<verify>` step and fixed inline before the first commit, per the plan's own iterate-until-green expectation; no Rule 1-4 deviation was needed since it was a self-authored typo in this same task, not a discovered pre-existing issue.

## Issues Encountered

None beyond the one gate-caught, self-fixed character-count overage noted above.

## User Setup Required

None. This plan touches no source file, dependency manifest, or credential.

## Next Phase Readiness

- `COVERAGE.md` and `04-UAT.md` are both in place for Phase 4's seal gate; the `api-coverage.verify-pre` check is green.
- `04-UAT.md`'s four pending entries and shared blocker give `04-03` (and whoever next has droplet/service-account access) a ready checklist — running the pasted commands closes all four in one sitting once access exists, including entry 4 once `04-03`'s `SheetNotShared` preflight has executed.
- No source file, test file, or dependency manifest was touched — `git status --porcelain src/ tests/ pyproject.toml` was empty throughout.

---
*Phase: 04-playwright-sheets*
*Completed: 2026-08-06*

## Self-Check: PASSED
- FOUND: .planning/phases/04-playwright-sheets/COVERAGE.md
- FOUND: .planning/phases/04-playwright-sheets/04-UAT.md
- FOUND: .planning/phases/04-playwright-sheets/04-04-SUMMARY.md
- FOUND commit: 0a89b97 (Task 1: COVERAGE.md)
- FOUND commit: be5ab42 (Task 2: 04-UAT.md)
