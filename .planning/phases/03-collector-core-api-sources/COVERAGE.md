# API Coverage — Phase 3 (YouTube Data API v3, Twitch Helix)

`INTEGRATE` is the default. This file is the **subtraction record**: every `OPT-OUT` carries a
one-line reason, cited to a written decision wherever one exists. YouTube and Twitch each get their
own full-coverage baseline — YouTube's opt-outs are not carried across to Twitch, or the reverse.
The `yt:` and `tw:` prefixes mark which baseline a row belongs to.

**Scope of the capability surface:** endpoints that could plausibly serve *this project's stated
purpose* — a daily, public, unauthenticated creator-metrics collector — not the entire vendor
catalogue. Endpoints requiring a channel-owner OAuth relationship are enumerated anyway, because the
absence of that relationship is itself a load-bearing project decision.

Citations: `REQUIREMENTS.md` §"Out of Scope" (OOS), `.claude/CLAUDE.md` §"Settled decisions"
(SETTLED), `03-CONTEXT.md` decisions (D-NN), `.planning/research/STACK.md` §7/§8 (STACK).

**Format contract:** exactly ONE `| capability | decision | reason |` table in this file. A second
table's header row is parsed as a data row by the `api-coverage` gate and fails it with
`decision "DECISION" not in {INTEGRATE, OPT-OUT}`. Capability ≤ 80 chars, reason ≤ 200 chars.

| capability | decision | reason |
|---|---|---|
| `yt: channels.list?part=statistics` | INTEGRATE | Returns `subscriberCount`, `viewCount`, `videoCount`, `hiddenSubscriberCount`. SRC-01 is exactly this call — 1 quota unit, API key only (STACK §7). |
| `yt: channels.list?forHandle=@handle` | INTEGRATE | Resolves the handle from `creators.yaml` inside the same 1-unit call — no separate lookup (03-CONTEXT.md, "Identifier resolution and quota"). |
| `yt: channels.list?part=snippet` | OPT-OUT | `creators.yaml` already carries the display name (CFG-02); parts are free but a field with no consumer is a field that rots. |
| `yt: channels.list?part=contentDetails` | OPT-OUT | Only useful as a step toward per-video enumeration, which no v1 requirement asks for. |
| `yt: channels.list?part=brandingSettings` | OPT-OUT | Cosmetic. No numeric metric. |
| `yt: channels.list?part=topicDetails` | OPT-OUT | Categorisation. No metric in REQUIREMENTS.md. |
| `yt: channels.list?part=status` | OPT-OUT | Privacy and upload status. No metric; the digest reports numbers, not account state. |
| `yt: channels.list?part=auditDetails` | OPT-OUT | The only `channels.list` part requiring OAuth. SRC-01 fixes API-key-only auth (STACK §7). |
| `yt: videos.list` | OPT-OUT | SRC-01 names channel-level metrics only. Per-video data is a different grain than one row per creator per day (DATA-01). |
| `yt: playlistItems.list` | OPT-OUT | Same grain mismatch, plus a second quota-bearing call per creator for a number no requirement reads. |
| `yt: search.list` | OPT-OUT | 100 quota units per call and redundant — `forHandle` does it for 1 unit inside the call already being made. |
| `yt: liveBroadcasts.list / search.list?eventType=live` | OPT-OUT | `is_live` is defined as a Twitch-sourced column (D-01). `search.list` costs 100 units; `liveBroadcasts` needs channel-owner OAuth. |
| `yt: commentThreads.list (engagement inputs)` | OPT-OUT | `engagement_rate` was removed from the record and the DDL (D-02) — no numerator, no denominator, no consumer. |
| `yt: subscriptions.list` | OPT-OUT | Requires channel-owner OAuth. No OAuth relationship exists with tracked creators. |
| `yt: Analytics API / Reporting API` | OPT-OUT | Channel-owner OAuth only — the same auth wall as Twitch followers, and OOS: "Public, unauthenticated sources only". |
| `yt: paid quota extension` | OPT-OUT | OOS: "Any paid API tier". 6 calls/day against a 10,000-unit daily quota is not a constraint (STACK §7). |
| `yt: polling more than once per day` | OPT-OUT | OOS: "Sub-daily polling — daily is the stated cadence; more frequent burns API quota for no added signal". |
| `tw: POST id.twitch.tv/oauth2/token (client_credentials)` | INTEGRATE | The app access token every other call carries. Minted fresh per run, no cache (D-17). |
| `tw: GET /helix/users?login=` | INTEGRATE | Resolves the `creators.yaml` login to the numeric `broadcaster_id` Get Videos and Get Streams require. Also the D-18 raise-on-empty site. |
| `tw: GET /helix/videos?type=archive&period=month&first=100` | INTEGRATE | SRC-02's `views` metric — the summed `view_count` of the window (D-05, D-07). One page, no pagination. |
| `tw: GET /helix/streams?user_login=` | INTEGRATE | SRC-02's live status → `is_live` 1/0 (D-01). An empty `data[]` here means offline, not not-found. |
| `tw: GET /helix/channels/followers` | OPT-OUT | Requires a broadcaster or moderator **user** token; no OAuth relationship exists with tracked creators. SETTLED — an auth wall, not to be worked around. OOS. |
| `tw: GET /helix/users → view_count field` | OPT-OUT | Deprecated April 2022, always returns `0`. Storing it would put silently-wrong data in a real column (OOS: "Twitch `view_count` field"). |
| `tw: GET /helix/videos pagination (after cursor)` | OPT-OUT | D-05 fixes one page at `first=100` — a variable number of calls for a sum that still moves, against a window Twitch's retention already bounds. |
| `tw: GET /helix/videos?type=highlight, type=upload, type=all` | OPT-OUT | D-07 — highlights and uploads are edited derivatives of the same broadcasts, so `type=all` counts the same views twice. |
| `tw: GET /helix/channels?broadcaster_id=` | OPT-OUT | Game, title, and tags. No numeric metric; the Sheet and the digest report numbers. |
| `tw: GET /helix/clips` | OPT-OUT | Clip views are a different noun from broadcast views; summing them into one column breaks the one-question rule D-07 protects. |
| `tw: GET /helix/games/top, GET /helix/search/channels` | OPT-OUT | Discovery endpoints. The creator list is operator-authored in `creators.yaml` (CFG-01), never discovered. |
| `tw: GET /helix/subscriptions` | OPT-OUT | Broadcaster user token required — the same auth wall as followers. |
| `tw: GET /helix/bits/leaderboard, GET /helix/analytics/*` | OPT-OUT | Broadcaster user token and revenue-grade data. Unobtainable and out of scope. |
| `tw: GET /helix/moderation/*, GET /helix/chat/*` | OPT-OUT | Moderator and user scopes; no metric in REQUIREMENTS.md. |
| `tw: EventSub (webhook or WebSocket subscriptions)` | OPT-OUT | A push cadence and a long-lived listener. This is a one-shot daily batch (RUN-03), and OOS forbids sub-daily polling. |
| `tw: Extensions / Drops / Ads endpoints` | OPT-OUT | Broadcaster-owned surfaces with no public metric relevant to a creator-metrics digest. |
| `tw: paid or partner-tier API access` | OPT-OUT | OOS: "Any paid API tier". |
| `tw: any other route to a follower count` | OPT-OUT | Borrowed user token, scraped profile page, or third-party mirror. SETTLED, and OOS: "Bot-detection evasion of any kind". |

---

## Consequences recorded here so they are not rediscovered

- **`followers` is NULL on every Twitch row.** Not a bug, not a gap — the subtraction above is the
  reason, and ROADMAP criterion 4 asks the author to prove it with a query.
- **`video_count` is NULL on every Twitch row.** Twitch exposes no lifetime video count; the
  in-window VOD count goes to the run's log line, never to the column (D-06).
- **`is_live` is NULL on every YouTube row.** YouTube live status is opted out above; the column is
  Twitch-only in this phase (D-01).
- **`likes` is NULL on every row this phase writes.** Neither integrated endpoint exposes it. It was
  to be filled by the TikTok source in Phase 4 — **but SRC-03 was cut on 2026-08-05** (ROADMAP.md
  §"Cut Order" item 2), so `likes` is now NULL on every row the project writes, for as long as the
  source list stays at two.

*Written: 2026-08-04 during Phase 3 planning. Re-check if a new endpoint is integrated.*
*Amended 2026-08-05: merged the two per-service tables into one so the `api-coverage` gate stops
reading the second header as a data row; shortened two capabilities past the 80-char cap and one
reason past the 200-char cap; corrected the `likes` consequence for the SRC-03 cut. No decision
changed — every INTEGRATE and OPT-OUT is the same call it was.*
