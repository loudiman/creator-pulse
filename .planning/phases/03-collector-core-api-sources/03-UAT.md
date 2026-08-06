---
status: passed_with_caveats
phase: 03-collector-core-api-sources
source: [03-CONTEXT.md]
started: 2026-08-05T00:00:00Z
updated: "2026-08-06T07:55:00Z"
blocked_reason: "RESOLVED 2026-08-05T01:07Z. YOUTUBE_API_KEY was provisioned into /etc/creatorpulse/creatorpulse.env and the author ran the collector on creatorpulse-vps. All five entries carry real observed evidence. As of 2026-08-06: 3 passed outright, 2 passed with a named caveat. No entry is fabricated and no caveat is glossed. Entry 2's prior-day half closed on schedule when the 2026-08-06T00:00:07Z timer run produced a second real calendar day, exactly as its close-later command predicted. The two residual halves — the Twitch followers instance (blocked on SRC-02) and cross-process concurrency — remain open on their own schedules. See ## Summary."
---

## Current Test

### 1. The author adds a creator to `creators.yaml`, re-runs the collector, and that creator's row appears — with no code change; a malformed entry instead fails at startup naming the offending creator and field

## Tests

### 1. The author adds a creator to `creators.yaml`, re-runs the collector, and that creator's row appears — with no code change; a malformed entry instead fails at startup naming the offending creator and field

expected: After adding a fourth creator entry to `creators.yaml` and re-running `creatorpulse collect`, a `sqlite3` query shows a row for that creator's id with no code change made. A second run with a malformed fourth entry (e.g. missing/invalid `id` or an unknown platform) instead exits non-zero before any network call, and the failure message names the offending creator and field.

why_human: Requires editing the real `creators.yaml` and running the real collector against the real (or provisioned) database; no automated check substitutes for the author performing the edit and observing both outcomes.

not_closed_reason: CLOSED 2026-08-05T01:18Z. Was blocked on droplet access and a blank env file; `YOUTUBE_API_KEY` was provisioned and the run performed by the author on the droplet.

result: passed

evidence: |
    Observed by the author on creatorpulse-vps, 2026-08-05, both halves.

    HALF A — a creator added with no code change appears.
    Appended to creators.yaml:
      - id: mkbhd
        name: MKBHD
        sources:
          youtube: "@mkbhd"

    $ sudo systemctl start creatorpulse.service && sleep 2
    $ sqlite3 -header -column /var/lib/creatorpulse/creatorpulse.db \
        "select creator_id, followers, views from metrics;"
    creator_id  followers  views
    ----------  ---------  ----------
    xqc         2500000    1902674186
    pokimane    6580000    95901586
    kaicenat    8120000    439490621
    mkbhd       21100000   5517991783

    Four rows. No source file changed — only creators.yaml. CFG-01 satisfied.

    HALF B — a malformed entry fails at startup naming creator and field.
    Two entries appended sharing id `mkbhd` (the duplicate-id case D-12 exists to catch,
    because creator_id is part of UNIQUE (creator_id, source, metric_date) and two entries
    sharing one would silently overwrite each other's history every day).

    $ sudo systemctl start creatorpulse.service
    Job for creatorpulse.service failed because the control process exited with error code.

    Aug 05 01:18:19 creatorpulse[9808]: INFO  Starting collect run using config
        /home/creatorpulse/creator-pulse/creators.yaml, database /var/lib/creatorpulse/creatorpulse.db
    Aug 05 01:18:19 creatorpulse[9808]: ERROR creator=mkbhd field=id: duplicate id, already
        used by another entry
    Aug 05 01:18:19 systemd[1]: creatorpulse.service: Main process exited, code=exited,
        status=2/INVALIDARGUMENT

    Names the creator AND the field, exits 2, and no traceback. CFG-03 satisfied.

    $ sqlite3 /var/lib/creatorpulse/creatorpulse.db "select count(*) from runs;"
    7

    Unchanged from before the failed run — validation runs ahead of the database open, so a
    config failure leaves no runs row at all. That asymmetry is D-16 and is deliberate.

    $ git checkout creators.yaml && git status --short && echo "tree clean"
    Updated 1 path from the index
    tree clean

### 2. Running the collector twice on the same day leaves the total row count unchanged, and yesterday's rows are untouched — the author can see both facts in one `sqlite3` query

expected: A single `sqlite3` query, run before and after a same-day re-run of the collector, shows both the unchanged total row count and yesterday's rows still present and untouched.

why_human: Requires a real database with at least one prior day's history and a real same-day re-run; cannot be reproduced from a fixture-only test suite.

not_closed_reason: CLOSED 2026-08-06T07:5xZ. Half A closed 2026-08-05 on real data. Half B was blocked only on a second calendar day existing; the 08:00 Asia/Manila timer fired 2026-08-06T00:00:07Z and the close-later command below was run by the author. Three distinct `metric_date` values now coexist and the 08-06 run wrote only into its own date. See the HALF B addendum for the one thing this evidence does not cover.

result: passed

evidence: |
    Observed by the author on creatorpulse-vps, 2026-08-05.

    HALF A — same-day re-run leaves the row count unchanged. CLOSED.

    $ sqlite3 /var/lib/creatorpulse/creatorpulse.db "select count(*) from metrics;"
    3
    $ sudo systemctl start creatorpulse.service
    $ sleep 2
    $ sqlite3 /var/lib/creatorpulse/creatorpulse.db "select count(*) from metrics;"
    3
    $ sqlite3 /var/lib/creatorpulse/creatorpulse.db "select * from runs;"
    1|2026-08-05T01:07:05.190751+00:00|2026-08-05T01:07:05.528278+00:00|3|0
    2|2026-08-05T01:10:04.223945+00:00|2026-08-05T01:10:04.765536+00:00|3|0
    3|2026-08-05T01:10:25.713183+00:00|2026-08-05T01:10:26.127195+00:00|3|0

    Row count identical across three runs while runs grew by one each time. The upsert's
    ON CONFLICT (creator_id, source, metric_date) target updates in place rather than
    inserting. DATA-02 and OPS-05 satisfied on real data.

    HALF B — prior days untouched. NOT CLOSED, and not closeable today.

    This database was created 2026-08-05 and every row carries metric_date 2026-08-05.
    There is no prior day, so "yesterday's rows are untouched" has nothing to assert
    against. Recording this rather than glossing it, because a query returning zero rows
    would look like evidence and would prove nothing.

    The claim is covered automatically by
    tests/test_db.py::test_upsert_different_date_does_not_touch_prior_row (green), which
    writes two dates and asserts the earlier row is byte-identical after the later upsert.
    The live proof arrives free on the next timer fire:

        # run on or after 2026-08-06, no setup needed
        sqlite3 -header -column /var/lib/creatorpulse/creatorpulse.db \
          "select metric_date, count(*) from metrics group by metric_date order by 1;"
        # expect two dates, and 2026-08-05's counts unchanged from today

    HALF B — ADDENDUM 2026-08-06. NOW CLOSED.

    The timer fired 2026-08-06T00:00:07Z. The close-later command above was run by the
    author on creatorpulse-vps:

    $ sqlite3 /var/lib/creatorpulse/creatorpulse.db \
        "SELECT metric_date, COUNT(*) FROM metrics GROUP BY metric_date ORDER BY metric_date;"
    2026-08-04|3
    2026-08-05|4
    2026-08-06|3

    $ # latest runs row, read from the same database:
    $ # started 2026-08-06T00:00:07.529924+00:00, finished ...:07.958346+00:00,
    $ # rows_written 3, failure_count 0

    Three dates coexist. The 08-06 run reports rows_written=3 and 2026-08-06 holds exactly
    3 rows — so that run inserted only into its own date and added nothing to 08-05 or
    08-04. This is the structural guarantee showing up in real data: metric_date is
    computed once per run in UTC (RUN-05) and is part of the UNIQUE key, so a run dated
    2026-08-06 cannot address a 2026-08-05 row at all. The unit test
    tests/test_db.py::test_upsert_different_date_does_not_touch_prior_row asserts the
    byte-level version of the same claim and is green.

    TWO OBSERVATIONS RECORDED RATHER THAN GLOSSED:

    (a) What this evidence does NOT cover: no byte-level before/after snapshot of 08-05's
        field values was captured immediately either side of the 08-06 run. The claim rests
        on the row-count arithmetic above plus the structural argument and the green unit
        test, not on a field-by-field diff of live rows. Stating it because "untouched" in
        the criterion's own wording is stronger than "not added to", and the distinction
        should be visible to anyone auditing this entry.

    (b) 2026-08-05 shows 4 rows here but 3 in the Half A evidence above. That is not drift
        from the 08-06 run — it is the `mkbhd` row, added later on 08-05 by the entry 3
        bogus-handle test (closed 2026-08-05T01:17Z, after Half A's 01:10Z snapshot).
        `mkbhd` was subsequently removed from creators.yaml, leaving a deliberate orphan
        row that is itself the live proof of DATA-04. Separately, 2026-08-04's three rows
        are synthetic seed data backdated after this entry's original evidence was written
        — real collected history begins 2026-08-05.

### 3. A source made to fail is logged with creator, source, and cause, counted in that run's `runs` row, and the remaining creators still complete

expected: A fourth `creators.yaml` entry with a real `id`, a real platform key, and an identifier that does not exist causes that one creator/source to fail without aborting the run. `journalctl` (or the equivalent local log) shows the failure line naming creator, source, and cause; the `runs` row for that run shows the failure counted; and the other configured creators still completed successfully in the same run. The file is reverted afterward.

why_human: Requires deliberately breaking one entry in the real config and observing the real run's log and `runs` row — the D-18 bogus-identifier proof is a live-system behavior, not something a fixture-driven unit test can stand in for.

not_closed_reason: CLOSED 2026-08-05T01:17Z. A real bogus handle met the real YouTube API on the real droplet — the D-18 proof, not the monkeypatched proxy.

result: passed

evidence: |
    Observed by the author on creatorpulse-vps, 2026-08-05.

    Appended a fifth entry with a real id, a real platform key, and an identifier that
    does not exist:
      - id: ghostchannel
        name: Does Not Exist
        sources:
          youtube: "@thishandlewillneverexist0000"

    $ sudo systemctl start creatorpulse.service && sleep 2
    $ sudo journalctl -u creatorpulse.service -n 12 --no-pager

    Aug 05 01:17:40 creatorpulse[9794]: INFO  skip creator=xqc source=twitch reason=no_fetcher_registered
    Aug 05 01:17:40 creatorpulse[9794]: INFO  skip creator=xqc source=tiktok reason=no_fetcher_registered
    Aug 05 01:17:40 creatorpulse[9794]: INFO  skip creator=pokimane source=twitch reason=no_fetcher_registered
    Aug 05 01:17:40 creatorpulse[9794]: INFO  skip creator=pokimane source=tiktok reason=no_fetcher_registered
    Aug 05 01:17:40 creatorpulse[9794]: INFO  skip creator=kaicenat source=twitch reason=no_fetcher_registered
    Aug 05 01:17:40 creatorpulse[9794]: INFO  skip creator=kaicenat source=tiktok reason=no_fetcher_registered
    Aug 05 01:17:40 creatorpulse[9794]: ERROR fetch failed creator=ghostchannel source=youtube
        cause=ChannelNotFound: forHandle='@thishandlewillneverexist0000' matched zero channels
    Aug 05 01:17:40 creatorpulse[9794]: INFO  Run wrote 4 rows with 1 failures
    Aug 05 01:17:40 creatorpulse[9794]: INFO  Run complete in 0.63 seconds

    $ sqlite3 /var/lib/creatorpulse/creatorpulse.db "select * from runs order by id desc limit 1;"
    7|2026-08-05T01:17:40.376131+00:00|2026-08-05T01:17:40.992324+00:00|4|1

    All three halves of the criterion, on one run:
      - logged with creator, source, AND cause
      - counted: failure_count=1 in the runs row
      - remaining creators still completed: 4 rows written, not 0

    Two details worth keeping:

    1. The cause is ChannelNotFound, a named error — not a KeyError. RESEARCH.md and D-18
       both asserted a bogus handle returns HTTP 200 with an EMPTY items list. The fixture
       recorded in 03-01 showed the items key is ABSENT entirely, so `data["items"]` would
       have raised KeyError and produced a confusing 3am log line. The parser was written
       as `data.get("items")` with an explicit raise because of that finding.

    2. The six skip lines are NOT counted as failures — failure_count is 1, not 7. Twitch
       and TikTok are known platforms with no registered fetcher (D-09's two-list split);
       a skip is neither a row written nor a failure. Had the single-list design been
       chosen, this run would have reported 7 failures and the signal would be worthless.

    Reverted afterward with `git checkout creators.yaml`; tree confirmed clean.

### 4. A metric the platform does not expose reads as NULL in the database, never 0 — and the Twitch `followers` column is NULL on every row for exactly this reason

expected: One query proves the Twitch `followers` column is NULL on every Twitch row. A second query shows a real stored `0` somewhere it legitimately belongs (e.g. `views` for an empty archive window, or `failure_count` on a clean run), so NULL and 0 are visibly different values in the same evidence block, not the same value rendered twice.

why_human: Requires reading the real database after a real run against real Twitch/YouTube data; the NULL-vs-0 distinction is exactly the kind of thing that is easy to silently get wrong and needs a human eyeballing actual rows.

not_closed_reason: Split claim, split status — recorded in full rather than glossed over.
**Part A** (real YouTube evidence: three real numbers + two real NULLs in the same row,
`03-05-PLAN.md` Task 3 Entry 4 Part A's two queries) needs a real droplet run and is blocked
by the same access gap as entries 1-3.
**Part B** (the never-COALESCE rule at the storage layer, needing no source/credential/fixture)
is *not* blocked and was run now, for real, on this machine — pasted below, unmodified.
**The Twitch instance** (every Twitch `followers` NULL) is separately blocked on SRC-02
(BLOCKED-EXTERNAL, Twitch 2FA — see `.planning/REQUIREMENTS.md` §Sources) and has no
Twitch rows to query regardless of droplet access, per the author's 2026-08-05 resolution
recorded in `03-05-PLAN.md`'s "Entry 4, resolved by the author" note.
UPDATE 2026-08-05T01:12Z: Part A is now CLOSED on real droplet data (pasted below). Part B was
already closed. The Twitch instance remains open behind SRC-02 and is the only outstanding half.

result: passed_with_caveat

evidence: |
  Part A — real YouTube rows, observed by the author on creatorpulse-vps, 2026-08-05.

  $ sqlite3 -header -column /var/lib/creatorpulse/creatorpulse.db \
      "select creator_id, source, metric_date, followers, views, video_count, likes, is_live from metrics;"
  creator_id  source   metric_date  followers  views       video_count  likes  is_live
  ----------  -------  -----------  ---------  ----------  -----------  -----  -------
  xqc         youtube  2026-08-05   2500000    1902674186  7250
  pokimane    youtube  2026-08-05   6580000    95901586    116
  kaicenat    youtube  2026-08-05   8120000    439490621   288

  followers, views, and video_count carry real non-zero integers. likes and is_live are
  empty — NULL — because the YouTube channels.list endpoint exposes neither. Both facts
  in the same rows, which is the criterion's actual claim: a metric the platform does not
  expose reads NULL, sitting beside metrics that carry real numbers.

  All three rows share metric_date 2026-08-05, computed once per run in UTC (RUN-05).

  Corroborating that this is live data rather than a cached response: pokimane's
  video_count reads 116 here, and read 115 when the API key was verified earlier the same
  day against the same endpoint. A video was published between the two calls.

  Part B — the never-COALESCE rule at the storage layer.
  pytest tests/test_db.py::test_stored_null_and_zero_round_trip_distinct -v
  ============================= test session starts =============================
  platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\loudi\orca\creator-pulse\.venv\Scripts\python.exe
  cachedir: .pytest_cache
  rootdir: C:\Users\loudi\orca\creator-pulse
  configfile: pyproject.toml
  collecting ... collected 1 item

  tests/test_db.py::test_stored_null_and_zero_round_trip_distinct PASSED   [100%]

  ============================== 1 passed in 0.06s ==============================

  STILL OPEN — the Twitch instance only. ROADMAP criterion 4 names "the Twitch followers
  column is NULL on every row" as an instance of the principle. The principle is closed
  above on YouTube evidence. The Twitch instance has no rows to query because SRC-02 is
  BLOCKED-EXTERNAL (Twitch account 2FA — see .planning/REQUIREMENTS.md §Sources), and
  closes when 03-03-PLAN.md executes. One query closes it then:

      sqlite3 <db> "select creator_id, followers from metrics where source = 'twitch';"
      # every followers cell must be empty, never 0

### 5. Every run appends a `runs` row with start, duration, rows written, and failure count, and the bot can read the database while the collector writes without a lock error

expected: The most recent `runs` row shows start time, finish/duration, rows written, and failure count. While the collector is mid-run, a `select count(*) from metrics;` issued from a second shell against the same database completes without a lock error.

why_human: Requires timing a concurrent read against a real in-progress collector run on the real database — not reproducible from an automated test suite that never touches a live run.

not_closed_reason: PARTIAL 2026-08-05T01:12Z. The runs-row half is closed outright on real data. The cross-process concurrency half is NOT claimed — the attempted overlap test is not conclusive evidence and is recorded as such rather than counted as a pass. DATA-05's flagged assumption in `03-05-PLAN.md` stands unresolved.

result: passed_with_caveat

evidence: |
    Observed by the author on creatorpulse-vps, 2026-08-05.

    HALF A — every run appends a runs row with all four fields. CLOSED.

    $ sqlite3 /var/lib/creatorpulse/creatorpulse.db "select * from runs;"
    1|2026-08-05T01:07:05.190751+00:00|2026-08-05T01:07:05.528278+00:00|3|0
    2|2026-08-05T01:10:04.223945+00:00|2026-08-05T01:10:04.765536+00:00|3|0
    3|2026-08-05T01:10:25.713183+00:00|2026-08-05T01:10:26.127195+00:00|3|0
    ...
    7|2026-08-05T01:17:40.376131+00:00|2026-08-05T01:17:40.992324+00:00|4|1

    Every column DATA-03 names: started_at, finished_at (duration derivable), rows_written,
    failure_count. UTC ISO-8601. Row 7 is the deliberate-failure run from entry 3, showing
    the failure count is real and not always zero.

    HALF B — reader and writer concurrent, no lock error. NOT CLOSED. Read this carefully.

    What was attempted:

    $ sudo systemctl start creatorpulse.service & sleep 0.15; \
        sqlite3 /var/lib/creatorpulse/creatorpulse.db "select count(*) from metrics;"; wait
    [1] 9593
    3

    The read returned 3 with no "database is locked" error. That is CONSISTENT with the
    claim but does not PROVE it: `systemctl start` has process-startup overhead before
    Python opens the database at all, so at 150ms the read may have landed after the write
    finished rather than during it. A passing result under a race that may not have raced
    is not evidence. Not counted as a pass.

    What IS verified — the mechanism rather than one timing sample:

    $ sqlite3 /var/lib/creatorpulse/creatorpulse.db "pragma journal_mode; pragma busy_timeout;"
    wal
    0

    journal_mode=wal is persisted in the database file header, so WAL is genuinely active
    for every connection. busy_timeout reads 0 here ONLY because it is a per-connection
    setting that this ad-hoc sqlite3 CLI connection never set — it is stored nowhere. The
    application sets both on every connection at src/creatorpulse/db.py:76-77, in both the
    create=True and create=False branches, and
    tests/test_db.py::test_connect_both_branches_set_wal_and_busy_timeout asserts
    busy_timeout == 5000 on the writer and the reader connection. One pragma persisting and
    the other not is the correct, expected asymmetry.

    To close half B properly, hold a read open across a write from two real processes:

        # shell 1 — hold a read transaction open
        sqlite3 /var/lib/creatorpulse/creatorpulse.db \
          "begin; select count(*) from metrics; select sleep(5);"
        # shell 2, while shell 1 is still open
        sudo systemctl start creatorpulse.service && echo "writer completed with reader open"

    Deferred rather than faked. The bot in Phase 6 is the real second process, and this
    entry closes naturally the first time it queries during a collector run.

## Summary

total: 5
passed: 2
passed_with_caveat: 3
pending: 0

Closed outright: entries 1 and 3.
Closed with a named, recorded caveat: entries 2, 4, and 5.

The three caveats, none of which is a defect and none of which needs work today:

| Entry | Closed | Outstanding | Closes when |
|-------|--------|-------------|-------------|
| 2 | same-day re-run leaves row count unchanged | prior-day rows untouched — no prior day exists yet | the 2026-08-06 timer fires; one query, no setup |
| 4 | the NULL-vs-0 principle, on real YouTube rows | the Twitch `followers` instance — no Twitch rows exist | `03-03-PLAN.md` executes (SRC-02 unblocks) |
| 5 | every run appends a `runs` row, all four fields | cross-process concurrent read — attempted, inconclusive, not claimed | the Phase 6 bot queries during a collector run |

## Gaps

~~**Phase 3 closes PARTIAL as of 2026-08-05: automated coverage green, human-observed run
outstanding.**~~ — **AMENDED 2026-08-06: both gates are now closed.** The two gates in
`03-05-PLAN.md`'s Definition of Green are distinct, and the record below is kept in its
original form with its correction attached rather than rewritten:

1. **Automated coverage — CLOSED.** `ruff format --check .`, `ruff check .`, `mypy src/`
   (strict), and `pytest` all exit 0 (63 tests). The eight test names
   `03-VALIDATION.md`'s Per-Task Verification Map fixes for this plan all exist and pass:
   `test_upsert_same_key_updates_not_duplicates`,
   `test_upsert_different_date_does_not_touch_prior_row`,
   `test_create_false_raises_on_missing_table`,
   `test_stored_null_and_zero_round_trip_distinct` (`tests/test_db.py`);
   `test_one_source_failure_does_not_abort_run`,
   `test_all_rows_from_one_run_share_metric_date`,
   `test_runs_row_written_on_crash`, `test_idempotent_rerun_same_day`
   (`tests/test_collector.py`).
2. ~~**Human-observed real-data run — OUTSTANDING.** This executor had no SSH access to the
   droplet and `/etc/creatorpulse/creatorpulse.env` there still holds blank values, so none of
   the five `03-UAT.md` entries above could be closed against real data. All five stay
   `pending`.~~ — **STALE AS WRITTEN. Superseded 2026-08-05T01:07Z and again 2026-08-06.**

   **Human-observed real-data run — CLOSED.** `YOUTUBE_API_KEY` was provisioned into
   `/etc/creatorpulse/creatorpulse.env` and the author ran the collector on creatorpulse-vps
   the same evening this paragraph was written; the frontmatter `blocked_reason` was updated
   at 01:20Z but this paragraph was not, and it has been contradicting the frontmatter and the
   five entries ever since. All five entries carry real observed evidence. **Nothing here is
   pending.** Current tally: **3 passed outright, 2 passed with a named caveat.**

   Closed since: entry 2's prior-day half, discharged 2026-08-06 by the
   `2026-08-06T00:00:07Z` timer run producing a second real calendar day — its close-later
   command was run and its output recorded in the entry's HALF B addendum.

   Two named caveats remain, both open on their own schedule rather than on work outstanding:
   the Twitch `followers` instance (entry 4, blocked on SRC-02's 2FA wall) and cross-process
   read/write concurrency (entry 5, DATA-05's flagged assumption, deliberately not claimed on
   inconclusive evidence).

   **Phase 3's status is therefore no longer PARTIAL on account of the human gate.** Anyone
   auditing this phase should read the five entries and this list, not the struck paragraph
   above — it is kept visible rather than deleted so the correction itself is auditable.

**SRC-02 (Twitch source) is separately deferred**, not merely a UAT gap: `03-03-PLAN.md` is
written, reviewed, and left unexecuted because Twitch application registration is
BLOCKED-EXTERNAL — the account's 2FA enrolment requires a mobile number and the verification
SMS never arrives, so no client id or secret exists and no Twitch fixtures could be recorded.
See `.planning/REQUIREMENTS.md` §Sources, the SRC-02 note, for the authoritative record. This
is why entry 4's Twitch-followers-NULL instance stays open even once a droplet run happens —
closing it requires SRC-02 to unblock first, which is independent of the droplet-access gap
above.

**What is NOT a gap:** the never-COALESCE principle itself (ROADMAP criterion 4's underlying
claim) is proven today, durably, with no source, no credential, and no droplet — see entry 4's
Part B evidence, `test_stored_null_and_zero_round_trip_distinct`, run and pasted above.
