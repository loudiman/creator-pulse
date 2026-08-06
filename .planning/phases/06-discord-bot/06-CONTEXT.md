# Phase 6: Discord Bot - Context

**Gathered:** 2026-08-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 makes Discord the place the numbers show up and the place you ask about them. Seven
requirements: **BOT-01** (daily digest of top movers and that run's failures), **BOT-02** (±20%
day-over-day flag), **BOT-03** (immediate failure alert, distinct from and earlier than the
digest), **BOT-04** (`/creator <name>`), **BOT-05** (`/status`), **BOT-06** (own systemd service —
*unit file human-built*), **BOT-07** (Developer Portal registration, intents, scopes, invite URL —
*human-built*).

**The phase has two processes, and the split is the phase's central structural fact.** The
collector is one-shot and dies; the bot is long-lived and stays connected. Work is assigned to
whichever process is alive when the work needs doing: the collector owns the *immediate* failure
alert because it is the only thing awake at the moment a source fails; the bot owns the *scheduled*
digest because it is the only thing awake 15 minutes later. Neither reaches into the other. They
meet at the SQLite file, where the collector is the only writer.

**Ownership — this is not the Phase 5 exception repeating itself.** Phase 5 D-01 relaxed the
Apps Script prohibition for one dated, scoped reason. `.claude/CLAUDE.md` Hard Rules **1 (VPS
provisioning and systemd units) and 3 (Discord Developer Portal)** were explicitly left untouched by
that amendment, and both bind this phase in full:

| Artifact | Owner | Agent may |
|---|---|---|
| `src/creatorpulse/bot.py` and every other Python file | agent | write |
| The bot's `.service` unit file | **human** | not write, not edit, not draft, not "fix" |
| Bot registration, intents, scopes, invite URL in the Developer Portal | **human** | not perform |
| `.env.example` additions naming the new variables | agent | write (names only, never values) |

The agent may state *what* the unit needs (which command, which `EnvironmentFile`, that it wants
`Restart=on-failure`) as prose in a plan or in `06-UAT.md`. It may not produce the file. Phase 2
D-12 is the binding text and it says "including when asked."

**Not in this phase:** the README and the build journal (Phase 7, OPS-08/09); the cold-start
narrated rehearsal (Phase 7); any change to the Dashboard column layout (frozen by Phase 4 D-03 and
now depended on by Phase 5's triggers); the Apps Script watchdog (Phase 5, done, and deliberately
*not* replaced by this bot — see D-04's note).

**Repo gap noticed during scout, not caused by this phase:** `git ls-files` shows no `deploy/`
directory and no `docs/deploy.md`, though Phase 2 D-12 and D-13 both say those are committed
artifacts. Phase 2's units appear to exist only on the droplet. This phase was supposed to add a
*second diffable* unit alongside the first; there is currently no first. Flagged for the author —
this is Phase 2/Phase 7 work, and the agent cannot close it (writing those files is exactly what
Hard Rule 1 forbids).

</domain>

<decisions>
## Implementation Decisions

### Who Posts What, and When

- **D-01:** **The bot posts the daily digest from its own `discord.ext.tasks.loop`.** Not the
  collector, not a second systemd timer. The bot is already a long-lived process that must exist
  anyway for BOT-04/05, so the schedule costs one decorator; `discord.ext.tasks` ships with
  discord.py and adds no dependency. Rejected: the collector posting the digest at end of run —
  simplest of the three, but it puts the digest and the failure alert in the same second, and
  ROADMAP criterion 3 requires the alert to be *"distinct from and earlier than the scheduled
  digest."* Also rejected: a second systemd timer running a one-shot `creatorpulse digest` — it
  would gain `Persistent=true` catch-up, but it costs a third human-built unit+timer pair under the
  clock, and BOT-01 says the *bot* posts the digest.
  **Known cost, accepted:** unlike the collector's timer, a task loop has no catch-up. If the bot
  process is down at 08:15 the digest is missed outright. D-05 accepts this rather than building
  state to paper over it.
  — **Reversibility:** reversible.

- **D-02:** **Split transport: the bot posts with its bot token, the collector posts to the Phase 5
  webhook.** The digest goes out via `channel.send()` on the already-connected gateway client. The
  collector — which has no bot token and must not acquire one — POSTs its failure alert to the
  `DISCORD_WEBHOOK_URL` established by Phase 5 D-16, using `requests`, already a dependency. Each
  process uses the credential it already holds and needs no second one. Two credentials, **one
  channel** (Phase 5 D-16 stands). Rejected: webhook for everything (the bot would hold a token it
  uses only for slash commands, and posting through a webhook from inside a connected client is
  hard to defend); bot-token for everything (needs an invented IPC channel from collector to bot).
  — **Reversibility:** reversible.

- **D-03:** **The digest fires 08:15 Asia/Manila.** *(Claude's discretion — author answered "you
  decide".)* The collector fires 08:00 (Phase 2 D-09) and completes in seconds; 15 minutes is
  comfortable margin over a slow or retried run. It also orders the three scheduled things in the
  system into a story that can be narrated in one breath: **08:00 collect** (systemd timer, on the
  droplet) → **08:15 digest** (task loop, in the bot) → **09:00 watchdog** (Apps Script trigger, on
  Google's infrastructure, deliberately off-box per Phase 5 D-05). Rejected: 09:00, which collides
  with the watchdog and can drop two messages into the same channel seconds apart.
  — **Reversibility:** reversible — a constant.

- **D-04:** **On a stale day the digest posts anyway, led by a staleness banner.** *(Claude's
  discretion.)* If the newest `runs` row is older than the freshness threshold, the digest opens
  with `⚠ last run: <timestamp> — STALE` and then shows the numbers it has. Rejected: staying
  silent and letting the 09:00 watchdog handle it — silence is indistinguishable from "the digest
  didn't fire", which is the failure mode this project has now refused four separate times
  (PITFALLS.md §18(d), Phase 3 D-16, Phase 4 D-07, Phase 5 D-13). It is also 45 minutes earlier
  than the watchdog. **The watchdog is not made redundant by this** — the watchdog's entire value
  is that it runs off-box and survives the droplet being down, and a stale-banner digest posted by
  a bot on the dead droplet is exactly the message that never arrives.
  This banner is the same computation Phase 7 criterion 2 needs from `/status` (D-17); write it
  once and share it.
  — **Reversibility:** reversible.

- **D-05:** **No catch-up digest.** *(Claude's discretion.)* A bot restarted at 09:30 waits for
  tomorrow's slot; it does not notice it missed today. Rejected: catch-up on startup — it needs a
  persisted "already posted today" marker (new state, new table or file), and a crash-restart loop
  would then need its own suppression logic. The gap is already covered three ways: the Sheet holds
  the numbers, `/status` reports staleness on demand, and the off-box watchdog is watching. Adding
  state to close a gap that three existing surfaces already cover is the trade this project keeps
  declining.
  — **Reversibility:** reversible.

### Failure Reporting

- **D-06:** **A new `run_failures` table carries per-failure detail.** Columns: `run_id` (the
  `runs` row it belongs to), `creator_id`, `source`, `cause` (the exception class name),
  `message`. The digest, `/status`, and the immediate alert all read it. Two mechanical
  consequences the planner must handle: `db.write_run_row()` currently returns `None` and must
  return the inserted `runs` id (`cursor.lastrowid`), and `collector.collect_once()` must
  accumulate a list of failures alongside `failure_count` rather than only counting them.
  **The migration is free:** `SCHEMA_DDL` is already all `CREATE TABLE IF NOT EXISTS` and is run on
  every `connect(create=True)`, so the live droplet database gains the table on the next collect
  run with no migration script and no downtime.
  Rejected: a TEXT summary column on `runs` (needs a hand-run `ALTER TABLE` against the live DB
  because the idempotent-DDL path can't add columns, and produces an unqueryable blob); persisting
  nothing and having the collector alert from memory (BOT-01 says the digest lists *"any failures
  from that run"* — with nothing persisted the bot can only report a number, and `/status` likewise).
  — **Reversibility:** reversible — additive table, no existing column or row changes. Dropping it
  later loses accumulated failure history but breaks no existing read path.

- **D-07:** **Any run with `failure_count > 0` posts an alert.** *(Claude's discretion.)* One rule,
  one sentence, no cross-run state. With three creators a failure is genuinely rare, so there is
  nothing to suppress. Rejected: alerting only after N consecutive failing days — it needs state
  and a threshold to justify, and it suppresses the single-day outage that is the most worth
  knowing about.
  **Not a failure, do not alert:** a `no_fetcher_registered` skip. Phase 3 D-09/D-10 settled that a
  skip is neither a row nor a failure, and `creators.yaml` still declares `tiktok` and `twitch`
  entries that skip cleanly on every run. Alerting on those would fire every single day.
  — **Reversibility:** reversible.

- **D-08:** **One alert message per run, listing every failure.** *(Claude's discretion.)* Sent from
  the collector after `collect_once()` returns and the `runs` row is committed — not from inside
  the per-pair `except` block. If the YouTube API is down, every creator fails and the channel gets
  one message rather than N. It also guarantees the alert and the `runs` row report the same count,
  because the alert is built from the same result. Rejected: per-pair alerts at the moment of
  failure — marginally faster, floods the channel that is also the demo surface.
  — **Reversibility:** reversible.

- **D-09:** **A Sheets sync failure alerts too, from the `except` block that already exists.**
  *(Claude's discretion.)* `cli.py:90` already catches `SheetNotShared` / `SheetsKeyfileUnusable` /
  `gspread.exceptions.APIError`, logs, and re-raises (Phase 4 D-07). The webhook POST goes in there,
  before the `raise` — the log-then-re-raise policy is unchanged, one line is added to it. A
  silently stale Sheet has no other symptom (PITFALLS.md §18(d)) and `systemctl --failed` going red
  at 08:00 is not something anyone is watching. Rejected: relying on systemd plus the 09:00 watchdog
  — the watchdog reports *staleness*, not *cause*, and it is an hour late.
  **Constraint:** the alert must not swallow the exception. Post, then re-raise, exactly as now. If
  the webhook POST itself fails it is logged and swallowed — a broken alert channel must never
  replace the real error in flight.
  — **Reversibility:** reversible.

### Digest Content

- **D-10:** **Rank and flag on percent change; display both absolute and percent.** *(Claude's
  discretion.)* Percent is computed in the bot as `(views - prev_views) / prev_views`. Ranking by
  percent is what makes "top movers" mean anything across creators of different size — xQc gaining
  50k views is noise, a small channel gaining 50k is the story. BOT-02's ±20% threshold is a
  percentage and needs this number to exist regardless. The absolute figure is shown alongside so
  the digest and Sheet column E visibly agree. Rejected: ranking by absolute Δ to match the Sheet's
  ordering — the largest channel would be permanently top of a "movers" list regardless of whether
  it moved.
  — **Reversibility:** reversible.

- **D-11:** **Every row, sorted by |percent change| descending. No top-N cap.** *(Claude's
  discretion.)* Three creators × YouTube = 3 rows today, 6 if Twitch is ever unblocked. A cap that
  never triggers is untested code that has to be explained. The sort is what makes it a movers
  list; truncation is not needed until the creator list is much longer, and that is the trigger to
  revisit.
  — **Reversibility:** reversible.

- **D-12:** **No baseline, or `prev_views = 0`, renders as `—` with no percent and no flag.**
  *(Claude's discretion.)* Reuse `sheets.DELTA_PLACEHOLDER` so the em dash is defined once and the
  two surfaces cannot drift. `prev_views = 0` yields no percent either — division by zero is not a
  10,000% gain, and 0 means "the platform reported zero", not "no data" (CLAUDE.md's NULL-vs-0
  rule). Rejected: omitting those rows — a creator vanishing from the digest looks identical to a
  creator that was never configured, and on the first day after adding a creator every row vanishes.
  The orphan `mkbhd` row from the Phase 3 bogus-handle test will render this way and is pointable
  live proof of DATA-04, exactly as it is on the Sheet.
  — **Reversibility:** reversible.

- **D-13:** **`LATEST_ROWS_SQL` and `fetch_latest_rows()` move from `sheets.py` to `db.py`; both
  `sheets.py` and the bot import them from there.** One definition of "yesterday" — strict
  `date(metric_date, '-1 day')` — shared by the Sheet and Discord, so the two surfaces cannot
  disagree about a delta. That is a claim worth being able to make out loud, and it is the merge
  rule applied to a data path. It also keeps `gspread` out of the bot process entirely, which the
  alternative would not. Rejected: the bot importing from `sheets.py` (zero refactor, but the bot
  would import the Google module and pull in gspread in order to read SQLite — indefensible on
  sight); the bot writing its own query (two baseline definitions kept in sync by hand, the exact
  drift the NULL and delta rules exist to prevent).
  **Scope of the move, and the ceiling:** move the SQL constant, the `LatestRow` type alias, and
  `fetch_latest_rows()`. `build_dashboard_rows()` stays in `sheets.py` — it is Sheet-shaped output,
  not shared. `tests/test_sheets.py` imports must follow. The four-command gate must be green after
  the move and before anything else is built on it.
  — **Reversibility:** costly — the move touches a finished, verified module (`sheets.py`), its
  test file, and every future caller. Undoing it means re-splitting the query across two modules
  and reintroducing the drift risk it removes. Do it once, early, as its own commit.

### Slash Commands and Build Order

- **D-14:** **BOT-04 and BOT-05 land in their own final plan, droppable whole.** *(Claude's
  discretion — author answered "you decide, I'm locking in".)* The digest, the failure alert, and
  the bot's connection/lifecycle land in earlier plans; the two slash commands are the last plan and
  nothing depends on it. They are cut-list item 1 with roughly thirteen hours to the interview and
  Phase 7 still outstanding, so the cut must be available as a *decision* — delete one plan file —
  rather than as a mid-execution scramble. This is the same discipline Phase 4 used when it
  exercised cut-order items 2 and 3 as written instead of rediscovering them under pressure.
  Rejected: one plan for everything (cutting then means editing a plan mid-flight); cutting BOT-04/05
  now (criterion 4 names both commands, and slash commands are the entire "and the place you ask
  about them" half of the phase goal).
  — **Reversibility:** reversible.

- **D-15:** **`/creator <name>` matches `creator_id` case-insensitively and exactly; an unknown name
  replies with the list of known slugs.** No fuzzy matching, no substring matching — there is no
  ambiguity rule to defend, and no path by which the bot silently answers about the wrong creator.
  The list-on-miss makes the failure discoverable instead of a dead end. Rejected: `app_commands`
  autocomplete (a genuinely good demo moment for ~10 lines, and unpickable wrong names — but it adds
  a Discord API surface to explain and fires a DB read per keystroke; noted as a deferred idea, not
  a rejection on merit); substring/fuzzy (ambiguity rules for three creators with distinct names).
  — **Reversibility:** reversible.

- **D-16:** **"Recent trend" is the last 7 daily rows for that creator: date, views, Δ.** *(Claude's
  discretion.)* One indexed read against `idx_metrics_creator_date` with `LIMIT 7`. The database
  currently holds only a couple of days, so it will show two rows — that is honest, and it fills in
  by itself with no code change. Same `—` and NULL rules as the digest (D-12). Rejected: today vs
  yesterday only — identical to the digest's per-row content, and BOT-04's "recent trend" plainly
  means more than one comparison.
  — **Reversibility:** reversible.

- **D-17:** **`/status` returns the numbers plus an OK/STALE verdict.** *(Claude's discretion.)* Last
  run time, duration (`finished_at - started_at`), rows written, failure count — plus `STALE` when
  the last run is older than the freshness threshold, and the failing sources by name from
  `run_failures` (D-06) when there are any. **The threshold is 26 hours, matching Phase 5 D-06's
  watchdog**, so the two surfaces cannot disagree about whether the system is stale; the reasoning
  behind that number (tolerate a slow or late run, alert on a genuinely missed one) transfers
  unchanged. Rejected: raw numbers only — Phase 7 criterion 2 requires `/status` to *report*
  staleness honestly when the run is deliberately broken, and building the verdict now means Phase 7
  rehearses instead of implements.
  — **Reversibility:** reversible.

### Process Lifecycle, Config, and Testing

- **D-18:** **The bot reads the same `/etc/creatorpulse/creatorpulse.env` the collector reads.** Four
  variables are added: `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_GUILD_ID`,
  `DISCORD_WEBHOOK_URL`. Both units point `EnvironmentFile` at the one file. The collector needs the
  webhook URL anyway (D-02), so a split file would put Discord secrets in two places and make
  "the Discord secrets live here" false. One file to `chmod 600`, one to remember, one already
  proven working on the droplet. Rejected: a separate `bot.env` isolating the token from the
  collector's blast radius — correct at larger scale, and it does not actually achieve isolation
  here because the webhook URL has to be shared regardless.
  **`.env.example` gains all four names with blank values** (agent-written, names only). The values
  never enter the repo — Phase 1 and Phase 2 D-04 discipline, unchanged.
  — **Reversibility:** reversible.

- **D-19:** **Missing or malformed config fails loudly at startup, before connecting to Discord.**
  All four variables are read and validated first; a missing one raises a named error saying exactly
  which variable to set, and the process exits non-zero so systemd marks the unit failed and the
  journal names the cause. `DISCORD_CHANNEL_ID` and `DISCORD_GUILD_ID` must parse as integers —
  a non-numeric value is a config error caught here, not a confusing gateway error later. Rejected:
  connecting anyway and degrading — a bot that is green in `systemctl` and posts nothing is the
  exact failure this project has refused at every prior boundary (`SheetNotShared`,
  `SheetsKeyfileUnusable`, Phase 3 D-16, Phase 5 D-13).
  — **Reversibility:** reversible.

- **D-20:** **pytest covers the pure formatters; the discord.py plumbing is untested, by design and
  in writing.** *(Claude's discretion.)* Digest text, trend text, status text, the ±20% flag, the
  percent computation, and the staleness verdict are pure functions from database rows to strings,
  tested against a temporary SQLite database the way `tests/test_sheets.py` already tests
  `build_dashboard_rows`. The gateway client, the task loop, and command registration get no tests.
  Rejected: mocking discord.py to test the command callbacks — hours spent mocking a library whose
  behaviour the mocks would then define, on interview day, for coverage the live human gate already
  provides.
  **The gap is stated, not hidden.** ROADMAP's manual gate is what proves the plumbing: the author
  watches a real scheduled digest and a real failure alert land in the real channel. `06-UAT.md`
  carries that as its evidence, and CONTEXT says out loud which half of the phase automated tests do
  not reach — a silent coverage gap would be the dishonest version of the same decision.
  — **Reversibility:** reversible.

### Claude's Discretion

The author answered "you decide" to eleven of the twenty questions asked, and "you decide, I'm
locking in" to build order. All are resolved above as recorded decisions with rationale, not left
open. What genuinely remains at the planner's and implementer's discretion:

- Module layout inside `src/creatorpulse/` — whether the bot is one `bot.py` or splits the pure
  formatters into a `digest.py` the collector can also import. Note that the collector's alert path
  (D-08/D-09) needs the webhook POST helper, so *something* must be importable by both processes
  without dragging discord.py into the collector. That constraint is real; where the seam goes is not
  dictated.
- Exact wording and layout of the digest, alert, trend, and status messages, within D-04's banner
  requirement, D-10's both-numbers requirement, and D-12's `—` rendering.
- Plain `content` string vs a Discord embed for any message. Plain content is the assumed default —
  it matches what Phase 5's webhook already sends, and one message shape across the whole system is
  easier to defend than two. An embed is permitted where it genuinely reads better.
- `discord.Client` + `CommandTree` versus `commands.Bot`. Whichever needs fewer lines to register
  two guild-scoped commands.
- Where guild-scoped sync happens (`setup_hook` vs `on_ready`) and whether it runs on every start.
- Slash command parameter descriptions and the `run_failures` column types/naming, within D-06's
  named fields.
- Whether the freshness threshold is one shared constant imported by the digest banner (D-04) and
  `/status` (D-17). Sharing it is strongly preferred — two copies of 26 can drift — but the
  mechanism is the implementer's.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Binding project rules

- `.claude/CLAUDE.md` — the hand-written "Hard Rules" block above the GSD markers, authoritative
  over the generated sections below it. **Hard Rules 1 (VPS/systemd) and 3 (Discord Developer
  Portal) bind this phase in full and are untouched by the Phase 5 amendment** — read the amendment
  text and note that it scopes itself to rule 2. The merge rule ("nothing enters the repo that the
  author cannot explain out loud") governs D-13's refactor and D-20's stated test gap.
  Also authoritative here: the NULL-vs-0 rule (D-12 depends on it) and the no-new-dependencies rule
  (`discord.py` is already in the locked set; nothing else may be added).
- `.planning/PROJECT.md` — constraints and the Key Decisions table. "The database is the source of
  truth; the Sheet is a disposable view" extends to Discord: every message this phase sends is
  derived from the database, and nothing this phase writes is data.

### Scope

- `.planning/ROADMAP.md` §"Phase 6: Discord Bot" — the goal, the five success criteria, and the
  Notes. The Notes pre-lock several things this discussion did not re-ask: guild-scoped command sync
  (not global), short-lived per-command database connections (no module-level global), no blocking
  calls in the event loop, minimum non-privileged intents, and separate unit / separate failure
  domain from the collector.
- `.planning/ROADMAP.md` §"Cut Order" — items 2 and 3 are spent. **BOT-04/BOT-05 are item 1 and are
  the only cut left**; D-14 structures the plans so that cut is one file deletion. The digest
  (BOT-01/02/03) is explicitly not cuttable. **Phase 6 is marked never-cut.**
- `.planning/ROADMAP.md` §"Definition of Green" — `ruff check .`, `mypy src/`, `pytest`, **plus** the
  human-observed real-data gate. For this phase the gate is: a real scheduled digest and a real
  failure alert landing in the real channel. Note the test-weakening guard — a test file changed
  during Verify is suspect unless explicitly requested.
- `.planning/REQUIREMENTS.md` §"Discord Bot" — BOT-01 through BOT-07, with the *(human-built)*
  markers on BOT-06's unit file and BOT-07 in full.

### Prior phase context — the contracts this phase consumes

- `.planning/phases/05-apps-script/05-CONTEXT.md` — **D-16** (one webhook, one channel; the bot
  posts to the same channel but does **not** share the webhook credential — a bot token and a
  webhook are different things), **D-06** (the 26-hour staleness threshold and 09:00 Manila fire
  time that D-17 and D-03 align against), **D-05** (why the watchdog lives off-box — do not let this
  phase reason itself into replacing it), **D-13** (throw-on-missing-config, the pattern D-19
  repeats).
- `.planning/phases/05-apps-script/05-COVERAGE.md` — the Discord webhook API surface already
  researched and recorded for Phase 5. **Read this before researching the webhook again** — the
  payload shape and rate-limit findings for D-02's collector-side POST are already here.
- `.planning/phases/04-playwright-sheets/04-CONTEXT.md` — **D-05** (the `—` no-baseline placeholder
  D-12 reuses) and **D-03** (the frozen seven-column Dashboard layout — this phase reads the same
  data but must not touch the Sheet at all).
- `.planning/phases/03-collector-core-api-sources/03-CONTEXT.md` — **D-15** (per-pair failure
  isolation, the loop D-06 hooks into), **D-16** (the `runs` row a dying run still writes, and the
  fail-loudly principle), **D-09/D-10** (a `no_fetcher_registered` skip is neither a row nor a
  failure — D-07 depends on this to avoid alerting daily on the unregistered tiktok/twitch entries),
  **D-04** (`connect(create=False)`, the bot's read path, and `DatabaseNotInitialized`).
- `.planning/phases/02-vps-systemd/02-CONTEXT.md` — **D-09** (collector fires 08:00 Asia/Manila =
  00:00 UTC, the arithmetic behind D-03), **D-04** (the root-owned `chmod 600` `EnvironmentFile`
  D-18 extends), and **D-12, binding and absolute:** unit files may be read and must never be
  written, edited, generated, reformatted, or "fixed" — *including when asked*.
- `.planning/phases/01-skeleton/01-CONTEXT.md` — the four-command gate and the fixtures-only rule
  that D-20 operates under.

### Technical grounding

- `.planning/research/PITFALLS.md` §18(d) — the silently stale surface. D-04, D-09, D-17, and D-19
  are all the same answer to it applied at four different boundaries.
- `.planning/research/ARCHITECTURE.md` §"Internal Boundaries" — the collector/bot boundary and the
  read/write split at SQLite.
- `.planning/STATE.md` §"Blockers/Concerns" — the outstanding Phase 3 droplet UAT and the Twitch
  2FA block. Relevant here because the digest must render correctly with only YouTube rows and with
  `twitch`/`tiktok` skipping silently every run.

### Source files this phase reads or changes

- `src/creatorpulse/db.py` — gains the `run_failures` table in `SCHEMA_DDL` (D-06), gains
  `LATEST_ROWS_SQL` / `LatestRow` / `fetch_latest_rows()` moved in from `sheets.py` (D-13), and
  `write_run_row()` changes to return the inserted row id (D-06).
- `src/creatorpulse/collector.py` — `collect_once()` accumulates failure detail, not just a count
  (D-06); the alert itself is sent by the caller, not from inside the per-pair `except` (D-08).
- `src/creatorpulse/cli.py` — `run_collect()` gains the failure alert after the `runs` row commits
  (D-08) and the sync-failure alert inside the existing `except` at line 90, before the re-raise
  (D-09). `cli.py:155`'s `bot` subcommand stub is the entry point the unit will invoke.
- `src/creatorpulse/sheets.py` — loses the query moved by D-13, keeps `build_dashboard_rows()` and
  `DELTA_PLACEHOLDER`. **Otherwise finished and not reopened.**
- `tests/test_sheets.py` — imports follow D-13's move. This is a mechanical import change, not a
  weakening; the test-weakening guard applies and the diff should show exactly that.
- `.env.example` — gains four blank-valued Discord variable names (D-18).

### External APIs — what research must confirm

No discord.py documentation has been fetched for this phase. The research step should verify against
the discord.py 2.7.1 docs (`discordpy.readthedocs.io`) and Discord's developer docs:

- `discord.ext.tasks.loop(time=...)` — accepts a `datetime.time`; confirm how it handles a
  timezone-aware time and whether the loop must be started in `setup_hook`/`on_ready`. Asia/Manila
  has no DST, which removes the usual hazard, but confirm the API rather than assume it.
- `app_commands.CommandTree.sync(guild=discord.Object(id=...))` — guild-scoped registration, where
  it belongs in the lifecycle, and whether re-syncing on every start is safe.
- **Intents:** confirm that slash commands need no privileged intents — `Intents.default()` with
  `message_content` left off. Criterion 5 requires the author to explain *which intents the bot
  requests and why none are privileged*, so this must be confirmed against docs, not assumed.
- `discord.Client` + `CommandTree` versus `commands.Bot` for two commands and one task loop.
- The 2000-character limit on a message `content`, and what the digest should do if it ever exceeds
  it (with ≤6 rows it will not — confirm the limit and note the ceiling).
- Interaction response timing — the 3-second initial-response window and whether a single indexed
  SQLite read needs `defer()`. It almost certainly does not; confirm the number.
- Webhook POST payload and rate limits: **check `05-COVERAGE.md` first**, it is already recorded.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`src/creatorpulse/cli.py:141,155`** — the `bot` subparser and its stub handler already exist,
  logging "bot is not implemented yet; Phase 6 fills it in" and returning 3. The entry point is
  built; this phase fills the body. `configure_logging()` at `cli.py:27` is the logging setup both
  processes share — stdout, captured by journald, no handler needed (STACK.md gap 4).
- **`src/creatorpulse/db.py:61` `connect(db_path, create=False)`** — the bot's read path, already
  written and tested. WAL mode plus `busy_timeout=5000` are set on every connection, which is what
  makes the bot reading while the collector writes safe (ROADMAP criterion 5 of Phase 3, already
  proven). Raises `DatabaseNotInitialized` rather than silently creating an empty database at the
  wrong path — the bot must let that propagate, not swallow it.
- **`src/creatorpulse/sheets.py:48` `LATEST_ROWS_SQL`** — the one query that defines "latest
  snapshot and its strict day-before baseline". D-13 moves it to `db.py` so both surfaces share it.
  Note its `LEFT JOIN`: a pair with no baseline still comes back, with `prev_views` as `NULL` — the
  case D-12 renders as `—`.
- **`src/creatorpulse/sheets.py:15` `DELTA_PLACEHOLDER`** — the em dash. Import it; do not retype it.
- **`src/creatorpulse/config.py` `resolve_paths()` / `resolve_sheets_config()`** — the established
  shape for reading environment configuration, including the settled rule that an empty-string
  environment variable is treated as unset rather than as a valid value. D-18/D-19's Discord config
  reader should follow the same shape rather than inventing a second one.
- **`tests/test_sheets.py`** — the pattern D-20 copies: a temporary SQLite database, rows inserted
  by hand, a pure function asserted on. No network, no mocking framework.
- **`requests`** — already a dependency (transitively via gspread, and used directly by
  `sources/youtube.py`). D-02's collector-side webhook POST needs nothing new.

### Established Patterns

- **Fail loudly, never silently.** Phase 3 D-16, Phase 4 D-07, Phase 5 D-13, PITFALLS.md §18(d).
  D-04, D-09, D-17, and D-19 are four more applications of it.
- **NULL is not 0, and is never coalesced before delta math.** CLAUDE.md, correctness rule. D-12.
- **Exit codes say whether the run COMPLETED, not whether every source succeeded** — `cli.py`'s
  docstring at line 38 explains this at length and it must not be undermined: adding a Discord alert
  for per-source failures does **not** make the run return non-zero. A run with failures still
  exits 0; the alert is the reporting channel, the exit code is not.
- **No new dependencies.** discord.py 2.7.1 is already locked in `pyproject.toml`. Nothing else.
- **One writer.** The collector writes SQLite; the bot only reads. Nothing in this phase changes
  that, including the `run_failures` table — it is written by the collector, read by the bot.
- **Secrets never enter the repo.** `.env.example` carries names with blank values; the real file is
  root-owned and `chmod 600` on the droplet.

### Integration Points

- **collector → `run_failures` → bot.** The only new data path. The collector writes failure rows in
  the same transaction context as the `runs` row; the digest and `/status` read them back.
- **collector → Discord webhook** (`requests.post`), two call sites: the run-failure alert (D-08)
  and the Sheets-sync-failure alert (D-09). Both in `cli.py`.
- **bot → Discord gateway** (`channel.send`, slash command responses), using `DISCORD_BOT_TOKEN`.
  A different credential to the same channel as the webhook (D-02, Phase 5 D-16).
- **bot → SQLite**, read-only, short-lived connection per command and per digest tick.
- **The bot's systemd unit → `creatorpulse bot`.** The unit is human-built. What the agent may state
  in plans and UAT prose: it invokes the same console script, points `EnvironmentFile` at
  `/etc/creatorpulse/creatorpulse.env`, runs as the `creatorpulse` service user, and wants
  `Restart=on-failure` because a long-lived process that dies must come back. The agent writes none
  of it.
- **Nothing in this phase touches the Sheet or the Apps Script.** The two layers meet only at the
  database and at the shared Discord channel.

</code_context>

<specifics>
## Specific Ideas

- **The three-schedule story is the interview answer, and D-03 exists to make it narratable.**
  08:00 collect (systemd timer, on the droplet) → 08:15 digest (task loop, in the bot process) →
  09:00 watchdog (Apps Script trigger, on Google's infrastructure). Three different scheduling
  mechanisms is not sloppiness — each job is scheduled by the thing that is alive to do it, and the
  watchdog is deliberately the odd one out because a watchdog hosted on the machine it watches is
  not a watchdog (Phase 5 D-05). Being able to say that sentence is worth more than schedule
  uniformity.
- **Criterion 5 has an explanation half, like Phase 5's criterion 5 did.** "The author can explain
  which intents it requests and why none of them are privileged." Phase 5's equivalent is still
  PENDING in `05-UAT.md`. Do not let this one accumulate the same way — the intents answer is short
  (slash commands arrive as interactions over the gateway, not as messages, so no
  `message_content`), and it should be written into `06-UAT.md` in the author's own words at the
  time the bot is invited, not deferred to the last hour.
- **Prove BOT-03 the way criterion 3 words it.** "Distinct from and earlier than the scheduled
  digest." The forced proof: break one source deliberately (a bogus handle in `creators.yaml`, the
  same technique that produced the `mkbhd` orphan row), run the collector by hand, watch the alert
  land immediately, then watch the 08:15 digest arrive separately with that failure listed. Both
  messages, in order, in one screenshot. That is the whole requirement and it is a two-minute proof.
- **The forced digest proof does not need to wait for 08:15.** Call the digest function directly
  the way Phase 5 D-08 forced the watchdog — run it by hand, confirm the message, then let the
  natural fire be captured opportunistically for the evidence screenshot.
- **`06-UAT.md` follows the `04-UAT.md` / `05-UAT.md` pattern.** Five entries against the five
  ROADMAP criteria, each with observed evidence or an explicit `not_closed_reason` plus a
  close-later command. Do not fabricate a close.
- **D-13's refactor goes first and alone.** It touches a finished module and a test file. It should
  be its own plan or its own first task with the four-command gate run immediately after, so that
  if it breaks something the breakage is isolated to a commit that does nothing else.
- **Watch `mypy src/` on the discord.py surface.** discord.py ships type hints, but decorated
  callbacks and `CommandTree` generics are a common source of new mypy errors. If it fights, the
  answer is a narrow per-module override in `pyproject.toml` alongside the existing gspread/yaml
  overrides — the same precedent, not a `# type: ignore` scattered through the file, and not
  loosening the gate globally.

</specifics>

<deferred>
## Deferred Ideas

- **`app_commands` autocomplete on `/creator`.** Declined by D-15 — a good demo moment for ~10
  lines, but it adds a Discord API surface to explain and fires a database read per keystroke.
  Cheap to add later; revisit if the creator list grows past a handful.
- **A top-N cap on the digest.** Declined by D-11 as speculative at 3–6 rows. The trigger to revisit
  is a creator list long enough that the message approaches Discord's 2000-character limit.
- **Catch-up digest after a missed 08:15 slot.** Declined by D-05 — needs persisted "already posted
  today" state and restart-loop suppression, to close a gap the Sheet, `/status`, and the off-box
  watchdog already cover three ways. Revisit only if the bot proves unreliable enough that missed
  digests become common.
- **A separate `bot.env` isolating the bot token.** Declined by D-18 — correct at team scale, and it
  fails to achieve isolation here anyway because the webhook URL must be shared with the collector
  regardless.
- **Mocking discord.py to test command callbacks.** Declined by D-20 on the clock, and noted rather
  than hidden. The honest statement is that the plumbing is proven by the human gate, not by pytest.
- **`OnFailure=` on the collector unit as a systemd-native alert path.** Not chosen and not
  available to the agent regardless — it is a unit-file change and therefore human-built (Hard
  Rule 1). D-09's in-process alert is the agent-writable equivalent. Worth mentioning as the
  systemd-native alternative if it comes up in the interview.
- **Alerting on consecutive-day failures rather than any failure.** Declined by D-07 — needs
  cross-run state and suppresses the single-day outage most worth knowing about. Revisit only if
  the channel ever becomes noisy, which three creators will not make it.
- **A second Discord channel separating ops alerts from digest.** Already declined by Phase 5 D-16
  and not reopened here.

### Out-of-phase item surfaced during scout

- **`deploy/creatorpulse.service`, `deploy/creatorpulse.timer`, and `docs/deploy.md` are missing
  from the repo** despite Phase 2 D-12 and D-13 declaring them committed artifacts. This is Phase 2
  debt that Phase 7 should close, and it is **human work by Hard Rule 1** — the agent must not
  create these files to "fix" the gap. Raised here because Phase 6 adds a second unit that D-12
  expected to be diffable against the first.

</deferred>

---

*Phase: 6-Discord Bot*
*Context gathered: 2026-08-06*
</content>
