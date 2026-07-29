# Project Research Summary

**Project:** CreatorPulse
**Domain:** Unattended daily creator-metrics collector -- single VPS, Python/SQLite/Sheets/Discord
**Researched:** 2026-07-29
**Confidence:** HIGH overall (stack/architecture/pitfalls verified against official docs; features research is MEDIUM since scope was largely pre-decided in PROJECT.md)

## Executive Summary

CreatorPulse is a small, portfolio-grade ops tool: a systemd-timed Python job pulls public metrics for a handful of creators from YouTube, Twitch, and TikTok, writes them idempotently to SQLite, syncs a Google Sheet, and posts a Discord digest -- no human in the loop. Experts build this exact shape as a single-writer batch job with a normalized record type, failure isolation per (creator, source) unit, and a dumb, disposable view layer (the Sheet) fed by a real database of record. The stack is already locked; research confirms every choice and closes all 8 open dependency gaps with zero new third-party packages -- every gap resolves to stdlib or something gspread already pulls in transitively (requests).

The main risk is not code complexity, it's silent correctness failures at seams: NULL-vs-0 in delta math, cell-by-cell Sheets writes hitting rate limits, a full-tab rewrite clobbering the human-edited Status column, systemd's stripped environment breaking a script that "works" interactively, and two platform-API auth walls (Twitch followers, YouTube subscriber rounding) that looked fine on paper but aren't. Both auth-wall issues are now SETTLED (below) rather than open risks. The highest pitfall density by far sits in the Playwright+Sheets phase -- this is where the roadmap should budget the most slack and the most explicit verification steps.

The recommended approach: build the DB schema and normalization boundary first (everything else depends on MetricRecord), stand up the two API sources before the higher-risk Playwright scraper, wire failure isolation and idempotency as the first tests, then layer Sheets, then the bot, with the human-built systemd/Apps Script/Discord-portal integration pass last. This ordering front-loads risk and leaves TikTok as the cleanest thing to cut if the 7-day window runs short (already the project's own stated cut order).

## SETTLED Decisions (do not re-litigate in roadmap)

### 1. Twitch metric: view/viewer counts, not followers
GET /helix/channels/followers requires a user access token from the broadcaster/moderator -- an app access token is rejected even for total-only counts (HIGH confidence, verified live against Twitch docs). CreatorPulse has no OAuth relationship with tracked creators, so follower count is unobtainable, full stop -- this is an auth wall, not a scraping/evasion question.

Decision: keep Twitch as a source; change the metric to app-token-accessible endpoints only:
- GET /helix/videos?user_id=... -> per-VOD view_count, summed over recent VODs -> stored in the existing views column
- GET /helix/streams?user_login=... -> live status + viewer_count when live
- followers column is NULL for all Twitch rows (NULL = "not applicable," never 0)
- Document the auth wall as a README design-decision entry

Roadmap flag: STACK.md verified the followers wall directly via live docs fetch but did NOT separately verify that Get Videos' view_count is reachable with an app token. Confirm with one live call early in the collector/Twitch-source phase before building the parser around it.

### 2. YouTube subscriberCount rounding: delta on views, not subscribers
subscriberCount rounds to 3 significant figures above 1,000 subs (PITFALLS.md + STACK.md, cross-checked, MEDIUM-HIGH). Day-over-day subscriber deltas are mostly rounding noise, not real signal.

Decision: Dashboard's primary day-over-day delta is computed on total view count (unrounded, moves daily). Subscriber count is still displayed but explicitly annotated as coarse/rounded so a flat line isn't misread as zero growth.

## Key Findings

### Recommended Stack

Every core technology (Python 3.12, sqlite3 stdlib, gspread 6.2.1, discord.py 2.7.1, Playwright 1.61.0, PyYAML 6.0.3, pytest, ruff, mypy) is locked and confirmed current with no version conflicts. The 8 open gaps are all decided in favor of minimalism:

- HTTP client: requests==2.34.2, not httpx -- already in gspread's dependency tree, no async need exists in this synchronous batch job.
- Retry/backoff: hand-roll a ~15-line decorator with time.sleep -- skip tenacity, only 3 call sites.
- Config validation: stdlib dataclasses + manual validate() -- skip pydantic, creators.yaml is a flat, self-authored, internal file.
- Logging: stdlib logging to stdout -- systemd captures unit stdout into the journal automatically; skip structlog/systemd-python.
- Playwright footprint: install Chromium only (playwright install chromium, not the 3-engine default) -- ~150-250MB, run headless, sequential (never concurrent) contexts.
- Sheets auth: gspread.service_account() alone is sufficient -- skip google-api-python-client, gspread already wraps the Sheets REST API via google-auth.
- YouTube: channels.list with part=statistics, forHandle=@name, API key only (no OAuth needed), 1 unit/call flat, 10k/day quota -- a non-issue at this scale. Never use search.list (100 units/call).
- Twitch: client-credentials app token (~58-day life, no refresh token, just re-request), see SETTLED decision above for the metric change.

### Expected Features

Feature scope is almost entirely pre-decided in PROJECT.md; FEATURES.md validates the categorization rather than discovering new requirements.

Must have (table stakes) -- all P1, must ship:
- creators.yaml config, no-code-change creator additions
- Failure isolation per (creator, source)
- Idempotent upsert on (creator_id, source, metric_date)
- runs table (start, duration, rows, failures) feeding both /status and journalctl
- Dashboard tab (latest + day-over-day delta) and History tab, batched writes only
- Discord daily digest, /status, /creator
- Secrets via chmod-600 env file

Should have (differentiators, cheap and worth it):
- Two-way Sheet-to-Discord round trip via Apps Script onEdit (human-built) -- the single most interesting demo moment
- Official-API-vs-scraper source split -- the core engineering judgment being demonstrated
- Static-threshold anomaly flag on the digest (|delta| > 20% -> warning) -- 2-4 hrs, near-free once delta exists
- Failure-triggers-immediate-Discord-ping, separate from the scheduled digest -- reuses the runs table

Defer/cut explicitly (anti-features): web frontend, auth/multi-user, data warehouse, Docker/K8s, >3 sources, paid APIs, LLM-written prose digest, bot-detection evasion, learned/ML anomaly detection, sub-daily polling, rolling averages/trend lines (not enough history in the build window), historical backfill, Grafana/Prometheus-style observability, Sheet cells as a second source of truth.

Cut order if behind schedule (already fixed in PROJECT.md): extra slash commands -> Playwright/TikTok source (ship API-only) -> History tab. Never cut VPS/systemd, Apps Script, or Discord bot phases.

### Architecture Approach

Two independent OS processes (systemd-timed one-shot collector; long-lived discord.py bot service) share nothing at runtime except the SQLite file (WAL mode), creators.yaml, and a small models.py/db.py core. The collector is the only writer, never overlaps itself (systemd Type=oneshot timer semantics), and the bot only ever reads with short-lived per-command connections.

Major components:
1. sources/* -- one module per platform (youtube.py, twitch.py, tiktok.py), a Protocol contract (creator -> MetricRecord), not an ABC -- no shared base class, since YouTube/Twitch/TikTok share almost nothing behaviorally. TikTok's browser lifecycle is isolated to its own context manager, dispatched once by the orchestrator, not leaked into the shared type signature.
2. collector.py -- orchestrator: loops creators x sources, wraps each (creator, source) unit in try/except (failure isolation), writes runs row. No retries at this layer -- the next day's timer run is the retry.
3. db.py -- thin stdlib sqlite3 wrapper: schema DDL (CREATE TABLE IF NOT EXISTS, no Alembic), WAL + busy_timeout=5000 set on every connection, ON CONFLICT ... DO UPDATE upsert.
4. sheets.py -- reads DB, computes deltas in Python (never Sheet formulas), writes Dashboard via column-scoped range (never full-tab clear, preserves the human-edited Status column) and History via append_rows batched.
5. bot/ -- discord.py, minimal intents (no privileged intents needed for slash commands), guild-scoped command sync for instant propagation during dev/demo.

Normalization boundary (non-negotiable seam): every adapter returns the same MetricRecord dataclass with 5 metric slots (followers, views, likes, engagement_rate, + metric_date). NULL means "this metric doesn't exist for this source," a real 0 means "the platform reported zero." Never coalesce NULL to 0 before delta math -- that's a correctness bug, not a style choice. This is the single most important cross-cutting rule in the whole system.

Build order (dependency-based): models.py+db.py first (everything depends on the record shape) -> YouTube/Twitch/TikTok sources + config.py in parallel -> collector.py -> sheets.py -> bot/ (shallow dependency chain, buildable any time after step 1) -> systemd/Apps Script/Discord-portal integration last, wired against already-working code.

### Critical Pitfalls

The Playwright + Sheets phase is the highest-pitfall-density phase in the project -- 9 of 19 pitfalls land there (service-account sharing, batched writes, USER_ENTERED vs RAW, column-scoped writes, browser teardown, JS-shell pages, silent None on selector drift). Budget accordingly.

1. Sheet never shared with the service-account email -- gspread.service_account() auths fine but every write 403s until the target Sheet is explicitly shared (Editor) with the JSON key's client_email. #1 first-run gspread failure, 100% reproducible. Fail loudly with the exact instruction, not a bare stack trace.
2. Cell-by-cell Sheets writes -- looks fine at 2 test rows, hits Sheets API rate limits and visible slowness once creator count grows, likely to surface for the first time during the live demo. Always build the full 2D array in memory, write once via update()/batch_update()/append_rows().
3. NULL vs 0 in delta math -- a missing prior-day row must render "--", never a computed delta against an assumed-zero baseline (which produces a wildly-wrong-looking "+1.2M" delta). COALESCE(x, 0) is the wrong reflex here; use LEFT JOIN + explicit IS NULL check.
4. Full-tab rewrite clobbers the human-edited Status column -- never .clear() the Dashboard tab; write only the DB-owned column range (e.g. A2:F{n}), leaving Status untouched. Reserve full-tab writes for the append-only History tab.
5. Script works interactively, fails silently under systemd -- stripped PATH/HOME/cwd in the service environment. Set WorkingDirectory, absolute ExecStart path, explicit Environment=HOME=..., and test with systemctl start (not just a terminal run) before trusting the timer.
6. Playwright OOM / zombie processes on a small VPS -- install browsers as the actual service user (not the interactive dev account), always teardown in finally, sequential (never concurrent) browser contexts, provision swap as cheap insurance.
7. SQLite "database is locked" between bot (reader) and collector (writer) -- PRAGMA journal_mode=WAL + busy_timeout=5000 on every connection in shared db.py, short-lived bot connections per command, not a module-level global.

## Implications for Roadmap

Based on research, suggested phase structure (matches phase names in must_surface):

### Phase 0: Skeleton
Rationale: .gitignore must exist before the first git add (secrets committed to history can't be un-committed, only rotated). Nothing else can safely start until this is true.
Delivers: repo skeleton, .gitignore, pyproject.toml, src/ layout, build journal started.
Avoids: secret-committed-before-gitignore pitfall.

### Phase 1: VPS
Rationale: Human-built (SSH, non-root user, UFW, systemd unit/timer, journalctl) -- unfakeable in conversation, never cut. Needs to exist before the collector can be deployed/tested under real systemd semantics rather than just interactively.
Delivers: provisioned VPS, systemd unit + timer files, swap file, service user.
Avoids: "works interactively, fails under systemd" (env/cwd/PATH), OnCalendar/Persistent= misunderstanding -- verify both with systemd-analyze calendar and a real systemctl start test, not just a terminal run.
Research flag: standard, well-documented systemd patterns -- skip research-phase.

### Phase 2: Collector core + SQLite
Rationale: Everything downstream depends on models.py/db.py and the normalization boundary; build and test this alone first with a throwaway fixture record.
Delivers: MetricRecord dataclass (NULL-vs-0 semantics baked in), schema DDL (WAL, busy_timeout, UNIQUE(creator_id, source, metric_date)), upsert helper, runs table, collector.py orchestration with per-(creator, source) failure isolation, config.py/creators.yaml loader, YouTube + Twitch API sources (fastest, lowest-risk, validate the plumbing before Playwright).
Uses: stdlib sqlite3, dataclasses, requests, PyYAML (safe_load only).
Avoids: naive-INSERT re-runnability breakage, metric_date UTC/local/midnight-slip, NULL-vs-0 delta corruption, SQLite lock contention.
Research flag: confirm Twitch Get Videos view_count app-token accessibility with one live call early in this phase (per SETTLED decision #1) -- the one item in this phase not already fully verified.

### Phase 3: Playwright + Sheets
Rationale: Highest pitfall density in the project (9 of 19 pitfalls). Riskiest single component (TikTok scraper, no fallback API) paired with the trickiest integration (Sheets writes). Do this while there's still slack in the 7-day window -- it's the first thing to cut if behind.
Delivers: TikTok Playwright source (Chromium-only install, sequential contexts, explicit teardown, raise-not-None on parse failure, wait-on-specific-element not just page-load), sheets.py (Dashboard column-scoped batched writes with USER_ENTERED, History append-only batched writes, delta computed in Python).
Addresses: TikTok/Playwright source, Dashboard tab, History tab, batched writes (all P1).
Avoids: service-account-not-shared 403, cell-by-cell writes, RAW-vs-USER_ENTERED silent breakage, full-tab-clobbers-Status, Playwright OOM/zombie processes, JS-shell empty page, silent-None-instead-of-raise on selector drift.
Research flag: most likely phase to need /gsd-plan-phase --research-phase 3 during planning -- TikTok's public page structure and exact selectors aren't knowable from this research pass and will need live inspection.

### Phase 4: Apps Script (human-built)
Rationale: Requires Phase 3's Dashboard tab to exist and have a stable column layout before Apps Script can attach onOpen/onEdit triggers to it. Human-built, never cut, agent does not generate this.
Delivers: conditional formatting, Status column onEdit -> Discord webhook.
Uses: stable column layout with Status always last (contract with Phase 3's write range).
Research flag: standard Apps Script patterns -- skip research-phase (this is explicitly the author's deepest existing skill area per PROJECT.md).

### Phase 5: Discord bot
Rationale: Shallow dependency chain (only needs db.py/models.py from Phase 2) -- could in principle build in parallel with Phase 3/4, but sequenced last here to match the project's own stated day-by-day plan and because /creator's trend display benefits from Sheets/delta logic already being proven.
Delivers: discord.py bot service (separate systemd unit from the collector), /creator, /status, daily digest.
Avoids: privileged-intents mismatch (request minimal intents only -- none needed for slash commands), blocking calls freezing the event loop, slash-command global-sync propagation delay (use guild-scoped sync).
Research flag: standard discord.py slash-command patterns -- skip research-phase.

### Phase 6: Reliability + docs
Rationale: This is explicitly what demo-day rehearsal is for -- several failure modes (cold start, quota burn from rehearsal itself, stale-token 401, silent sync failure) are dormant during solo dev and only appear "under observation." Must happen after every other phase is individually verified.
Delivers: rehearsed manual trigger + journalctl -f tailing, /status proven to surface staleness/failure honestly, Twitch token refresh proactively tested, early dry run on interview-day morning, README with architecture diagram and design-decision entries (including both SETTLED decisions above), build journal finalized.
Avoids: demo-day-only failure modes, Twitch token-expiry 401, quota exhaustion from repeated manual testing.
Research flag: no new research needed -- this phase is synthesis/rehearsal of prior work.

### Phase Ordering Rationale

- Phases 2->3 order (API sources before Playwright) is deliberate: YouTube/Twitch validate the collector/db plumbing fast and cheaply; TikTok is the highest-risk, highest-effort piece and the project's own cut-order already treats it as first-to-drop if behind, so proving the rest of the system works before committing more time to it reduces total risk.
- Apps Script (Phase 4) is sequenced after Sheets (Phase 3) because it has a hard structural dependency: the onEdit trigger and conditional formatting need the Dashboard tab's column layout to be finalized and stable.
- The Discord bot (Phase 5) has the shallowest dependency chain of any component (only db.py) and could be pulled earlier for parallelism if two work sessions run concurrently -- flagged as a legitimate reordering option, not a strict requirement.
- Reliability/docs (Phase 6) must be last by definition -- it rehearses and verifies the whole assembled system, not a single component.

### Research Flags

Needs deeper research during planning: Phase 3 (Playwright/TikTok selector work -- page structure not knowable in advance; confirm Twitch Get Videos endpoint early in Phase 2 too, though that's a smaller confirming check, not a full research pass).

Standard, well-documented patterns (skip --research-phase): Phase 1 (systemd), Phase 4 (Apps Script -- author's strength), Phase 5 (discord.py slash commands), Phase 2 (SQLite/upsert patterns are canonical and already fully verified against sqlite.org), Phase 6 (rehearsal, not new build).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified live via PyPI JSON API; Twitch/YouTube auth requirements verified via direct official-docs fetch, not search-summary. One MEDIUM sub-call: install-size figures for Playwright are approximate/version-dependent. |
| Features | MEDIUM | Scope is almost entirely pre-decided in PROJECT.md (HIGH there); the general "what ops teams expect" framing is supplementary web search, used only to sanity-check categorization, not as an authoritative claim. |
| Architecture | MEDIUM-HIGH | SQLite/systemd mechanics cross-checked against sqlite.org and multiple independent sources (HIGH); Protocol-vs-ABC pattern and gspread rate-limit guidance are well-established community consensus, not vendor-authoritative (MEDIUM). |
| Pitfalls | HIGH | systemd, SQLite, gspread quotas, YouTube quota costs, discord.py intents all verified against current official docs. Twitch follower-auth trap and Playwright OOM thresholds are MEDIUM -- verified via docs + community reports, numbers approximate. |

Overall confidence: HIGH

### Gaps to Address

- Twitch Get Videos view_count app-token accessibility -- verified indirectly (the followers wall is confirmed HIGH, but Get Videos itself wasn't separately live-tested). Confirm with one real API call early in Phase 2 before building the parser around it (SETTLED decision #1's flag).
- TikTok page structure/selectors -- inherently unknowable until live inspection in Phase 3; budget time for selector-writing against saved HTML fixtures and expect at least one iteration.
- Retry/backoff "hand-roll vs tenacity" call -- STACK.md flags this as MEDIUM-subjective judgment, not fact; a reasonable person could pick tenacity instead. Left as the user's call if they want to override during planning.
- creators.yaml validation approach (dataclasses vs pydantic) -- same flavor of judgment call, explicitly flagged as override-able by STACK.md.

## Sources

### Primary (HIGH confidence)
- PyPI JSON API -- live version queries for every locked/gap-filling dependency
- developers.google.com/youtube/v3/docs/channels/list -- direct fetch, auth/quota/forHandle verified
- dev.twitch.tv/docs/api/reference/ and /docs/authentication/getting-tokens-oauth/ -- direct fetch, follower-endpoint auth wall and token flow verified
- sqlite.org/lang_upsert.html -- official UPSERT syntax
- developers.google.com/workspace/sheets/api/limits -- official rate-limit docs
- gspread source (github.com/burnash/gspread) -- direct fetch, confirmed requests/AuthorizedSession usage and dependency chain

### Secondary (MEDIUM confidence)
- Twitch Developer Forums + twitchdev/issues GitHub -- community confirmation of follower-endpoint scope-gating and /users/follows deprecation
- Rival IQ / dev.to / ChannelCrawler explainers -- YouTube subscriberCount rounding and quota-cost patterns, cross-checked across multiple independent sources
- playwright.dev browser-install docs + community blog posts -- install footprint figures, approximate
- systemd/journald logging best-practice blog posts -- stdout-capture-into-journal behavior itself is HIGH (established systemd behavior); the "skip structlog" recommendation is a MEDIUM synthesis call

### Tertiary (LOW confidence)
- General web search on ops-tooling feature conventions (Ablebits, Analytics Vidhya, FasterCapital, Sifflet) -- used only to sanity-check FEATURES.md categorization against general industry practice, not treated as authoritative for this project's specific decisions

---
*Research completed: 2026-07-29*
*Ready for roadmap: yes*
