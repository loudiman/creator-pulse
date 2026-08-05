# Phase 4: Playwright & Sheets - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning

<domain>
## Phase Boundary

**This phase is Sheets only. Playwright is cut.** The name stays for roadmap continuity; the
content does not match it any more.

Phase 4 delivers one module, `sheets.py`, that turns the SQLite database into a readable Google
Sheet Dashboard. It reads `metrics` through `db.py`, computes the day-over-day view delta in
Python, and writes one batched range per run. The human-typed Status column survives every write
because the write range never reaches it. A Sheet that has not been shared with the service
account fails with the exact `client_email` to share it with.

Two requirements were cut from this phase during discussion, both sanctioned by ROADMAP.md
§"Cut Order":

- **SRC-03 (TikTok / Playwright) — CUT.** Cut-order item 2, exercised. No `sources/tiktok.py`, no
  Playwright dependency exercised, no HTML fixtures, no `robots.txt` runtime check. `creators.yaml`
  keeps its `tiktok` entries and they keep skipping cleanly through Phase 3 D-09's
  known-but-unregistered path — no config edit is needed, and none should be made.
- **SHEET-04 (History tab) — CUT.** Cut-order item 3, exercised. Dashboard only.

Remaining requirements: **SHEET-01, SHEET-02, SHEET-03, SHEET-05, SHEET-06, SHEET-07** — six, down
from eight.

**Not in this phase:** any Apps Script (Phase 5 — this phase's job is to hand it a stable column
layout), any Discord code (Phase 6), any Twitch code (SRC-02, blocked external, plan `03-03` sits
written and unexecuted), the README and the journal (Phase 7).

**Why the cut, recorded honestly:** roughly 23 hours to ship, and Phase 5 is human-built, never
cuttable, and the author's largest gap. The cut order exists precisely so this trade is made
deliberately rather than discovered at 3am. "We shipped API-only and here is why" is a better
interview answer than a half-finished scraper.

</domain>

<decisions>
## Implementation Decisions

### Dashboard Shape

- **D-01:** The Dashboard's row list comes from **the database**, not from `creators.yaml`. The
  query is `SELECT DISTINCT creator_id, source FROM metrics`, ordered. `sheets.py` therefore reads
  `db.py` and nothing else, which is the internal boundary ARCHITECTURE.md §"Internal Boundaries"
  already draws — reading the config too would give the module two inputs that can disagree.
  **Live consequence, deliberate:** the database currently holds an orphan — `mkbhd`, written by
  the Phase 3 entry-1a bogus-handle test, then removed from `creators.yaml` by a `git checkout`
  that correctly did not delete rows. It renders on the Dashboard with a `—` delta. That is
  DATA-04 working, visible, and pointable-at in the interview, which is worth more than a tidier
  table. The author confirmed keeping it.
  **Second consequence:** column A holds `creator_id` (the slug), not the display name, because
  the database has no display name column. This is a feature, not a shortfall — column A is the
  join key, so a Status-column misalignment is visible to the naked eye rather than silent.
  — **Reversibility:** reversible — switching to a config-driven row list is a one-query change,
  though it would then need a second input and a policy for creators that have rows but no config
  entry.

- **D-02:** **One row per (creator, source) pair**, not one row per creator with source-grouped
  columns. This matches the database's `UNIQUE (creator_id, source, metric_date)` grain exactly, so
  no reshaping happens between the query and the array. Four rows today: three configured creators
  plus `mkbhd`, YouTube only. When SRC-02 unblocks, Twitch arrives as **more rows, not more
  columns** — so the layout never changes and Phase 5's conditional formatting and `onEdit` never
  need a migration. The wide alternative was rejected for exactly that reason: it would widen the
  sheet on un-blocking, which is the column-reorder-in-the-daily-path move PITFALLS.md §6 says
  never to make. Reads slightly against ROADMAP criterion 1's literal "one row per creator"
  wording; the criterion's intent (one visible line of current numbers per thing being tracked) is
  met. *(Claude's call — the author chose "you decide".)*
  — **Reversibility:** costly — the grain is the contract Phase 5's triggers attach to. Changing it
  after Apps Script is written means rewriting the Apps Script at the same time.

- **D-03:** **Seven columns, frozen for v1:**

  | Col | Header | Owner | Source |
  |-----|--------|-------|--------|
  | A | `Creator` | DB | `metrics.creator_id` |
  | B | `Source` | DB | `metrics.source` |
  | C | `Followers (coarse)` | DB | `metrics.followers`, blank when NULL |
  | D | `Views` | DB | `metrics.views` |
  | E | `Δ Views` | DB | computed in Python (D-05) |
  | F | `Last updated (UTC)` | DB | `metrics.collected_at` |
  | G | `Status` | **human** | never written, never read |

  SHEET-02's "labelled coarse" is satisfied **once, in the C header**, not per cell — a per-cell
  annotation would make the column non-numeric and break the formatting Phase 5 wants to key on.
  The Videos and Live columns from the fuller mirror were dropped: `video_count` is YouTube-only
  and `is_live` is Twitch-only (Phase 3 D-06), so with Twitch blocked one of them would render
  permanently blank. *(Claude's call — the author chose "you decide".)*
  **Ceiling, and it is load-bearing:** the column set is **frozen for v1**. Inserting a column
  later shifts Status out from under Phase 5's `e.range.getColumn()` check. Any future column is a
  deliberate migration performed in the same sitting as the Apps Script update — never a change
  made inside the daily write path.

  > **Tab name, added 2026-08-05 — the same class of frozen contract, and easy to overlook.** The
  > live Sheet's tab is named **`Dashboard`**, renamed from Google's default `Sheet1` during
  > credential setup. Every artifact in this phase names that tab, and Phase 5's `onOpen` menu and
  > `onEdit` trigger will bind to it. Renaming it later breaks the Apps Script exactly the way
  > inserting a column does — and with the same invisibility, because the collector goes on writing
  > happily to a tab nothing is listening to. **Freeze the tab name alongside the column set.**
  > (Sheet: `creatorpulse-sheet`, id `1hP7rZqq9Z-QnYGCkt8uhNK1yiwF3dsM9e-T2sYQOqQI`.)

  — **Reversibility:** one-way in practice — column G's position, and now the tab name, are a
  published contract with human-built Apps Script code that this repo does not contain and cannot
  refactor.

- **D-04:** The write is **one call to `worksheet.update`** covering `A1:F{n+1}` — headers
  included, every run. Column G is outside the range and is never touched, which is how SHEET-06 is
  satisfied structurally rather than by care. Including row 1 costs nothing extra (same single
  call), makes the header row self-healing if someone edits it, and removes the need for a separate
  bootstrap path. `.clear()` is never called on this tab. `value_input_option="USER_ENTERED"` so
  columns D, E, and F land as real numbers and a real timestamp — PITFALLS.md §5, and Phase 5's
  conditional formatting depends on it. `creator_id` is a slug and cannot be misparsed by
  `USER_ENTERED`.
  **Row-count note:** the DB-sourced row list only ever grows, so a shorter write can never leave
  stale trailing rows behind. This is a second point in D-01's favour.
  — **Reversibility:** reversible.

### Delta Computation

- **D-05:** The delta is **strict day-over-day on views**: yesterday is `metric_date - 1 day`
  exactly, not "the most recent earlier row". If that exact row is absent, cell E reads `—`. A run
  that never fired leaves a gap, and a gap must read as a gap — reaching back two days would
  silently relabel a 48-hour change as a daily one, which is the same class of quiet wrongness
  PITFALLS.md §13 is about. The delta is computed only when **both** rows exist and **both**
  `views` values are non-NULL; either side missing gives `—`, never a number against an assumed
  zero (SHEET-03, CLAUDE.md's NULL-versus-0 rule). No `COALESCE` appears anywhere in the query.
  Delta is on **views** and never on followers — settled in CLAUDE.md, not reopened here.
  `—` in an otherwise numeric column is intentional: Phase 5's formatting rules skip non-numeric
  cells, which is the correct behaviour for "no comparison available".
  — **Reversibility:** reversible.

### Invocation & Failure

- **D-06:** **Both entry points.** `creatorpulse collect` calls the sync after `collect_once`
  returns, so the human-built unit's `ExecStart` does not change — Phase 2 D-12 forbids touching
  it. **And** `creatorpulse sync` exists as its own subcommand that reads only the database. The
  standalone command is what makes tonight survivable: every Dashboard layout iteration runs
  against committed rows with zero YouTube quota spent and no wait for the timer. It also gives
  Phase 7 a way to re-sync a stale Sheet without a collection run. *(Claude's call — the author
  chose "you decide".)*
  — **Reversibility:** reversible.

- **D-07:** A Sheets failure after the rows are committed is **logged, then re-raised — the process
  exits non-zero**. It is *not* counted in `failure_count`. Rationale: the `runs` row is already
  written by Phase 3 D-16's `try`/`finally` and its `failure_count` means "source fetches that
  failed"; folding a sync failure into that integer conflates "a source broke" with "the view did
  not update", and Phase 3 D-10 already refused to add a column to tell them apart. A non-zero exit
  marks the unit failed in `systemctl status` and puts a named line in the journal, which is the
  loud tell PITFALLS.md §18(d) demands — a Sheet quietly showing yesterday's numbers is the demo
  failure mode with no natural symptom. The database work stays committed; the next day's timer run
  is the retry, consistent with the no-retries-in-the-orchestrator rule. *(Claude's call — the
  author chose "you decide".)*
  — **Reversibility:** reversible.

- **D-08:** The **SHEET-07 preflight wraps `open_by_key` on the real path, every run.** Read
  `client_email` out of the service-account JSON and re-raise a named exception whose message says:
  share the Sheet with `<client_email>` as Editor. A separate one-shot `sheets-check` command was
  rejected — it would leave the daily 08:00 path unguarded, so a permission revoked weeks later
  produces a raw 403 with nobody watching. Criterion 4 is then proven by pasting the actual error
  text. *(Claude's call — the author chose "you decide".)*

  > **CORRECTION 2026-08-05, verified against the installed gspread 6.2.1 during `04-01` planning.**
  > This decision originally said to catch `APIError` / `SpreadsheetNotFound`. That is wrong for the
  > primary case: **an unshared Sheet raises a bare builtin `PermissionError` with no message.** A
  > preflight catching only the two gspread exceptions would miss exactly the failure SHEET-07 exists
  > to catch, and the raw 403 would reach the journal unannotated. Catch `PermissionError` **first**,
  > and keep `gspread.exceptions.APIError` / `SpreadsheetNotFound` as the secondary arms.
  > Note also that `gspread.APIError` does not exist — the path is `gspread.exceptions.APIError`.
  > `open_by_key` is **not** lazy (`Spreadsheet.__init__` calls `fetch_sheet_metadata()`), which
  > confirms it as the correct call site for this preflight rather than the first write.

  — **Reversibility:** reversible.

### Configuration & Secrets

- **D-09:** Two new environment variables, both following the existing `CREATORPULSE_` prefix that
  `CREATORPULSE_CONFIG` and `CREATORPULSE_DB` established: **`CREATORPULSE_SHEET_ID`** (the
  spreadsheet key) and **`CREATORPULSE_SHEETS_KEYFILE`** (absolute path to the service-account JSON).
  Both are read through the same `resolve_paths()`-style treatment already in `config.py` —
  empty string means unset, and the resolved values are logged at run start, never their contents.
  The agent writes **`.env.example` only**. Placing the real values and the key file itself
  (`chmod 600`, owned by the service user) into `/etc/creatorpulse/creatorpulse.env` on the droplet
  is human-built work under Phase 2's ownership, and the key file must land somewhere `.gitignore`
  already covers or be added to it before it exists.
  — **Reversibility:** reversible.

### Claude's Discretion

The author answered "you decide" to all seven questions asked. Every one is resolved above as a
recorded decision rather than left open. What genuinely remains at the planner's discretion:

- Module layout inside `sheets.py`: whether the client construction, the query, the array build, and
  the write are four functions or two. ARCHITECTURE.md names the module; it does not name the
  functions.
- The exact seam for fixture testing, though the shape is constrained by the fixtures-only rule: a
  pure `build_dashboard_rows(rows) -> list[list[object]]` tested against an in-memory SQLite
  database, with the gspread worksheet injected so no network is reachable from `pytest`. Use
  stdlib `unittest.mock` if a double is needed — no new dependency.
- Whether the two-query (today, yesterday) or one-query self-join form is used for the delta, so
  long as the missing-row case branches explicitly and never coalesces.
- Log-line wording and level for the resolved Sheet ID, the row count written, and the sync
  duration. INFO, matching Phase 1 D-19/D-20.
- Exception class names, provided the SHEET-07 one carries the `client_email` in its message.
- Test file name and fixture case names within the conventions Phase 1 D-15 fixed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Binding project rules

- `.claude/CLAUDE.md` — the hand-written "Hard Rules" block above the GSD markers, authoritative
  over the generated sections below it in the same file. Three rules bind this phase: the
  day-over-day delta is computed on **view count, not subscribers**; NULL means "this platform does
  not expose this metric" and `0` means "the platform reported zero", so **never `COALESCE(x, 0)`
  before delta math**; and a test may not be weakened to reach green. It also forbids the agent from
  writing any Apps Script — this phase hands Phase 5 a column layout and stops there.
- `.planning/PROJECT.md` — constraints, the three human-built areas, and the Key Decisions table.
  "The database is the source of truth; the Sheet is a disposable view" is the rule D-01 follows.

### Scope

- `.planning/ROADMAP.md` §"Phase 4: Playwright & Sheets" — the goal, the five success criteria, and
  the ten notes. **Criteria 4 and 5 are now partly void:** criterion 4 (History tab) is cut with
  SHEET-04, and criterion 5's TikTok clause is cut with SRC-03 — only its `client_email` clause
  survives, as D-08. Criteria 1, 2, and 3 stand unchanged.
- `.planning/ROADMAP.md` §"Cut Order" — the authority for both cuts. Item 2 is TikTok, item 3 is the
  History tab. Both are now exercised. Nothing below item 3 exists; the next thing to give would be
  a phase, and Phases 5 and 6 are marked never-cut.
- `.planning/ROADMAP.md` §"Definition of Green" — `ruff format --check .`, `ruff check .`,
  `mypy src/`, `pytest`, **plus** the manual gate that applies from Phase 3 onward: a human-observed
  run with real data reaching the real Sheet. Automated checks alone cannot close this phase.
- `.planning/REQUIREMENTS.md` §Sheet — the six surviving requirements: SHEET-01, SHEET-02, SHEET-03,
  SHEET-05, SHEET-06, SHEET-07. **SHEET-04 and SRC-03 are cut from this phase and need re-marking
  in this file and in ROADMAP.md's coverage table** (see Specific Ideas below).
- `.planning/REQUIREMENTS.md` §"Out of Scope" — "Sheet cells as a second source of truth" is the row
  that makes the Status column the single human-owned exception.

### Prior phase context

- `.planning/phases/03-collector-core-api-sources/03-CONTEXT.md` — **D-01** (the nine-column
  `metrics` shape this phase reads), **D-03** (the two absent-metric rules, which is why `followers`
  can legitimately be NULL on a YouTube row), **D-04** (`connect(create=...)`), **D-05** and **D-08**
  (the Twitch moving-window caveat the delta will inherit if SRC-02 ever unblocks), **D-09** (the
  known-but-unregistered skip path that lets `creators.yaml` keep its now-permanently-cut `tiktok`
  entries without an edit), **D-10** and **D-16** (the four-column `runs` table and the
  `try`/`finally` that writes it — both are why D-07 does not touch `failure_count`).
- `.planning/phases/02-vps-systemd/02-CONTEXT.md` — **D-05**/**D-06** (the database path arrives from
  `CREATORPULSE_DB`; invent no default), **D-09** (08:00 Asia/Manila = 00:00 UTC, so the UTC
  `metric_date` equals the Manila calendar date — relevant to how "yesterday" reads to a human), and
  **D-12, binding:** `deploy/creatorpulse.service` and `deploy/creatorpulse.timer` may be read and
  must **never** be written, edited, generated, or reformatted. D-06 is the reason the sync hangs
  off `collect` rather than off a new unit.
- `.planning/phases/01-skeleton/01-CONTEXT.md` — **D-05** (mypy `strict = true` on `src/`),
  **D-13/D-15/D-16** (fixture-in, record-out; the `tests/fixtures/{source}/{case}` layout;
  `scripts/record_fixture.py` as the only sanctioned fixture creator), **D-19/D-20** (stdlib logging
  to stdout, human-readable).

### Technical grounding

- `.planning/research/ARCHITECTURE.md` §"Sheets Sync Boundary" — the Dashboard read-compute-write
  shape, delta in Python not in a formula, and the single batched `worksheet.update`. Its History-tab
  paragraph is now moot.
- `.planning/research/ARCHITECTURE.md` §"Internal Boundaries" — the `sheets.py` ↔ `db.py` row: it
  reads from `db.py` and never from `sources/*`. D-01 keeps this true. The Apps Script row states the
  Python side's only obligation to Phase 5: the Status column's location and format stay stable.
- `.planning/research/PITFALLS.md` §3 — the service-account share failure, "100% of the time" on
  first run. The source of D-08 and of SHEET-07.
- `.planning/research/PITFALLS.md` §4 — cell-by-cell writes. The source of SHEET-05 and D-04.
- `.planning/research/PITFALLS.md` §5 — `RAW` vs `USER_ENTERED`. The source of D-04's
  `value_input_option`, and the 5-second visual check: the delta column must render right-aligned.
- `.planning/research/PITFALLS.md` §6 — the full-tab rewrite that clobbers Status, and the warning
  against reordering columns in the daily write path. The source of D-03's frozen-column ceiling and
  D-04's never-`.clear()` rule.
- `.planning/research/PITFALLS.md` §13 — NULL versus 0 corrupting delta math. The source of D-05.
- `.planning/research/PITFALLS.md` §18(d) — the silently stale Sheet. The source of D-07's
  exit-non-zero call.
- `.planning/research/STACK.md` §6 — gspread's own auth path is sufficient; `google-auth` arrives
  transitively; **do not add `google-api-python-client`**.
- `.planning/STATE.md` §"Blockers/Concerns" — the outstanding Phase 3 UAT (droplet env not yet
  filled) is the same gate this phase's manual verification depends on. `YOUTUBE_API_KEY` is
  available; Twitch is not.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`src/creatorpulse/db.py:61-89`** — `connect(db_path, *, create)`. `sheets.py` and the `sync`
  subcommand open with **`create=False`**, which raises `DatabaseNotInitialized` rather than
  silently creating an empty database at a mistyped path (Phase 3 D-04). This is the same guard the
  Phase 6 bot uses; the Sheet writer is a reader and must behave like one.
- **`src/creatorpulse/db.py:9-33`** — `SCHEMA_DDL`, including
  `CREATE INDEX idx_metrics_creator_date ON metrics (creator_id, metric_date)`. The delta query
  should use it: it is exactly the index for "this creator, these two dates".
- **`src/creatorpulse/models.py:7-17`** — `MetricRecord`, the nine fields D-03's columns select from.
- **`src/creatorpulse/config.py:24-30`** — `resolve_paths()` already resolves `CREATORPULSE_CONFIG`
  and `CREATORPULSE_DB` from the environment and treats an empty string as unset. D-09's two new
  variables follow the same treatment; extend this rather than writing a second resolver.
- **`src/creatorpulse/cli.py:22-33`** — `run_collect()` owns the run-start and run-end log lines and
  the resolved-path announcement. The sync call attaches after `collect_once` returns. The
  `collect` subcommand's name, flags, and log shape are fixed by Phase 1 D-02/D-03 and must not
  change — a human-typed unit file targets them. The new `sync` subcommand is additive.
- **`src/creatorpulse/collector.py:55-60`** — the outer `try`/`finally` that guarantees a `runs` row.
  D-07 depends on it: the sync runs **after** `collect_once` returns, so the `runs` row is already
  committed before a Sheets failure can propagate.
- **`tests/test_db.py`, `tests/test_collector.py`** — the existing suite's style, and its in-memory
  SQLite setup. The Dashboard tests extend it; no live network, no real Sheet.

### Established Patterns

- **`@dataclass(frozen=True, slots=True)`** for record types.
- **mypy `strict = true` on `src/`** (Phase 1 D-05). Every metric is `int | None`, so strict mode is
  what forces the delta's both-sides-present branch to be written rather than assumed.
- **`ignore_missing_imports` is already scoped to `gspread.*` and `yaml`** — gspread needs no new
  mypy configuration. Do not widen the override.
- **stdlib `logging` to stdout**, plain human-readable format (Phase 1 D-19/D-20).
- **No new dependencies.** `gspread` and `google-auth` are already in the locked set and already
  installed. Playwright stays installed but, with SRC-03 cut, unexercised — do not remove it from
  `pyproject.toml` in this phase; that is a Phase 7 tidy at most.
- **The four-command gate**, in order: `ruff format --check .`, `ruff check .`, `mypy src/`,
  `pytest` (Phase 1 D-04/D-08).

### Integration Points

- **`cli.py` → `sheets.py`** — one call at the end of `run_collect()`, plus the standalone `sync`
  subcommand (D-06).
- **`sheets.py` → `db.py`** — read-only, `create=False`, one query for today's rows and the delta.
  Never imports `sources/*`, never imports `collector.py`.
- **Phase 5 consumes D-02, D-03, and D-04.** The Apps Script `onEdit` attaches to column G and must
  check `e.range.getColumn()` against it; the conditional formatting keys on column E's numeric
  values. Both break if the column set moves, which is why D-03 freezes it.
- **Phase 6 is unaffected** — the bot reads the database, not the Sheet.
- **Phase 7 consumes D-06 and D-07** — `creatorpulse sync` is the re-sync path, and the non-zero
  exit is what makes a failed sync visible in the cold-start rehearsal.

</code_context>

<specifics>
## Specific Ideas

- **Two documents need updating outside this file, and the planner should not silently absorb it.**
  ROADMAP.md's Phase 4 entry, its coverage table, and its progress table still claim eight
  requirements including SRC-03 and SHEET-04; REQUIREMENTS.md's traceability table still maps both
  to Phase 4. Both cuts are roadmap-level scope changes, not planning details. Run
  `/gsd-phase edit 4` (or edit both by hand) before planning, so the plan is graded against six
  requirements rather than eight and the verifier does not open gaps for work that was deliberately
  cut.
- **The orphan is a feature — say so out loud.** `mkbhd` on the Dashboard with a `—` delta is live,
  pointable evidence of DATA-04 and of the NULL-versus-zero rule in the same cell. It is a better
  answer to "what happens when you remove a creator?" than a clean table would be. Worth a line in
  the Phase 7 README.
- **Verify the cell types by eye, once.** PITFALLS.md §5's five-second check: after the first real
  write, confirm the `Δ Views` column renders **right-aligned** (numeric) and not left-aligned
  (text). If it is left-aligned, `value_input_option` is wrong and every Phase 5 conditional-format
  rule will silently do nothing. Cheaper to catch now than to debug inside Apps Script tomorrow.
- **Prove SHEET-06 the way criterion 3 words it:** type something into a Status cell, run
  `creatorpulse sync`, confirm the text is still there. That is a ten-second proof and it is the
  requirement's entire content.
- **Build the standalone `sync` first, then wire it into `collect`.** It is the same code either
  way, and having the standalone command early is what lets the Dashboard layout be iterated
  against already-committed rows without spending quota or waiting on the timer.
- **`04-UAT.md` follows the `02-UAT.md` / `03-UAT.md` pattern** — pasted command output per
  criterion, no screenshots, with the criteria renumbered to the three that survive the cuts plus
  D-08's `client_email` proof. The same droplet-access blocker that left Phase 3's UAT PENDING
  applies here; `YOUTUBE_API_KEY` is available, so the Sheet path is provable even while Twitch
  is not.

</specifics>

<deferred>
## Deferred Ideas

- **SRC-03 — the TikTok source.** Cut from this phase via cut-order item 2. Not deferred to a later
  phase in this milestone; there is no later phase that could take it before the interview. It
  becomes a v2 candidate. `creators.yaml` keeps its `tiktok` entries and Phase 3 D-09's
  known-but-unregistered skip path keeps them harmless, so re-adding the source later is still one
  module plus one registry line.
- **SHEET-04 — the History tab.** Cut via cut-order item 3. The design is settled if it ever
  returns: one read of the tab's key column, diff against today's rows, one batched `append_rows`
  of only what is missing — two API calls, idempotent across same-day re-runs. Roughly 30–40 lines
  plus a fixture test. The database keeps full daily history regardless (DATA-04), so nothing is
  lost by not rendering it.
- **A Videos and a Live column on the Dashboard.** Dropped by D-03 because each would be
  single-source and one would be permanently blank while Twitch is walled off. Revisit only
  together with the Phase 5 Apps Script, per D-03's frozen-column ceiling.
- **Display names on the Dashboard.** Column A shows `creator_id` (D-01). Showing `creator.name`
  would mean `sheets.py` reading `creators.yaml` as a second input, or a `creators` table in the
  database. Neither is worth it at four rows; the slug is legible.
- **Reaching further back than one day for a delta baseline.** Declined by D-05. A gap must read as
  a gap. Revisit only if run gaps become routine, which the timer plus `Persistent=true` is designed
  to prevent.
- **Removing Playwright from `pyproject.toml`** now that SRC-03 is cut. Not this phase — a
  dependency removal is a gate-touching change with no benefit tonight. Phase 7 tidy at most, and
  arguably leave it: the browser is installed on the droplet and the option to add the source back
  costs nothing to keep open.
- **`skipped_count` on the `runs` table** — still declined (Phase 3 D-10). With TikTok cut
  permanently, the skip lines for `tiktok` are now permanent too, which makes the column marginally
  more tempting and no more justified.

</deferred>

---

*Phase: 4-Playwright & Sheets*
*Context gathered: 2026-08-05*
