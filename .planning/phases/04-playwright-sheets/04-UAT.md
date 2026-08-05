---
status: pending
phase: 04-playwright-sheets
source: [04-CONTEXT.md]
started: 2026-08-05T17:36:21Z
updated: "2026-08-05T17:36:21Z"
blocked_reason: "No Google service account exists yet from this executor's vantage — CREATORPULSE_SHEETS_KEYFILE has nothing to point at, no spreadsheet has been created or shared with a service account's client_email, so all four entries below are unobservable today. Unblocks when: a service account is created in the Google Cloud console, its JSON key is placed chmod 600 on the droplet under Phase 2's human ownership (D-09), and a Sheet is shared with that account's client_email as Editor. (Note: STATE.md's decision log records this groundwork as already done in a prior session for the live creatorpulse-sheet — this scaffold is written PENDING regardless, per the plan's own instruction, so the checklist is usable in one sitting rather than assumed closed.)"
---

## Current Test

### 1. The author opens the real Google Sheet after a real run and sees one Dashboard row per creator-source pair with the latest snapshot and its day-over-day delta on views — with subscriber/follower figures visibly labelled coarse

## Tests

### 1. The author opens the real Google Sheet after a real run and sees one Dashboard row per creator-source pair with the latest snapshot and its day-over-day delta on views — with subscriber/follower figures visibly labelled coarse

expected: Two halves, both required.

First — the row set and the values, cross-checked against the database rather than eyeballed: run
`creatorpulse sync`, then run a `sqlite3 -header -column` query over `metrics` selecting
`creator_id`, `source`, `followers`, `views`, and `collected_at`. Every returned row must match the
Dashboard's columns A–D and F, cell for cell, and the Sheet's C1 header must read exactly
`Followers (coarse)` — SHEET-02's labelling is satisfied once, in the header, never per cell (D-03).

Second, and stated as its own explicit sub-check — the PITFALLS §5 eye-check: column E (`Δ Views`)
must render **right-aligned**. Right-aligned means the delta arrived as a number; left-aligned means
it arrived as text, `value_input_option` is wrong, and every Phase 5 conditional-format rule will
silently do nothing (D-04). Five seconds, and unprovable by any other means — which is exactly why it
lives here and not in `pytest`.

why_human: The row-vs-database cross-check needs a real Sheet and a real `sqlite3` query run
side by side; the right-alignment eye-check is a rendering fact only visible in the Google Sheets UI,
not observable from a mock in the test suite.

not_closed_reason: PENDING — no service account/spreadsheet access from this executor's vantage.
`CREATORPULSE_SHEETS_KEYFILE` has nothing to point at.

result: pending

evidence: |
    Commands that will close this entry once run. Paste output verbatim, do not fabricate.

    Cross-check the Dashboard against the database:
      $ creatorpulse sync
      $ sqlite3 -header -column /var/lib/creatorpulse/creatorpulse.db \
          "select creator_id, source, followers, views, collected_at from metrics
           where (creator_id, source, metric_date) in (
             select creator_id, source, max(metric_date) from metrics
             group by creator_id, source
           ) order by creator_id, source;"

    Compare every row against the Dashboard's columns A, B, C, D, F for the same
    (creator_id, source) pair. Confirm cell C1 reads exactly "Followers (coarse)".

    Eye-check column E:
      Open the live Sheet, look at the Δ Views column. Confirm it renders right-aligned
      (numeric), not left-aligned (text). Record the verdict as one word: "right-aligned"
      or "left-aligned".

### 2. A creator with no prior-day row shows `—` for delta, not a number computed against zero

expected: The live instance rather than a contrived one. **`mkbhd`** — written into the database by
Phase 3's bogus-handle test (`03-UAT.md` entry 1) and then removed from `creators.yaml` by a
`git checkout` that correctly did not delete rows — renders on the Dashboard with a `—` in column E.
One cell proves DATA-04 (the database keeps history the config no longer lists), D-01 (rows come from
the database, not the config), and the NULL-versus-zero rule, together. This is deliberate and kept
per D-01, not a table that wants tidying.

why_human: Requires opening the real Sheet after a real sync and reading one specific cell for
`mkbhd`; no automated check substitutes for a human confirming the rendered character is `—` and not
a computed number or a blank.

not_closed_reason: PENDING — same blocker as entry 1: no service account/spreadsheet access from
this executor's vantage.

result: pending

evidence: |
    Commands that will close this entry once run. Paste output verbatim, do not fabricate.

    $ creatorpulse sync
    $ sqlite3 -header -column /var/lib/creatorpulse/creatorpulse.db \
        "select creator_id, source, metric_date, views from metrics where creator_id = 'mkbhd'
         order by metric_date;"

    Open the live Sheet, find the mkbhd / youtube row, confirm column E reads "—" — not a
    number, not blank. Paste the Dashboard row's A–F values alongside the query output.

### 3. The author types into the Status column, re-runs the collector, and the typed value is still there afterwards

expected: Type a recognisable string into a `G` cell on the live Dashboard, run `creatorpulse sync`,
reload the Sheet, confirm the string is unchanged — the ten-second proof that the write range ends at
F (D-03, D-04, SHEET-06).

why_human: `04-02`'s test suite already asserts structurally that the write range string never names
column G (`test_sync_write_range_never_names_column_g`), but only a human typing into a live Sheet and
re-running the real sync proves the value survives a real round trip, not just a structural assertion
against a mock.

not_closed_reason: PENDING — same blocker: no service account/spreadsheet access from this executor's
vantage.

result: pending

evidence: |
    Commands that will close this entry once run. Paste output verbatim, do not fabricate.

    In the live Sheet, type a recognisable marker into any G cell, e.g. "reviewing 2026-08-0N".
    $ creatorpulse sync
    Reload the Sheet. Confirm the G cell still reads the marker, unchanged.

    Paste: the marker text typed, the sync command's stdout/log lines, and the G cell's
    value after reload.

### 4. A Sheet that has not been shared with the service account fails with a message naming the exact `client_email` to share it with

expected: Point `CREATORPULSE_SHEET_ID` at a second, deliberately unshared spreadsheet, run
`creatorpulse sync`, and paste the failure verbatim. It must contain the service account's
`client_email` address and the instruction to share as Editor, and the process must exit non-zero
(D-07, D-08).

Record the verified correction so the tester knows what they are looking at: an unshared Sheet
raises a bare builtin `PermissionError` with no message — which is why the preflight catches
`PermissionError` **first**, with `gspread.exceptions.APIError` / `SpreadsheetNotFound` as secondary
arms (D-08's verified CORRECTION block). Pasting the `client_email` is fine — it is a public
identifier. Pasting the key file, or its contents, is not.

why_human: Requires a real second spreadsheet deliberately left unshared and a real run against it;
the exact wording and presence of `client_email` in the raised message is an end-to-end behaviour, not
something a fixture-driven unit test substitutes for.

not_closed_reason: PENDING — needs a second, deliberately unshared spreadsheet in addition to the
already-blocked service account access; `04-03` (the `SheetNotShared` preflight itself) has not yet
executed.

result: pending

evidence: |
    Commands that will close this entry once run. Paste output verbatim, do not fabricate.

    Create or pick a second spreadsheet not shared with the service account's client_email.
    $ CREATORPULSE_SHEET_ID=<second-unshared-sheet-id> creatorpulse sync
    (or set the var in the environment file and re-run)

    Paste the full failure output, non-zero exit code included. Confirm the message names
    the service account's client_email and instructs sharing as Editor. Confirm the caught
    exception is the bare builtin PermissionError case, not a generic traceback.

## Summary

total: 4
passed: 0
passed_with_caveat: 0
pending: 4

| Entry | What closes it |
|-------|----------------|
| 1 | A service account + shared Sheet + a real `creatorpulse sync` run, cross-checked against `sqlite3`, plus the column-E eye-check |
| 2 | The same run — read the live `mkbhd` row's column E |
| 3 | The same access — type into G, re-run sync, confirm survival |
| 4 | The same access, plus a second deliberately-unshared spreadsheet, and `04-03`'s preflight executed |

## Gaps

**The automated half is not this file's to claim.** `ruff format --check .`, `ruff check .`,
`mypy src/`, and `pytest` are owned by `04-01` through `04-03`; both `04-01-SUMMARY.md` and
`04-02-SUMMARY.md` record those four commands green as of their own closeout (with one pre-existing,
out-of-scope `ruff format` finding on `04-PATTERNS.md`, not a regression from this plan).

**The human-observed half is outstanding for all four entries, behind one shared blocker, not four.**
No Google service account or spreadsheet is reachable from this executor's vantage, so none of the
four entries above could be closed against real data in this session. All four stay `pending`, each
carrying its own `not_closed_reason` and the exact commands that will close it — usable as a
checklist in one sitting the hour that access exists. Entry 4 carries a second, narrower blocker on
top of the shared one: it additionally needs a deliberately-unshared second spreadsheet and `04-03`'s
`SheetNotShared` preflight, neither of which exist yet.

Live-verification facts already on record from `04-01`/`04-02`'s own execution sessions (not
re-derived here, cited for continuity): the Sheet `creatorpulse-sheet`
(`1hP7rZqq9Z-QnYGCkt8uhNK1yiwF3dsM9e-T2sYQOqQI`), tab renamed `Sheet1` → `Dashboard`, header row and
right-aligned Views column confirmed once already, and the G2 marker `"reviewing 2026-08-06"`
surviving one prior sync — see `04-01-SUMMARY.md`. `04-02-SUMMARY.md` separately recorded that the
live Sheet still holds only single-date synthetic seed rows (`kaicenat`, `pokimane`, `xqc`), so no
consecutive-day pair exists yet for entry 1's delta half or entry 1's right-alignment-on-a-real-delta
check to run against — this scaffold's entry 1 command set is what closes that the next time
`creatorpulse sync` runs after a second day of rows exists.
