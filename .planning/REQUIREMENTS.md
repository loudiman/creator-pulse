# Requirements: CreatorPulse

**Defined:** 2026-07-29
**Core Value:** The unattended daily run — a timer fires, real numbers land in the database, the Sheet reflects them, and Discord says so, with no human in the loop.

**Ownership legend:** Requirements marked *(human-built)* are implemented by the author, not the agent. The agent may write code that depends on them, but must not generate the artifact itself.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Configuration

- [x] **CFG-01**: Operator can add a creator by editing `creators.yaml` — no code change required
- [x] **CFG-02**: Each creator entry declares its platform and that platform's identifier (YouTube handle or channel ID, Twitch login, TikTok username)
- [x] **CFG-03**: An invalid or incomplete `creators.yaml` fails at startup with a message naming the offending creator and field, not a bare traceback

### Sources

- [x] **SRC-01**: YouTube source returns subscriber count, total view count, and video count for a configured channel via YouTube Data API v3 using an API key
- [ ] **SRC-02**: Twitch source returns summed recent-VOD view count and current live status for a configured channel using an app access token *(BLOCKED-EXTERNAL as of 2026-08-05 — see note below)*

  > **SRC-02 is blocked on Twitch account 2FA, not on effort or design.** Registering an application
  > in the Twitch Developer Console requires two-factor authentication on the account, 2FA enrolment
  > requires a mobile number, and the verification SMS does not arrive. No client id or secret can be
  > obtained, so the five Twitch fixtures cannot be recorded through `scripts/record_fixture.py` and
  > hand-authoring a fixture is forbidden. Plan `03-03-PLAN.md` is written, reviewed, and left
  > unexecuted; the source layer's `Protocol` plus `FETCHERS` registry means wiring it in is one
  > registry line once credentials exist. This is the second time Twitch has walled this project off —
  > the first was the follower-count endpoint requiring a broadcaster user token (see Out of Scope).

- [ ] **SRC-03**: TikTok source returns follower count, total likes, and video count by reading the public profile page with Playwright
- [x] **SRC-04**: Every source returns the same normalized record shape; a metric the platform does not expose is NULL, never 0
- [x] **SRC-05**: A source failing on a transient error retries with backoff before the attempt is recorded as failed

### Storage

- [x] **DATA-01**: Metrics persist to SQLite with one row per creator, per source, per date
- [x] **DATA-02**: Re-running the collector on the same day updates existing rows rather than duplicating them — total row count is unchanged
- [x] **DATA-03**: Every run writes a row to `runs` recording start time, duration, rows written, and failure count
- [x] **DATA-04**: Previous days' rows are never overwritten by a later run — full daily history stays queryable
- [ ] **DATA-05**: The collector (writer) and the Discord bot (reader) can use the database concurrently without lock errors

### Collection Run

- [ ] **RUN-01**: One creator or one source failing does not abort the run — all remaining work still completes
- [ ] **RUN-02**: Each failure is logged with creator, source, and cause, and counted in that run's `runs` row
- [x] **RUN-03**: The collector runs unattended on a daily systemd timer *(human-built: unit and timer files)*
- [x] **RUN-04**: Run output is readable after the fact via `journalctl -u <unit>`
- [x] **RUN-05**: `metric_date` is computed once per run in UTC, so a run slipping past midnight cannot split one run across two dates

### Sheet

- [ ] **SHEET-01**: Dashboard tab shows one row per creator with the latest snapshot and its day-over-day delta
- [ ] **SHEET-02**: Day-over-day delta is computed on view count; subscriber and follower counts are displayed but labelled coarse where the platform rounds them
- [ ] **SHEET-03**: A creator with no prior-day row shows `—` for delta, never a delta computed against an assumed zero
- [ ] **SHEET-04**: History tab appends one row per creator per day and is never rewritten
- [ ] **SHEET-05**: Sheet writes are batched — at most one write call per tab per run, never cell-by-cell
- [ ] **SHEET-06**: The human-edited Status column survives a Dashboard refresh untouched
- [ ] **SHEET-07**: A Sheet not shared with the service account fails with an explicit instruction naming the `client_email` to share it with, not a raw 403

### Apps Script

*(entire category human-built — the agent does not generate these)*

- [ ] **SCRIPT-01**: Sheet has an `onOpen` custom menu
- [ ] **SCRIPT-02**: A time-driven trigger runs on schedule
- [ ] **SCRIPT-03**: Editing a Status cell posts to a Discord webhook via `onEdit`
- [ ] **SCRIPT-04**: Conditional formatting highlights day-over-day movement on the Dashboard

### Discord

- [ ] **BOT-01**: Bot posts a daily digest listing top movers and any failures from that run
- [ ] **BOT-02**: Digest flags any creator whose day-over-day delta exceeds ±20%
- [ ] **BOT-03**: A run that records failures posts to Discord immediately, separate from the scheduled digest
- [ ] **BOT-04**: `/creator <name>` returns that creator's current numbers and recent trend
- [ ] **BOT-05**: `/status` reports last run time, duration, rows written, and failure count
- [ ] **BOT-06**: The bot runs as its own systemd service, separate from the collector *(human-built: unit file)*
- [ ] **BOT-07**: Bot registration, intents, scopes, and invite URL configured in the Discord Developer Portal *(human-built)*

### Operations & Quality

- [x] **OPS-01**: Secrets load from a `chmod 600` env file via systemd `EnvironmentFile` and are never committed
- [x] **OPS-02**: `ruff check .` passes clean
- [x] **OPS-03**: `mypy src/` passes clean
- [x] **OPS-04**: `pytest` passes running only against saved fixtures — no live network calls in the suite
- [ ] **OPS-05**: Tests cover idempotency — run the collector twice, assert row count unchanged
- [x] **OPS-06**: Tests cover normalisation — a saved fixture in produces the expected record out, for each source
- [ ] **OPS-07**: Tests cover failure isolation — one source raises, the run still completes, the failure is logged
- [ ] **OPS-08**: README explains the architecture with a diagram and records the design decisions behind it
- [ ] **OPS-09**: Build journal records what broke, what was decided, and what agent proposals were rejected and why

## v2 Requirements

Deferred to future release. Tracked but not in the current roadmap.

### Data

- **V2-DATA-01**: Rolling averages and multi-day trend lines — needs ≥7 days of accumulated history the build window itself won't produce
- **V2-DATA-02**: Historical backfill of dates before first run — most platforms don't expose it, and it's not needed to prove the loop

### Discord

- **V2-BOT-01**: Additional slash commands beyond `/creator` and `/status` (e.g. `/compare`, `/history`)
- **V2-BOT-02**: Configurable per-creator alert thresholds instead of a single global ±20%

### Sources

- **V2-SRC-01**: A fourth data source — blocked by the deliberate 3-source cap, not by capability

### Operations

- **V2-OPS-01**: journald priority mapping so `journalctl -p err` filters correctly — needs `systemd-python` and `libsystemd-dev` on the VPS

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Web frontend or dashboard UI | The Sheet is the UI. A frontend is a different job posting |
| Authentication, multi-user, roles | Single operator, single machine |
| Cloud data warehouse | SQLite on one box is correct at this scale; anything more is resume-driven |
| Docker, Kubernetes, message queues | One process on one machine is the entire point of the project |
| Postgres | Overkill for a single machine. SQLite is one file, zero setup, real SQL |
| Cron | systemd timer gives real logs via journalctl, survives reboot, and is the better interview answer |
| More than 3 data sources | Deliberate cap — YouTube, Twitch, TikTok |
| Any paid API tier | Free official/public endpoints only |
| LLM-written prose digest | Needs a paid key, which the paid-tier ban excludes. Digest stays a deterministic template |
| ML or learned anomaly detection | 5–7 days of data cannot train a baseline. Static ±20% threshold instead |
| Sub-daily polling | Daily is the stated cadence; more frequent burns API quota for no added signal |
| Grafana/Prometheus-style observability | `journalctl` plus the `runs` table plus `/status` is proportionate for one machine |
| Twitch follower count | Hard auth wall — `/helix/channels/followers` requires a broadcaster or moderator *user* token, unobtainable for third-party creators. Replaced by VOD view counts and live status (see SRC-02) |
| Bot-detection evasion of any kind | Public unauthenticated pages only, respect `robots.txt`. If a source needs evasion to load, the source gets dropped |
| Sheet cells as a second source of truth | The database is the source of truth; the Sheet is a view. Only the Status column is human-owned |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFG-01 | Phase 3: Collector Core & API Sources | Complete |
| CFG-02 | Phase 3: Collector Core & API Sources | Complete |
| CFG-03 | Phase 3: Collector Core & API Sources | Complete |
| SRC-01 | Phase 3: Collector Core & API Sources | Complete |
| SRC-02 | Phase 3: Collector Core & API Sources | Blocked (external — Twitch 2FA) |
| SRC-03 | Phase 4: Playwright & Sheets | Pending |
| SRC-04 | Phase 3: Collector Core & API Sources | Complete |
| SRC-05 | Phase 3: Collector Core & API Sources | Complete |
| DATA-01 | Phase 3: Collector Core & API Sources | Complete |
| DATA-02 | Phase 3: Collector Core & API Sources | Complete |
| DATA-03 | Phase 3: Collector Core & API Sources | Complete |
| DATA-04 | Phase 3: Collector Core & API Sources | Complete |
| DATA-05 | Phase 3: Collector Core & API Sources | Pending |
| RUN-01 | Phase 3: Collector Core & API Sources | Pending |
| RUN-02 | Phase 3: Collector Core & API Sources | Pending |
| RUN-03 | Phase 2: VPS & systemd | Complete |
| RUN-04 | Phase 2: VPS & systemd | Complete |
| RUN-05 | Phase 3: Collector Core & API Sources | Complete |
| SHEET-01 | Phase 4: Playwright & Sheets | Pending |
| SHEET-02 | Phase 4: Playwright & Sheets | Pending |
| SHEET-03 | Phase 4: Playwright & Sheets | Pending |
| SHEET-04 | Phase 4: Playwright & Sheets | Pending |
| SHEET-05 | Phase 4: Playwright & Sheets | Pending |
| SHEET-06 | Phase 4: Playwright & Sheets | Pending |
| SHEET-07 | Phase 4: Playwright & Sheets | Pending |
| SCRIPT-01 | Phase 5: Apps Script | Pending |
| SCRIPT-02 | Phase 5: Apps Script | Pending |
| SCRIPT-03 | Phase 5: Apps Script | Pending |
| SCRIPT-04 | Phase 5: Apps Script | Pending |
| BOT-01 | Phase 6: Discord Bot | Pending |
| BOT-02 | Phase 6: Discord Bot | Pending |
| BOT-03 | Phase 6: Discord Bot | Pending |
| BOT-04 | Phase 6: Discord Bot | Pending |
| BOT-05 | Phase 6: Discord Bot | Pending |
| BOT-06 | Phase 6: Discord Bot | Pending |
| BOT-07 | Phase 6: Discord Bot | Pending |
| OPS-01 | Phase 2: VPS & systemd | Complete |
| OPS-02 | Phase 1: Skeleton | Complete |
| OPS-03 | Phase 1: Skeleton | Complete |
| OPS-04 | Phase 1: Skeleton | Complete |
| OPS-05 | Phase 3: Collector Core & API Sources | Pending |
| OPS-06 | Phase 3: Collector Core & API Sources | Complete |
| OPS-07 | Phase 3: Collector Core & API Sources | Pending |
| OPS-08 | Phase 7: Reliability & Docs | Pending |
| OPS-09 | Phase 7: Reliability & Docs | Pending |

**Coverage:**

- v1 requirements: 45 total
- Mapped to phases: 45
- Unmapped: 0 — full coverage, no orphans, no duplicates

**By phase:**

| Phase | Owner | Requirements |
|-------|-------|--------------|
| 1. Skeleton | agent | 3 |
| 2. VPS & systemd | human | 3 |
| 3. Collector Core & API Sources | agent | 18 |
| 4. Playwright & Sheets | agent | 8 |
| 5. Apps Script | human | 4 |
| 6. Discord Bot | mixed | 7 |
| 7. Reliability & Docs | mixed | 2 |

Notes on two assignment calls:

- **OPS-02/03/04 sit in Phase 1** because that is where the gate is built. They are re-enforced at every subsequent phase via the Definition of Green in ROADMAP.md, not re-owned by later phases.
- **OPS-06 (normalisation tests, "for each source") sits in Phase 3** alongside the two API sources. The TikTok fixture test is added in Phase 4 as part of SRC-03's own work rather than reopening OPS-06.

---
*Requirements defined: 2026-07-29*
*Last updated: 2026-07-29 after roadmap creation (traceability populated)*
