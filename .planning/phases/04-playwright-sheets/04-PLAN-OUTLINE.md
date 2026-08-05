# Phase 4: Playwright & Sheets — Plan Outline

**Drafted:** 2026-08-05
**Scope:** Sheets only. SRC-03 (TikTok/Playwright) and SHEET-04 (History tab) are CUT per
ROADMAP.md §"Cut Order" items 2 and 3. Six requirements, four plans.

| Plan ID | Objective | Wave | Depends On | Requirements |
|---------|-----------|------|------------|--------------|
| `04-01` | **Tracer — one path, DB to real Sheet.** Extend `config.py` with `CREATORPULSE_SHEET_ID` / `CREATORPULSE_SHEETS_KEYFILE` (D-09, empty-string-unset idiom, plus `.env.example`); create `src/creatorpulse/sheets.py` with the frozen seven-column layout (D-03) and one batched `worksheet.update("A1:F{n+1}", …, value_input_option="USER_ENTERED")` (D-04, never `.clear()`, column G never in range); implement `creatorpulse sync` reading the DB with `connect(create=False)` (D-06 standalone half, built first per CONTEXT §Specifics). Delta column E emits `—` placeholder only — real delta lands in `04-02`. Carries the `checkpoint:decision` for D-03. | 1 | — | SHEET-01, SHEET-02, SHEET-05, SHEET-06 |
| `04-02` | **Delta + NULL semantics, fixture-tested.** Strict day-over-day on `views` (`metric_date - 1 day` exactly, D-05); both rows present *and* both `views` non-NULL or the cell reads `—`; no `COALESCE` anywhere (CLAUDE.md NULL-vs-0 rule); query uses `idx_metrics_creator_date`. Create `tests/test_sheets.py`: pure `build_dashboard_rows` tests against in-memory SQLite seeded via `db.upsert_metric`, gspread worksheet injected as `Mock(spec=…)` — no network reachable from `pytest`. Includes a test asserting the write range never names column G (SHEET-06 proved structurally). | 2 | `04-01` | SHEET-01, SHEET-02, SHEET-03, SHEET-06 |
| `04-03` | **Failure paths + second entry point.** `SheetNotShared` preflight wrapping `open_by_key` on the real daily path, catching `APIError`/`SpreadsheetNotFound` and re-raising with `client_email` read from the service-account JSON in the message (D-08, SHEET-07). D-07 failure policy: log then re-raise so the process exits non-zero and `failure_count` is untouched. Attach the sync call at the end of `run_collect()` after `collect_once` returns (D-06 second half) — `collect`'s name, flags, and log shape unchanged; `deploy/*.service` and `*.timer` never touched (Phase 2 D-12). Fixture tests for both failure branches. | 3 | `04-02` | SHEET-06, SHEET-07 |
| `04-04` | **Phase artifacts.** `COVERAGE.md` — Google Sheets API v4 capability matrix in the house style of `03-collector-core-api-sources/COVERAGE.md`, recording what gspread 6.2.1 exposes, what this phase uses, and what it deliberately does not (no `append_rows`, no `.clear()`, no `google-api-python-client`). `04-UAT.md` scaffold following the `02-UAT.md` / `03-UAT.md` pattern: pasted-command-output-per-criterion, criteria renumbered to the four that survive the cuts, plus the PITFALLS §5 right-alignment eye-check and the type-into-Status re-run proof. No source files touched. | 2 | `04-01` | SHEET-01, SHEET-02, SHEET-03, SHEET-05, SHEET-06, SHEET-07 |

## Ownership notes

`COVERAGE.md` and the `04-UAT.md` scaffold are both owned by **`04-04`**, which touches no source
file and therefore runs in wave 2 in parallel with `04-02` (its only dependency on `04-01` is that
the column layout must be frozen before the UAT criteria can name it). The `checkpoint:decision`
for **D-03** — the one-way seven-column layout with Status in G, a published contract with
human-built Apps Script this repo cannot refactor — sits in **`04-01`**, immediately before the
column-layout task, making `04-01` non-autonomous. D-02's costly rating (one row per
creator-source pair) is flagged in the same checkpoint's context rather than gated separately.

All four plans are sequential on `src/creatorpulse/sheets.py` except `04-04`, which is why waves
run 1 → 2 (×2) → 3 rather than fanning wider.
