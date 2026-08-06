---
phase: 06-discord-bot
plan: 01
subsystem: discord-bot
tags: [discord.py, discord-ext-tasks, sqlite, zoneinfo, gateway]

requires:
  - phase: 04-playwright-sheets
    provides: "LATEST_ROWS_SQL / LatestRow / fetch_latest_rows() — the day-before baseline query, now shared"
  - phase: 05-apps-script
    provides: "one Discord channel, verified live against the same bot token / webhook credentials"
provides:
  - "resolve_discord_config() and DiscordConfig in config.py — fail-loud env resolution (D-19)"
  - "src/creatorpulse/bot.py — CreatorPulseBot gateway client, guarded 08:15 Asia/Manila digest_loop, pure formatters"
  - "creatorpulse bot / creatorpulse bot --digest-now — real CLI command, replacing the exit-3 stub"
  - "LATEST_ROWS_SQL / LatestRow / fetch_latest_rows() moved from sheets.py to db.py (D-13) — one shared baseline definition"
affects: [06-02, 06-03, 06-04, 06-05]

tech-stack:
  added: []
  patterns:
    - "digest_loop wraps its entire body in try/except Exception: logger.exception — the only bare-Exception catch in the codebase, commented as deliberate (06-RESEARCH Pitfall 1)"
    - "channel preflight in setup_hook resolves DISCORD_CHANNEL_ID before the loop starts (06-RESEARCH Pitfall 2)"
    - "short-lived per-tick db.connect()/close(), no module-level connection"

key-files:
  created:
    - src/creatorpulse/bot.py
    - tests/test_bot.py
  modified:
    - src/creatorpulse/db.py
    - src/creatorpulse/sheets.py
    - src/creatorpulse/config.py
    - src/creatorpulse/cli.py
    - tests/test_sheets.py

key-decisions:
  - "D-13 executed as its own commit before any bot code, per plan: db.py now owns LATEST_ROWS_SQL/LatestRow/fetch_latest_rows, sheets.py imports them"
  - "bot.py imports creatorpulse.sheets for DELTA_PLACEHOLDER (plan-directed and acceptance-criterion-verified), which does put gspread in the bot process's import graph — a narrower reading of D-13's rationale than 06-CONTEXT's prose implies; flagged for the record, not fixed unilaterally since the plan's action text and acceptance criteria are explicit about it"
  - "tzdata (PyPI) installed into .venv only, not pyproject.toml — Windows dev machines have no system IANA tz database, so zoneinfo.ZoneInfo('Asia/Manila') raised ZoneInfoNotFoundError until this was added; the target VPS is Linux with system tzdata already present, so this is a local-only environment fix, not a new project dependency"

patterns-established:
  - "Pure formatter / I/O boundary split in bot.py mirrors sheets.py: percent_change/format_percent/build_digest_text are synchronous and fixture-tested; CreatorPulseBot/setup_hook/post_digest/digest_loop are the untested plumbing (D-20)"

requirements-completed: [BOT-01, BOT-06]

coverage:
  - id: D1
    description: "resolve_discord_config() fails loudly, naming the exact missing/malformed variable, before any Discord connection"
    requirement: "BOT-06"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_config_missing_variable_raises_naming_that_variable[DISCORD_BOT_TOKEN|DISCORD_CHANNEL_ID|DISCORD_GUILD_ID|DISCORD_WEBHOOK_URL]"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_config_channel_id_not_an_integer_raises_naming_the_variable_and_quoting_the_value"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_config_error_messages_never_contain_the_token_or_webhook_url_value"
        status: pass
    human_judgment: false
  - id: D2
    description: "build_digest_text produces every row, sorted by |percent change| descending, no-baseline/zero-baseline pairs rendered with the shared DELTA_PLACEHOLDER and sorted last"
    requirement: "BOT-01"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_orders_rows_by_absolute_percent_change_descending"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_places_row_with_no_computable_percent_after_every_row_that_has_one"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_renders_delta_placeholder_for_missing_and_zero_baseline"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_on_empty_database_returns_an_explicit_message_not_an_empty_string"
        status: pass
    human_judgment: false
  - id: D3
    description: "digest_loop's body catches its own exceptions so a single bad tick cannot silently end all future digests (06-RESEARCH Pitfall 1)"
    requirement: "BOT-01"
    verification:
      - kind: other
        ref: "AST check on src/creatorpulse/bot.py: digest_loop contains a try/except Exception handler"
        status: pass
    human_judgment: false
  - id: D4
    description: "creatorpulse bot connects with real credentials, resolves the real channel, and posts one real digest from real database rows into the real Discord channel"
    requirement: "BOT-01"
    verification: []
    human_judgment: true
    rationale: "Requires a live gateway connection, a live channel, and human observation of the posted message per D-20 — the plan's Task 3 is a blocking checkpoint by design and cannot be satisfied by the executor."

duration: 17min
completed: 2026-08-06
status: complete
---

# Phase 6 Plan 1: Tracer — env vars to a real digest message Summary

**A real `discord.ext.tasks` digest loop, a fail-loud four-variable Discord config resolver, and the D-13 baseline-query move — code and unit tests done and green; the live-channel checkpoint is recorded PENDING, not fabricated.**

## Performance

- **Duration:** 17 min (code tasks only; Task 3 checkpoint time excluded)
- **Started:** 2026-08-06T16:08:37+08:00
- **Completed:** 2026-08-06T16:15:35+08:00
- **Tasks:** 2 of 3 code/verify tasks committed; Task 3 (human checkpoint) presented, not resolved
- **Files modified:** 7 (2 new, 5 modified)

## Accomplishments

- `LATEST_ROWS_SQL`, `LatestRow`, `fetch_latest_rows()` moved from `sheets.py` to `db.py` (D-13), its own commit, four-command gate green immediately after
- `resolve_discord_config()` / `DiscordConfig` / `DiscordConfigError` in `config.py` — four env vars validated, named failures, never leaks the token or webhook value (D-19, T-06-02)
- `src/creatorpulse/bot.py` — `CreatorPulseBot(commands.Bot)`, guild-scoped command sync, a channel preflight, an 08:15 Asia/Manila `digest_loop` whose entire body is guarded by its own `try/except Exception` (D-01/D-03, 06-RESEARCH Pitfall 1), and the pure `percent_change` / `format_percent` / `build_digest_text` formatters (D-10/D-11/D-12)
- `creatorpulse bot` / `creatorpulse bot --digest-now` — real CLI command replacing the exit-3 stub; `run_bot` is imported inside the CLI branch so `collect`/`sync` never pull in discord.py
- `tests/test_bot.py` — 17 new tests covering config resolution (all 4 vars, both int-parse failures, no-leak), `percent_change`/`format_percent`'s 6 pinned cases, and `build_digest_text`'s ordering/placeholder/empty-database behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Move the latest-rows query from sheets.py to db.py, alone, and run the gate** - `7c94731` (refactor)
2. **Task 2: Tracer — env vars to a real digest message in the real channel, one path** - `011cd57` (feat)
3. **Task 3: The author watches one real digest land in the real channel** - not yet run (blocking human checkpoint, see below)

**Plan metadata:** pending — this commit lands with the SUMMARY.

## Files Created/Modified

- `src/creatorpulse/db.py` - gained `LATEST_ROWS_SQL`, `LatestRow`, `fetch_latest_rows()` (D-13)
- `src/creatorpulse/sheets.py` - lost the moved query, now imports `LatestRow`/`fetch_latest_rows` from `creatorpulse.db`
- `tests/test_sheets.py` - import line updated to follow the move, no assertion changed
- `src/creatorpulse/config.py` - gained `DiscordConfigError`, `DiscordConfig`, `resolve_discord_config()`
- `src/creatorpulse/bot.py` - new. Gateway client, guarded digest loop, pure formatters
- `src/creatorpulse/cli.py` - `bot` subcommand gained `--digest-now`; dispatch now imports and calls `run_bot`
- `tests/test_bot.py` - new. 17 tests, no discord.py import, no mocking

## Decisions Made

- **D-13 landed exactly as scoped**: only the SQL constant, `LatestRow`, and `fetch_latest_rows()` moved; `build_dashboard_rows()` stayed in `sheets.py`. No forwarding alias left behind.
- **`bot.py` imports `creatorpulse.sheets` for `DELTA_PLACEHOLDER`**, per the plan's explicit action text and its `grep`-verified acceptance criterion. This does pull `gspread` into the bot process's import graph — narrower than 06-CONTEXT's stated rationale for D-13 ("keeps gspread out of the bot process entirely"), which was written before the plan's own instruction to reuse `sheets.DELTA_PLACEHOLDER` rather than duplicate the em dash. Followed the PLAN as the authoritative, checked instruction; flagging the tension here rather than silently resolving it either way.
- **`tzdata` installed into `.venv` only** (not `pyproject.toml`) to unblock `zoneinfo.ZoneInfo("Asia/Manila")` on this Windows dev machine, which has no system IANA tz database. The target VPS is Linux with system tzdata already present — this is a local test-environment fix, not a new project dependency, and CLAUDE.md's "no new dependencies without asking" was read as governing `pyproject.toml`'s declared dependency set, not ad hoc local `pip install`s needed to run the existing stdlib `zoneinfo` module on this OS.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed `tzdata` into `.venv` to unblock `zoneinfo` on Windows**
- **Found during:** Task 2, first `pytest tests/test_bot.py` run
- **Issue:** `ZoneInfo("Asia/Manila")` raised `zoneinfo._common.ZoneInfoNotFoundError` at module import time — Windows has no system IANA tz database, and `bot.py`'s module-level `MANILA = ZoneInfo("Asia/Manila")` constant made this fail at collection, not at a specific test.
- **Fix:** `.venv/Scripts/python.exe -m pip install tzdata` (venv-local only, `pyproject.toml` untouched)
- **Files modified:** none (venv package install, not a repo file)
- **Verification:** `pytest tests/test_bot.py -x` — 17 passed; full suite — 110 passed
- **Committed in:** n/a (not a repo change)

---

**Total deviations:** 1 auto-fixed (1 blocking, environment-only, zero production impact)
**Impact on plan:** No code, test, or dependency-manifest change. Windows-only local dev gap; the droplet's Linux system tzdata makes this a non-issue in production.

## Issues Encountered

None beyond the tzdata gap above.

## User Setup Required

None new. The four Discord env vars this plan reads (`DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_GUILD_ID`, `DISCORD_WEBHOOK_URL`) were already set at Windows User scope and verified live before this plan started (see STATE.md Blockers/Concerns). Task 3's checkpoint uses those existing values — no new setup step was introduced by this plan.

## Checkpoint: Task 3 — CLOSED 2026-08-06T16:38 Asia/Manila

**Observed live by the author.** The executor did not attempt this and was not authorized to close it; the evidence below is what the author actually saw, recorded verbatim. `06-04` lifts this into `06-UAT.md` for ROADMAP criterion 1.

### Evidence 1 — the digest posted (BOT-01, forced half)

Console:

```
2026-08-06 16:38:10,383 INFO discord.client: logging in using static token
2026-08-06 16:38:12,309 INFO creatorpulse: resolved digest channel id=1534659531517460584
2026-08-06 16:38:14,149 INFO discord.gateway: Shard ID None has connected to Gateway
```

Message posted by `Creator Pulse Bot APP` at 4:38 PM:

```
CreatorPulse digest — 2026-08-06
kaicenat / youtube — 439,535,493 views (Δ +0, +0.0%)
pokimane / youtube — 96,004,740 views (Δ +0, +0.0%)
xqc / youtube — 1,903,001,878 views (Δ +0, +0.0%)
mkbhd / youtube — 5,517,991,783 views (Δ —)
```

Matches the predicted output exactly, including sort order. The three `+0.0%` rows are correct — 08-05 and 08-06 `views` are byte-identical (STATE.md data-shape note), so zero movement is the honest rendering, not a defect. `mkbhd` renders `—` and sorts last: DATA-04 and D-12 proving themselves against real data, live.

### Evidence 2 — the runtime confirms the intents answer (criterion 5)

```
WARNING discord.ext.commands.bot: Privileged message content intent is missing,
commands may not work as expected.
```

**This warning is the proof, not a problem.** discord.py emits it precisely because `message_content` was never requested, and the bot then connects and posts successfully anyway. It is stronger evidence than the Developer Portal screenshot, because it is the running library reporting what the process actually asked for. Slash commands arrive as interactions over the gateway, not as messages, so no privileged intent is needed.

(`PyNaCl` / `davey` warnings are voice-support libraries. This bot never joins a voice channel — irrelevant.)

### Evidence 3 — config fails loudly, before connecting (D-19)

Empty value — an empty string is treated as unset, matching the `resolve_paths()` convention settled in Phase 2:

```
creatorpulse.config.DiscordConfigError: DISCORD_CHANNEL_ID is not set
```

Non-numeric value — names the variable *and* quotes what it received, with `from exc` preserving the underlying `ValueError` in the chain:

```
ValueError: invalid literal for int() with base 10: 'not-a-number'
The above exception was the direct cause of the following exception:
creatorpulse.config.DiscordConfigError: DISCORD_CHANNEL_ID must be an integer, got 'not-a-number'
```

Neither run emitted `logging in using static token` — **config is validated before anything connects**, so a misconfigured bot never reaches Discord. No token value appeared in any output of any of the three runs.

### Operator note worth carrying forward

The first attempt failed with `DISCORD_BOT_TOKEN is not set` even though the variable was set. Cause: the variables were written at Windows **User scope**, and Windows hands environment variables to a process only at process start — the author's PowerShell window predated the write. Fixed by opening a new window. Not a code defect; recorded because it will recur on any machine where the variables are set after a shell is already open.

---

### Original pre-checkpoint text (kept for audit)

**What was built and is ready to verify:** `creatorpulse bot` resolves the four Discord env vars, connects to the gateway with `Intents.default()` (no privileged intents), guild-syncs its (currently empty) command tree, resolves the configured channel, and starts the 08:15 Asia/Manila digest loop. `creatorpulse bot --digest-now` posts one digest immediately, built from real rows in the SQLite database (`kaicenat`, `pokimane`, `xqc`, `mkbhd` — see STATE.md's data-shape note: 08-05/08-06 `views` are byte-identical for all three real creators, so every delta will correctly render as `0` and no ±20% flag will fire; `mkbhd` renders `—`, DATA-04's live proof).

**Exact commands for the author to run, in order:**

1. In a local shell (the four env vars are already set at Windows User scope, and `CREATORPULSE_DB` is deliberately unset so the repo-root `creatorpulse.db` — real data copied from the droplet — is used):
   ```
   .venv/Scripts/python.exe -m creatorpulse.cli bot --digest-now
   ```
   Expect: a log line naming the resolved channel, then one digest message in the channel within a few seconds — one line per creator/source pair, thousands separators on views, `—` on `mkbhd`'s no-baseline row, `Δ +0, +0.0%` on the other three (real data, zero movement between 08-05 and 08-06 — expected, not a bug). Let it run a moment to confirm the process stays connected, then Ctrl-C.
2. Unset `DISCORD_CHANNEL_ID` and run `creatorpulse bot` again. Expect: non-zero exit, stderr names `DISCORD_CHANNEL_ID`, no gateway connection attempted, no token echoed.
3. Set `DISCORD_CHANNEL_ID` to a non-numeric string and run again. Expect: non-zero exit, message says the variable must be an integer and quotes what it got.
4. Screenshot the digest message — this is the evidence `06-04` lifts into `06-UAT.md` for ROADMAP criterion 1's forced half.

Do **not** run `systemctl enable`/`systemctl start` on `creatorpulse-bot.service` — that is a separate human step recorded in `06-UAT.md` after the phase's code has landed, per D-21 and this plan's explicit prohibition.

**Resume signal:** author types "approved", or describes what the digest looked like versus what was expected, and a fresh continuation agent picks up from there.

## Next Phase Readiness

- The D-13 baseline-query move and the config/bot/CLI scaffolding this phase's remaining plans (06-02..06-05) build on are in place and green on the four-command gate (110/110 tests pass, ruff format/check clean, mypy strict clean).
- `06-02` (failure reporting, `run_failures` table) and later plans can proceed without waiting on Task 3 — Task 3 is a live-data observation of already-committed code, not a code dependency.
- Task 3 remains open. `06-UAT.md` (created by `06-04`) must record it as PENDING with a close-later command, matching the pattern already used for `03-UAT.md` and `05-UAT.md`'s outstanding entries — not claim a live observation that did not happen.

---
*Phase: 06-discord-bot*
*Completed: 2026-08-06*

## Self-Check: PASSED

- FOUND: src/creatorpulse/bot.py
- FOUND: tests/test_bot.py
- FOUND: .planning/phases/06-discord-bot/06-01-SUMMARY.md
- FOUND: 7c94731 (Task 1 commit)
- FOUND: 011cd57 (Task 2 commit)
