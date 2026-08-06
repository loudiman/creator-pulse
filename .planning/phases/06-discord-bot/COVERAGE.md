# API Coverage — Phase 6 (Discord Bot: Gateway, Application Commands, and the Webhook Reused From Python)

`INTEGRATE` is the default. This file is the **subtraction record**: every `OPT-OUT` carries a
one-line reason, cited to a written decision. The `INTEGRATE` rows are the small minority — the
value of this file is in the reasoned remainder, not in the inventory of what got built.

**Scope of the capability surface:** what could plausibly serve *this project's stated purpose* —
a single-guild bot that posts one scheduled digest, answers two slash commands, and a collector
that POSTs failure alerts to a webhook — not Discord's entire API. Phase 5's
`05-apps-script/COVERAGE.md` already recorded the incoming-webhook surface `Code.gs` uses; this
file does not restate those rows. The exception is the two webhook capabilities this phase's
collector newly exercises from Python (`_post_alert()` in `cli.py`), which appear here as
`INTEGRATE` rows pointing back at that file rather than being re-researched.

Citations: `06-CONTEXT.md` decisions (D-NN), `06-RESEARCH.md` (Architecture Patterns, Don't
Hand-Roll, Common Pitfalls), `ROADMAP.md` §"Phase 6: Discord Bot" Notes, `.claude/CLAUDE.md`
(no-new-dependencies rule), and `05-apps-script/COVERAGE.md` for the webhook surface this phase
reuses rather than restates.

**Format contract:** exactly ONE `| capability | decision | reason |` table in this file. A second
table's header row is parsed as a data row by the `api-coverage` gate and fails it with
`decision "DECISION" not in {INTEGRATE, OPT-OUT}`. Capability ≤ 80 chars, reason ≤ 200 chars,
neither containing a literal pipe or newline.

| capability | decision | reason |
|---|---|---|
| `discord.Intents.default()` | INTEGRATE | The only intents object constructed — slash commands arrive as interactions, not messages, so no privileged intent is requested (`bot.py`, T-06-05). |
| `message_content` privileged intent | OPT-OUT | Never requested — slash-command interactions carry no message text to read. Criterion 5's answer for content (ROADMAP criterion 5, 06-CONTEXT D-21). |
| `members` (Server Members) privileged intent | OPT-OUT | No command or the digest reads guild member lists; nothing in BOT-04/BOT-05 needs it (ROADMAP criterion 5). |
| `presence` privileged intent | OPT-OUT | No command or digest reads online/offline status; unrequested by design (ROADMAP criterion 5). |
| `commands.Bot` vs bare `discord.Client` + manual tree | INTEGRATE | `commands.Bot` ships `self.tree` for free — fewer lines to register two guild-scoped commands (06-CONTEXT "Claude's Discretion"). |
| Bare `discord.Client` + hand-attached `CommandTree` | OPT-OUT | Rejected alternative to the row above — `commands.Bot` needs no manual tree wiring for two commands. |
| `Client.run(token, log_handler=None)` | INTEGRATE | One blocking call starts the event loop; `log_handler=None` keeps `configure_logging()` (`cli.py`) the one shared logging setup. |
| Separate `start()`/`login()` coroutines | OPT-OUT | `run()` already does connect-and-block for a single-process bot with no other asyncio work to interleave. |
| `setup_hook` for startup work | INTEGRATE | Guild sync and the channel preflight run once, before READY — the one-time async setup point discord.py recommends (06-RESEARCH). |
| `on_ready` for startup work | OPT-OUT | Fires on every reconnect, not once — would re-sync commands and re-log the channel preflight on every gateway hiccup. |
| `wait_until_ready()` | INTEGRATE | Guards `digest_loop`'s `before_loop` — channel objects do not resolve before READY (`bot.py` `_before_digest`). |
| `get_channel()` then `fetch_channel()` fallback | INTEGRATE | Cache-first lookup with an API fallback for an integer that parses but may not be visible to the bot (06-RESEARCH Pitfall 2). |
| `AllowedMentions.none()` | INTEGRATE | Every reply and the digest itself suppress pings — mirrors Phase 5 D-16's `allowed_mentions` on the webhook side. |
| `CommandTree.sync(guild=...)` | INTEGRATE | Guild-scoped sync propagates immediately; ROADMAP's Notes pre-lock this over global sync for demo reliability. |
| `CommandTree.sync()` global | OPT-OUT | Global propagation can take up to an hour — ROADMAP Notes explicitly reject this for a demo. |
| `copy_global_to(guild=...)` | INTEGRATE | Copies the two tree-registered commands into the guild-scoped sync target before `setup_hook` calls `sync`. |
| `app_commands.describe()` parameter descriptions | INTEGRATE | `/creator`'s `name` parameter carries a description so Discord's client UI hints at the expected input. |
| `app_commands.autocomplete` | OPT-OUT | Declined by D-15 — a real demo moment for ~10 lines, but fires a DB read per keystroke and adds surface to explain. |
| `app_commands.checks` / permission decorators | OPT-OUT | Guild-role permission stripping (View Channel + Send Messages only, done by hand, BOT-07) is the access control; no per-command check layers on top. |
| Context menus (user/message commands) | OPT-OUT | Neither BOT-04 nor BOT-05 needs a right-click entry point; only two slash commands are required. |
| Command groups (`app_commands.Group`) | OPT-OUT | Two flat commands need no subcommand namespace. |
| `Interaction.response.send_message()` | INTEGRATE | Both `/creator` and `/status` reply this way — the one response method either handler needs. |
| `Interaction.response.defer()` | OPT-OUT | A single indexed SQLite read finishes inside the 3-second window; deferring would cost a second round trip for nothing (06-RESEARCH Priority 4). |
| Ephemeral responses | OPT-OUT | Both commands answer a shared-channel question; no reply is meant to be private to the caller. |
| Interaction followups | OPT-OUT | Never deferred (see the `defer` row above), so no followup is ever needed. |
| Modals | OPT-OUT | Neither command collects free-form user input; both take at most one string parameter. |
| Buttons and select menus | OPT-OUT | No interactive follow-up UI is required by BOT-01 through BOT-05. |
| `discord.ext.tasks.loop(time=DIGEST_TIME)` | INTEGRATE | The digest's 08:15 Asia/Manila schedule (D-01, D-03). Ships with discord.py, adds no dependency. |
| `tasks.loop(seconds=...)` / `minutes=...` interval form | OPT-OUT | The digest is a fixed daily clock time, not a repeating interval — `time=` is the correct decorator argument for D-03. |
| `Loop.before_loop` hook | INTEGRATE | Waits for READY before the first tick can touch `self.channel` (`bot.py` `_before_digest`). |
| `Loop.after_loop` hook | OPT-OUT | Nothing needs to run once after the loop stops; the process either keeps running or is killed by systemd. |
| `Loop.error` hook (`@digest_loop.error`) | OPT-OUT | The loop body's own `try/except Exception` already observes every failure without suppressing it — see Consequences below. |
| `Loop.restart()` / `Loop.cancel()` | OPT-OUT | Nothing in this phase restarts or cancels the loop programmatically — its lifecycle is the process's, and systemd owns restarting the process. |
| `Loop.reconnect` parameter | OPT-OUT | Left at its default (`True`), not customized — the loop body's own exception guard is the layer this phase actually relies on (06-RESEARCH Pitfall 1). |
| Plain `content` string on every message | INTEGRATE | The digest, both command replies, and the webhook alert all use one message shape (06-CONTEXT "Claude's Discretion"). |
| `discord.Embed` | OPT-OUT | Plain content was the assumed default; nothing needed richer formatting than the fixed-width row prefix already provides. |
| File attachments | OPT-OUT | Every message is a formatted string built in Python; nothing in this phase produces a file to attach. |
| Threads | OPT-OUT | The bot posts to one channel, not a thread (05-CONTEXT D-16, inherited); nothing here creates or targets one. |
| Message editing (`Message.edit`) | OPT-OUT | Every digest, alert, and command reply is fire-and-forget; no decision calls for correcting a sent message. |
| Reactions | OPT-OUT | No requirement or decision calls for reacting to a message the bot or a user sent. |
| The 2000-character `content` limit, truncation logic | OPT-OUT | D-11 has no top-N cap at 3-6 creators; the digest cannot approach the limit today — revisit if the creator list grows materially. |
| `POST /webhooks/{id}/{token}` (Execute Webhook), from the collector | INTEGRATE | `_post_alert()` (D-08/D-09) reuses the endpoint `05-apps-script/COVERAGE.md` already recorded for `Code.gs` — same webhook, new Python caller. |
| `content` field on the webhook POST | INTEGRATE | `build_alert_text()`'s formatted string is the whole payload body — the same field `05-apps-script/COVERAGE.md` integrated for `postToDiscord()`. |
| `allowed_mentions: {parse: []}` on the webhook POST | INTEGRATE | Suppresses pings the same way `05-apps-script/COVERAGE.md` records for the watchdog — kept consistent even though failure text here is not user-editable. |

---

## Consequences recorded here so they are not rediscovered

- **The `error` hook is an `OPT-OUT` precisely because it observes without suppressing.** The
  loop body's own `try/except Exception: logger.exception(...)` is what actually keeps the digest
  alive — discord.py's `reconnect=True` machinery only auto-retries a narrow set of network
  exceptions (`OSError`, `GatewayNotFound`, `ConnectionClosed`, `aiohttp.ClientError`,
  `asyncio.TimeoutError`), and anything else raised inside the loop body would otherwise kill the
  underlying `Task` permanently after one log line, with systemd still reporting the unit healthy
  (06-RESEARCH Pitfall 1). A `@digest_loop.error` handler would log the same failure a second time,
  not prevent it — the guard belongs inside the body, and it is already there.
- **`defer()` is an `OPT-OUT` because a single indexed SQLite read sits comfortably inside the
  three-second interaction window.** Deferring would buy nothing here and would cost a second round
  trip to Discord for every `/creator` and `/status` call, for no correctness or UX benefit
  (06-RESEARCH Priority 4).
- **The intents rows above are the written form of ROADMAP criterion 5's "why none are
  privileged" half — but that criterion does not close on this file.** It closes only when the
  author writes the explanation into `06-UAT.md` unaided. This file is the evidence the author
  checks their own answer against afterward, not a substitute for giving it.

*Written: 2026-08-06 during Phase 6 execution (`06-04`). Re-check if a new capability is
integrated.*
