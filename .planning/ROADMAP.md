# Roadmap: CreatorPulse

## Overview

Seven phases, roughly one per day of the Thu 30 Jul – Wed 5 Aug 2026 build window. The shape follows the research's proposed structure unchanged (Skeleton → VPS → Collector core → Playwright+Sheets → Apps Script → Discord bot → Reliability+docs), which itself matches the author's own day-by-day plan. Risk is front-loaded: the toolchain gate and the deployment target exist before any real code; the normalization boundary and database land before any source that depends on them; the two official APIs prove the plumbing before the one scraper; the highest-pitfall phase (Playwright + Sheets) sits mid-window while there is still slack behind it. The three human-built areas — VPS/systemd, Apps Script, Discord Developer Portal — are phases in their own right because they are the interview's actual subject matter, not incidental setup.

## Ownership

Every phase declares an owner. This is a hard constraint, not a preference.

| Owner | Meaning |
|-------|---------|
| `agent` | Claude writes it |
| `human` | The author writes it by hand. The agent must not generate the artifact, even if asked to "help" |
| `mixed` | Agent writes code that depends on a human-built artifact; the human builds the artifact |

The three human-built areas: VPS provisioning + systemd units/timers, the entire Apps Script layer, and Discord Developer Portal registration. Requirements carrying *(human-built)* in REQUIREMENTS.md belong to these.

## Cut Order (fixed by the author — do not rediscover this)

If behind schedule, cut in this order and no other:

1. Extra slash commands (`/creator`, `/status` beyond the digest) — BOT-04, BOT-05
2. TikTok / Playwright source — ship API-only — SRC-03
3. History tab — SHEET-04

**Never cut Phase 2 (VPS/systemd), Phase 5 (Apps Script), or Phase 6 (Discord bot).** Those three are the author's real gaps and the interview's real subject matter. A later replan that "optimises" them away has misunderstood the project.

## Definition of Green

A phase does not close on "it ran without crashing." Green means all of:

- `ruff check .` clean
- `mypy src/` clean
- `pytest` passing — including the idempotency (OPS-05), normalisation (OPS-06), and failure-isolation (OPS-07) tests once they exist

**Manual verification gate:** from Phase 3 onward, every phase additionally requires a human-observed end-to-end run against real data — real API responses landing in the real database from Phase 3, reaching the real Google Sheet from Phase 4, and producing a real Discord post from Phase 5 onward. Automated checks alone cannot close these phases.

**Test-weakening guard:** diff test files every Verify iteration. A test changed during Verify is suspect unless the change was explicitly requested.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Skeleton** - Repo layout, toolchain, and the green gate that every later phase must pass (completed 2026-07-30)
- [x] **Phase 2: VPS & systemd** - Provisioned box, timer, journal, and secrets that never touch the repo (completed 2026-08-04)
- [ ] **Phase 3: Collector Core & API Sources** - Normalized records land idempotently in SQLite from YouTube and Twitch
- [ ] **Phase 4: Playwright & Sheets** - TikTok scraped, and the Sheet becomes a readable view of the database
- [ ] **Phase 5: Apps Script** - The Sheet gains a menu, formatting, and a two-way trip back to Discord
- [ ] **Phase 6: Discord Bot** - Daily digest, failure alerts, and on-demand answers from the database
- [ ] **Phase 7: Reliability & Docs** - The system survives being watched, and a stranger can read the README

## Phase Details

### Phase 1: Skeleton

**Goal**: The repo has a shape and a gate — every later phase can be judged pass/fail by one command
**Mode:** mvp
**UI hint**: no
**Owner:** agent
**Depends on**: Nothing (first phase)
**Requirements**: OPS-02, OPS-03, OPS-04
**Success Criteria** (what must be TRUE):

  1. `ruff check .`, `mypy src/`, and `pytest` all run and pass on a fresh clone with no manual setup beyond a documented install step
  2. `git status` is clean and `.gitignore` covers the env file, the SQLite database, the research cache, and Python artifacts — the author can confirm no secret path is trackable
  3. The repo has a `src/` package layout, a `pyproject.toml` pinning the locked dependency set, and a `creators.yaml` that is loadable but not yet consumed
  4. `journal.md` exists with a day-one entry

**Plans**: 3/3 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Walking skeleton tracer: installed package → `creatorpulse collect` reads `creators.yaml`, logs a run, exits 0

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — The suite is real: one loader test, the fixture root, and the hand-run recorder

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — The gate is documented and green: README block, journal day-one entry, `.gitignore` extension

Notes:

- `.gitignore` already exists at the repo root and is committed. This phase **extends** it; it does not create it. Secrets must never reach git history — an un-commit is a rotation, not a fix.
- `pytest` passing here means the suite runs and is wired, not that it covers behaviour. OPS-05/06/07 land in Phase 3.
- No new dependencies beyond the locked set (`requests`, `gspread`, `discord.py`, `playwright`, `PyYAML`, `pytest`, `ruff`, `mypy`). Research closed all 8 gaps against stdlib.

### Phase 2: VPS & systemd

**Goal**: A rented Linux box runs scheduled work unattended, logs it, and holds secrets the repo never sees
**Mode:** mvp
**UI hint**: no
**Owner:** mixed *(changed from `human` by D-01 — the agent writes environment-variable path resolution in `src/creatorpulse/` and nothing else; the unit, the timer, UFW, SSH, and `docs/deploy.md` stay human-built)*
**Depends on**: Phase 1
**Requirements**: RUN-03, RUN-04, OPS-01
**Success Criteria** (what must be TRUE):

  1. A systemd timer fires on schedule with no human present, and the author sees its output afterwards via `journalctl -u <unit>`
  2. `systemctl start <unit>` succeeds against the same code path that works interactively — proving the stripped systemd environment (PATH, HOME, cwd) has been handled, not dodged
  3. The service reads secrets from a `chmod 600` env file via `EnvironmentFile`, and those values are absent from the repo and from `git log`
  4. The timer survives a reboot and, with `Persistent=true`, catches up a missed run
  5. The author can explain out loud, without notes, why systemd timer beats cron here

**Plans**: 3/3 plans executed

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Tracer: a run announces which config and which database it used; plus `.env.example` and the `02-UAT.md` proof scaffold

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — The author provisions the box and starts the service; the agent proves git history never saw a secret (criteria 2, 3)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — The timer fires unattended and catches up across a reboot; `02-UAT.md` closed (criteria 1, 4, 5)

Notes:

- **Human-built. The agent does not generate the unit file, the timer file, the UFW rules, or the SSH configuration.** This is an afternoon of work and unfakeable in conversation.
- At this point the collector does not exist. The timer targets a placeholder entrypoint from Phase 1; RUN-03 fully closes when the real collector is wired in Phase 3, whose criteria carry that check forward.
- Verify the schedule with `systemd-analyze calendar`, not by reasoning about the `OnCalendar` string.
- Provision a swap file now — it is cheap insurance against Playwright OOM in Phase 4.
- Install Playwright's Chromium as the *service* user, not the interactive account, or Phase 4 will fail under systemd only.
- Never cut this phase.

### Phase 3: Collector Core & API Sources

**Goal**: Real numbers from YouTube and Twitch land in SQLite with history, and one broken source cannot take the run down
**Mode:** mvp
**UI hint**: no
**Owner:** agent
**Depends on**: Phase 2
**Requirements**: CFG-01, CFG-02, CFG-03, SRC-01, SRC-02, SRC-04, SRC-05, DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, RUN-01, RUN-02, RUN-05, OPS-05, OPS-06, OPS-07
**Success Criteria** (what must be TRUE):

  1. The author adds a creator to `creators.yaml`, re-runs the collector, and that creator's row appears — with no code change; a malformed entry instead fails at startup naming the offending creator and field
  2. Running the collector twice on the same day leaves the total row count unchanged, and yesterday's rows are untouched — the author can see both facts in one `sqlite3` query
  3. A source made to fail is logged with creator, source, and cause, counted in that run's `runs` row, and the remaining creators still complete
  4. A metric the platform does not expose reads as NULL in the database, never 0 — and the Twitch `followers` column is NULL on every row for exactly this reason
  5. Every run appends a `runs` row with start, duration, rows written, and failure count, and the bot can read the database while the collector writes without a lock error

**Plans**: 2/6 plans executed

> **SRC-02 deferred 2026-08-05, blocked external.** Registering a Twitch application requires 2FA on
> the account, 2FA enrolment requires a mobile number, and the verification SMS does not arrive. No
> client id, no secret, no app access token, so the five Twitch fixtures cannot be recorded and
> hand-authoring one stays forbidden. `03-03-PLAN.md` is written, reviewed, and left unexecuted; the
> `Protocol` plus `FETCHERS` registry makes wiring it in one registry line once credentials exist.
> See REQUIREMENTS.md §Sources SRC-02. Twitch has now walled this project off twice — the first was
> the follower endpoint requiring a broadcaster user token.

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Four YouTube fixtures (two recorded, two derived), the `--header` flag, and the `03-UAT.md` scaffold (human-gated). The five Twitch fixtures and the live `view_count` verification are held in its Deferred section.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — Tracer: one creator, one source, `creators.yaml` → YouTube parse → a real SQLite row → a `runs` row → an exit code

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 03-04-PLAN.md — `validate()` names the creator and the field, and the run refuses to start on a bad config
- [ ] 03-06-PLAN.md — Retry decorator wrapping the YouTube call: narrow transient list, fixed backoff, no header parsing (SRC-05)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 03-05-PLAN.md — Failure isolation, the `runs` row a dying run still writes, the bot's read path, and the five UAT proofs
- [ ] 03-03-PLAN.md — **DEFERRED (SRC-02)** — the Twitch source: one module, one registry line, `followers` NULL by design. Do not execute until Twitch credentials exist.

Notes:

- Heaviest phase by requirement count (18 of 45). Expect several plans. Build order within it is dependency-driven: `models.py` + `db.py` first (everything depends on the record shape), then `config.py` and the two API sources, then `collector.py` orchestration.
- **Confirm early, before building the parser:** make one live `GET /helix/videos` call with an app access token to confirm `view_count` is reachable. The followers auth wall is verified HIGH; this endpoint was not separately live-tested. If it also walls off, the Twitch metric needs rethinking on day one, not day five.
- SETTLED, do not re-litigate: Twitch metric is summed recent-VOD views + live status, not followers. YouTube delta is computed on view count, not subscribers (subscriberCount rounds to 3 significant figures above 1k).
- The normalization boundary is the single most important seam in the system. NULL means "this metric does not exist for this source"; 0 means "the platform reported zero." Never `COALESCE(x, 0)` before delta math.
- `metric_date` computed once per run in UTC, so a run slipping past midnight cannot split across two dates.
- WAL mode + `busy_timeout=5000` on every connection, set in the shared `db.py`.
- No retries in the orchestrator — the next day's timer run is the retry. Retries live in the source layer (SRC-05) for transient errors only.
- Manual gate: the author watches a real run pull real API data into the real database.

### Phase 4: Playwright & Sheets

**Goal**: The third source works without an API, and the ops team gets a Sheet they can actually read
**Mode:** mvp
**UI hint**: no
**Owner:** agent
**Depends on**: Phase 3
**Requirements**: SRC-03, SHEET-01, SHEET-02, SHEET-03, SHEET-04, SHEET-05, SHEET-06, SHEET-07
**Success Criteria** (what must be TRUE):

  1. The author opens the real Google Sheet after a real run and sees one Dashboard row per creator with the latest snapshot and its day-over-day delta on views — with subscriber/follower figures visibly labelled coarse
  2. A creator with no prior-day row shows `—` for delta, not a number computed against zero
  3. The author types into the Status column, re-runs the collector, and the typed value is still there afterwards
  4. The History tab gains exactly one row per creator per day and no existing row is rewritten
  5. A TikTok profile page yields follower count, total likes, and video count into the database; a Sheet that has not been shared with the service account fails with a message naming the exact `client_email` to share it with

**Plans**: TBD

Notes:

- **Highest pitfall density in the project** — 9 of 19 identified pitfalls land here. Budget the most slack and the most explicit verification.
- Likely needs `/gsd-plan-phase --research-phase 4`. TikTok's live page structure and selectors are not knowable in advance and will need at least one iteration against saved HTML fixtures.
- Never `.clear()` the Dashboard tab. Write only the DB-owned column range (e.g. `A2:F{n}`) so the human-edited Status column survives. Keep Status last in the column order — this layout is a contract with Phase 5.
- One write call per tab per run. Build the full 2D array in memory first. Cell-by-cell looks fine at two rows and breaks in front of the interviewer.
- Deltas computed in Python from the database, never as Sheet formulas.
- Playwright: Chromium only, headless, sequential contexts (never concurrent), teardown in `finally`. Wait on a specific element, not page load. Raise on selector drift — never return `None` silently.
- Public unauthenticated pages only, respect `robots.txt`. If TikTok needs evasion to load, the source gets dropped — that is the correct outcome, and a better interview answer than a bypass.
- Second on the cut list. If the window is tight, ship API-only and say why.
- Manual gate: the author watches real data reach the real Sheet.

### Phase 5: Apps Script

**Goal**: The Sheet stops being a dump and becomes a two-way surface — it formats itself and talks back to Discord
**Mode:** mvp
**UI hint**: no
**Owner:** human
**Depends on**: Phase 4
**Requirements**: SCRIPT-01, SCRIPT-02, SCRIPT-03, SCRIPT-04
**Success Criteria** (what must be TRUE):

  1. Opening the Sheet shows a custom menu that was not there before
  2. The author edits a Status cell and a Discord message appears within seconds — observed live, not inferred from logs
  3. Day-over-day movement is visually obvious on the Dashboard through conditional formatting, without reading the numbers
  4. A time-driven trigger fires on schedule and its execution is visible in the Apps Script execution log
  5. The author can walk someone through the `onEdit` trigger's event object and the webhook call from memory

**Plans**: TBD

Notes:

- **Entirely human-built — roughly 100 lines typed by hand. The agent does not generate this code.** It is the author's biggest gap and the interviewer's deepest skill, which is exactly why it is not delegated.
- Hard structural dependency on Phase 4: the Dashboard column layout must be final and stable, with Status last, before triggers attach to it.
- The Status-edit → Discord round trip is the single most interesting demo moment in the project. Rehearse it.
- Never cut this phase.

### Phase 6: Discord Bot

**Goal**: Discord becomes the place the numbers show up and the place you ask about them
**Mode:** mvp
**UI hint**: no
**Owner:** mixed
**Depends on**: Phase 3 (database), Phase 5 (webhook proven)
**Requirements**: BOT-01, BOT-02, BOT-03, BOT-04, BOT-05, BOT-06, BOT-07
**Success Criteria** (what must be TRUE):

  1. A daily digest posts itself to the channel on schedule, listing top movers and any failures from that run — with no human triggering it
  2. A creator whose day-over-day delta exceeds ±20% is visibly flagged in that digest
  3. A run that records failures produces its own immediate Discord message, distinct from and earlier than the scheduled digest
  4. `/creator <name>` returns that creator's current numbers and recent trend, and `/status` returns last run time, duration, rows written, and failure count — both answered from the database, in-channel
  5. The bot survives a reboot as its own systemd service, independent of the collector, and the author can explain which intents it requests and why none of them are privileged

**Plans**: TBD

Notes:

- **Mixed ownership.** BOT-07 (bot registration, intents, scopes, invite URL in the Discord Developer Portal) and BOT-06's systemd unit file are human-built. The agent writes the command handlers and digest logic; the author must understand the permission model well enough to defend it.
- The bot is a long-lived process and must not share a lifecycle with the one-shot collector. Separate unit, separate failure domain.
- Slash commands need no privileged intents. Request the minimum.
- Guild-scoped command sync, not global — global propagation delay will bite during a demo.
- Short-lived database connections per command, not a module-level global. The collector is the only writer.
- No blocking calls in the event loop.
- BOT-04 and BOT-05 are first on the cut list. The digest (BOT-01/02/03) is not cuttable — it is half the core value.
- Never cut this phase.
- Manual gate: the author watches a real scheduled digest and a real failure alert land in the real channel.

### Phase 7: Reliability & Docs

**Goal**: The whole loop runs cold, unattended, while someone watches — and a stranger can understand it from the README alone
**Mode:** mvp
**UI hint**: no
**Owner:** mixed
**Depends on**: Phase 6
**Requirements**: OPS-08, OPS-09
**Success Criteria** (what must be TRUE):

  1. A cold-start run — triggered by the timer, not by hand — lands rows in SQLite, updates the Sheet, and posts to Discord while the author tails `journalctl -f` and narrates it
  2. `/status` honestly reports staleness and failures when the run is deliberately broken, rather than reporting success from stale data
  3. The README explains the architecture with a diagram and records why each contested decision was made — including the Twitch follower auth wall and the subscriber-rounding delta choice — and reads correctly to someone who has never seen the repo
  4. The build journal contains what broke, what was decided, and which agent proposals were rejected and why — enough to answer the "how has AI changed the way you build" question truthfully
  5. A dry run on the morning of Thu 6 Aug confirms the Twitch app token is still valid and API quota has not been burned by rehearsal

**Plans**: TBD

Notes:

- Only two requirements, but this is a real day of work and it cannot be folded into Phase 6. Several failure modes — cold start, quota burn from rehearsal itself, stale-token 401, silent sync failure — are dormant during solo development and appear only under observation. This phase is what rehearsal is for.
- No new research needed; this is synthesis and rehearsal of prior work.
- Proactively test the Twitch client-credentials token refresh path. The token lives ~58 days with no refresh token — you just re-request. Do not discover that mechanism during the interview.
- Manual gate: the entire loop, observed, end to end, twice.

## Coverage

All 45 v1 requirements are mapped to exactly one phase. No orphans, no duplicates.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1. Skeleton | OPS-02, OPS-03, OPS-04 | 3 |
| 2. VPS & systemd | RUN-03, RUN-04, OPS-01 | 3 |
| 3. Collector Core & API Sources | CFG-01, CFG-02, CFG-03, SRC-01, SRC-02, SRC-04, SRC-05, DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, RUN-01, RUN-02, RUN-05, OPS-05, OPS-06, OPS-07 | 18 |
| 4. Playwright & Sheets | SRC-03, SHEET-01, SHEET-02, SHEET-03, SHEET-04, SHEET-05, SHEET-06, SHEET-07 | 8 |
| 5. Apps Script | SCRIPT-01, SCRIPT-02, SCRIPT-03, SCRIPT-04 | 4 |
| 6. Discord Bot | BOT-01, BOT-02, BOT-03, BOT-04, BOT-05, BOT-06, BOT-07 | 7 |
| 7. Reliability & Docs | OPS-08, OPS-09 | 2 |
| **Total** | | **45** |

Notes on two assignment calls:

- **OPS-02/03/04 sit in Phase 1** because that is where the gate is built. They are re-enforced at every subsequent phase via the Definition of Green above, not re-owned.
- **OPS-06 (normalisation tests, "for each source") sits in Phase 3** with the two API sources. The TikTok fixture test is added in Phase 4 as part of SRC-03's own work rather than reopening OPS-06.

## Notes on Structure

The research's proposed structure was adopted without deviation, renumbered from 0-6 to 1-7 per GSD convention. It matches PROJECT.md's own day-by-day plan and the author's stated cut order, and requirement coverage did not force a change.

Every phase is annotated `**UI hint**: no`. "Dashboard" here is a Google Sheets tab, not a frontend — PROJECT.md explicitly places a web UI out of scope. `/gsd-ui-phase` should not be suggested for any phase in this roadmap.

The annotation is load-bearing, not decorative. The UI safety gate detects a frontend by sniffing the phase section for the standalone words `UI`, `interface`, `frontend`, `component`, `layout`, `page`, `screen`, `view`, `form`, `dashboard`, and `widget`. Four phases tripped it on ordinary prose: Phase 1 on "package layout", Phase 3 on "view count", Phase 4 on the Sheets "Dashboard" tab plus a TikTok profile "page" plus the column "layout", and Phase 5 on the same two. Each was a false positive, and each blocked planning until `--skip-ui` was passed by hand. `**UI hint**: yes|no` is the detector's own authoritative override — it short-circuits the sniff and strips its own line first, so the bare word `UI` inside it cannot self-trigger. Do not remove these lines to tidy the metadata block; the gate will start blocking again on the next wording change.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

Roughly one phase per day across Thu 30 Jul – Wed 5 Aug 2026. Interview Thu 6 Aug.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Skeleton | 3/3 | Complete    | 2026-07-30 |
| 2. VPS & systemd | 3/3 | Complete    | 2026-08-04 |
| 3. Collector Core & API Sources | 2/6 | In Progress|  |
| 4. Playwright & Sheets | 0/TBD | Not started | - |
| 5. Apps Script | 0/TBD | Not started | - |
| 6. Discord Bot | 0/TBD | Not started | - |
| 7. Reliability & Docs | 0/TBD | Not started | - |

---
*Roadmap created: 2026-07-29*
