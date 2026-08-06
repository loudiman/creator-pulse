---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 06
current_phase_name: discord-bot
status: executing
stopped_at: Completed 06-05-PLAN.md
last_updated: "2026-08-06T09:22:45.524Z"
last_activity: 2026-08-06
last_activity_desc: Phase 06 execution started
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 24
  completed_plans: 22
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-29)

**Core value:** The unattended daily run — a timer fires, real numbers land in the database, the Sheet reflects them, and Discord says so, with no human in the loop.
**Current focus:** Phase 06 — discord-bot

## Current Position

Phase: 06 (discord-bot) — EXECUTING
Plan: 5 of 5
Status: Ready to execute
Last activity: 2026-08-06 — Phase 06 execution started

Progress: [█████████░] 92%

## Performance Metrics

**Velocity:**

- Total plans completed: 10
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | - | - |
| 02 | 3 | - | - |
| 4 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 6min | 2 tasks | 5 files |
| Phase 01 P02 | 4min | 2 tasks | 3 files |
| Phase 01 P03 | 12min | 2 tasks | 5 files |
| Phase 02-vps-systemd P01 | 20min | 2 tasks | 5 files |
| Phase 02-vps-systemd P02 | 25min | 3 tasks | 1 files |
| Phase 02-vps-systemd P03 | 20min | 2 tasks | 1 files |
| Phase 03 P01 | 15min | 3 tasks | 8 files |
| Phase 03 P02 | 25min | 2 tasks | 8 files |
| Phase 03 P06 | 20min | 1 tasks | 3 files |
| Phase 03 P04 | 20min | 2 tasks | 3 files |
| Phase 03 P05 | 30min | 3 tasks | 5 files |
| Phase 04 P01 | 45min | 2 tasks | 5 files |
| Phase 04 P02 | 35min | 2 tasks | 2 files |
| Phase 04 P04 | 20min | 2 tasks | 2 files |
| Phase 04 P03 | 50min | 3 tasks | 5 files |
| Phase 05 P01 | 40min | 2 tasks | 5 files |
| Phase 05 P02 | 55min | 3 tasks | 2 files |
| Phase 05 P03 | 20min | 1 tasks | 3 files |
| Phase 06 P01 | 17min | 2 tasks | 7 files |
| Phase 06 P02 | 8min | 2 tasks | 7 files |
| Phase 06 P03 | 12min | 2 tasks | 4 files |
| Phase 06 P05 | 15min | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Settled before Phase 1, do not re-litigate:

- Twitch metric is summed recent-VOD views + live status, not followers — `/helix/channels/followers` requires a broadcaster user token. Auth wall, not a scraping problem.
- Day-over-day delta computed on view count, not subscribers — YouTube rounds `subscriberCount` to 3 significant figures above 1k.
- No new dependencies beyond the locked set. Research closed all 8 open gaps against stdlib or `requests` (already transitive via gspread).
- Database is the source of truth; the Sheet is a disposable view. Only the Status column is human-owned.
- [Phase ?]: Extended gspread mypy override to also cover yaml module (no new dep) since PyYAML ships no type stubs
- [Phase ?]: Creator list finalized: xQc, Pokimane, Kai Cenat (author approved) across youtube/twitch/tiktok
- [Phase ?]: record_fixture.py validates --source/--case against ^[a-z0-9_]+$ before any network call, then re-checks resolved-path containment as a second belt
- [Phase ?]: recorder raises on non-2xx instead of saving the body, so a blocked/challenge response can never masquerade as a real fixture
- [Phase ?]: Fixed ruff-format drift on ARCHITECTURE.md with ruff format . (real reformat), not a scope exclusion
- [Phase ?]: resolve_paths(): empty-string env var treated as unset, not cwd; db_path logged only, never opened, in this phase
- [Phase ?]: D-05 confirmed unchanged (Task 1); criterion-wording gap recorded: git log -S per .env.example variable hits 2 commits not 1 (plan-file prose also names vars, blank-valued) — wording gap, not a leak; D-03 private-repo deviation resolved by author before clone
- [Phase ?]: Entry 1 limitation: RUN-03 partial closure — timer proven unattended, real collector output waits for Phase 3
- [Phase ?]: Reboot catch-up: both attempts recorded (diagnosed true-negative + passing catch-up), not just the pass — margin-vs-boot-time is a real reboot-test failure mode
- [Phase ?]: systemd-analyze calendar validates a CLI string, not the loaded unit — stale test schedule caught and corrected via systemctl cat before entry 4 closed
- [Phase ?]: channel_not_found.json items key is absent entirely (not empty list) — 03-02 parser must use data.get('items')
- [Phase ?]: OPS-06 not marked complete — plan frontmatter notes it is only partly satisfied by YouTube fixtures alone
- [Phase ?]: Task 1 option-a confirmed: nine-column metrics shape ships with video_count/is_live, engagement_rate removed (advisory gate, pre-resolved)
- [Phase ?]: youtube.py uses data.get('items') not data['items'] — channel_not_found.json has no items key at all, raises named ChannelNotFound
- [Phase ?]: test_paths.py needed the same fixture/env mocking as test_collector.py since cli.py's seam is no longer a stub
- [Phase ?]: sources/_retry.py: retry() wraps YouTube's requests.get call, narrow D-13 list (Timeout/ConnErr/429/5xx), fixed 2s/4s backoff (D-14); _token sentinel documented for deferred 03-03 Twitch token mint
- [Phase ?]: retry() uses PEP 695 generic syntax (def retry[**P](...)) instead of module-level ParamSpec — ruff UP047 rejects legacy form on py312 target
- [Phase ?]: validate() checks source keys against KNOWN_PLATFORMS not FETCHERS — tiktok/twitch stay known-but-unregistered and skip cleanly, only a genuine typo fails
- [Phase ?]: Import KNOWN_PLATFORMS via module-qualified 'from creatorpulse import sources as source_registry' so config.py has exactly one grep-able KNOWN_PLATFORMS line, matching the plan's own acceptance gate
- [Phase ?]: upsert_metric deliberately outside the per-pair try/except: a source-fetch failure isolates per D-15, a db write failure propagates through the outer try/finally instead of being counted per-pair
- [Phase ?]: Task 3 precondition re-checked and confirmed unmet (no SSH, no env, no credentials) — 03-UAT.md all 5 entries PENDING with not_closed_reason and close-later commands, Phase 3 closes PARTIAL
- [Phase ?]: Google service account provisioned 2026-08-05: project creatorpulse-2026ldm, sheets.googleapis.com enabled, SA creatorpulse-collector@creatorpulse-2026ldm.iam.gserviceaccount.com. Key at C:\Users\loudi\.creatorpulse\service-account.json locally (outside the repo) and /etc/creatorpulse/service-account.json on the droplet. NO IAM role granted — Sheet access comes from sharing the doc with client_email, never from project IAM.
- [Phase ?]: Sheet wired 2026-08-05: CREATORPULSE_SHEET_ID=1hP7rZqq9Z-QnYGCkt8uhNK1yiwF3dsM9e-T2sYQOqQI (creatorpulse-sheet, link-editable by author's accepted choice). Tab renamed Sheet1 -> Dashboard. Verified live: token minted with scope auth/spreadsheets ONLY (no Drive), open_by_key succeeds, and a write succeeded — proving Editor not Viewer. D-09's narrowed scope is now verified against a live credential, not just gspread source.
- [Phase ?]: Droplet Sheets wiring verified 2026-08-05: /etc/creatorpulse/service-account.json placed (creatorpulse:creatorpulse, 600), /etc/creatorpulse/creatorpulse.env carries CREATORPULSE_SHEET_ID and CREATORPULSE_SHEETS_KEYFILE. systemctl show creatorpulse.service -p EnvironmentFiles confirms the unit points at that file. /etc/creatorpulse dir tightened 755->750 root:creatorpulse (was already other-traversable, now locked to root+service group). sudo -u creatorpulse cat service-account.json succeeds -- service user reads the key on the actual runtime path, not just via systemd's env parsing. Both Google auth paths (dev machine, droplet) now proven end to end.
- [Phase ?]: 04-01 Task 1 checkpoint resolved option-a: D-02/D-03 shipped as written, no code change (confirmation gate)
- [Phase ?]: 04-01 Task 2 human-check resolved verified: live Sheet header row, right-aligned Views column, G2 marker survives creatorpulse sync (SHEET-06 proven live)
- [Phase ?]: Live Sheet holds 3 synthetic seed rows (kaicenat, pokimane, xqc, YouTube only) plus G2 test marker, deliberately left in place per author instruction as proof, not cleared -- not real collected metrics, Phase 3 droplet UAT still gates real numbers
- [Phase ?]: 04-02: LATEST_ROWS_SQL left-joins metrics AS prev on date(metric_date, '-1 day'), keyed on idx_metrics_creator_date -- pair with no baseline still reaches Dashboard
- [Phase ?]: 04-02: build_dashboard_rows column E is DELTA_PLACEHOLDER if views is None or prev_views is None else views - prev_views -- one conditional expression, is-None guard on both sides, zero renders 0, negative unclamped
- [Phase ?]: 04-02: no 04-01 assertion pinned column E to DELTA_PLACEHOLDER (verified via grep), so the plan's anticipated one-line amendment did not apply -- zero lines amended/deleted
- [Phase ?]: 04-04: COVERAGE.md gate-verified 7 INTEGRATE/27 OPT-OUT, every opt-out cites a written decision
- [Phase ?]: 04-04: 04-UAT.md ships all 4 entries pending (one shared blocker) per plan instruction, even though prior-session groundwork (SA/Sheet) is recorded in STATE.md
- [Phase ?]: run_collect() treats missing Sheets config as a sync failure (raises + logs), never a silent skip -- consistent with D-07/PITFALLS.md §18(d)
- [Phase ?]: 3 pre-existing run_collect() callers (test_config.py, test_paths.py) updated with Sheets env vars + stubbed sync -- new mandatory dependency, no assertion weakened
- [Phase ?]: 05-01: column F is a string under USER_ENTERED, not a Date; new Date(raw) parses clean (Wave 0 answer for 05-02's staleness math)
- [Phase ?]: 05-01: installTriggers() delete-then-recreate guard confirmed live — second click reports removed 1/created 1, exactly one onStatusEdit trigger persists
- [Phase ?]: 05-02: checkFreshness discards NaN at parse time (before comparison) so a single unparseable column-F cell cannot make the watchdog permanently silent
- [Phase ?]: 05-02: applyFormatting toast() bug (Sheet has no toast method, only Spreadsheet does) found in orchestrator review before live paste; fixed by hoisting ss=SpreadsheetApp.getActive(), confirmed live via the fixed toast
- [Phase ?]: 05-02: watchdog's three outcomes (stale, cannot-determine, silence) proven independently live; silence backed by a Completed Executions run closes D-07 as verified, not assumed
- [Phase ?]: 05-03: Task 2 (author's live criterion-5 walkthrough/write-up) deliberately not attempted — author decided to proceed to Phase 6 ahead of the interview; recorded PENDING in 05-UAT.md per D-03, not fabricated
- [Phase ?]: 05-03: COVERAGE.md ships 4 INTEGRATE / 27 OPT-OUT rows for the Discord webhook surface; REQUIREMENTS.md By-phase Phase 5 owner corrected human -> mixed
- [Phase ?]: 06-01: D-13 moved LATEST_ROWS_SQL/LatestRow/fetch_latest_rows to db.py alone, own commit, gate green before Task 2
- [Phase ?]: 06-01: bot.py imports sheets.DELTA_PLACEHOLDER per plan text/acceptance criteria — pulls gspread into bot process import graph, narrower than 06-CONTEXT's D-13 rationale; flagged not resolved
- [Phase ?]: 06-01: tzdata installed into .venv only (not pyproject.toml) to unblock zoneinfo Asia/Manila on Windows dev machine lacking system tz database; VPS is Linux with system tzdata, zero production impact
- [Phase ?]: cli.py owns build_alert_text/_post_alert (not bot.py) so the collector never imports discord.py
- [Phase ?]: D-08/D-09 alert-path tests mock sheets.sync as a no-op to keep the two call sites independently testable
- [Phase ?]: MOVER_FLAG prefix is a fixed 2-char lead-in on every mover row (emoji+space or two blank spaces) so Discord's proportional font can't visually stagger the creator/source column
- [Phase ?]: Failures section omitted entirely (no header) when there is no runs row — the could-not-determine banner already covers it, an empty header would misleadingly imply a run happened
- [Phase ?]: round(hours) for the staleness banner age, matching Code.gs's Math.round(ageHours) exactly so both surfaces report the same integer hour count
- [Phase ?]: 06-05: /creator matches known slugs via str.lower() (not casefold) against config._SLUG_RE's ASCII constraint; unknown name lists known slugs, empty DB says so
- [Phase ?]: 06-05: fetch_creator_trend returns full per-source history (WHERE creator_id=? bound), TREND_LIMIT=7 applied per source in Python, not a flat SQL LIMIT
- [Phase ?]: 06-05: build_status_text reuses fetch_last_run/staleness_hours/STALE_AFTER_HOURS unchanged from the digest banner so /status and the digest can never disagree about staleness

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 3, confirm early:** `GET /helix/videos` `view_count` app-token accessibility was verified indirectly, not live-tested. Make one real call before building the parser around it. If it walls off like the followers endpoint, the Twitch metric needs rethinking on day one.
- **Phase 4, unknowable in advance:** TikTok public page structure and selectors need live inspection. Budget for at least one iteration against saved HTML fixtures. Likely needs `--research-phase 4`.
- **Ownership constraint, all phases (AMENDED 2026-08-06, twice):** Phase 2 is human-built except `.service`/`.timer` files, which the agent may now write into `deploy/` — see `.claude/CLAUDE.md` "Amendment 2026-08-06 — rule 1 narrowed for `deploy/` unit files" and 06-CONTEXT.md D-21. Phase 5 is `mixed` (Apps Script written by the agent, Phase 5 D-01). Still binding in full: SSH config, non-root user setup, UFW rules, `docs/deploy.md`, and all Discord Developer Portal configuration. Both amendments are dated, scoped exceptions granted on the clock, not a general relaxation.
- **Hard deadline:** ship Wed 5 Aug 2026, interview Thu 6 Aug 8:00pm PHT. Roughly one phase per day, part-time. Cut order is fixed in ROADMAP.md — slash commands, then TikTok, then History tab. Never cut Phases 2, 5, or 6.
- **RESOLVED 2026-08-06 — Phase 3's human-observed real-data run has happened.** The droplet's
  `/var/lib/creatorpulse/creatorpulse.db` holds real collected YouTube rows for **2026-08-05 and
  2026-08-06**, written by the 08:00 Manila timer (latest `runs` row: started `2026-08-06T00:00:07Z`,
  3 rows written, 0 failures). Evidence gathered while preparing the Phase 6 tracer; the database was
  copied to the dev machine for local work. The prior two entries claiming this was outstanding were
  stale and have been replaced by this one. **03-UAT.md's five PENDING entries are not closed by this
  note** — each carries its own per-entry evidence requirement and must be closed against its own
  close-later command, not against this summary. Twitch remains blocked on 2FA (SRC-02).

- **Data-shape findings from that database, relevant to Phase 6 execution (recorded 2026-08-06):**
  - **2026-08-04's three rows are synthetic seed data, not collected metrics** — round figures
    (1,095,000,000 / 895,000,000 / 8,100,000,000 followers 13,000,000), all three creators, no
    `mkbhd`. They are the seed rows this file already records as deliberately left in place. **Real
    collected history begins 2026-08-05**, so the project has two days of real data, not three. A
    consequence to expect and not misread: xqc's followers appear to "drop" 13,000,000 → 2,500,000
    between 08-04 and 08-05 — that is the seed giving way to the real number, not a metric movement.

  - **08-05 and 08-06 `views` are byte-identical for all three real creators** (kaicenat 439,535,493;
    pokimane 96,004,740; xqc 1,903,001,878). YouTube's `viewCount` is served from a cache that had not
    rolled over between the two runs. This is a property of the data source, not a collector bug — and
    `0` correctly means "the platform reported the same number", never "no data" (CLAUDE.md NULL-vs-0).

  - **Therefore today's digest renders every delta as 0 and no ±20% flag can fire live (BOT-02).**
    Decision: accept and record it. BOT-02 is proven by the four boundary unit tests plan 06-03
    specifies (either side of ±20%), and `06-UAT.md` must state plainly that no flag fired live
    because real data did not move — not claim a live proof that did not happen. A forced proof
    (temporarily editing one 08-05 `views` value, watching the flag render, restoring) remains
    available for the interview demo and must be labelled a forced proof, exactly as Phase 5 D-08
    labelled the forced watchdog run.

  - **`mkbhd` still renders `—` and is unaffected** — its latest row is 08-05 with no 08-04 baseline
    of its own, so it is live proof of DATA-04 and D-12 regardless of the zero deltas.

- Phase 5 PARTIAL: 05-UAT.md entry 7 (ROADMAP criterion 5, author's unaided onEdit/webhook explanation) PENDING by author decision at ~06:00 Asia/Manila 2026-08-06 to proceed to Phase 6; interview is 20:00 same day. Close-later step in 05-UAT.md. Also PENDING (non-gating): criterion 4's natural 09:00 Manila trigger fire, bonus evidence only.
- `docs/deploy.md` (Phase 2 D-13) still absent from the repo. Human-owned and untouched by the rule-1 amendment — the agent must not draft or outline it. Phase 7 work.
- `deploy/creatorpulse-bot.service` is committed but must NOT be installed or enabled yet: `creatorpulse bot` is still the stub at `src/creatorpulse/cli.py:155` returning exit 3, and `Restart=on-failure` would produce a 10-second restart loop. Install after Phase 6 executes.
- Local branch is 25+ commits ahead of `origin/main` and unpushed. Also blocks worktree isolation (`origin/HEAD` unresolved → quick tasks auto-degrade to sequential).
- **Dev-machine credentials are set at Windows User scope (2026-08-06), not session scope:**
  `DISCORD_BOT_TOKEN`, `DISCORD_WEBHOOK_URL`, `DISCORD_CHANNEL_ID`, `DISCORD_GUILD_ID`,
  `YOUTUBE_API_KEY`. They persist in the user registry until removed and are read by any new shell —
  this is what makes plan 06-01's checkpoint runnable locally. `CREATORPULSE_DB` is deliberately
  unset locally so the repo-root `creatorpulse.db` (gitignored, real data copied from the droplet)
  is used. Remove with:
  `'DISCORD_BOT_TOKEN','DISCORD_WEBHOOK_URL','DISCORD_CHANNEL_ID','DISCORD_GUILD_ID','YOUTUBE_API_KEY' | ForEach-Object { [Environment]::SetEnvironmentVariable($_,$null,'User') }`

- **Discord credentials verified live 2026-08-06, and they cross-check:** bot token authenticates as
  `Creator Pulse Bot#6328` (id 1534687081308225556); the bot is a member of guild
  `Creator Pulse Discord` matching `DISCORD_GUILD_ID`; and the webhook's own `channel_id` and
  `guild_id` match `DISCORD_CHANNEL_ID` / `DISCORD_GUILD_ID`. That last check proves the bot's digest
  (bot token → channel) and the collector's alert (webhook) reach the **same** channel — Phase 6 D-02's
  split transport and Phase 5 D-16's one-channel rule are verified against live credentials, not
  assumed. No message was posted; a `GET` on a webhook returns metadata only.

- **BOT-07 completed by hand 2026-08-06** (Hard Rule 3, human-owned): zero privileged intents
  (Presence, Server Members, Message Content all OFF), Public Bot OFF, Install Link , Guild
  Install context ON, and the bot's guild role stripped of Administrator down to View Channel +
  Send Messages. This is the evidence for ROADMAP Phase 6 criterion 5's "why of them are
  privileged" half; the author's own written explanation still has to land in `06-UAT.md` unaided.

- 06-01 Task 3 (blocking human checkpoint): creatorpulse bot --digest-now not yet run live. Exact commands recorded in 06-01-SUMMARY.md's Checkpoint section. Author must run and screenshot before 06-04's 06-UAT.md closes criterion 1's forced half.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260806-k5w | land deploy/ unit files, .env.example Discord + keyfile vars, and the dated Hard Rule 1 amendment | 2026-08-06 | bb9c72f | [260806-k5w-land-deploy-unit-files-env-example-disco](./quick/260806-k5w-land-deploy-unit-files-env-example-disco/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-08-06T09:22:45.491Z
Stopped at: Completed 06-05-PLAN.md
Resume file: None
