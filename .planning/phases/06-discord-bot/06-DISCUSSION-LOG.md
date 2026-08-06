# Phase 6: Discord Bot - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-06
**Phase:** 6-discord-bot
**Areas discussed:** Digest ownership & timing, Failure reporting depth, Digest content & ±20% flag, Slash commands & build order, Process lifecycle / config / testability

**Note on format:** questions were batched 4-per-turn rather than asked one at a time (default mode's
single-question cadence), a deliberate deviation for the clock — roughly 13 hours to the interview
with Phase 7 still outstanding. The author was told at the time.

---

## Digest ownership & timing

### Q1 — Who actually posts the daily digest?

| Option | Description | Selected |
|--------|-------------|----------|
| Bot, on its own task loop | `discord.ext.tasks.loop(time=...)` inside the long-lived bot. Matches BOT-01's wording, no second unit. No catch-up if the process is down. | ✓ |
| Collector posts it at end of run | Zero scheduling, causally tied to the run. Collides with criterion 3's "earlier than the scheduled digest". | |
| Second systemd timer, one-shot digest | Bot stays reactive, `Persistent=true` catch-up. Costs a third human-built unit+timer under the clock. | |

**User's choice:** Bot, on its own task loop → D-01

### Q2 — Which credential carries each message?

| Option | Description | Selected |
|--------|-------------|----------|
| Split: bot token for digest, webhook for alert | Each process uses the credential it already holds. Two credentials, one channel. | ✓ |
| Webhook for everything | One credential, testable without a gateway. Bot then holds a token used only for slash commands. | |
| Bot token for everything | Needs an invented collector→bot IPC channel. | |

**User's choice:** Split → D-02

### Q3 — When does the digest fire?

| Option | Description | Selected |
|--------|-------------|----------|
| 08:15 Asia/Manila | 15 min after the collector, well ahead of the 09:00 watchdog. Three schedules in narratable order. | ✓ (Claude) |
| 09:00 Asia/Manila | One less number, but collides with the watchdog. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected 08:15 → D-03

### Q4 — Digest on a day the collector didn't run?

| Option | Description | Selected |
|--------|-------------|----------|
| Post anyway with a staleness banner | Silence is indistinguishable from "the digest didn't fire". Pre-builds Phase 7 criterion 2. | ✓ (Claude) |
| Stay silent, let the watchdog handle it | Avoids a duplicate alert 45 min earlier. Silence is ambiguous. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected post-with-banner → D-04. Claude additionally
decided the no-catch-up rule (D-05) as the direct consequence of choosing a task loop in Q1.

---

## Failure reporting depth

### Q1 — How do failure details reach the digest?

| Option | Description | Selected |
|--------|-------------|----------|
| New `run_failures` table | Self-migrates via the existing `CREATE TABLE IF NOT EXISTS` DDL. Needs `write_run_row` to return lastrowid and the collector to accumulate failures. | ✓ |
| Text summary column on `runs` | Smaller diff, but needs a hand `ALTER TABLE` on the live DB and produces an unqueryable blob. | |
| Persist nothing — collector alerts in-process | Zero schema change. Digest could then only report a count, not name failures. | |

**User's choice:** New `run_failures` table → D-06

### Q2 — What triggers the immediate failure alert?

| Option | Description | Selected |
|--------|-------------|----------|
| Any run with `failure_count > 0` | One rule, no cross-run state. | ✓ (Claude) |
| Only after N consecutive failing days | Suppresses blips; also suppresses the one-day outage. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected any-failure → D-07

### Q3 — One alert per run, or per failed source?

| Option | Description | Selected |
|--------|-------------|----------|
| One message per run, listing all failures | An API outage produces one message, not N. Alert and `runs` row can't disagree. | ✓ (Claude) |
| One message per failed (creator, source) pair | Lands at the moment of failure; floods the channel on an outage. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected per-run → D-08

### Q4 — Should a Sheets sync failure alert too?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — from the existing `cli.py:90` except block | One line added to the existing log-then-re-raise. PITFALLS §18(d). | ✓ (Claude) |
| No — systemd + the 09:00 watchdog cover it | Keeps one alert caller. Nobody watches `systemctl` at 08:00. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected yes → D-09

---

## Digest content & ±20% flag

### Q1 — Rank and flag on what?

| Option | Description | Selected |
|--------|-------------|----------|
| Rank by \|% change\|, show both numbers | Makes "top movers" meaningful across creators of different size. BOT-02's threshold is a percentage anyway. | ✓ (Claude) |
| Rank by absolute Δ, flag on percent | Matches Sheet column E ordering; largest channel permanently top. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected percent → D-10

### Q2 — How many rows?

| Option | Description | Selected |
|--------|-------------|----------|
| All rows, sorted by \|% change\| | 3 rows today, 6 with Twitch. A cap that never triggers is dead code. | ✓ (Claude) |
| Top 5 plus a count of the rest | Bounded forever; invisible and untested at three rows. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected all rows → D-11

### Q3 — No baseline, or `prev_views = 0`?

| Option | Description | Selected |
|--------|-------------|----------|
| `—` for delta, no percent, never flagged | Same placeholder as the Sheet. Division by zero is not a 10,000% gain. | ✓ (Claude) |
| Omit those rows | Shorter message; a vanished creator looks like an unconfigured one. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected `—` → D-12

### Q4 — Where does the delta/baseline query live?

| Option | Description | Selected |
|--------|-------------|----------|
| Move it to `db.py`, both import it | One definition of "yesterday" shared by Sheet and Discord; keeps gspread out of the bot. Touches a finished module + tests. | ✓ |
| Bot imports from `sheets.py` as-is | Zero refactor; the bot would pull in gspread to read SQLite. | |
| Bot writes its own query | Two baseline definitions kept in sync by hand. | |

**User's choice:** Move to `db.py` → D-13 (rated **costly** — the only non-reversible-by-default
decision in this phase)

---

## Slash commands & build order

### Q1 — How do BOT-04/05 get planned?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate plan, droppable whole | The cut becomes one file deletion rather than a mid-execution scramble. | ✓ (Claude) |
| One plan, everything together | Fewer files; cutting means editing a plan under pressure. | |
| Cut BOT-04/05 now | Buys hours for Phase 7; Phase 6 would close PARTIAL against criterion 4. | |

**User's choice:** *"you decide im lockin"* → Claude selected separate droppable plan → D-14

### Q2 — How does `/creator <name>` resolve a name?

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive exact slug, list on miss | No ambiguity rule to defend; no path to silently answering about the wrong creator. | ✓ |
| Autocomplete on the creator list | Wrong names unpickable, good demo; extra API surface, DB read per keystroke. | |
| Substring / fuzzy match | Forgiving; ambiguity rules for three distinct names. | |

**User's choice:** Case-insensitive exact slug → D-15 (autocomplete recorded as a deferred idea, not
a rejection on merit)

### Q3 — What is "recent trend"?

| Option | Description | Selected |
|--------|-------------|----------|
| Last 7 daily rows: date, views, Δ | One indexed read, `LIMIT 7`. Shows two rows today; fills in by itself. | ✓ (Claude) |
| Today vs yesterday only | Identical to the digest's per-row content. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected 7 days → D-16

### Q4 — Does `/status` render a verdict?

| Option | Description | Selected |
|--------|-------------|----------|
| Numbers plus an OK/STALE verdict | 26h threshold, matching the Apps Script watchdog. Phase 7 criterion 2 then rehearses instead of implements. | ✓ (Claude) |
| Raw numbers only | Reader draws their own conclusion; Phase 7 adds the verdict under more pressure. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected verdict → D-17

---

## Process lifecycle, config & testability

*(Area chosen by Claude at the author's request — "you decide what areas need to discuss further".)*

### Q1 — Where do the bot's secrets live?

| Option | Description | Selected |
|--------|-------------|----------|
| Same `/etc/creatorpulse/creatorpulse.env` | Collector needs the webhook URL anyway, so a split wouldn't isolate Discord secrets. One file already proven on the droplet. | ✓ |
| Its own `/etc/creatorpulse/bot.env` | Token isolated from the collector; two files, and the webhook is still shared. | |
| You decide | | |

**User's choice:** Shared env file → D-18

### Q2 — Missing `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_ID` at startup?

| Option | Description | Selected |
|--------|-------------|----------|
| Fail loudly at startup, before connecting | Named error saying which variable; non-zero exit; systemd marks failed. Matches `SheetNotShared` / Phase 5 D-13. | ✓ |
| Connect anyway, degrade | Green in `systemctl`, posts nothing — the failure this project keeps refusing. | |
| You decide | | |

**User's choice:** Fail loudly → D-19

### Q3 — What does pytest actually cover?

| Option | Description | Selected |
|--------|-------------|----------|
| Pure formatters; discord.py plumbing untested, stated out loud | Same shape as `test_sheets.py`. Human gate proves the plumbing. | ✓ (Claude) |
| Mock discord.py and test handlers too | Hours of mocking on interview day for coverage the live demo provides. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected pure formatters → D-20

### Q4 — Catch-up digest after a missed slot?

| Option | Description | Selected |
|--------|-------------|----------|
| No catch-up — next day | Catch-up needs persisted state and restart-loop suppression, for a gap three surfaces already cover. | ✓ (Claude) |
| Catch up on startup if today's hasn't posted | Digest never silently missing; new state, spam risk. | |
| You decide | | ✓ (user) |

**User's choice:** "You decide" → Claude selected no catch-up → D-05

---

## Claude's Discretion

The author answered "you decide" to eleven of twenty questions, and "you decide im lockin" to build
order. All twelve were resolved as recorded decisions with rationale in CONTEXT.md, not left open:

| Question | Claude's call | Decision |
|---|---|---|
| Digest fire time | 08:15 Asia/Manila | D-03 |
| Stale-day behaviour | Post with a staleness banner | D-04 |
| Missed-slot catch-up | None | D-05 |
| Failure alert trigger | Any run with `failure_count > 0` | D-07 |
| Alert shape | One message per run | D-08 |
| Sheets sync failure alert | Yes, from the existing except block | D-09 |
| Ranking metric | Percent change, both numbers shown | D-10 |
| Row count | All rows, no cap | D-11 |
| No-baseline rendering | `—`, no percent, no flag | D-12 |
| BOT-04/05 build order | Separate droppable final plan | D-14 |
| Trend window | Last 7 daily rows | D-16 |
| `/status` verdict | Numbers plus OK/STALE at 26h | D-17 |
| Test coverage boundary | Pure formatters only, gap stated | D-20 |

Genuinely left open to the planner/implementer: module layout inside `src/creatorpulse/`, exact
message wording, plain content vs embed, `discord.Client` + `CommandTree` vs `commands.Bot`, where
guild-scoped sync runs, `run_failures` column types, and whether the 26-hour threshold is one shared
constant.

## Deferred Ideas

- `app_commands` autocomplete on `/creator` — declined by D-15, good demo, extra surface
- Top-N cap on the digest — declined by D-11 as speculative at 3–6 rows
- Catch-up digest after a missed slot — declined by D-05, needs persisted state
- Separate `bot.env` for the bot token — declined by D-18, fails to isolate anyway
- Mocking discord.py to test callbacks — declined by D-20 on the clock, gap stated not hidden
- `OnFailure=` on the collector unit — systemd-native alternative to D-09, and human-built regardless
- Consecutive-day failure alerting — declined by D-07, suppresses the outage worth knowing about
- A second Discord channel for ops alerts — already declined by Phase 5 D-16, not reopened

## Raised, out of phase

- `deploy/creatorpulse.service`, `deploy/creatorpulse.timer`, and `docs/deploy.md` are absent from
  `git ls-files` despite Phase 2 D-12/D-13 declaring them committed. Phase 2 debt for Phase 7 to
  close, and human work by Hard Rule 1 — the agent must not create them.
</content>
