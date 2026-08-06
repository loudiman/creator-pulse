---
status: partial
phase: 06-discord-bot
source: [06-01-SUMMARY.md, 06-02-SUMMARY.md, 06-03-SUMMARY.md, 06-05-SUMMARY.md, 06-VALIDATION.md, ROADMAP.md, STATE.md]
started: 2026-08-06T17:20:00+08:00
updated: "2026-08-06T17:20:00+08:00"
blocked_reason: "PARTIAL as of 2026-08-06, authored during 06-04 with the interview at 20:00 the
  same day. Entry 1 is passed_with_caveat (the forced digest is closed on 06-01's checkpoint
  evidence; the unattended 08:15 fire is not yet observed). Entries 2, 3, and 4 are pending —
  each is proven by unit tests but not yet observed live, for reasons specific to each entry (see
  each entry's not_closed_reason). Entry 5 is pending on both halves by design: the systemd
  install is a human step this plan does not perform, and the intents explanation is left for the
  author to write unaided, exactly as Phase 5's equivalent (05-UAT.md entry 7) still is. See
  ## Open Items for every close-later command."
---

## Current Test

[testing complete for what this plan can close from existing evidence — four of five entries left
PENDING or CAVEAT rather than fabricated; see ## Open Items]

## Tests

### 1. A daily digest posts itself to the channel on schedule, listing top movers and any failures from that run — with no human triggering it (BOT-01, ROADMAP criterion 1)

expected: Two halves, both required by the criterion's own wording. HALF A — the forced proof:
`creatorpulse bot --digest-now` posts one real digest message into the real channel, built from
real database rows. HALF B — the unforced proof, which is what "with no human triggering it"
actually asks for: the digest fires on its own at 08:15 Asia/Manila with nobody running a command.

why_human: requires a live gateway connection and a real channel; the fixtures-only rule forbids
network calls inside the test suite (06-VALIDATION.md Manual-Only Verifications row 1).

not_closed_reason: HALF A — CLOSED, see evidence, lifted verbatim from 06-01-SUMMARY.md's Task 3
checkpoint (closed live by the author 2026-08-06T16:38 Asia/Manila). HALF B — PENDING. Only the
forced `--digest-now` path has been observed; the natural, unattended 08:15 fire has not yet
happened at the time this file was written. Close-later: watch the real channel at or after 08:15
Asia/Manila with the bot process left running and nobody typing a command, and paste the posted
message plus its timestamp here.

result: passed_with_caveat

evidence: |
    HALF A — forced proof, CLOSED. Lifted verbatim from 06-01-SUMMARY.md's checkpoint (author
    observed live, 2026-08-06T16:38 Asia/Manila; the executor did not attempt this and was not
    authorized to close it).

    Console:

        2026-08-06 16:38:10,383 INFO discord.client: logging in using static token
        2026-08-06 16:38:12,309 INFO creatorpulse: resolved digest channel id=1534659531517460584
        2026-08-06 16:38:14,149 INFO discord.gateway: Shard ID None has connected to Gateway

    Message posted by `Creator Pulse Bot APP` at 4:38 PM:

        CreatorPulse digest — 2026-08-06
        kaicenat / youtube — 439,535,493 views (Δ +0, +0.0%)
        pokimane / youtube — 96,004,740 views (Δ +0, +0.0%)
        xqc / youtube — 1,903,001,878 views (Δ +0, +0.0%)
        mkbhd / youtube — 5,517,991,783 views (Δ —)

    Matches the predicted output exactly, including sort order. The three `+0.0%` rows are
    correct — 08-05 and 08-06 `views` are byte-identical (STATE.md data-shape note), so zero
    movement is the honest rendering, not a defect. `mkbhd` renders `—` and sorts last: DATA-04
    and D-12 proving themselves against real data, live.

    Config-fails-loudly evidence, same checkpoint, same source (D-19): an empty
    `DISCORD_CHANNEL_ID` raised `DiscordConfigError: DISCORD_CHANNEL_ID is not set`, and a
    non-numeric value raised `DiscordConfigError: DISCORD_CHANNEL_ID must be an integer, got
    'not-a-number'`. Neither run emitted `logging in using static token` — config is validated
    before anything connects. No token value appeared in any output.

    HALF B — unforced proof, PENDING. No natural 08:15 Asia/Manila fire has been observed yet.
    Not fabricated here.

### 2. A creator whose day-over-day delta exceeds ±20% is visibly flagged in that digest (BOT-02, ROADMAP criterion 2)

expected: A real posted digest message shows at least one row prefixed with the 🚨 flag because
that row's `|percent change|` strictly exceeds 20%.

why_human: the flag's computation and rendering are unit-tested; whether a *real* digest message
actually shows a flagged row can only be read off a real posted message — nothing in the test
suite posts to Discord (06-VALIDATION.md Manual-Only Verifications row 2).

not_closed_reason: PENDING. All three real creators (kaicenat, pokimane, xqc) moved exactly 0%
between 2026-08-05 and 2026-08-06 — see entry 1's evidence above — because YouTube's `viewCount`
was served from a cache that had not rolled over between the two collector runs (STATE.md
data-shape note). This is a property of the data source, not a code gap: real data simply did not
move enough to cross the threshold, so no flag fired live, and none is claimed to have. The flag
logic itself is proven by four boundary unit tests, either side of ±20%, plus a fifth test proving
the flag reads the unrounded float rather than the rounded display text (06-03-SUMMARY.md coverage
ids D1/D2). Close-later, either path: (a) wait for real data to cross ±20% naturally and screenshot
the flagged row in a live digest, or (b) run a **forced proof**, labelled as forced exactly as
Phase 5 D-08 labelled the forced watchdog run — temporarily edit one 2026-08-05 `views` value in
`creatorpulse.db` so the 2026-08-06 delta crosses ±20%, run `creatorpulse bot --digest-now`,
screenshot the flagged 🚨 row, then restore the edited value with the same `sqlite3` statement run
in reverse.

result: pending

evidence: |
    What IS proven — 06-03-SUMMARY.md, coverage id D1 (four named boundary tests, one per side):
      tests/test_bot.py::test_digest_flag_pair_at_exactly_positive_threshold_is_not_flagged
      tests/test_bot.py::test_digest_flag_pair_one_step_over_positive_threshold_is_flagged
      tests/test_bot.py::test_digest_flag_pair_at_exactly_negative_threshold_is_not_flagged
      tests/test_bot.py::test_digest_flag_pair_one_step_over_negative_threshold_is_flagged
    and coverage id D2:
      tests/test_bot.py::test_digest_flag_reads_the_unrounded_float_not_the_rounded_display_text
    All five pass (139/139 full suite green at 06-03's close).

    What is NOT proven — no live digest has ever shown a flagged row, because no real delta has
    crossed ±20% since real data collection began (2026-08-05). Stated plainly rather than
    claimed: the flag exists and is correct by unit test; it has not fired in the wild yet.

### 3. A run that records failures produces its own immediate Discord message, distinct from and earlier than the scheduled digest (BOT-03, ROADMAP criterion 3)

expected: Lifted verbatim from 06-VALIDATION.md's Manual-Only Verifications table. Put a bogus
handle in `creators.yaml` — the same technique that produced the `mkbhd` orphan row — run the
collector by hand, watch the alert land immediately, then watch the 08:15 digest arrive separately
listing that failure. Both messages, in order, in one screenshot. `creators.yaml` must be restored
afterward with `git checkout creators.yaml`. Note that the `mkbhd` row already in the database is
itself pointable proof of DATA-04, independent of this entry.

why_human: this is an ordering claim across two separate processes (the one-shot collector versus
the long-lived bot) and a real webhook POST; no fixture-only test suite can assert that message A
landed before message B in a real Discord channel (06-VALIDATION.md Manual-Only Verifications row
3).

not_closed_reason: PENDING — not yet run. 06-02-SUMMARY.md's own coverage table records this exact
claim as `id: D5`, `human_judgment: true`, `verification: []`, with the note: "carried forward to
06-UAT.md by 06-04 with the forced proof CONTEXT names." That forward-carry is this entry. Both
webhook call sites (D-08's per-run alert, D-09's Sheets-sync-failure alert) and the alert
formatter are unit-tested, but the cross-process ordering itself has not been observed. Close-later:
add a bogus handle to `creators.yaml` (the `mkbhd`-style technique from `03-UAT.md` entry 3), run
`creatorpulse collect` by hand, confirm the failure alert lands in the channel immediately, then
either wait for or force the 08:15 digest and confirm it separately lists that same failure — both
messages, in order, one screenshot — then run `git checkout creators.yaml` to restore the file.

result: pending

evidence: |
    What IS proven — 06-02-SUMMARY.md coverage ids D1-D4, all unit-tested and green:
      D1: one run_failures row per failure, attributed to the correct run_id
        (tests/test_db.py::test_write_run_row_returns_rowid_not_none,
         tests/test_db.py::test_write_run_failures_round_trip_matches_run_id,
         tests/test_collector.py::test_one_source_failure_produces_one_run_failure_with_cause_and_message)
      D2: one alert per failing run, sent after collect_once returns, zero POST calls on a clean run
        (tests/test_bot.py::test_run_collect_with_one_failure_calls_alert_path_exactly_once_and_still_returns_0,
         tests/test_bot.py::test_run_collect_with_zero_failures_does_not_call_the_alert_path)
      D3: a Sheets-sync failure alerts too, and a broken webhook never swallows the real exception
        (tests/test_bot.py::test_run_collect_sheets_failure_and_broken_webhook_still_propagates_sheet_not_shared,
         tests/test_bot.py::test_post_alert_whose_post_raises_connection_error_logs_and_returns_without_raising)
      D4: no log record or alert body ever contains the webhook URL value
        (tests/test_bot.py::test_post_alert_never_logs_the_webhook_url_value)

    What is NOT proven — the live, cross-process ordering itself (alert first, digest second,
    both real, in one channel) has not been observed and is not claimed here.

### 4. `/creator <name>` returns that creator's current numbers and recent trend, and `/status` returns last run time, duration, rows written, and failure count — both answered from the database, in-channel (BOT-04, BOT-05, ROADMAP criterion 4)

expected: `06-05-PLAN.md` still exists and its plan executed (`06-05-SUMMARY.md`, status
`complete`) — this criterion was not cut. Typing `/creator kaicenat` and `/status` into the real
Discord guild produces in-channel replies matching `build_trend_text()` / `build_status_text()`'s
rendering, read live from the real database.

why_human: slash-command dispatch needs a real gateway connection and a real guild; the formatters
are unit-tested against a temporary SQLite database, but no interaction has been sent through the
actual Discord client and no reply has been read off the real channel (06-VALIDATION.md
Manual-Only Verifications row 4).

not_closed_reason: PENDING. 06-05 was executed, not cut — both commands are implemented,
registered on the guild-scoped command tree, and covered by 24 new unit tests
(06-05-SUMMARY.md coverage ids D1-D6). Their exact rendered output against the live database
(`creatorpulse.db`, real collected rows for kaicenat/pokimane/xqc/mkbhd) was already captured by
calling the pure formatters directly — the same technique 06-01's Task 3 checkpoint and 06-03 used
— and is quoted below verbatim from 06-05-SUMMARY.md. What has not happened is typing either
command into the real guild and reading Discord's own reply. Close-later: with `creatorpulse bot`
running and connected, type `/creator kaicenat` and `/status` in the guild, confirm the replies
match the verbatim text already recorded below, and paste the live output here.

result: pending

evidence: |
    Verbatim rendered command text, captured live against the real dev-machine database by
    calling build_trend_text()/build_status_text() directly (06-05-SUMMARY.md, "Verbatim rendered
    command text for 06-04's 06-UAT.md" section) — not yet observed as an actual Discord reply.

    `/creator kaicenat` (mixed-case input, matches the stored slug `kaicenat`):

        Recent trend for kaicenat:
        kaicenat / youtube
          2026-08-06: 439,535,493 views (Δ +0)
          2026-08-05: 439,535,493 views (Δ -655,464,507)
          2026-08-04: 1,095,000,000 views (Δ —)

    `/creator nobody` (unknown name):

        No creator named 'nobody' — known creators: kaicenat, mkbhd, pokimane, xqc

    `/status` (against the live database's newest run):

        Last run finished 2026-08-06T00:00:07.958346+00:00 — OK
        Duration: 0.4s
        Rows written: 3
        Failures: 0

    Backing unit tests (06-05-SUMMARY.md coverage ids D1-D6, all pass): 14 `/creator` tests
    covering exact case-insensitive match, unknown-name reply, the seven-row-per-source window,
    a SQL-injection-shaped name probe; 10 `/status` tests covering the no-runs-row case, the
    26.0h/26h1min staleness boundary, duration rendering, and failure-naming.

### 5. The bot survives a reboot as its own systemd service, independent of the collector, and the author can explain which intents it requests and why none of them are privileged (BOT-06, BOT-07, ROADMAP criterion 5)

expected: Two halves, both required. HALF A — after the author installs and enables
`deploy/creatorpulse-bot.service` and reboots the droplet, `systemctl status creatorpulse-bot`
shows `active (running)`, independent of `creatorpulse.service`'s own lifecycle. HALF B — the
author writes, unaided, in their own words, which intents the bot requests and why none of them
are privileged.

why_human: HALF A requires the droplet and systemd, and is explicitly a human step under
`.claude/CLAUDE.md` Hard Rule 1 and 06-CONTEXT.md D-21 — no task in this plan may run `systemctl`
in any form. HALF B is a human knowledge check, unfakeable by any test (06-VALIDATION.md
Manual-Only Verifications row 6).

not_closed_reason: PENDING, both halves, by design — neither is closeable by the agent.

    HALF A: `deploy/creatorpulse-bot.service` is committed but deliberately not installed.
    Installing it before `creatorpulse bot` became real (this phase) would have produced a
    ten-second `Restart=on-failure` loop against the exit-3 stub (STATE.md Blockers/Concerns).
    Now that `creatorpulse bot` is implemented, installation is the author's step; this plan does
    not perform it. Close-later, exact commands for the author to run (none executed here):

        sudo cp deploy/creatorpulse-bot.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable --now creatorpulse-bot
        sudo systemctl status creatorpulse-bot
        sudo reboot
        # after reboot:
        sudo systemctl status creatorpulse-bot
        sudo journalctl -u creatorpulse-bot -n 20 --no-pager

    HALF B: left blank on purpose. See `COVERAGE.md`'s intents rows (the `Intents.default()`
    `INTEGRATE` row and the three privileged-intent `OPT-OUT` rows) as the place to check the
    answer *afterward*, not as the source to copy from — an entry the author closes by reading
    their own COVERAGE.md proves nothing. Phase 5's equivalent (`05-UAT.md` entry 7) is still
    PENDING; this one must not quietly join it.

result: pending

evidence: |
    HALF A — not performed, not claimed. `git status --porcelain deploy/` is empty; no unit file
    was created, edited, or reformatted by this plan.

    HALF B — the author's unaided write-up goes here. Not pre-filled.

    > [Author writes, with bot.py closed and no notes open: which intents does
    > CreatorPulseBot request, and why is none of them privileged?]

## Open Items

Five items remain open at this plan's close, in criterion order. All are recorded here rather
than omitted, following the precedent `03-UAT.md` and `05-UAT.md` already set for entries that
cannot close on the day this file is written.

1. **Entry 1, HALF B — the natural, unattended 08:15 Asia/Manila digest fire.** Not yet observed;
   only the forced `creatorpulse bot --digest-now` path has run. Close-later: watch the real
   channel at or after 08:15 Asia/Manila with the bot process already running and nobody typing a
   command; paste the posted message and its timestamp into entry 1's evidence block.

2. **Entry 2 — the ±20% flag firing in a real, live digest.** All three real creators moved
   exactly 0% between 2026-08-05 and 2026-08-06 (YouTube view-count cache had not rolled over), so
   no flag has fired live. Close-later: wait for real data to cross ±20%, or run the labelled
   forced proof — temporarily edit one 2026-08-05 `views` value in `creatorpulse.db`, run
   `creatorpulse bot --digest-now`, screenshot the flagged row, restore the value.

3. **Entry 3 — the failure alert landing immediately, before and separate from the digest.** Not
   yet run. Close-later: add a bogus handle to `creators.yaml`, run `creatorpulse collect` by
   hand, confirm the alert lands immediately, confirm the 08:15 digest separately lists the same
   failure, one screenshot with both messages in order, then `git checkout creators.yaml`.

4. **Entry 4 — `/creator` and `/status` answering in the real guild.** The formatters and their
   exact output against the live database are already proven and quoted verbatim in this file;
   only the live Discord round trip is missing. Close-later: with `creatorpulse bot` running,
   type `/creator kaicenat` and `/status` in the guild and paste the live replies into entry 4's
   evidence block.

5. **Entry 5, HALF A — installing `deploy/creatorpulse-bot.service` and surviving a reboot.**
   Deliberately not performed by this plan (Hard Rule 1, D-21). Close-later: the exact `systemctl`
   commands are listed in entry 5's `not_closed_reason` above; the author runs them on the
   droplet.

6. **Entry 5, HALF B — the author's unaided intents explanation.** Deliberately left blank. Not
   closeable by the agent by construction — see the prohibition in `06-04-PLAN.md`. Close-later:
   the author writes the answer into entry 5's evidence block, in their own words, with `bot.py`
   closed, mirroring Phase 5's still-open `05-UAT.md` entry 7 so this one does not join it
   silently.

## Summary

total: 5
passed: 0
passed_with_caveat: 1
pending: 4

| Entry | Requirement | Result | Note |
|-------|-------------|--------|------|
| 1 | BOT-01 | passed_with_caveat | Forced digest CLOSED on 06-01's live checkpoint evidence; natural 08:15 fire still open |
| 2 | BOT-02 | pending | Flag logic proven by 5 unit tests; no live delta has crossed ±20% yet (real data moved 0%) |
| 3 | BOT-03 | pending | Both webhook call sites unit-tested; cross-process ordering not yet observed live |
| 4 | BOT-04, BOT-05 | pending | Commands implemented, tested, and their exact output captured directly; no live guild interaction yet |
| 5 | BOT-06, BOT-07 | pending | Systemd install is a human step, not performed; author's intents write-up deliberately left blank |

## Gaps

**Phase 6 closes PARTIAL as of 2026-08-06, authored during `06-04` ahead of the same-day
interview.** This is not a capability gap — every requirement this plan can prove without a human
present (BOT-01 through BOT-05's code and formatters, BOT-06's config validation, BOT-07's
`Intents.default()`-only connection) is proven by a green four-command gate (166 tests,
`ruff format --check .` / `ruff check .` / `mypy src/` all clean) and, for BOT-01, by one real
observed digest. What remains open in every case above is a *live, human-observed* proof this
plan's tasks are explicitly prohibited from performing themselves (BOT-06's systemd install,
BOT-07's Developer Portal work, already done by hand) or that had not yet had the chance to happen
naturally at the time this file was written (the 08:15 fire, a live ±20% delta, a live ordering
screenshot, a live slash-command round trip).

**Do not read entry 1's `passed_with_caveat` as fully closing ROADMAP criterion 1** — the
criterion's own wording, "with no human triggering it," is exactly the half that stays open until
the natural fire is observed. The forced half proves the code path works; it does not prove the
schedule does.

**Carried forward from Phase 5, not repeated here:** `05-UAT.md` entry 7 (the author's unaided
`onEdit`/webhook explanation) is separately still PENDING. This file's entry 5 HALF B is the
Phase 6 analogue and is deliberately written the same way — left blank, not pre-filled — so it
does not silently join Phase 5's still-open item without being named as its own open item.
