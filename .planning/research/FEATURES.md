# Feature Research

**Domain:** Internal creator-metrics ops tool (single-operator, Sheet + Discord surface)
**Researched:** 2026-07-29
**Confidence:** MEDIUM (project scope is already decided in PROJECT.md — HIGH confidence there; general domain claims below are supplementary web search, LOW confidence, used only to sanity-check categorization)

## Framing

This is not a SaaS competitive analysis. "Table stakes" = what an ops person glancing at the Sheet/Discord would immediately flag as missing. A feature common in Hootsuite/Sprout Social is irrelevant here if it costs more than a few hours or needs infra this project explicitly rejects (see PROJECT.md Out of Scope). Build-cost signals below are calibrated to the stated 7-day part-time window and the existing stack (Python 3.12, SQLite, gspread, discord.py, Playwright).

## Feature Landscape

### Table Stakes (An Ops Team Would Notice These Missing)

| Feature | Why Expected | Build Cost | Notes |
|---------|--------------|------------|-------|
| Per-creator config file (`creators.yaml`) | Adding/removing a tracked creator is a daily ops action, not a deploy | Hours | Already decided in PROJECT.md. One YAML parse + Pydantic/dataclass validation. |
| Failure isolation (one creator/source failing doesn't kill the run) | A dead TikTok scrape shouldn't blank out YouTube numbers for 20 other creators | Hours–1 day | try/except per (creator, source) pair, log and continue. Cheapest high-value feature in the whole project. |
| Idempotent upsert on `(creator_id, source, metric_date)` | Re-running a failed job must not double-count or duplicate rows | Hours | A UNIQUE constraint + `INSERT ... ON CONFLICT DO UPDATE`. Correctness by construction, not app logic — cheap and it's the thing to defend in the interview. |
| `runs` table (start, duration, rows written, failure count) | "Did it run last night, and did it work?" is the first question any ops person asks | Hours | One INSERT per run, one UPDATE at the end. Feeds both `/status` and journalctl narrative. |
| systemd timer + journalctl visibility | Ops tooling that can't be inspected with standard OS tools isn't ops tooling | Already decided (human-built) | Not app code — a systemd unit/timer file. |
| History tab (append-only daily rows) | "Show me last month" is a reflexive ask; a dashboard with only today's snapshot reads as a toy | Hours | Straight append from SQLite history query. Cut-order item #3 if behind schedule — see PROJECT.md. |
| Dashboard tab: one row per creator, latest snapshot + day-over-day delta | The whole point of a daily tracker is "what changed since yesterday" — a snapshot without a delta is just a spreadsheet export | 1 day | Delta = `SELECT` yesterday's row minus today's, computed in Python before the Sheet write (not a Sheet formula — keeps the Sheet a pure view). |
| Conditional formatting on delta (green up / red down) | Scanning 15–20 rows for the 2 that moved is what conditional formatting exists to solve | Already decided (human-built, Apps Script) | Standard "greater than 0 → green, less than 0 → red" rule on the delta column. |
| Batched Sheet writes (never cell-by-cell) | Cell-by-cell writes on ~20 creators × several columns will hit Sheets API rate limits inside days, not weeks | Hours | `gspread` `update()` with a 2D array, one call per tab per run. Not user-visible but a silent table-stakes correctness requirement — omit it and the tool intermittently fails in front of the interviewer. |
| Discord daily digest on schedule | An ops channel that requires someone to open a Sheet to know anything happened defeats the "Discord surface" half of the pitch | 1 day | Templated string (creator, current value, delta arrow), not prose generation — see anti-features. |
| `/status` slash command (last run time, duration, failures) | First thing anyone asks a bot that owns a background job: "is it alive?" | Hours–1 day | Direct read of the `runs` table's latest row. Doubles as the operability feature and a Discord feature — cheapest command to build. |
| `/creator <name>` slash command | An ops person in a Discord thread wants one creator's numbers without opening the Sheet | 1 day | Query latest + prior row for that creator_id, format inline. Cut-order item #1 if behind — see PROJECT.md. |
| Secrets outside the repo (`chmod 600` env file) | Any credential in a public/portfolio repo is disqualifying, not just sloppy | Hours | Already decided. `.gitignore` before first commit. |

### Differentiators (What Makes This Worth Showing an Interviewer)

| Feature | Value Proposition | Build Cost | Notes |
|---------|--------------------|------------|-------|
| Two-way Sheet↔Discord round trip (editing a Status/Notes cell fires a Discord webhook via `onEdit`) | Most take-home ops tools are read-only reporting; a human-editable cell that talks back demonstrates the Sheet is a *surface*, not a dump — this is the single most interesting thing in the project | Already scoped (human-built, ~part of the 100-line Apps Script) | Depends on: Dashboard tab existing, Status column existing. This is the feature to walk the interviewer through slowly. |
| Official-API-vs-scraper source split (YouTube/Twitch API, TikTok Playwright) | Shows the judgment call ops engineers actually make — not "can you scrape," but "do you know when scraping is the wrong tool" | Already decided, ~1–2 days for the Playwright adapter + fixtures | The TikTok adapter is the most expensive single feature in the project (browser automation + fixture-based tests + no official API to fall back on). If the week runs short, this is the second thing to cut per PROJECT.md cut-order. |
| Simple anomaly flag on the digest (e.g., `⚠️` if `|delta| > 20%` day-over-day) | Turns the digest from "here are numbers" into "here's what's worth looking at" without any ML | 2–4 hours | Do NOT build a learned baseline (see anti-features) — a static threshold on the delta you already compute is nearly free once day-over-day delta exists. Genuine differentiator-per-dollar: cheapest feature with real "wow" per hour spent. |
| Failure-triggers-a-Discord-ping (distinct from the scheduled digest) | Ops teams don't want to wait for tomorrow's digest to learn last night's run failed entirely | 2–3 hours | Reuses the `runs` table + digest job's own Discord client; just an `if failure_count == total` branch that posts immediately instead of waiting for the schedule. Cheap, and answers "how would you know if this broke at 3am" before the interviewer asks it. |
| Idempotency test as a first-class pytest (run collector twice, assert row count unchanged) | Most take-homes claim idempotency; almost none prove it in a test an interviewer can run live | Hours (already required by PROJECT.md's Definition of Green) | This is a testing feature, not a user feature, but it's the kind of thing that reads as senior judgment in a live walkthrough. |
| Build journal (design decisions, rejected AI suggestions) | Directly answers "how has AI changed how you build" and "a time you rejected an AI suggestion" — already-submitted application answers, now made verifiable | 10 min/day, already scoped in PROJECT.md | Not a software feature but a deliverable; listed here because it's the actual differentiator versus every other take-home the interviewer will see. |

### Anti-Features (Deliberately Not Building)

| Feature | Why It Looks Appealing | Why It's Wrong Here | What to Do Instead |
|---------|------------------------|----------------------|---------------------|
| Web UI / dashboard frontend | Feels like "a real product" | Duplicates the Sheet, which is the actual UI the interviewer's own team uses; building a frontend is a different job posting's worth of work in a 7-day window | The Sheet is the UI. Ship that well instead. |
| Auth / multi-user / roles | Standard SaaS checklist item | Single operator, single VPS — there is no second user or tenant boundary to protect | None; document the assumption. |
| Data warehouse (BigQuery/Snowflake/etc.) | "Scalable analytics" sounds impressive | Tens of creators × one row/day is a few thousand rows/year — SQLite on one file handles this for the tool's entire lifetime | SQLite as source of truth (already decided). |
| Docker / Kubernetes / message queues | "Production-grade infra" | One process, one systemd timer, one box — orchestration for a single daily job is infra theater that the interviewer will see through, not be impressed by | systemd timer + `EnvironmentFile` (already decided). |
| More than 3 data sources | "More coverage" | Each new source is a full adapter + normalized schema mapping + fixture set + tests — not a config change. Diminishing returns past the point that already demonstrates the API-vs-scraper split | Cap at YouTube + Twitch + TikTok (already decided). |
| Any paid API tier | Higher rate limits, richer data | Explicit non-goal; also a personal-money-in-a-portfolio-project problem no interviewer wants to see | Free/official public endpoints only. |
| LLM-written prose digest | "Smart" summary reads nicer than a template | Needs a paid key (banned), and it introduces nondeterministic output into something the pytest suite needs to assert against | Templated digest string: creator name, value, delta, arrow/emoji. Deterministic, testable, and reads perfectly fine to an ops audience who wants numbers, not prose. |
| Bot-detection evasion (rotating proxies, stealth headers, CAPTCHA solving) | Higher scrape reliability | Ethical/legal line explicitly drawn in PROJECT.md; also unnecessary — 2 of 3 sources are official APIs and TikTok only needs a public, unauthenticated, `robots.txt`-respecting page fetch | Stop and log if blocked; do not escalate. |
| Statistical/ML-based anomaly detection (learned baselines, rolling z-scores) | "Real" anomaly detection tools use this | Needs weeks of history to establish a baseline — the build window produces 5–7 days of real data, nowhere near enough to train or validate a model; research on this category also flags alert fatigue as the dominant failure mode of over-tuned detectors | Static threshold on day-over-day delta (see differentiators table) — same user-facing value, near-zero cost, no false confidence in an untrained model. |
| Sub-daily / real-time polling | "Live" data feels more capable | Daily cadence matches the daily digest and the ops use case; polling more often burns free-tier API quota for numbers nobody is watching between digests | Once-daily systemd timer (already decided). |
| Rolling averages / N-day trend columns | Common in analytics dashboards | Needs ≥7 days of history to mean anything; the build window itself only accumulates 5–7 days of real data, so this column would ship empty or meaningless at demo time | Day-over-day delta only for v1. Revisit once weeks of real history exist post-ship. |
| Historical backfill of years of past platform data | "Complete" dataset looks thorough | The tool's value is prospective daily tracking with real live runs, not a one-time import job; backfill is also the one feature most likely to trip TikTok scraping rate limits for no ops value | None needed — the daily runs themselves build history from day one. |
| Grafana/Prometheus-style observability stack for the pipeline | "Proper" monitoring | Directly the kind of infra the project's Out of Scope section rejects (no Docker, no extra services) for one daily batch job | journalctl (already available via systemd) + `/status` Discord command + `runs` table. Three free surfaces already cover the observability need. |
| Sheet cells as a second source of truth (manual metric edits) | Feels flexible | Breaks dedup/idempotency guarantees the moment a human overwrites a number the next run will overwrite back | Sheet is a read-view; only the Status/Notes column is human-editable and it is deliberately *not* a metrics column. |

## Feature Dependencies

```
creators.yaml config
    └──required by──> collector run (per-creator, per-source loop)

Idempotent upsert (creator_id, source, metric_date)
    └──required by──> History tab
    └──required by──> Day-over-day delta (needs ≥2 days of rows to diff)
                           └──required by──> Conditional formatting (green/red on delta)
                           └──required by──> Static-threshold anomaly flag on digest
                           └──enhances─────> /creator command (shows trend, not just current value)

runs table
    └──required by──> /status command
    └──required by──> Failure-triggers-immediate-Discord-ping

Dashboard tab (Sheet)
    └──required by──> Status/Notes column
                           └──required by──> onEdit → Discord webhook (human-built Apps Script)

Day-over-day delta
    └──weak-dependency──> Rolling averages / N-day trend (needs ≥7 days history — likely absent during build window; see anti-features)

Official API sources (YouTube, Twitch)
    └──independent of──> Playwright/TikTok source (no shared code path; isolated per PROJECT.md failure-isolation requirement)
```

### Dependency Notes

- **Day-over-day delta requires the idempotent-upsert schema and at least 2 days of real runs.** Ship the collector and let it run for 2+ days before the delta column has anything to show — this affects demo-day sequencing, not just build sequencing.
- **The Status/Notes round-trip requires the Dashboard tab to exist first** (human-built Apps Script layer depends on the Python side writing a stable tab structure it can attach triggers to).
- **`/status` and the failure-ping both key off the same `runs` table** — build the table once, get two features.
- **Rolling averages and true trend lines are gated on history depth the build window won't reach.** Don't schedule them; the anti-features table already flags this as a hard cut, not a stretch goal.
- **TikTok/Playwright is isolated from the two API sources by the failure-isolation requirement** — it can be cut entirely (ship API-only) per PROJECT.md's stated cut order without touching YouTube/Twitch code.

## MVP Definition

PROJECT.md's Active requirements already are the MVP scope for this build window — restated here as the feature layer:

### Launch With (v1 — this build window)

- [ ] `creators.yaml` config — no code change to add a creator
- [ ] YouTube + Twitch API sources, TikTok Playwright source
- [ ] Idempotent SQLite upsert with history
- [ ] Per-(creator, source) failure isolation
- [ ] `runs` table + systemd/journalctl observability
- [ ] Sheet: Dashboard (latest + delta) and History tabs, batched writes
- [ ] Apps Script: conditional formatting, Status column, `onEdit` → Discord (human-built)
- [ ] Discord: daily digest, `/creator`, `/status`
- [ ] Secrets via `chmod 600` env file

### Add After Validation (only if ahead of schedule, per PROJECT.md cut-order in reverse)

- [ ] Static-threshold anomaly flag on the digest (2–4 hrs, cheapest real differentiator left)
- [ ] Failure-triggers-immediate-Discord-ping, separate from scheduled digest (2–3 hrs)
- [ ] Additional slash commands (e.g., `/top` — highest single-day gain across all tracked creators)

### Future Consideration (post-portfolio, not this window)

- [ ] Rolling/N-day averages — needs weeks of accumulated history to be meaningful
- [ ] Learned-baseline anomaly detection — needs training data this window can't produce
- [ ] A 4th+ data source — only after proving the 3-source pattern holds up in production

## Feature Prioritization Matrix

| Feature | Ops Value | Build Cost | Priority |
|---------|-----------|-------------|----------|
| Idempotent upsert + history | HIGH | LOW | P1 |
| Failure isolation | HIGH | LOW | P1 |
| `runs` table | HIGH | LOW | P1 |
| Dashboard + delta | HIGH | MEDIUM | P1 |
| History tab | MEDIUM | LOW | P1 (cut-order #3) |
| Discord digest | HIGH | MEDIUM | P1 |
| `/status` | HIGH | LOW | P1 |
| `/creator` | MEDIUM | MEDIUM | P1 (cut-order #1) |
| Status/Notes round-trip | HIGH (interview narrative) | LOW (human-built) | P1 |
| TikTok/Playwright source | MEDIUM (narrative value) | HIGH | P1 (cut-order #2) |
| Static-threshold anomaly flag | MEDIUM | LOW | P2 |
| Failure-ping | MEDIUM | LOW | P2 |
| Extra slash commands | LOW | LOW–MEDIUM | P3 |
| Rolling averages | LOW (no data to show) | MEDIUM | P3 / defer |
| Learned anomaly detection | LOW (unbuildable well in-window) | HIGH | Cut |

**Priority key:**
- P1: In PROJECT.md's Active requirements — must ship
- P2: Cheap, add only if ahead of schedule
- P3 / defer / cut: Explicitly not this window's job

## Sources

- PROJECT.md (this repo) — primary source; requirements, constraints, and cut-order already decided. HIGH confidence.
- General web search (Brave/WebSearch, LOW confidence, used only for sanity-checking categorization, not as authoritative claims):
  - [Ablebits: Google Sheets conditional formatting guide](https://www.ablebits.com/office-addins-blog/google-sheets-conditional-formatting/) — status-column and full-row-highlight conventions
  - [Analytics Vidhya: Conditional formatting in Google Sheets](https://medium.com/analytics-vidhya/use-conditional-formatting-in-google-sheets-like-a-pro-c3a46758e8d2) — avoid over-formatting, direct attention to exceptions
  - [Discord Developer Docs: Application Commands](https://docs.discord.com/developers/interactions/application-commands) — slash command structure
  - [FasterCapital: Social media anomaly detection](https://fastercapital.com/content/Social-Media-Anomaly-Detection--How-to-Detect-and-Handle-Outliers-and-Errors-in-Your-Social-Media-Data.html) — spike/dip patterns, alert fatigue as common failure mode
  - [Sifflet: What is data pipeline monitoring](https://www.siffletdata.com/blog/data-pipeline-monitoring) — run-status, historical trend, alert-management as core monitoring components

---
*Feature research for: internal creator-metrics ops tool (CreatorPulse)*
*Researched: 2026-07-29*
