# Phase 6: Discord Bot - Research

**Researched:** 2026-08-06
**Domain:** discord.py 2.7.1 (gateway client, `app_commands`, `discord.ext.tasks`), sqlite3 (WAL reader), stdlib config validation
**Confidence:** MEDIUM

## Summary

This phase adds no new library — discord.py 2.7.1 is already locked and its full surface (intents,
`app_commands.CommandTree`, `discord.ext.tasks.loop`) covers every requirement. The two genuinely
sharp edges research surfaced are not in the "happy path" APIs the CONTEXT already named, but in
their **failure semantics**: (1) `discord.ext.tasks.loop`'s built-in `reconnect` machinery only
retries a narrow set of network exceptions (`OSError`, `GatewayNotFound`, `ConnectionClosed`,
`aiohttp.ClientError`, `asyncio.TimeoutError`) — verified by reading the pinned v2.7.1 source. Any
other exception (a `KeyError` from a malformed row, a `ZeroDivisionError` in the percent-change
math) is **not** retried: it is logged once via the loop's `error()` hook and then the loop's
underlying `Task` dies permanently. `@loop.error` only observes the exception; it cannot suppress
it. This directly threatens D-01 ("the bot posts the digest from its own task loop") — a single bad
digest tick would silently end all future digests until the bot is restarted, with no other symptom
(exactly the failure PITFALLS.md §18(d) exists to prevent). The plan needs a task that wraps the
digest body in its own `try/except Exception: log`, inside the decorated coroutine, so the loop
itself never sees anything but the network-transient exceptions it already knows how to retry.
(2) Guild-scoped command sync (`tree.sync(guild=...)`) is immediate and safe to call on every
process start for two commands — it is not the slow, rate-limited path; that is global sync
(`guild=None`), which this phase does not use per ROADMAP's pre-lock.

The rest of the priorities confirm what CONTEXT already assumed: `Intents.default()` is sufficient
(none of the three privileged intents are needed for `channel.send()` plus slash-command
interactions), a single indexed SQLite read does not need `interaction.response.defer()` (comfortably
inside the 3-second window), the 2000-character message limit is nowhere close to being reached by
3–6 digest rows, and a WAL-mode reader running as the same OS user as the writer, against the same
directory, needs no special handling.

**Primary recommendation:** Build the bot on `commands.Bot` (not bare `discord.Client` +
manually-attached `CommandTree`) for the one-line `self.tree` it already carries, register the loop
body's own `try/except Exception` guard as a non-negotiable line in the digest task from the first
draft (not an after-the-fact fix), and sync commands in `setup_hook()` with
`tree.copy_global_to(guild=...)` + `tree.sync(guild=...)` — guild-scoped, on every start, which is
inexpensive.

## User Constraints (from CONTEXT.md)

### Locked Decisions (D-01 through D-21, D-06/D-13 mechanically binding on this research)

- **D-01:** The bot posts the daily digest from its own `discord.ext.tasks.loop` (not the collector,
  not a second systemd timer). Known cost accepted: no catch-up if the bot is down at 08:15.
- **D-02:** Split transport — bot posts the digest with its bot token via `channel.send()`; the
  collector posts failure/sync alerts to the Phase 5 webhook via `requests`. One channel, two
  credentials.
- **D-03:** Digest fires 08:15 Asia/Manila (15 min after the 08:00 collector, 45 min before the
  09:00 off-box Apps Script watchdog).
- **D-04:** On a stale day the digest posts anyway, led by a `⚠ last run: <ts> — STALE` banner. The
  watchdog is not made redundant by this.
- **D-05:** No catch-up digest. A bot restarted after 08:15 waits for tomorrow.
- **D-06:** New `run_failures` table: `run_id`, `creator_id`, `source`, `cause`, `message`.
  `db.write_run_row()` must return `cursor.lastrowid`; `collector.collect_once()` must accumulate a
  failures list, not just a count. Migration is free (`CREATE TABLE IF NOT EXISTS`, runs on every
  `connect(create=True)`).
- **D-07:** Any run with `failure_count > 0` posts an alert — one rule, no cross-run state. A
  `no_fetcher_registered` skip is never a failure.
- **D-08:** One alert message per run, listing every failure, sent from the collector after
  `collect_once()` returns and the `runs` row is committed — not from inside the per-pair `except`.
- **D-09:** A Sheets sync failure alerts too, from the existing `except` block at `cli.py:90`,
  before the `raise`. Log-then-re-raise policy unchanged; a failed webhook POST is logged and
  swallowed, never replacing the real error.
- **D-10:** Rank and flag on percent change; display both absolute and percent. Percent computed in
  the bot: `(views - prev_views) / prev_views`.
- **D-11:** Every row, sorted by `|percent change|` descending. No top-N cap.
- **D-12:** No baseline or `prev_views = 0` renders as `—` (reuse `sheets.DELTA_PLACEHOLDER`), no
  percent, no flag. `prev_views = 0` is a real zero, not "no data" — never coalesced.
- **D-13:** `LATEST_ROWS_SQL`, `LatestRow`, and `fetch_latest_rows()` move from `sheets.py` to
  `db.py`. `build_dashboard_rows()` stays in `sheets.py`. `tests/test_sheets.py` imports follow.
  This move goes first, alone, its own commit, four-command gate immediately after.
- **D-14:** BOT-04/BOT-05 (`/creator`, `/status`) land in their own final, droppable plan.
- **D-15:** `/creator <name>` matches `creator_id` case-insensitively and exactly. Unknown name
  replies with the list of known slugs. No fuzzy/substring matching.
- **D-16:** "Recent trend" is the last 7 daily rows for that creator (date, views, Δ), one indexed
  read against `idx_metrics_creator_date` with `LIMIT 7`. Same `—`/NULL rules as the digest.
- **D-17:** `/status` returns last run time, duration, rows written, failure count, plus an
  OK/STALE verdict at the same 26-hour threshold as Phase 5's watchdog, plus failing source names
  from `run_failures` when any exist.
- **D-18:** Bot reads the same `/etc/creatorpulse/creatorpulse.env` as the collector. Four new
  vars: `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_GUILD_ID`, `DISCORD_WEBHOOK_URL`.
  `.env.example` gains all four names with blank values.
- **D-19:** Missing or malformed config fails loudly at startup, before connecting to Discord. All
  four vars read and validated first; a missing one raises a named error naming the variable, exits
  non-zero. `DISCORD_CHANNEL_ID`/`DISCORD_GUILD_ID` must parse as integers.
- **D-20:** pytest covers the pure formatters (digest/trend/status text, ±20% flag, percent, staleness
  verdict) against a temp SQLite database. The gateway client, task loop, and command registration
  get **no tests** — proven by the human-observed gate instead. This gap is stated in writing, not
  hidden.
- **D-21:** The agent wrote `deploy/creatorpulse-bot.service` under a dated Hard Rule 1 exception —
  already committed. Not installed/enabled yet (the `bot` subcommand is still a stub returning 3).

### Claude's Discretion

- Module layout inside `src/creatorpulse/` — one `bot.py`, or split pure formatters into a
  `digest.py` the collector can also import for the webhook POST helper. *Something* must be
  importable by both processes without dragging discord.py into the collector.
- Exact wording/layout of digest, alert, trend, status messages within D-04/D-10/D-12's constraints.
- Plain `content` string vs. embed. Plain content is the assumed default (matches Phase 5's webhook
  shape); an embed is permitted where it reads better.
- `discord.Client` + `CommandTree` vs. `commands.Bot` — whichever needs fewer lines for two
  guild-scoped commands. **Research finding below: `commands.Bot` needs fewer lines** (see Priority 3).
- Where guild-scoped sync happens (`setup_hook` vs. `on_ready`) and whether it runs on every start.
- Slash command parameter descriptions; `run_failures` column types/naming within D-06's named fields.
- Whether the freshness threshold is one shared constant imported by D-04 and D-17. Sharing it is
  strongly preferred.

### Deferred Ideas (OUT OF SCOPE)

- `app_commands` autocomplete on `/creator` (declined by D-15 — adds an API surface + a DB read per
  keystroke; cheap to add later).
- A top-N cap on the digest (declined by D-11 — speculative at 3–6 rows).
- Catch-up digest after a missed 08:15 slot (declined by D-05 — needs persisted state and
  restart-loop suppression to close a gap three other surfaces already cover).
- A separate `bot.env` isolating the bot token (declined by D-18 — the webhook URL must be shared
  with the collector regardless, so isolation isn't achieved anyway).
- Mocking discord.py to test command callbacks (declined by D-20 — the honest statement is that
  plumbing is proven by the human gate, not pytest).
- `OnFailure=` on the collector unit as a systemd-native alert path (not available to the agent —
  unit-file change, Hard Rule 1).
- Alerting on consecutive-day failures rather than any failure (declined by D-07).
- A second Discord channel separating ops alerts from digest (already declined, Phase 5 D-16).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Daily digest post (BOT-01/02) | Backend process (long-lived bot) | — | Only the bot is awake at 08:15; `discord.ext.tasks.loop` is a bot-process concern, not the one-shot collector's. |
| Immediate failure alert (BOT-03) | Backend process (one-shot collector) | — | Only the collector is awake at the moment a source fails; it posts via webhook, not the bot's gateway connection. |
| `/creator`, `/status` (BOT-04/05) | Backend process (long-lived bot) | Database / Storage (read) | Interaction handlers are bot-process code; each handler opens a short-lived read connection to SQLite. |
| Failure detail persistence (`run_failures`) | Database / Storage | Backend process (collector, writer) | The collector is the sole writer; the bot and the collector's own alert-builder are readers of the same run's in-memory result. |
| Config validation (D-19) | Backend process (both) | — | Each process validates its own env at its own startup — no shared config-loading tier exists beyond the `config.py` module both import. |
| Command registration (guild sync) | Backend process (bot) | Discord API (Developer Portal) | Sync is a bot-process call against Discord's REST API; the Developer Portal registration that makes commands possible at all is human-owned (BOT-07). |
| Webhook POST (collector→Discord) | Backend process (collector) | CDN / External API (Discord) | `requests.post` to a Discord-owned endpoint; no intermediate tier. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| discord.py | 2.7.1 | Gateway client, `app_commands`, `discord.ext.tasks` | Already locked project-wide (`pyproject.toml`). No new dependency for any BOT-0x requirement. |
| stdlib `sqlite3` | bundled | Bot's read-only DB access | Same `db.connect(create=False)` path already written and tested in Phase 3. |
| stdlib `zoneinfo` | bundled (3.9+) | Asia/Manila tzinfo for `tasks.loop(time=...)` | No DST in Asia/Manila (UTC+8 year-round), removing the usual `zoneinfo` DST-transition hazard, but the API still requires a real `tzinfo`, not a naive `datetime.time`. |

No new supporting libraries. No alternatives to consider — the "no new dependencies" rule
(`.claude/CLAUDE.md`) and the already-locked stack close this table.

**Installation:** none — `discord.py==2.7.1` is already in `pyproject.toml`'s `dependencies`.

**Version verification:** `discord.py` pinned at `2.7.1` in `pyproject.toml` (verified by direct
read of the file). Not re-verified against PyPI this session — no new package to check, and the
Package Legitimacy Audit below is scoped to "packages this phase installs," which is none.

## Package Legitimacy Audit

**No new packages are installed by this phase.** discord.py 2.7.1 and requests 2.34.2 are already
locked, already installed, and already used elsewhere in the codebase (`cli.py`, `sources/youtube.py`).
The Package Legitimacy Gate applies to packages a phase *installs*; this phase installs none.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| *(none — no new packages)* | — | — | — | — | — | N/A |

**Packages removed due to SLOP verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────┐        ┌──────────────────────────┐
│  systemd timer (08:00)  │        │  systemd service (bot)   │
│  creatorpulse.timer     │        │  creatorpulse-bot.service │
└───────────┬──────────────┘        └────────────┬──────────────┘
            │ fires                               │ Restart=on-failure,
            ▼                                     │ long-lived
┌─────────────────────────┐                       ▼
│  collector (one-shot)   │        ┌──────────────────────────────┐
│  cli.py: run_collect()  │        │  bot process (long-lived)     │
│                          │        │  cli.py: run_bot()            │
│  collect_once() ────────┼───┐    │                                │
│    per (creator,source) │   │    │  on ready / setup_hook:        │
│    try/except isolation │   │    │   - validate 4 env vars (D-19) │
│    accumulate failures  │   │    │   - copy_global_to(guild)      │
│    write runs row       │   │    │   - tree.sync(guild=...)       │
│    write run_failures   │   │    │   - digest_loop.start()        │
└──────────┬───────────────┘   │    └──────┬──────────┬─────────────┘
           │                    │           │          │
           │ writes             │ D-08/D-09 │ 08:15    │ interaction
           ▼                    │ webhook   │ tick     │ (/creator, /status)
┌──────────────────────┐        │ POST      ▼          ▼
│  SQLite (WAL)         │        │    ┌────────────┐ ┌──────────────┐
│  metrics, runs,       │◄───────┼────┤ digest task │ │ command       │
│  run_failures          │  read  │    │ loop        │ │ handlers       │
└──────────┬─────────────┘        │    │ fetch_latest│ │ fetch_latest_  │
           │ read (same rows)      │    │ _rows()     │ │ rows() / trend │
           ▼                       ▼    │ build text  │ │ query          │
┌──────────────────────┐   ┌─────────────┴──┐ channel.send()  interaction
│  Discord webhook       │   │ Discord gateway │◄────┴──────────►.response
│  (collector's alerts)  │   │ (bot token)      │                 .send_message
└──────────┬─────────────┘   └────────┬─────────┘
           │                            │
           └──────────────┬─────────────┘
                           ▼
                 one Discord channel
              (immediate alert + digest + slash replies)
```

### Recommended Project Structure

```
src/creatorpulse/
├── db.py           # + run_failures DDL, write_run_row() returns lastrowid,
│                    #   LATEST_ROWS_SQL/LatestRow/fetch_latest_rows() moved in (D-13)
├── collector.py     # collect_once() accumulates failure detail, not just a count (D-06)
├── cli.py           # run_collect() posts alerts after commit (D-08/D-09); `bot` subcommand
│                    #   dispatches to bot.run_bot() or similar
├── sheets.py         # loses the moved query; keeps build_dashboard_rows(), DELTA_PLACEHOLDER
├── config.py         # + resolve_discord_config() following resolve_sheets_config()'s shape (D-18/19)
└── bot.py            # NEW — discord.py client, task loop, slash command handlers, formatters
                       #   (or split formatters into digest.py if the collector's alert-builder
                       #    needs to share them without importing discord.py — implementer's choice)
```

### Pattern 1: `commands.Bot` over bare `discord.Client` + manual `CommandTree`

**What:** `discord.ext.commands.Bot` already constructs and exposes `self.tree` (an
`app_commands.CommandTree`) — `discord.Client` requires manually instantiating
`app_commands.CommandTree(client)` and assigning it as an attribute.
**When to use:** Any bot that needs slash commands and has no reason to avoid the `commands.ext`
machinery (this project has none — no prefix commands are needed, but `commands.Bot` costs nothing
extra to use for slash-only).
**Example:**
```python
# Pattern verified via community consensus (fallendeity.github.io/discord.py-masterclass,
# Rapptz/discord.py discussion #8442) — commands.Bot already has self.tree built in.
import discord
from discord.ext import commands

intents = discord.Intents.default()  # no privileged intents needed — see Pitfall/Priority 1
bot = commands.Bot(command_prefix="!", intents=intents)  # prefix unused, required by the constructor

@bot.tree.command(name="status", description="Report last run time, duration, and failure count")
async def status(interaction: discord.Interaction) -> None:
    ...
```
Rejected: `discord.Client` + manually attached `CommandTree` — same end result, one extra line
(`client.tree = app_commands.CommandTree(client)`), no offsetting benefit for this bot's shape.

### Pattern 2: guild-scoped sync in `setup_hook`, on every start

**What:** `tree.copy_global_to(guild=discord.Object(id=GUILD_ID))` then
`await tree.sync(guild=discord.Object(id=GUILD_ID))`, called from `setup_hook()`.
**When to use:** A bot with a small, fixed, known guild (this project — one server). Guild-scoped
sync propagates immediately; global sync (`guild=None`) can take up to an hour to reach clients —
unacceptable during a live demo.
**Example:**
```python
# Source: discord.py v2.7.1 source (discord/app_commands/tree.py), CommandTree.sync/copy_global_to
# docstrings — fetched and quoted directly this session.
class CreatorPulseBot(commands.Bot):
    async def setup_hook(self) -> None:
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.digest_loop.start()
```
Re-syncing on every process start is safe for two commands — `sync()` returns the list of synced
`AppCommand`s and raises `HTTPException`/`CommandSyncFailure`/`Forbidden` on failure, none of which
are rate-limit-specific for a guild-scoped sync of this size. `Forbidden` specifically means the bot
lacks the `applications.commands` scope in the guild — a Developer Portal / invite-URL problem
(BOT-07, human-owned), not something the plan needs to guard against in code beyond letting it
propagate loudly.

### Pattern 3: the digest loop must catch its own exceptions

**What:** The coroutine decorated by `@tasks.loop(time=...)` must wrap its entire body in
`try/except Exception: log`, so that a bug in digest formatting (bad row shape, division edge case)
never reaches the loop's own exception handling.
**When to use:** Always, for this loop specifically — see Pitfall 1 below. This is not optional
hardening; it is the only mechanism available to satisfy D-01's implicit expectation that the digest
keeps firing daily.
**Example:**
```python
# Source: discord.py v2.7.1 source, discord/ext/tasks/__init__.py — the _valid_exception tuple
# and the _loop method's except Exception branch, fetched and quoted directly this session.
@tasks.loop(time=datetime.time(hour=8, minute=15, tzinfo=ZoneInfo("Asia/Manila")))
async def digest_loop(self) -> None:
    try:
        await post_digest(self.channel, self.db_path)
    except Exception:
        logger.exception("digest tick failed — will retry at the next scheduled time")
        # deliberately not re-raised: an exception here is NOT one of the 5 types
        # discord.ext.tasks retries automatically, so letting it propagate kills the
        # Task permanently and no future digest ever fires again.
```

### Anti-Patterns to Avoid

- **Letting the digest coroutine's exceptions propagate unguarded.** Confirmed by direct source
  read (Priority 6 finding): only `OSError`, `discord.GatewayNotFound`, `discord.ConnectionClosed`,
  `aiohttp.ClientError`, and `asyncio.TimeoutError` are auto-retried by `reconnect=True` (the
  default). Anything else — a `KeyError`, a `ZeroDivisionError`, a malformed SQLite row — kills the
  loop's `Task` permanently after one log line from the `@error` handler. The `@error` decorator
  **observes**, it does not **suppress**.
- **Module-level global DB connection in the bot process.** ROADMAP Notes pre-lock short-lived
  per-command connections. Open, query, close inside each command handler and each digest tick —
  matching the collector's own `connect()`/`.close()` discipline.
- **Blocking calls inside the event loop.** `sqlite3` is synchronous; a single indexed read against
  a database with a handful of rows is fast enough in practice that this project does not need
  `asyncio.to_thread()` — but a slow filesystem stall (e.g., an unresponsive network mount) would
  block the whole gateway connection. Noted as an accepted risk given this project's local disk and
  scale (ROADMAP explicitly calls out "no blocking calls in the event loop" as a note, not a
  measured requirement — see Open Questions).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Daily scheduling in the bot process | A manual `asyncio.sleep`-until-next-occurrence loop | `discord.ext.tasks.loop(time=...)` | Ships with discord.py, handles the sleep-until-time math and (partial) exception-retry machinery already — see Pitfall 1 for its one real gap. |
| Slash command registration | Manual REST calls to the Discord application-commands endpoint | `app_commands.CommandTree.sync()` | The library already wraps the endpoint, including the `HTTPException`/`CommandSyncFailure`/`Forbidden` distinctions this project needs to fail loudly and correctly. |
| ±20% flag / percent computation | A third-party stats/rounding library | A single `(views - prev_views) / prev_views` expression, `None`-guarded per D-12 | Already the shape D-10 specifies; no library reduces this below one line. |
| Staleness verdict shared by digest banner and `/status` | Two separately-computed staleness checks | One shared constant/function importing the same 26-hour threshold Phase 5's watchdog uses (D-17) | Two copies of the number 26 is exactly the drift risk `CLAUDE.md`'s merge rule and PITFALLS.md §18(d) exist to prevent. |

**Key insight:** every "don't hand-roll" candidate in this phase is already covered by discord.py
itself; the actual risk this phase carries is not under-building (reaching for a library that
isn't needed) but *trusting* a discord.py convenience (`tasks.loop`'s `reconnect=True`) to do more
than it actually does.

## Common Pitfalls

### Pitfall 1: An unguarded exception in the digest loop silently ends all future digests

**What goes wrong:** The bot runs fine for days. One day a row shape the formatter didn't expect
(e.g., a creator with all-NULL metrics) raises inside `digest_loop`'s body. The loop's `@error`
handler logs one line, then the exception re-raises out of `_loop()` and the `Task` object backing
the loop ends. No exception reaches systemd (the bot process itself doesn't crash — only the loop's
internal `Task` dies), so `Restart=on-failure` never fires, `systemctl status` stays green, and the
digest simply never posts again, silently, until someone restarts the bot.
**Why it happens:** `discord.ext.tasks.loop`'s `reconnect=True` default only retries a narrow
network-exception allowlist (`OSError`, `discord.GatewayNotFound`, `discord.ConnectionClosed`,
`aiohttp.ClientError`, `asyncio.TimeoutError`) — verified by reading the pinned v2.7.1 source
(`discord/ext/tasks/__init__.py`). Anything else is treated as fatal to the loop.
**How to avoid:** Wrap the entire loop-body call in `try/except Exception: logger.exception(...)`
*inside* the decorated coroutine (Pattern 3 above), so no application-level bug is ever visible to
the loop's own exception machinery. This is the exact `PITFALLS.md §18(d)` failure mode (a silently
stale/missing surface with no other symptom) applied to a fourth boundary the CONTEXT's D-04/D-09/
D-17/D-19 list did not yet name.
**Warning signs:** `journalctl -u creatorpulse-bot` shows one `ERROR` line from `_error` around the
time of a missed digest, then nothing at 08:15 on subsequent days, while `systemctl status` reports
the unit as still running.

### Pitfall 2: Assuming `channel.send()` to an inaccessible channel fails loudly by default

**What goes wrong:** `DISCORD_CHANNEL_ID` is validated as *parseable as an integer* by D-19, but an
integer that parses fine can still name a channel the bot's role cannot see or post in (e.g., wrong
ID pasted, or the bot's invite was scoped to a different channel). `channel.send()` in that state
raises `discord.Forbidden` (403) at the moment of the first send — not at startup, unless the plan
adds an explicit preflight.
**Why it happens:** discord.py does not validate channel-level permissions when a
`discord.TextChannel` object is constructed or fetched by ID; the permission check happens
server-side, at message-send time.
**How to avoid:** D-19 already requires "loud failure with a named cause" for config. The natural
place to catch this early is a startup preflight: fetch the channel object via
`client.get_channel(id)` or `await client.fetch_channel(id)` inside `setup_hook`/`on_ready`, and if
it is `None` or a `discord.Forbidden` is raised, log a named error ("channel <id> not visible or not
postable by this bot — check the invite's channel permissions") before the digest loop ever starts,
rather than letting the first `channel.send()` at 08:15 be the first time this surfaces.
**Warning signs:** the bot starts cleanly, slash commands register, but the first digest attempt
(or `/status`, if it also posts) raises `discord.Forbidden` at the exact 08:15 tick — same failure
shape as Pitfall 1 if not caught inside the guarded `try/except`.

### Pitfall 3: An invalid `DISCORD_BOT_TOKEN` looks like a hang, not a crash, without a login step

**What goes wrong:** `discord.LoginFailure` is raised by `Client.login()`/`Client.run()` on an
invalid or revoked token (HTTP 401 during the static-login call). Because `Client.run()` is a
blocking call that internally awaits `login()` before ever opening the gateway, an invalid token
surfaces immediately as an unhandled exception — the process crashes with a non-zero exit, which
systemd correctly marks as `failed`. This is *not* silent, but it is easy to misdiagnose as a
network problem if the error message isn't logged with enough context (D-19 pattern) before the
`client.run(token)` call is made.
**Why it happens:** discord.py's login flow makes one authenticated HTTP call before any gateway
connection; a bad token fails there, deterministically, every restart.
**How to avoid:** D-19's "fails loudly before connecting" already covers config *presence* and
*shape* (integer parsing). This is the one failure D-19 cannot catch in advance — a syntactically
valid but revoked/wrong token can only be caught by discord.py's own login call. No extra code is
needed beyond letting `discord.LoginFailure` propagate uncaught (matching the "fail loudly, not
silently degrade" pattern already used for `SheetNotShared`/`SheetsKeyfileUnusable`); do not wrap
`client.run()` in a broad `try/except` that swallows this.
**Warning signs:** `journalctl -u creatorpulse-bot` shows `discord.errors.LoginFailure: Improper
token has been passed.` and `RestartSec=10` produces a restart loop identical in shape to any other
bad-config crash loop.

## Code Examples

### Discord config resolution, following `resolve_sheets_config()`'s established shape (D-18/D-19)

```python
# Pattern matches config.py's existing resolve_sheets_config() — empty string treated as unset,
# not a valid value, per the established rule this codebase already follows.
import os
from dataclasses import dataclass


class DiscordConfigError(Exception):
    """Raised when a required Discord env var is missing or fails to parse (D-19)."""


@dataclass(frozen=True, slots=True)
class DiscordConfig:
    bot_token: str
    channel_id: int
    guild_id: int
    webhook_url: str


def resolve_discord_config() -> DiscordConfig:
    token = os.environ.get("DISCORD_BOT_TOKEN") or None
    channel_raw = os.environ.get("DISCORD_CHANNEL_ID") or None
    guild_raw = os.environ.get("DISCORD_GUILD_ID") or None
    webhook = os.environ.get("DISCORD_WEBHOOK_URL") or None

    if not token:
        raise DiscordConfigError("DISCORD_BOT_TOKEN is not set")
    if not channel_raw:
        raise DiscordConfigError("DISCORD_CHANNEL_ID is not set")
    if not guild_raw:
        raise DiscordConfigError("DISCORD_GUILD_ID is not set")
    if not webhook:
        raise DiscordConfigError("DISCORD_WEBHOOK_URL is not set")

    try:
        channel_id = int(channel_raw)
    except ValueError as exc:
        raise DiscordConfigError(
            f"DISCORD_CHANNEL_ID must be an integer, got {channel_raw!r}"
        ) from exc
    try:
        guild_id = int(guild_raw)
    except ValueError as exc:
        raise DiscordConfigError(f"DISCORD_GUILD_ID must be an integer, got {guild_raw!r}") from exc

    return DiscordConfig(bot_token=token, channel_id=channel_id, guild_id=guild_id, webhook_url=webhook)
```

### Digest task loop, guarded per Pitfall 1

```python
# Source: discord.py v2.7.1 docs (discordpy.readthedocs.io/en/stable/ext/tasks/index.html) for
# the time= parameter shape; discord.py v2.7.1 source for the exception-retry allowlist this
# guard exists to work around.
from datetime import time
from zoneinfo import ZoneInfo

from discord.ext import tasks

MANILA = ZoneInfo("Asia/Manila")
DIGEST_TIME = time(hour=8, minute=15, tzinfo=MANILA)


class CreatorPulseBot(commands.Bot):
    @tasks.loop(time=DIGEST_TIME)
    async def digest_loop(self) -> None:
        try:
            await post_digest(self.get_channel(self.channel_id), self.db_path)
        except Exception:
            logger.exception("digest tick failed; next scheduled time will retry")

    @digest_loop.before_loop
    async def _before_digest(self) -> None:
        await self.wait_until_ready()  # channel objects only resolve after READY
```

### Slash command with the recommended non-defer path (3-second window)

```python
# Confirmed: a single indexed SQLite read (idx_metrics_creator_date) completes in low
# single-digit milliseconds locally — comfortably inside Discord's 3-second initial-response
# window (docs.discord.com/developers/interactions/receiving-and-responding). defer() is not
# needed and adds a second round trip (an edit-the-deferred-response call) for no benefit here.
@bot.tree.command(name="status", description="Report last collector run's status")
async def status(interaction: discord.Interaction) -> None:
    conn = db.connect(db_path, create=False)
    try:
        text = build_status_text(conn)
    finally:
        conn.close()
    await interaction.response.send_message(text)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Global slash command registration | Guild-scoped registration during development/small-server deployment | Standard discord.py 2.x guidance since app_commands landed (2.0, 2022) | Immediate propagation vs. up to 1 hour — already what CONTEXT/ROADMAP pre-lock; confirmed here, not a new finding. |
| `discord.Client` with manually attached `CommandTree` | `commands.Bot`, which already exposes `self.tree` | Consistent since 2.0 | Fewer lines for this project's shape (two slash commands, no prefix commands, one task loop). |

**Deprecated/outdated:** nothing in this phase's surface is deprecated. discord.py 2.7.1 (released
March 2026 per pyproject.toml's locked version) is current.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `discord.Forbidden` (not some other exception) is what `channel.send()` raises when the bot cannot post to the named channel. | Pitfall 2, Priority 6 | If a different exception type is actually raised, the preflight catch clause in the plan needs adjusting; low risk — either way it is an `Exception` subclass and the guarded `try/except Exception` in Pattern 3 still prevents the loop from dying. |
| A2 | Guild-scoped `tree.sync()` carries no meaningful rate-limit risk when called on every bot process start for two commands. | Pattern 2 | If wrong, a restart-loop scenario (Pitfall 3's crash loop) combined with sync-on-every-start could hit a 429; low risk given `RestartSec=10` throttles restart frequency already, and Discord's command-sync rate limits are documented as generous for guild-scoped operations. |
| A3 | A single indexed SQLite read (a handful of rows) completes well under 3 seconds on the target VPS, so `defer()` is unnecessary for both `/creator` and `/status`. | Code Examples, Priority 4 | If the VPS is under unexpected load or the query planner behaves differently at scale, an interaction could time out; low risk at this project's data volume (a few creators, a few days of history) and reversible (adding `defer()` is a 2-line change). |
| A4 | The 2000-character message content limit is not explicitly stated on Discord's own `resources/message` documentation page (as fetched this session) and is instead corroborated only by community/GitHub-issue reports of the `50035` error code. | Priority 5 | Low risk — extremely widely and consistently reported across independent sources (multiple `Rapptz/discord.py` and `python-discord/bot` issues); the digest's row count (3–6) makes this a non-issue either way. |

## Open Questions

1. **Does a synchronous `sqlite3` read inside a discord.py event-loop coroutine ever need
   `asyncio.to_thread()`?**
   - What we know: ROADMAP's Notes explicitly say "no blocking calls in the event loop" as a
     phase-wide constraint, but do not define a latency threshold. The project's actual query load
     (a handful of creators, an indexed lookup) is fast in absolute terms.
   - What's unclear: whether the note is a hard requirement the plan-checker will gate on, or
     guidance to keep in mind. Local disk I/O for a database this small is not measured to be slow
     enough to matter in practice.
   - Recommendation: treat it as guidance, not a requirement to route every DB call through
     `asyncio.to_thread()` — that would add complexity (thread-safety of `sqlite3.Connection`
     objects across threads needs care) disproportionate to the actual risk at this data volume. If
     the plan-checker or the author wants strict compliance, the two-line fix is
     `await asyncio.to_thread(build_status_text, conn)` per handler.

2. **Exact wording of the "why none of the intents are privileged" answer for criterion 5.**
   - What we know: `Intents.default()` already excludes all three privileged intents (Presences,
     Server Members, Message Content); slash-command interactions arrive over the gateway as
     `INTERACTION_CREATE` events, not as `MESSAGE_CREATE` events, so `message_content` specifically
     is never needed for this bot's two commands.
   - What's unclear: nothing technically — this is settled. Left here only because CONTEXT itself
     flags this as the graded criterion and the exact spoken sentence belongs in `06-UAT.md`, not
     baked into a plan file as a checkbox that could be checked without the author actually saying
     it.
   - Recommendation: the plan should include a task that has the author write this sentence into
     `06-UAT.md` at the moment the bot is invited (per CONTEXT's own "Specific Ideas" note), mirroring
     Phase 5's still-PENDING criterion-5 entry as a cautionary example not to repeat.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| discord.py | Bot process (all of BOT-01..05) | Yes (locked) | 2.7.1 (pyproject.toml) | — |
| Python `zoneinfo` (stdlib) | Digest schedule timezone (D-03) | Yes (bundled, Python 3.9+) | Python 3.12 target | — |
| Discord Developer Portal bot registration + invite | Bot process login, slash command visibility (BOT-07) | **Not verifiable from this session** — human-owned, out of scope for research | — | None — this is the one true blocker; BOT-06/07 are human-built and must be completed before the bot process can run at all. |
| `deploy/creatorpulse-bot.service` install/enable on the droplet | BOT-06 | Committed to repo, **not yet installed** (per STATE.md: "must NOT be installed or enabled yet") | — | Install after this phase's `bot` subcommand stops being a stub. |
| SQLite WAL-mode file at `/var/lib/creatorpulse/creatorpulse.db` | Bot's read path | Exists once the collector has run at least once; not independently verified this session | — | None needed — `db.connect(create=False)` already raises `DatabaseNotInitialized` loudly if absent (Phase 3, proven). |

**Missing dependencies with no fallback:**
- Discord Developer Portal bot registration, intents configuration, and invite URL (BOT-07) —
  human-owned, must exist before the bot process can authenticate at all. This is not something
  research or planning can substitute for.

**Missing dependencies with fallback:**
- None beyond the above — everything else (library, stdlib, unit file) is either already present or
  has a documented install step later in the phase's own plan (installing/enabling the systemd unit
  after the `bot` subcommand is implemented).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (already locked, `pyproject.toml` `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` (`testpaths = ["tests"]`) |
| Quick run command | `pytest tests/test_bot.py -x` (new file this phase creates) |
| Full suite command | `pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOT-01 | Digest text lists top movers and that run's failures, from a temp SQLite DB | unit | `pytest tests/test_bot.py -k digest -x` | ❌ Wave 0 |
| BOT-02 | ±20% day-over-day flag renders on the correct rows | unit | `pytest tests/test_bot.py -k flag -x` | ❌ Wave 0 |
| BOT-03 | Alert message content built from a run's failures (formatter only — the webhook POST plumbing is untested per D-20) | unit | `pytest tests/test_bot.py -k alert or tests/test_cli.py -k alert -x` | ❌ Wave 0 |
| BOT-04 | `/creator <name>` formatter — current numbers + 7-row trend, case-insensitive match, unknown-name fallback | unit | `pytest tests/test_bot.py -k creator -x` | ❌ Wave 0 |
| BOT-05 | `/status` formatter — last run, duration, rows, failures, OK/STALE verdict | unit | `pytest tests/test_bot.py -k status -x` | ❌ Wave 0 |
| BOT-06 | Bot survives reboot as its own systemd service | manual-only — human-observed gate, D-20/ROADMAP-locked | — | N/A (untestable by design) |
| BOT-07 | Bot registration, intents, invite URL in Developer Portal | manual-only — human-owned, out of scope for automated tests | — | N/A |

### Sampling Rate

- **Per task commit:** `pytest tests/test_bot.py -x` (and `tests/test_db.py`/`tests/test_collector.py`
  if D-06/D-13 touched them in that commit)
- **Per wave merge:** `pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus the human-observed real-data gate
  ROADMAP names (a real scheduled digest and a real failure alert landing in the real channel)

### Wave 0 Gaps

- [ ] `tests/test_bot.py` — new file, covers the pure formatters (digest text, trend text, status
  text, ±20% flag, percent computation, staleness verdict) against a temp SQLite database — the
  exact pattern `tests/test_sheets.py` already establishes for `build_dashboard_rows()`.
- [ ] `tests/test_db.py` — extend for the `run_failures` table DDL and `write_run_row()` returning
  `cursor.lastrowid` (D-06).
- [ ] `tests/test_collector.py` — extend for `collect_once()` accumulating failure detail (creator,
  source, cause, message), not just a count (D-06).
- [ ] `tests/test_sheets.py` — imports updated to pull `LATEST_ROWS_SQL`/`LatestRow`/
  `fetch_latest_rows()` from `db.py` instead of `sheets.py` (D-13) — a mechanical import change,
  not a new test.
- No new test framework or fixture-root install needed — `pytest`, `tmp_path`, and the
  temp-SQLite-database pattern are already fully wired from Phase 1 onward.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | Partially | The bot token and webhook URL are bearer credentials read from a `chmod 600` env file (already-established pattern, D-18) — no code-level authentication of *users* exists or is needed; the bot has one operator-controlled guild. |
| V3 Session Management | No | No web sessions; Discord's gateway connection and interaction tokens are managed entirely by discord.py internally. |
| V4 Access Control | Partially | `/creator` and `/status` are visible to anyone in the one guild the bot is invited to — no per-user authorization is required or specified (a single-operator project per CLAUDE.md's Out of Scope table: "Authentication, multi-user, roles"). Discord's own guild-membership boundary is the access control, not application code. |
| V5 Input Validation | Yes | `/creator <name>` input is matched case-insensitively and *exactly* against known `creator_id` values (D-15) — no string interpolation into SQL; `fetch_latest_rows()`/the trend query use parameterized `conn.execute()` calls exactly as the rest of the codebase already does. `DISCORD_CHANNEL_ID`/`DISCORD_GUILD_ID` are validated as integers before use (D-19). |
| V6 Cryptography | No | No cryptographic operations are added by this phase; the bot token is an opaque credential handled entirely by discord.py's own TLS-secured gateway connection. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| SQL injection via `/creator <name>` | Tampering | Already the codebase's established pattern: all `db.py`/`sheets.py` queries use `conn.execute(sql, params)` with bound parameters, never f-string interpolation. The `/creator` command's name lookup must follow the same discipline — `WHERE creator_id = ?` bound, not `f"WHERE creator_id = '{name}'"`. |
| Bot token leakage into logs or error messages | Information Disclosure | The token is read once via `resolve_discord_config()` and passed directly to `client.run(token)`; it must never be logged, and error messages (e.g., `DiscordConfigError`) must name the *variable*, not the *value* — the same discipline `resolve_sheets_config()` already follows for keyfile paths. |
| Overprivileged bot role in the guild | Elevation of Privilege | Out of scope for code — this is exactly what BOT-07's human-owned Developer Portal step controls (Administrator already stripped per CONTEXT's domain section: "leaving View Channel + Send Messages"). Nothing in this phase's code can compensate for an overprivileged invite; it can only rely on the intents actually requested being minimal (`Intents.default()`, no privileged intents). |
| A malicious or malformed `creators.yaml` entry reaching Discord unescaped | Tampering / Information Disclosure | Not new to this phase — `creators.yaml` is operator-authored (CFG-01..03, already validated at Phase 3). The digest/trend/status text interpolates `creator_id`/`name` values directly into a plain-text Discord message; Discord's own markdown renders any Markdown syntax present, but since `creators.yaml` is self-authored (not third-party input), this is a low-severity, already-accepted risk, not a new attack surface this phase introduces. |

## Sources

### Primary (HIGH confidence)

None reached HIGH this session — no source both came from an authoritative origin *and* was
independently tool-verified in a way the `classify-confidence` seam scores as HIGH (that tier
requires a `context7`-class fetch or a verified package-registry check; no MCP `context7` tool was
exposed in this session, so all lookups fell back to `WebFetch`/`WebSearch`, capped at
LOW/MEDIUM by the seam's own scoring).

### Secondary (MEDIUM confidence — cross-checked, or direct pinned-version source read)

- discord.py v2.7.1 **source code**, directly fetched and quoted this session:
  `github.com/Rapptz/discord.py` at tag `v2.7.1`, `discord/ext/tasks/__init__.py` (the `_loop`
  method, `_valid_exception` tuple, `error()`/`before_loop`/`after_loop` hooks) and
  `discord/app_commands/tree.py` (`sync()`, `copy_global_to()` docstrings). Pinned to the exact
  locked version, so this is effectively a primary source despite the seam scoring `webfetch`
  fetches as LOW by policy.
- Discord developer docs, directly fetched: `docs.discord.com/developers/interactions/receiving-and-responding`
  (3-second interaction window, `defer()` semantics) and `docs.discord.com/developers/resources/message`
  (checked for the content-length limit; not explicitly stated on that page — see Assumption A4).
- `discordpy.readthedocs.io/en/stable/ext/tasks/index.html` and `.../intents.html`, directly
  fetched: `time=` parameter type, timezone assumption, `Intents.default()` composition, the three
  privileged intents.
- Community cross-checks (WebSearch, multiple independent results per query): `Intents.default()` +
  slash commands needing no privileged intents (Python Discord docs, discord.py-masterclass,
  Rapptz/discord.py discussion #8442); `commands.Bot` vs. `discord.Client` line-count comparison
  (discord.py-masterclass, Umbra's blog); 2000-character message limit + `HTTPException` 50035
  (multiple `Rapptz/discord.py` and `python-discord/bot` GitHub issues); `discord.LoginFailure`
  triggers and propagation (Rapptz/discord.py issue #7336); SQLite WAL read-only directory
  write-permission requirement (`sqlite.org/wal.html`, SQLite forum threads).

### Tertiary (LOW confidence)

- None isolated to a single unverified source — every finding above was either a direct pinned
  source-code read or corroborated by 2+ independent web results.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new library, versions read directly from the repo's own `pyproject.toml`.
- Architecture: MEDIUM — patterns match CONTEXT's pre-locked decisions; the guild-scoped-sync and
  `commands.Bot`-vs-`Client` findings are corroborated by multiple independent community sources
  plus direct source-code confirmation, but no `context7`-tier fetch was available this session.
- Pitfalls: MEDIUM-HIGH for Pitfall 1 specifically (direct pinned-version source-code read, the
  strongest evidence gathered this session); MEDIUM for Pitfalls 2/3 (documented exception types,
  standard community-corroborated behavior, not independently reproduced in this project's code).

**Research date:** 2026-08-06
**Valid until:** 30 days (discord.py is a stable, slow-moving library at this project's usage
depth; re-verify sooner only if discord.py is upgraded past 2.7.1 before this phase executes).
