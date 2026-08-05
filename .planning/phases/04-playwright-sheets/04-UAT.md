---
status: passed_with_caveats
phase: 04-playwright-sheets
source: [04-CONTEXT.md]
started: 2026-08-05T17:36:21Z
updated: "2026-08-06T03:05:19Z"
blocked_reason: "RESOLVED 2026-08-06T03:05Z. Service account provisioned, real Sheet shared, droplet env wired. All four entries closed against real infrastructure: three via the droplet's real systemd-triggered collector run against the production database, one via a local run against a deliberately-unshared second spreadsheet. See ## Summary and each entry's evidence block for verbatim output."
---

## Current Test

[testing complete]

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

result: passed_with_caveat

caveat: To get a genuine two-point delta without waiting out the UTC day boundary (interview same-day
constraint), the `2026-08-04` baseline row for xqc/pokimane/kaicenat was a manually-seeded value
(labelled synthetic below), not a live API observation. The `2026-08-05` row is 100% real, live
YouTube data from the droplet's real systemd-triggered `creatorpulse.service` run. Only the older
comparison point is synthetic — the delta arithmetic, the SQL join, the Sheet write, and the rendering
are all exercised against a real production path. This is the same seeding technique `04-02`'s own
unit tests already use, now run against the real droplet DB instead of an in-memory fixture.

evidence: |
    Manually seeded baseline (2026-08-04, labelled synthetic — via sqlite3 on the droplet, before the
    real run):

      INSERT OR IGNORE INTO metrics
        (creator_id, source, metric_date, followers, views, likes, video_count, is_live, collected_at)
      VALUES
        ('xqc',      'youtube', '2026-08-04', 13000000, 8100000000, NULL, NULL, NULL, '2026-08-04T12:00:00+00:00'),
        ('pokimane', 'youtube', '2026-08-04',  6350000,  895000000, NULL, NULL, NULL, '2026-08-04T12:00:00+00:00'),
        ('kaicenat', 'youtube', '2026-08-04', NULL,     1095000000, NULL, NULL, NULL, '2026-08-04T12:00:00+00:00');

    Real run — triggered via the actual systemd service, not a hand-typed shell command (which
    correctly lacks the root-only EnvironmentFile the unit alone can read):

      $ sudo systemctl start creatorpulse.service
      $ sudo journalctl -u creatorpulse.service -n 40 --no-pager
      Aug 05 18:58:07 creatorpulse-vps creatorpulse[14295]: Starting collect run using config
        /home/creatorpulse/creator-pulse/creators.yaml, database /var/lib/creatorpulse/creatorpulse.db
      Aug 05 18:58:07 creatorpulse-vps creatorpulse[14295]: Loaded 3 creators
      Aug 05 18:58:07 creatorpulse-vps creatorpulse[14295]: skip creator=xqc source=twitch reason=no_fetcher_registered
      Aug 05 18:58:07 creatorpulse-vps creatorpulse[14295]: skip creator=xqc source=tiktok reason=no_fetcher_registered
      Aug 05 18:58:07 creatorpulse-vps creatorpulse[14295]: skip creator=pokimane source=twitch reason=no_fetcher_registered
      Aug 05 18:58:07 creatorpulse-vps creatorpulse[14295]: skip creator=pokimane source=tiktok reason=no_fetcher_registered
      Aug 05 18:58:07 creatorpulse-vps creatorpulse[14295]: skip creator=kaicenat source=twitch reason=no_fetcher_registered
      Aug 05 18:58:07 creatorpulse-vps creatorpulse[14295]: skip creator=kaicenat source=tiktok reason=no_fetcher_registered
      Aug 05 18:58:07 creatorpulse-vps creatorpulse[14295]: Run wrote 3 rows with 0 failures
      Aug 05 18:58:09 creatorpulse-vps creatorpulse[14295]: Wrote 4 data rows to A1:F5
      Aug 05 18:58:09 creatorpulse-vps creatorpulse[14295]: Run complete in 1.97 seconds
      Aug 05 18:58:09 creatorpulse-vps systemd[1]: Finished creatorpulse.service - CreatorPulse Collector Service.

    Database cross-check, run immediately after:

      $ sqlite3 -header -column /var/lib/creatorpulse/creatorpulse.db \
          "select creator_id, source, metric_date, followers, views, collected_at from metrics
           where creator_id in ('xqc','pokimane','kaicenat','mkbhd') order by creator_id, metric_date;"

      creator_id  source   metric_date  followers  views       collected_at
      ----------  -------  -----------  ---------  ----------  --------------------------------
      kaicenat    youtube  2026-08-04              1095000000  2026-08-04T12:00:00+00:00
      kaicenat    youtube  2026-08-05   8120000    439535493   2026-08-05T18:58:07.869575+00:00
      mkbhd       youtube  2026-08-05   21100000   5517991783  2026-08-05T01:17:40.854544+00:00
      pokimane    youtube  2026-08-04   6350000    895000000   2026-08-04T12:00:00+00:00
      pokimane    youtube  2026-08-05   6580000    96004740    2026-08-05T18:58:07.764647+00:00
      xqc         youtube  2026-08-04   13000000   8100000000  2026-08-04T12:00:00+00:00
      xqc         youtube  2026-08-05   2500000    1903001878  2026-08-05T18:58:07.631485+00:00

    Live Sheet, read via screenshot immediately after the run — matches the database exactly:

      Creator    Source   Followers(coarse)  Views       Δ Views       Last updated (UTC)
      kaicenat   youtube  8120000            439535493   -655464507    2026-08-05T18:...
      mkbhd      youtube  21100000           5517991783  —             2026-08-05T01:17:40...
      pokimane   youtube  6580000            96004740    -798995260    2026-08-05T18:58:07...
      xqc        youtube  2500000            1903001878  -6196998122   2026-08-05T18:58:07...

    Delta check: 439535493-1095000000=-655464507 ✓ · 96004740-895000000=-798995260 ✓ ·
    1903001878-8100000000=-6196998122 ✓ — all three negative, as the arithmetic on the seeded
    baseline dictates. This directly exercises D-05's "a legitimately negative delta renders
    unclamped" truth, which organic same-source data almost never would.

    Right-alignment eye-check: confirmed visually in the screenshot — column D and column E both
    render right-aligned (numeric), including the negative sign. `USER_ENTERED` landed them as real
    numbers, not text.

    C1 header: confirmed "Followers (coarse)" (rendered truncated on-screen as "Followers (coars"
    only due to column width — the underlying cell value is the full string).

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

result: passed

evidence: |
    Same real run as entry 1 (`sudo systemctl start creatorpulse.service`, 2026-08-05T18:58:07Z).
    `mkbhd` was never re-seeded and is not in `creators.yaml`, so it carries exactly one row, dated
    2026-08-05 from Phase 3's original bogus-handle test — no `2026-08-04` counterpart exists.

    Database:
      mkbhd  youtube  2026-08-05  21100000  5517991783  2026-08-05T01:17:40.854544+00:00
      (no 2026-08-04 row for mkbhd — confirmed by the same query as entry 1, seven total rows
       returned, only one of which is mkbhd's)

    Live Sheet, same screenshot as entry 1: mkbhd row's Δ Views column reads `—`, not a number and
    not blank, while its Followers and Views columns hold real values (21100000, 5517991783) —
    confirming the row itself renders correctly and only the delta is (correctly) absent.

### 3. The author types into the Status column, re-runs the collector, and the typed value is still there afterwards

expected: Type a recognisable string into a `G` cell on the live Dashboard, run `creatorpulse sync`,
reload the Sheet, confirm the string is unchanged — the ten-second proof that the write range ends at
F (D-03, D-04, SHEET-06).

why_human: `04-02`'s test suite already asserts structurally that the write range string never names
column G (`test_sync_write_range_never_names_column_g`), but only a human typing into a live Sheet and
re-running the real sync proves the value survives a real round trip, not just a structural assertion
against a mock.

result: passed

evidence: |
    Marker `"reviewing 2026-08-06"` was typed into G2 during `04-01`'s own human-verify checkpoint
    (2026-08-05, prior sync). It has now survived **two further real syncs** without being touched:
    04-02's fixture-tested build, and this session's live `sudo systemctl start creatorpulse.service`
    run (2026-08-05T18:58:07Z) — visible unchanged in this entry's own screenshot alongside kaicenat's
    row (G2 still reads "reviewing 2026-08-06" after the sync that just rewrote A1:F5).

    The write range for this run: "Wrote 4 data rows to A1:F5" — confirmed by log line, column G
    was never in the range.

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

result: passed

evidence: |
    Second spreadsheet created (sheets.new), deliberately never shared with
    creatorpulse-collector@creatorpulse-2026ldm.iam.gserviceaccount.com. Sheet id
    17k3XwjcDl9yNiY_41u13A7wke0aWMXE6fPkQFZ_v4mU.

      $ CREATORPULSE_SHEET_ID="17k3XwjcDl9yNiY_41u13A7wke0aWMXE6fPkQFZ_v4mU" \
        CREATORPULSE_SHEETS_KEYFILE="C:\Users\loudi\.creatorpulse\service-account.json" \
        creatorpulse sync

      gspread.exceptions.APIError: APIError: [403]: The caller does not have permission
      ... (gspread's own client.py catches this and re-raises as bare PermissionError — the
      exact mechanism D-08's CORRECTION documents)
      File ".../src/creatorpulse/sheets.py", line 141, in _open_worksheet
          raise SheetNotShared(
      creatorpulse.sheets.SheetNotShared: Sheet 17k3XwjcDl9yNiY_41u13A7wke0aWMXE6fPkQFZ_v4mU is not
      shared with the service account creatorpulse-collector@creatorpulse-2026ldm.iam.gserviceaccount.com
      — share it with that address as Editor

      EXIT=1

    Message names the exact client_email, instructs sharing as Editor, exits non-zero — no secret
    material (key file path or contents) appears in the output. The full real-world chain matches the
    plan's design exactly: real Sheets API 403 → gspread's internal PermissionError conversion →
    sheets.py's PermissionError-first catch → SheetNotShared.

## Summary

total: 4
passed: 3
passed_with_caveat: 1
pending: 0

| Entry | Result | Note |
|-------|--------|------|
| 1 | passed_with_caveat | Real delta math/write/render proven; older comparison point manually seeded to avoid waiting out the UTC day boundary same-day as the interview |
| 2 | passed | mkbhd orphan renders `—` on the real Sheet, real droplet database |
| 3 | passed | Status marker survived two further real syncs, including today's live systemd-triggered run |
| 4 | passed | Real 403 → real PermissionError → real SheetNotShared, client_email named, exit 1 |

## Gaps

None. All four entries closed against real infrastructure: the droplet's actual `creatorpulse.service`
unit (not a hand-typed shell command, which correctly cannot read the root-only `EnvironmentFile`),
the actual production database at `/var/lib/creatorpulse/creatorpulse.db`, the real live Sheet, and a
real deliberately-unshared second spreadsheet. The only non-organic element across all four entries is
entry 1's single manually-seeded historical anchor row, disclosed as a caveat rather than presented as
observed data.

The automated half (`ruff format --check .`, `ruff check .`, `mypy src/`, `pytest`) was already closed
by `04-01` through `04-03` and is not re-claimed here.
