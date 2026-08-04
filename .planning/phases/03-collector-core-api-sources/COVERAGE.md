# API Coverage — Phase 3 (YouTube Data API v3, Twitch Helix)

`INTEGRATE` is the default. This file is the **subtraction record**: every `OPT-OUT` carries a
one-line reason, cited to a written decision wherever one exists. YouTube and Twitch each get their
own full-coverage baseline — YouTube's opt-outs are not carried across to Twitch, or the reverse.

**Scope of the capability surface:** endpoints that could plausibly serve *this project's stated
purpose* — a daily, public, unauthenticated creator-metrics collector — not the entire vendor
catalogue. Endpoints requiring a channel-owner OAuth relationship are enumerated anyway, because the
absence of that relationship is itself a load-bearing project decision.

Citations: `REQUIREMENTS.md` §"Out of Scope" (OOS), `.claude/CLAUDE.md` §"Settled decisions"
(SETTLED), `03-CONTEXT.md` decisions (D-NN), `.planning/research/STACK.md` §7/§8 (STACK).

---

# API Coverage — YouTube Data API v3

| capability | decision | reason |
|---|---|---|
| `channels.list?part=statistics` (`subscriberCount`, `viewCount`, `videoCount`, `hiddenSubscriberCount`) | INTEGRATE | SRC-01 is exactly this call. 1 quota unit, API key only (STACK §7). |
| `channels.list?forHandle=@handle` (identifier resolution) | INTEGRATE | Resolves the human-friendly handle from `creators.yaml` in the same 1-unit call — no separate lookup (CONTEXT.md Claude's Discretion, "Identifier resolution and quota"). |
| `channels.list?part=snippet` (title, description, thumbnail) | OPT-OUT | `creators.yaml` already carries the display name (CFG-02); parts are free but a field with no consumer is a field that rots. |
| `channels.list?part=contentDetails` (uploads playlist id) | OPT-OUT | Only useful as a step toward per-video enumeration, which no v1 requirement asks for. |
| `channels.list?part=brandingSettings` | OPT-OUT | Cosmetic. No numeric metric. |
| `channels.list?part=topicDetails` | OPT-OUT | Categorisation. No metric in REQUIREMENTS.md. |
| `channels.list?part=status` (privacy, upload status) | OPT-OUT | No metric; the digest reports numbers, not account state. |
| `channels.list?part=auditDetails` | OPT-OUT | The only `channels.list` part requiring OAuth. SRC-01 fixes API-key-only auth (STACK §7). |
| `videos.list` (per-video statistics) | OPT-OUT | SRC-01 names channel-level metrics only. Per-video data is a different grain than one row per creator per day (DATA-01). |
| `playlistItems.list` (recent uploads) | OPT-OUT | Same grain mismatch, plus a second quota-bearing call per creator for a number no requirement reads. |
| `search.list` (handle → channel id) | OPT-OUT | 100 quota units per call and redundant — `forHandle` does it for 1 unit inside the call already being made. |
| `search.list?eventType=live` / `liveBroadcasts.list` (YouTube live status) | OPT-OUT | `is_live` is defined as a Twitch-sourced column (D-01). `search.list` costs 100 units; `liveBroadcasts` needs channel-owner OAuth. |
| `commentThreads.list` / `videos.list` like counts (engagement inputs) | OPT-OUT | `engagement_rate` was removed from the record and the DDL (D-02) — no numerator, no denominator, no consumer. |
| `subscriptions.list` | OPT-OUT | Requires channel-owner OAuth. No OAuth relationship exists with tracked creators. |
| YouTube Analytics API / Reporting API | OPT-OUT | Channel-owner OAuth only — the same auth wall as Twitch followers, and out of scope for a public-sources-only project (OOS: "Public, unauthenticated sources only"). |
| Paid quota extension (quota increase request) | OPT-OUT | OOS: "Any paid API tier". 6 calls/day against a 10,000-unit daily quota is not a constraint (STACK §7). |
| Polling more than once per day | OPT-OUT | OOS: "Sub-daily polling — daily is the stated cadence; more frequent burns API quota for no added signal". |

---

# API Coverage — Twitch Helix

| capability | decision | reason |
|---|---|---|
| `POST https://id.twitch.tv/oauth2/token` (`grant_type=client_credentials`) | INTEGRATE | The app access token every other call carries. Minted fresh per run, no cache (D-17). |
| `GET /helix/users?login=` | INTEGRATE | Resolves the `creators.yaml` login to the numeric `broadcaster_id` that Get Videos and Get Streams require. Also the D-18 raise-on-empty site. |
| `GET /helix/videos?user_id=&type=archive&period=month&first=100` | INTEGRATE | SRC-02's `views` metric — the summed `view_count` of the window (D-05, D-07). One page, no pagination. |
| `GET /helix/streams?user_login=` | INTEGRATE | SRC-02's live status → `is_live` 1/0 (D-01). An empty `data[]` here means offline, not not-found. |
| `GET /helix/channels/followers` | OPT-OUT | Requires a broadcaster or moderator **user** access token. No OAuth relationship exists with tracked creators. SETTLED — an auth wall, not a scraping problem, and explicitly not to be worked around. Also OOS: "Twitch follower count". |
| `GET /helix/users` → `view_count` field | OPT-OUT | Deprecated April 2022, always returns `0`. Storing it would put silently-wrong data in a real column (OOS row: "Twitch `view_count` field on Get Users"). |
| `GET /helix/videos` pagination (`after` cursor, further pages) | OPT-OUT | D-05 fixes one page at `first=100` — a variable number of calls for a sum that still moves, against a window Twitch's own retention already bounds. |
| `GET /helix/videos?type=highlight` / `type=upload` / `type=all` | OPT-OUT | D-07 — highlights and uploads are edited derivatives of the same broadcasts, so `type=all` counts the same views twice and the number stops answering one question. |
| `GET /helix/channels?broadcaster_id=` (game, title, tags) | OPT-OUT | No numeric metric. The Sheet and the digest report numbers. |
| `GET /helix/clips` | OPT-OUT | Clip views are a different noun from broadcast views; summing them into the same column breaks the one-question rule D-07 protects. |
| `GET /helix/games/top`, `GET /helix/search/channels` | OPT-OUT | Discovery endpoints. The creator list is operator-authored in `creators.yaml` (CFG-01), never discovered. |
| `GET /helix/subscriptions` (subscriber count) | OPT-OUT | Broadcaster user token required — the same auth wall as followers. |
| `GET /helix/bits/leaderboard`, `GET /helix/analytics/*` | OPT-OUT | Broadcaster user token and revenue-grade data. Unobtainable and out of scope. |
| `GET /helix/moderation/*`, `GET /helix/chat/*` | OPT-OUT | Moderator/user scopes; no metric in REQUIREMENTS.md. |
| EventSub (webhook or WebSocket subscriptions) | OPT-OUT | A push cadence and a long-lived listener. This is a one-shot daily batch (RUN-03), and OOS forbids sub-daily polling. |
| Twitch Extensions / Drops / Ads endpoints | OPT-OUT | Broadcaster-owned surfaces with no public metric relevant to a creator-metrics digest. |
| Paid or partner-tier API access | OPT-OUT | OOS: "Any paid API tier". |
| Any route to a follower count other than the walled endpoint (borrowed user token, scraped profile page, third-party mirror) | OPT-OUT | SETTLED, and OOS: "Bot-detection evasion of any kind". The `followers` column is NULL on every Twitch row by design (criterion 4). |

---

## Consequences recorded here so they are not rediscovered

- **`followers` is NULL on every Twitch row.** Not a bug, not a gap — the subtraction above is the
  reason, and ROADMAP criterion 4 asks the author to prove it with a query.
- **`video_count` is NULL on every Twitch row.** Twitch exposes no lifetime video count; the
  in-window VOD count goes to the run's log line, never to the column (D-06).
- **`is_live` is NULL on every YouTube row.** YouTube live status is opted out above; the column is
  Twitch-only in this phase (D-01).
- **`likes` is NULL on every row this phase writes.** Neither integrated endpoint exposes it;
  TikTok fills it in Phase 4.

*Written: 2026-08-04 during Phase 3 planning. Re-check if a new endpoint is integrated.*
