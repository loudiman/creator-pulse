# CreatorPulse

## What This Is

A daily creator-metrics collector that runs unattended on a rented Linux VPS. Every morning a systemd timer fires a Python job that pulls public stats for a configured list of social media creators, writes them with full history into SQLite, syncs a Google Sheet view, and posts a summary to Discord. Nobody touches it.

It is intentionally small. It is a portfolio artifact for a Content Lab automation role — a working version of the interviewer's own internal-tooling stack, built to be explained out loud rather than to look impressive.

## Core Value

**The unattended daily run.** A timer fires, real numbers land in the database, the Sheet reflects them, and Discord says so — with no human in the loop. If the LLM digest, the extra slash commands, and even the scraper all get cut, that loop must still work.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Collector reads creator list from `creators.yaml` — adding a creator never requires a code change
- [ ] YouTube Data API v3 source returns normalized metrics for a channel
- [ ] Twitch Helix API source returns summed recent-VOD view count and live status for a channel (follower count is unobtainable — see Key Decisions)
- [ ] TikTok source scrapes public profile pages via Playwright
- [ ] Metrics persist to SQLite with history and an idempotent upsert on `(creator_id, source, metric_date)`
- [ ] One creator or one source failing does not kill the run — failure is isolated and logged
- [ ] Every run writes a row to a `runs` table: start, duration, rows written, failure count
- [ ] Collector runs on a systemd timer on the VPS and is observable via `journalctl`
- [ ] Google Sheet has a Dashboard tab: one row per creator, latest snapshot plus day-over-day delta
- [ ] Google Sheet has a History tab: append-only daily rows
- [ ] Sheet writes are batched, never cell-by-cell
- [ ] Apps Script `onOpen` menu, time-driven trigger, and conditional formatting on the Dashboard *(human-built)*
- [ ] Editing a Status cell in the Sheet posts to a Discord webhook via Apps Script `onEdit` *(human-built)*
- [ ] Discord bot posts a daily digest on schedule from the VPS
- [ ] Digest flags any creator whose day-over-day delta exceeds ±20% (static threshold, not learned)
- [ ] A run that records failures posts to Discord immediately, separate from the scheduled digest
- [ ] Discord `/creator` command returns a named creator's current numbers and trend
- [ ] Discord `/status` command reports last run time, duration, and failure count
- [ ] Secrets load from a `chmod 600` env file via systemd `EnvironmentFile`, never from the repo
- [ ] `ruff check .`, `mypy src/`, and `pytest` all pass, with tests running against saved fixtures only
- [ ] README with architecture diagram, presentable to a stranger

### Out of Scope

- Web frontend or dashboard UI — the Sheet is the UI; a frontend is a different job posting
- Authentication, multi-user, roles — single operator, single machine
- Cloud data warehouse, Docker, Kubernetes, message queues — one process on one box; this is the whole point
- More than 3 data sources — YouTube, Twitch, TikTok is the cap
- Anything requiring a paid API tier — free public/official endpoints only
- LLM-written prose digest — needs a paid key, first item on the cut list, excluded from v1 and v2
- Bot-detection evasion of any kind — public unauthenticated pages, respect `robots.txt`, stop if blocked
- Twitch follower count — hard auth wall on the official API, replaced by VOD view counts and live status
- ML or learned anomaly detection — 5–7 days of data cannot train a baseline; static threshold instead
- Postgres — SQLite is correct for one machine; Postgres is resume-driven overkill
- Cron — systemd timer gives real logs, survives reboot, and is the better answer in conversation

## Context

**Why this project exists:** Content Lab's ops team runs exactly this kind of internal tooling, and the interviewer built theirs personally. A small working version of their own stack beats a large impressive thing in a stack they don't use. Interview is Thursday 6 Aug 2026, 8:00pm PHT.

**Build window:** Thursday 30 July – Wednesday 5 August 2026. Seven days, part-time.

**The three human-built components.** These are the interview's real subject matter and the author's real gaps. The agent does not generate them:

1. **VPS setup** — SSH keys, non-root user, UFW, systemd unit and timer, `journalctl`. An afternoon of work, and unfakeable in conversation.
2. **The Apps Script layer** — roughly 100 lines. The author's biggest gap and the interviewer's deepest skill. Typed by hand.
3. **Discord Developer Portal** — bot registration, intents, scopes, invite URL. The agent may write command handlers; the author must understand the permissions.

Everything else the agent can draft: parsing, retries, logging, schema, tests, README scaffolding.

**Source split, and why it matters.** Official API first, Playwright only where no API exists. YouTube (Data API v3) and Twitch (Helix) are official and free. TikTok has no free public API, so it gets Playwright against public profile pages. This split — knowing when a scraper is the wrong tool and when it's the only tool — is the engineering judgment worth defending in the interview.

**Database is the source of truth, not the Sheet.** The Sheet is a view. The database gives history, deduplication, and re-runnability; the Sheet gives a surface the ops team can actually read and edit.

**Build journal.** A markdown file, a few lines a day: what broke, what was decided, what the agent proposed that got rejected and why. It becomes three things at once — the design-decisions section of the README, the answers when the interviewer drills into architecture, and the truthful version of the "how has AI changed the way you build" and "a time you rejected an AI solution" answers already submitted on the application. Ten minutes a day. Not optional.

**Definition of green.** Verify cannot pass on "it ran without crashing." Green means all of: `ruff check .`, `mypy src/`, and `pytest` — where pytest includes an idempotency test (run collector twice, assert row count unchanged), a normalisation test (fixture in → expected record out), and a failure-isolation test (one source raises, run completes, failure logged). Plus a manual end-to-end run the author watches, with real data landing in the real Sheet and a real Discord post, at the end of every phase from Phase 3 onward.

**Guard against the classic failure.** Agents under pressure weaken tests to reach green. Diff test files each iteration; treat any test change during Verify as suspect unless it was explicitly requested.

**Cut order if behind:** extra slash commands → Playwright/TikTok source (ship API-only) → History tab. Never cut the VPS/systemd phase, the Apps Script phase, or the Discord bot phase — those are the three gaps that actually matter.

## Constraints

- **Merge rule**: Nothing enters the repo that the author cannot explain out loud — this outranks every other consideration, including speed
- **Ownership**: VPS/systemd config, Apps Script, and Discord Developer Portal setup are human-built — the agent must not generate them
- **Timeline**: Ship by Wed 5 Aug 2026; interview Thu 6 Aug — seven days, part-time
- **Tech stack**: Python 3.12, SQLite, `gspread` + service account, `discord.py`, Playwright, `pytest`, `ruff`, `mypy` — no new dependencies without asking
- **Budget**: Free tiers only — no paid API plans
- **Deployment**: One rented Linux VPS, systemd timer — no Docker, no orchestration, no cloud services beyond the Sheets API
- **Secrets**: Env file, `chmod 600`, loaded via systemd `EnvironmentFile` — `.gitignore` written before the first commit, never committed
- **Testing**: Fixtures only — no live network calls inside the test suite, which would be slow, flaky, and get the scraper blocked
- **Ethics/legal**: Public, unauthenticated sources only; respect `robots.txt`; never build detection evasion

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python 3.12 | Author's strongest language; Playwright and Sheets libraries are mature | — Pending |
| SQLite over Postgres | One file, zero setup, real SQL. Postgres is overkill for a single machine | — Pending |
| Database is source of truth, Sheet is a view | Gives history, dedup, and re-runnability; Sheet stays disposable | — Pending |
| Official API first, Playwright only where none exists | YouTube and Twitch have free official APIs; TikTok does not. Knowing which tool fits is the judgment worth defending | — Pending |
| Data sources: YouTube, Twitch, TikTok | Two official APIs plus one scrape — demonstrates both halves of the split, caps at the 3-source limit | — Pending |
| systemd timer over cron | Real logs via `journalctl`, survives reboot, better answer in interview | — Pending |
| `gspread` with a service account, batch writes only | Cell-by-cell writes hit Sheets rate limits | — Pending |
| `discord.py` bot as a separate systemd service | Long-lived process; must not share a lifecycle with the one-shot collector | — Pending |
| Sheet layout: Dashboard + History tabs | Dashboard gives conditional formatting and an editable Status column for `onEdit`; History gives the demo something to scroll | — Pending |
| `creators.yaml` for config | Adding a creator must never require a code change | — Pending |
| pytest against saved HTML/JSON fixtures | Live pages in a test loop are slow, flaky, and get you blocked | — Pending |
| LLM digest excluded entirely, not deferred | Needs a paid key; non-goals ban paid tiers. Excluding it from requirements stops it creeping back in | — Pending |
| Unique constraint on `(creator_id, source, metric_date)` | Makes re-runs idempotent by construction rather than by application logic | — Pending |
| Twitch metric is VOD view count + live status, not followers | `GET /helix/channels/followers` requires a broadcaster or moderator *user* token — app credentials are rejected even for total-only counts. No OAuth relationship exists with tracked creators, so follower count is an auth wall, not a scraping problem. `Get Videos` and `Get Streams` are app-token accessible. Documented in README as a design decision | — Pending |
| Day-over-day delta computed on view count, not subscribers | YouTube rounds `subscriberCount` to 3 significant figures above 1k subs, so sub deltas are rounding noise. View counts are unrounded and move daily. Subscriber counts still shown, labelled coarse | — Pending |
| No new dependencies beyond `requests` | Research closed all 8 open gaps against stdlib: hand-rolled retry over tenacity, dataclasses over pydantic, stdlib logging over structlog, gspread's own auth over google-api-python-client. `requests` is already transitive via gspread | — Pending |
| Host: DigitalOcean droplet, Singapore region, 2 GB | Needs a real VM with systemd — container platforms (Fly, Railway, Render) have no init system and Phase 2's whole deliverable is a systemd timer. Chose DO over Hetzner (better value, but new-account identity verification risks a day) and over EC2/Compute Engine (VPC/IAM setup is hours that teach nothing the interview examines). 2 GB gives Playwright headroom without fighting OOM; Singapore keeps SSH latency low from PH. Hourly billing means the build week costs ~$3. **Revisit if Content Lab turns out to be an AWS or GCP shop** — matching their stack would outweigh the setup tax, and AWS Lightsail is the low-friction way to say "it runs on AWS" | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-29 after initialization*
