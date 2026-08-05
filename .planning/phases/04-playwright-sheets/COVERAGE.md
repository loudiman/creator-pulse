# API Coverage — Phase 4 (Google Sheets API v4, via gspread 6.2.1)

`INTEGRATE` is the default. This file is the **subtraction record**: every `OPT-OUT` carries a
one-line reason, cited to a written decision. The `INTEGRATE` rows are the small minority — the
value of this file is in the reasoned remainder, not in the inventory of what got built.

**Scope of the capability surface:** what could plausibly serve *this project's stated purpose* —
a daily, one-way, DB-to-Sheet view sync into a single Dashboard tab with one human-owned column —
not the entire Google Sheets / Drive catalogue gspread can reach. Drive-scoped capabilities are
enumerated anyway, because the deliberately narrowed OAuth scope that walls them off is itself a
load-bearing project decision (D-09).

Citations: `04-CONTEXT.md` decisions (D-NN), `ROADMAP.md` §"Cut Order", `REQUIREMENTS.md` §"Out of
Scope" (OOS), `.planning/research/STACK.md` §6 (STACK), `.planning/research/PITFALLS.md` §3–§6
(PITFALLS), `.claude/CLAUDE.md` (the three human-built areas).

**Format contract:** exactly ONE `| capability | decision | reason |` table in this file. A second
table's header row is parsed as a data row by the `api-coverage` gate and fails it with
`decision "DECISION" not in {INTEGRATE, OPT-OUT}`. Capability ≤ 80 chars, reason ≤ 200 chars,
neither containing a literal pipe or newline.

| capability | decision | reason |
|---|---|---|
| `gspread.service_account(filename=...)` | INTEGRATE | gspread's own auth path; `google-auth` arrives transitively, no separate install (D-09, STACK §6). |
| OAuth scope `auth/spreadsheets` | INTEGRATE | Deliberately narrowed from the Drive-bearing default — Sheets access only, no file discovery or creation (D-09). |
| `client.open_by_key(sheet_id)` | INTEGRATE | The SHEET-07 preflight call site. Verified non-lazy — `Spreadsheet.__init__` calls `fetch_sheet_metadata()` (D-08). |
| `Spreadsheet.worksheet(title)` | INTEGRATE | Opens the frozen `Dashboard` tab by its frozen name (D-03). |
| `Worksheet.update(range, values, value_input_option=...)` | INTEGRATE | The one batched write per run, range literal `A1:F{n+1}` (D-04, SHEET-05). |
| `gspread.utils.ValueInputOption.user_entered` | INTEGRATE | Columns D/E/F must land as real numbers and a real timestamp, not text (PITFALLS §5, D-04). |
| PermissionError (primary), APIError / SpreadsheetNotFound (secondary) | INTEGRATE | The verified preflight exception surface — an unshared Sheet raises a bare `PermissionError` first (D-08 CORRECTION, SHEET-07). |
| `Worksheet.append_row` / `Worksheet.append_rows` | OPT-OUT | SHEET-04 (History tab) was cut — ROADMAP.md §Cut Order item 3. An explicit reasoned subtraction, not an oversight; the append-only design is recorded in `04-CONTEXT.md` §Deferred Ideas if it returns. |
| `Worksheet.clear` / `Worksheet.batch_clear` | OPT-OUT | Would clobber the human-owned Status column in G — correctness, not preference (PITFALLS §6, D-04). |
| `Worksheet.update_cell` / `Worksheet.update_acell` | OPT-OUT | Cell-by-cell looks fine at four rows and breaks in front of the interviewer (PITFALLS §4, SHEET-05). |
| `Worksheet.batch_update` with multiple ranges | OPT-OUT | One contiguous range needs exactly one call, not several (D-04). |
| any write whose range reaches column G | OPT-OUT | Status is human-owned, never written, never read — SHEET-06 is satisfied structurally by the range ending at F (D-03). |
| `Worksheet.get_all_values` | OPT-OUT | The database is the source of truth; the Sheet is a disposable view — reading it back would invert that rule (OOS: "Sheet cells as a second source of truth"). |
| `Worksheet.get_all_records` | OPT-OUT | Same inversion as `get_all_values` — no read-back path exists (OOS). |
| `Worksheet.get` / `Worksheet.batch_get` | OPT-OUT | Same inversion — nothing in `sheets.py` ever reads the Sheet it writes (OOS, D-01). |
| `value_render_option` | OPT-OUT | Only meaningful on a read path this project does not have (OOS). |
| `add_worksheet` / `del_worksheet` / `duplicate` | OPT-OUT | Dashboard is the only tab; the History tab that would have used this was cut (SHEET-04, ROADMAP §Cut Order item 3). |
| `insert_cols` / `delete_columns` / `resize` | OPT-OUT | D-03 freezes the seven-column set for v1 — inserting a column shifts Status out from under Phase 5's `e.range.getColumn()` check. |
| `Worksheet.format` | OPT-OUT | Formatting is Phase 5's job; `.claude/CLAUDE.md` forbids this agent from writing any part of the Apps Script layer. |
| `freeze` (rows/columns) | OPT-OUT | Presentation, owned by Phase 5's human-built Apps Script, not this phase. |
| `set_basic_filter` | OPT-OUT | Presentation, owned by Phase 5. |
| `sort` | OPT-OUT | Presentation, owned by Phase 5 — sorting server-side would also fight the DB's own ordering (D-01). |
| conditional-formatting requests via `Spreadsheet.batch_update` | OPT-OUT | Phase 5's `onEdit`/conditional-format rules key on column E's numeric values; writing formatting rules is Apps Script territory (CLAUDE.md). |
| `insert_note` | OPT-OUT | Presentation, owned by Phase 5. |
| tab colour and `Worksheet.hide` | OPT-OUT | Presentation, owned by Phase 5. |
| `client.open(title)` | OPT-OUT | Title-based lookup needs Drive scope; the OAuth scope is deliberately narrowed to `auth/spreadsheets` only (D-09). |
| `client.create(title)` | OPT-OUT | Sheet creation needs Drive scope, deliberately excluded (D-09). The Sheet already exists and is opened by key. |
| `client.openall` / `list_spreadsheet_files` | OPT-OUT | Discovery across Drive needs Drive scope, deliberately excluded (D-09). |
| `Spreadsheet.share` | OPT-OUT | Sharing is the human step SHEET-07's error message asks for — the code names the `client_email`, the human clicks Share (D-08, D-09). |
| `gspread.oauth()` end-user flow | OPT-OUT | An unattended 08:00 timer job has no browser and no consent screen to complete (D-09, RUN-03). |
| `gspread.client.BackOffHTTPClient` | OPT-OUT | A Sheets failure logs and re-raises so the unit shows failed and the next day's timer is the retry; a silent backoff would hide the stale-Sheet failure mode (D-07, PITFALLS §18(d)). |
| `google-api-python-client` | OPT-OUT | Redundant beside gspread, which already wraps the same REST API using `google-auth` (STACK §6). |
| Drive change notifications / watch channels | OPT-OUT | A one-shot daily batch has no listener process to receive a push notification (RUN-03). |
| Apps Script API (`script.googleapis.com`) | OPT-OUT | The entire Apps Script layer is human-built; `.claude/CLAUDE.md` forbids the agent from generating or driving it. |

---

## Consequences recorded here so they are not rediscovered

- **Column G is absent from every write range by construction, not by care.** The range literal is
  `A1:F{n+1}`; there is no code path that can widen it without a deliberate edit (D-03, D-04).
- **Column A holds `creator_id`, not a display name**, because the database has no display-name
  column (D-01). A Status-column misalignment is therefore visible to the naked eye rather than
  silent.
- **The Sheet is never read**, so nothing typed into it — including a hostile or malformed value in
  column G — can ever flow back into the database (D-01). This is also why SHEET-06's proof is a
  ten-second retype-and-resync rather than a query.
- **A `—` in column E is a deliberate non-numeric value in an otherwise numeric column** (D-05).
  Phase 5's conditional-format rules skip it on purpose; it is not a formatting bug to fix later.

*Written: 2026-08-06 during Phase 4 execution (`04-04`). Re-check if a new capability is integrated.*
