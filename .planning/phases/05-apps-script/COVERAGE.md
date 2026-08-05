# API Coverage — Phase 5 (Discord Incoming Webhooks)

`INTEGRATE` is the default. This file is the **subtraction record**: every `OPT-OUT` carries a
one-line reason, cited to a written decision. The `INTEGRATE` rows are the small minority — the
value of this file is in the reasoned remainder, not in the inventory of what got built.

**Scope of the capability surface:** what could plausibly serve *this project's stated purpose* —
a one-way notifier, run from Apps Script, that posts short plain-text messages into one Discord
channel — not Discord's entire API. A webhook is not a bot: the credential is different, and
everything that needs a bot token, an application, or the gateway (slash commands, interactions,
intents) is Phase 6's and is human-built in the Developer Portal under `.claude/CLAUDE.md` Hard
Rule 3. That boundary is why the bot-token surface is enumerated here as an `OPT-OUT` rather than
silently omitted — it is the largest single subtraction this file records.

Citations: `05-CONTEXT.md` decisions (D-NN), `05-RESEARCH.md` (Code Examples, Don't Hand-Roll),
`.claude/CLAUDE.md` (the three human-built areas), `.planning/REQUIREMENTS.md` §"Out of Scope".

**Format contract:** exactly ONE `| capability | decision | reason |` table in this file. A second
table's header row is parsed as a data row by the `api-coverage` gate and fails it with
`decision "DECISION" not in {INTEGRATE, OPT-OUT}`. Capability ≤ 80 chars, reason ≤ 200 chars,
neither containing a literal pipe or newline.

| capability | decision | reason |
|---|---|---|
| `POST /webhooks/{webhook.id}/{webhook.token}` (Execute Webhook) | INTEGRATE | The one endpoint both `postToDiscord()` call sites (watchdog, onEdit) POST to — the entire webhook surface this phase touches (D-16). |
| `content` field (plain-text message body) | INTEGRATE | D-14/D-15's full message shape — creator, source, and both Status values in one string; no richer body needed at this scale. |
| `allowed_mentions: {parse: []}` | INTEGRATE | Suppresses @everyone/@here from an untrusted, link-editable Status cell (T-05-05) — the one capability integrated for security, not function. |
| HTTP response-status check (2xx success, else logged) | INTEGRATE | `postToDiscord()` reads `response.getResponseCode()` and logs a non-2xx body, per the fail-loudly rule (D-13, PITFALLS §18(d)). |
| `embeds` array | OPT-OUT | Left to implementer discretion (05-CONTEXT.md); the plain message shipped, a reasoned subtraction recorded in §Deferred Ideas, not an oversight. |
| `username` override | OPT-OUT | One webhook, one identity, one channel (D-16) — nothing here needs a per-message display name. |
| `avatar_url` override | OPT-OUT | Same reasoning as `username` — no per-message identity need exists. |
| `tts` flag | OPT-OUT | No decision or requirement asks for audible alerts in the Discord client. |
| `flags` (embed-suppression bits) | OPT-OUT | Only affects embed rendering, and no embed is ever sent. |
| `components` (buttons, select menus) | OPT-OUT | Interactive components need a bot's interaction endpoint — Phase 6 / Developer Portal territory, human-built (CLAUDE.md Hard Rule 3). |
| File attachments / multipart upload | OPT-OUT | Every message is a one-line string; nothing in `Code.gs` produces a file to attach. |
| `poll` object | OPT-OUT | No requirement or decision calls for a Discord poll from the Sheet. |
| `thread_id` query param | OPT-OUT | D-16 posts to one channel, not a thread — no thread exists to target. |
| `thread_name` (auto-create thread) | OPT-OUT | Same as `thread_id` — D-16's one-channel design has no thread to create. |
| `applied_tags` (forum tags) | OPT-OUT | The target is a normal text channel per D-16, not a forum channel. |
| `?wait=true` query param and its `200`-with-body response | OPT-OUT | Success is a `204` with no body; nothing here reads a created message back, so the round trip buys an unread payload. |
| Get Webhook / Get Webhook with Token | OPT-OUT | `Code.gs` only ever POSTs; nothing reads the webhook's own metadata back. |
| Modify Webhook / Modify Webhook with Token | OPT-OUT | The webhook's name/channel are set once by the human who created it (D-13); no code path edits it. |
| Delete Webhook / Delete Webhook with Token | OPT-OUT | Webhook lifecycle is a manual, one-time human step; nothing here tears it down. |
| Create Webhook | OPT-OUT | The human step D-13 depends on — created once via Server Settings, never through code. |
| Get Channel Webhooks | OPT-OUT | The one URL comes from Script Properties, never discovered by enumerating a channel. |
| Get Webhook Message | OPT-OUT | Nothing reads a previously-posted message back; the Sheet is the record, not Discord. |
| Edit Webhook Message | OPT-OUT | Every alert is fire-and-forget; no decision calls for correcting a sent message. |
| Delete Webhook Message | OPT-OUT | Same as Edit — nothing here revisits a message once posted. |
| Slack-compatible endpoint (`/slack`) | OPT-OUT | A compatibility shim for Slack's payload shape; `Code.gs` sends Discord's own JSON directly. |
| GitHub-compatible endpoint (`/github`) | OPT-OUT | Same reasoning as Slack-compatible — a shim for a payload shape this project never produces. |
| `429` response / `retry_after` handling | OPT-OUT | A daily watchdog plus a handful of Status edits cannot approach any rate limit (RESEARCH.md Don't-Hand-Roll). |
| Bot-token surface — gateway, intents, slash commands, interactions | OPT-OUT | A webhook is not a bot; that credential and Developer Portal registration are Phase 6's, human-built (CLAUDE.md Hard Rule 3). |

---

## Consequences recorded here so they are not rediscovered

- **The webhook URL is a bearer credential and never enters the repo.** D-13 puts it in Script
  Properties precisely because `Code.gs` is committed (D-04) — this file records the surface, never
  the value, and no line above contains the literal URL.
- **`allowed_mentions` is the one capability integrated for a security reason rather than a
  functional one.** It will look gratuitous to a reader who has not read T-05-05 — the Sheet is
  link-editable and column G is untrusted free text, so a typed `@everyone` must not ping the
  channel.
- **Phase 6's bot shares the *channel* this phase posts to, not the credential.** A bot token and a
  webhook token are different secrets; nothing recorded here creates anything Phase 6 can reuse
  beyond the channel itself (D-16, 05-CONTEXT.md §Integration Points).

*Written: 2026-08-06 during Phase 5 execution (`05-03`). Re-check if a new capability is integrated.*
