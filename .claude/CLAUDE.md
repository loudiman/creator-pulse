# CreatorPulse — Hard Rules

<!-- Hand-written. Lives above the GSD markers so regeneration cannot strip it. -->

## Do not generate these

Three areas are **human-built**. Do not write them, do not "help" by drafting them, do not
generate them into a scratch file for the author to copy:

1. **VPS provisioning and systemd** — SSH config, non-root user, UFW rules, `.service` and
   `.timer` unit files. You may write Python the units invoke; you may not write the units.
2. ~~**The entire Apps Script layer** — `onOpen`, `onEdit`, time-driven triggers, conditional
   formatting. Roughly 100 lines, typed by hand.~~ — **AMENDED 2026-08-06, see below.**
3. **Discord Developer Portal setup** — bot registration, intents, scopes, invite URL. You may
   write command handlers; the author owns the permission model.

If asked to produce one of these, say no and explain which phase owns it.

### Amendment 2026-08-06 — rule 2 relaxed to `mixed`

With roughly ten hours to the interview and Phases 5, 6, and 7 all outstanding, the author
reclassified Phase 5 from `human` to `mixed`. **The agent now writes the Apps Script**; the author
reads it line by line with a walkthrough, pastes it, and must still be able to explain it cold.
The reason is the clock, and it is recorded as the clock rather than dressed up as a design
improvement.

The control that replaces hand-typing: ROADMAP criterion 5 ("the author can walk someone through
the `onEdit` trigger's event object and the webhook call from memory") stands unchanged, and closes
only when the author writes that explanation into `05-UAT.md` in their own words, unaided.

**Rules 1 and 3 are untouched and still bind in full.** This is one scoped, dated exception, not a
general relaxation. See `.planning/phases/05-apps-script/05-CONTEXT.md` D-01 through D-04.

## Merge rule

Nothing enters the repo that the author cannot explain out loud. This outranks every other
consideration, including speed. Prefer the version that is easy to defend over the version that
is clever.

Corollaries:
- No new dependencies without asking. Research already closed all 8 open gaps against stdlib —
  no tenacity, no pydantic, no structlog, no httpx, no `google-api-python-client`.
- No Docker, no web UI, no auth, no Postgres, no queues.

## Settled decisions — do not re-litigate

- **Twitch follower count is unobtainable.** `GET /helix/channels/followers` requires a *user*
  access token from the broadcaster or a moderator; an app access token is rejected even for the
  total-only case. There is no OAuth relationship with tracked creators. This is an auth wall, not
  a scraping problem, and **not something to work around**. The Twitch metric is summed recent-VOD
  view count (`GET /helix/videos`) plus live status (`GET /helix/streams`). The `followers` column
  is NULL on every Twitch row. *(Note: the generated Technology Stack section below lost this
  caveat — its "What NOT to Use" row for `helix/channels/followers` is misleading. This block is
  authoritative.)*
- **Day-over-day delta is computed on view count, not subscribers.** YouTube rounds
  `subscriberCount` to 3 significant figures above 1k subs, so subscriber deltas are rounding
  noise. Subscriber counts are still displayed, labelled coarse.
- **NULL vs 0.** NULL means "this platform does not expose this metric." 0 means "the platform
  reported zero." Never `COALESCE(x, 0)` before delta math. This is a correctness rule, not a
  style preference.

## Testing

Fixtures only — no live network calls inside the test suite. Green means `ruff check .` **and**
`mypy src/` **and** `pytest` — never "it ran without crashing."

**Do not weaken a test to reach green.** If a test fails, the code is wrong until proven
otherwise. Any test-file change during a Verify step is suspect unless the author asked for it.

## Ethics

Public, unauthenticated sources only. Respect `robots.txt`. Never build detection evasion —
no stealth plugins, no fingerprint spoofing, no CAPTCHA solving, no proxy rotation to dodge
blocks. If a source cannot be read from public pages without evasion, the correct outcome is
dropping that source.

---

<!-- GSD:project-start source:PROJECT.md -->

## Project

**CreatorPulse**

A daily creator-metrics collector that runs unattended on a rented Linux VPS. Every morning a systemd timer fires a Python job that pulls public stats for a configured list of social media creators, writes them with full history into SQLite, syncs a Google Sheet view, and posts a summary to Discord. Nobody touches it.

It is intentionally small. It is a portfolio artifact for a Content Lab automation role — a working version of the interviewer's own internal-tooling stack, built to be explained out loud rather than to look impressive.

**Core Value:** **The unattended daily run.** A timer fires, real numbers land in the database, the Sheet reflects them, and Discord says so — with no human in the loop. If the LLM digest, the extra slash commands, and even the scraper all get cut, that loop must still work.

### Constraints

- **Merge rule**: Nothing enters the repo that the author cannot explain out loud — this outranks every other consideration, including speed
- **Ownership**: VPS/systemd config, Apps Script, and Discord Developer Portal setup are human-built — the agent must not generate them
- **Timeline**: Ship by Wed 5 Aug 2026; interview Thu 6 Aug — seven days, part-time
- **Tech stack**: Python 3.12, SQLite, `gspread` + service account, `discord.py`, Playwright, `pytest`, `ruff`, `mypy` — no new dependencies without asking
- **Budget**: Free tiers only — no paid API plans
- **Deployment**: One rented Linux VPS, systemd timer — no Docker, no orchestration, no cloud services beyond the Sheets API
- **Secrets**: Env file, `chmod 600`, loaded via systemd `EnvironmentFile` — `.gitignore` written before the first commit, never committed
- **Testing**: Fixtures only — no live network calls inside the test suite, which would be slow, flaky, and get the scraper blocked
- **Ethics/legal**: Public, unauthenticated sources only; respect `robots.txt`; never build detection evasion

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Recommended Stack

### Core Technologies (locked — confirmed, not re-decided)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Runtime | Locked. Confirmed current, well past EOL risk (3.12 supported into 2028). |
| sqlite3 (stdlib) | bundled w/ 3.12 | Persistence | Locked. One file, zero setup, real SQL, `UNIQUE(creator_id, source, metric_date)` gives idempotency by construction. |
| gspread | **6.2.1** | Google Sheets writes | Locked. `service_account()` + batch methods (`batch_update`, `worksheet.update` with a single range) satisfy "no cell-by-cell" requirement natively. |
| discord.py | **2.7.1** | Discord bot | Locked. Actively maintained (release Mar 2026), 3.8+, native slash-command support via `app_commands`. |
| Playwright (Python) | **1.61.0** | TikTok scrape | Locked. See install-footprint section below for the VPS-sizing gap. |
| PyYAML | **6.0.3** | `creators.yaml` parsing | Locked. Use `yaml.safe_load` only — never `yaml.load` unqualified. |
| pytest | **9.1.1** | Tests | Locked. |
| ruff | **0.16.0** | Lint + format | Locked. Can replace flake8/isort/black in one tool — nothing else needed. |
| mypy | **2.3.0** | Type checking | Locked. |

### Supporting Libraries (the 8 gaps — decided)

| Library | Version | Purpose | Decision |
|---------|---------|---------|----------|
| requests | **2.34.2** | HTTP client for YouTube + Twitch calls | **Use requests, not httpx.** See rationale below. |
| *(no new dep)* | — | Retry/backoff | **Hand-roll a ~15-line retry decorator using stdlib `time.sleep`.** Do not add tenacity. |
| *(no new dep)* | — | `creators.yaml` validation | **stdlib `dataclasses` + a manual `validate()` function.** Do not add pydantic. |
| *(no new dep)* | — | Structured logging to journald | **stdlib `logging` to stdout**, formatted; systemd captures unit stdout into the journal automatically. Do not add structlog or `systemd-python`. |
| *(already transitive)* | google-auth **2.56.2** | Sheets auth | Already pulled in by gspread — do not add `google-api-python-client`. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | lint + format | `ruff check .` and `ruff format .`; one config block in `pyproject.toml`. |
| mypy | static types | Run `mypy src/` with `--strict` on new code if time allows; loosen only if the 7-day clock forces it. |
| pytest | tests, fixtures only | No live network calls in the suite (hard constraint) — record fixtures once by hand or with a throwaway script, commit the fixture files. |

## Installation

# Core (already locked)

# The one new gap-filling dependency

# Dev dependencies

## The 8 gaps, decided

### 1. HTTP client: requests, not httpx

- This is a synchronous, one-shot batch job with exactly two REST call sites (YouTube, Twitch). httpx's entire value proposition — async support, HTTP/2, one client for sync+async — buys nothing here; there is no concurrency in this job.
- **requests is already in the dependency tree.** Verified: `gspread` depends on `google-auth-oauthlib`, which depends on `requests-oauthlib`, which depends on `requests`. gspread's own `http_client.py` imports `requests.Session` and `google.auth.transport.requests.AuthorizedSession` directly. Picking requests for the app's own YouTube/Twitch calls adds zero net-new packages to what gspread already resolves — it's the same HTTP stack Sheets already uses.
- httpx (0.28.1) last released Dec 2024 — stable but not moving; requests (2.34.2) shipped May 2026 and is the more actively-touched project right now. Either is "maintained," but requests is the more boring, more proven choice for this shape of job.
- Confidence: HIGH (version via PyPI JSON API; dependency-chain claim verified against gspread's own source and PyPI metadata).

### 2. Retry/backoff: hand-roll it, skip tenacity

- tenacity (**9.1.4**, actively maintained) is a fine library, but 3 call sites in a 7-day part-time build don't justify a dependency whose main value is a rich DSL (custom wait strategies, jitter, stop conditions, retry-on-exception-type combinators) this project won't use beyond "retry N times with exponential backoff."
- A ~15-20 line function is easier to explain line-by-line in an interview than "I added a library for this" — and this project's whole thesis is judgment about when a tool is warranted (see the API-vs-Playwright split). The same judgment applies here.
- Concretely: `for attempt in range(1, max_attempts+1): try: return fn(); except (requests.RequestException, PlaywrightError): if attempt == max_attempts: raise; time.sleep(backoff * attempt); log the retry`.
- Confidence: HIGH on tenacity's version/maintenance; MEDIUM-subjective on the "not worth it" call (a defensible reasonable person could pick tenacity here — flagging so the user can override).

### 3. Config validation: dataclasses + manual validation, skip pydantic

- pydantic v2 (**2.13.4**) is excellent, but its value is proportional to schema complexity (nested unions, coercion, auto-generated error messages for external/untrusted input). `creators.yaml` is authored by the operator, has a handful of flat fields per creator (name, platform, channel id/handle), and fails loudly at startup either way.
- This is an internal, single-operator config file, not user-facing input — the bar for validation ergonomics is lower than pydantic is built for.
- If `creators.yaml` grows nested per-source overrides or optional fields multiply significantly in a later milestone, revisit — that's the trigger to reconsider, not scope creep now.
- Confidence: HIGH on pydantic's version; this is a judgment call the user should feel free to override (explicitly called out as required by the brief).

### 4. Structured logging to journald: stdlib logging to stdout, skip structlog

- When the collector runs as a systemd service (fired by the timer), systemd automatically captures the unit's stdout/stderr into the journal, tagged with the unit's `SYSLOG_IDENTIFIER` — no journal-specific handler is required to get useful `journalctl -u creatorpulse.service` output.
- structlog's value (structured key=value or JSON fields, contextvars binding) is aimed at services with many concurrent request contexts. A once-daily one-shot job with a linear run has no context-juggling problem to solve; format strings with `%(message)s` plus an occasional inline `f"upserted {n} rows for {creator}"` are entirely sufficient and far easier to defend as "I didn't need more than this."
- If proper journal *priority* mapping (so `journalctl -p err` filters correctly) turns out to matter in practice, the incremental upgrade is `systemd.journal.JournalHandler` from the `systemd-python` package (needs `libsystemd-dev` on the VPS to build) — worth asking about if it comes up, not worth defaulting to.
- Confidence: MEDIUM (best-practice synthesis from several blog/community sources, not a single canonical doc; the stdout-capture behavior of systemd units itself is well-established systemd behavior, HIGH confidence).

### 5. Playwright browser footprint: chromium only, `--only-shell` if truly headless-only

- Chromium browser alone is ~161 MB; add `--only-shell` to install just the headless shell (~100 MB) if you never need a headed run for debugging — but keep the full Chromium build if you'll ever want to run headed locally to debug selector breakage (recommended for a scraper you'll be hand-maintaining).
- On the VPS: run headless (`p.chromium.launch(headless=True)`), no extra flags needed for a small single-instance job. Budget ~1-2 GB RAM headroom for the one Chromium instance; a single sequential scrape (not concurrent tabs) keeps this well within a small VPS's means.
- Hard constraint restated for clarity: no stealth/evasion plugins, no fingerprint spoofing, no CAPTCHA solving. If TikTok's public profile pages start requiring any of that to load, the correct move is dropping TikTok as a source, not adding evasion — this is explicit in PROJECT.md's cut order too.
- Confidence: MEDIUM (install-size figures from community/blog sources cross-referenced against playwright.dev's own docs on browser installation flags — the flag names and existence are HIGH confidence, the exact MB figures are approximate and version-dependent).

### 6. gspread auth: gspread's own path is sufficient, no google-api-python-client

- Verified: gspread 6.2.1 declares `google-auth>=1.12.0` and `google-auth-oauthlib>=0.4.1` as dependencies and gspread's `HTTPClient` directly builds a `google.auth.transport.requests.AuthorizedSession`. This is gspread wrapping the Sheets v4 REST API itself — `google-api-python-client` (the generic Google API discovery-doc client) is a different, heavier way to call the same API and isn't needed alongside a library that already wraps it.
- `google-auth` (**2.56.2**) arrives as a transitive dependency automatically; no separate `pip install google-auth` line is needed, though pinning it explicitly in `requirements.txt` is reasonable for reproducibility.
- Confidence: HIGH (verified directly against gspread's source and PyPI dependency metadata).

### 7. YouTube Data API v3: exact endpoint, auth, quota

- **Endpoint:** `GET https://www.googleapis.com/youtube/v3/channels`
- **Params:** `part=statistics` (add `part=snippet` if display name/thumbnail wanted too — parts don't add quota cost), and either `id=CHANNEL_ID` or **`forHandle=@handlename`** (with or without the `@`) to resolve directly by a creator's public @handle — no separate lookup call needed.
- **Auth:** **API key alone is sufficient.** No OAuth needed for public channel statistics (subscriberCount, viewCount, videoCount) — OAuth is only required for the `auditDetails` part, which this project has no use for.
- **Quota:** 1 unit per call, flat, regardless of which parts are requested. Default project quota is 10,000 units/day — for a creator list capped at a handful of channels run once daily, this is nowhere close to a constraint (a daily run of even 50 channels costs 50 units).
- Confidence: HIGH (verified directly against developers.google.com/youtube/v3/docs/channels/list).

### 8. Twitch Helix: app access token flow, and the follower-count endpoint problem (read this one)

- `POST https://id.twitch.tv/oauth2/token` with `client_id`, `client_secret`, `grant_type=client_credentials` returns an **app access token**.
- Lifetime: ~5,000,000 seconds (~58 days). No refresh token is issued or needed — on expiry, just repeat the POST for a new one. For a daily job, the simplest approach is requesting a fresh app token on every run (one extra cheap call) rather than persisting/tracking expiry.
- App access tokens only reach non-sensitive, public, app-level data — they cannot carry user scopes.
- `GET /helix/streams?user_login=...` — live status + `viewer_count` while live (returns nothing when the channel is offline — this is a point-in-time snapshot, not a persistent metric).
- `GET /helix/users?login=...` — profile data (display name, profile image, account creation date). Its `view_count` field has been deprecated since April 2022 and always returns `0` — do not treat it as a real metric.
- `GET /helix/channels?broadcaster_id=...` — current game/category, stream title, tags. No numeric metric.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| requests | httpx | If the collector ever grows a concurrent/async fan-out across many creators — not the case here (one-shot, ~10s of calls/day). |
| hand-rolled retry | tenacity | If retry logic needs to grow past simple exponential backoff (e.g. respecting `Retry-After` headers, jittered backoff across many more call sites) — revisit if source count or call sites grow materially. |
| dataclasses + manual validation | pydantic | If `creators.yaml` schema grows nested/optional-heavy, or if config errors need to be surfaced to a non-technical editor with friendly messages. |
| stdlib logging to stdout | `systemd-python` JournalHandler | If `journalctl -p <priority>` filtering by level becomes something you actually rely on day-to-day, or you want structured KEY=VALUE journal fields queryable via `journalctl -o json`. |
| chromium only | full `playwright install` (all 3 engines) | Never for this project — TikTok's public profile pages render fine under Chromium; no reason to carry Firefox/WebKit. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Twitch `helix/users/follows` | Fully removed/shut down since Sept 2023, will 404/410 | `helix/channels/followers` (but read the auth caveat above — it may not solve the actual need) |
| Twitch `view_count` field on Get Users | Deprecated since April 2022, always returns `0` — silently wrong data if trusted | `viewer_count` from Get Streams (live-only), or drop the metric |
| `yaml.load()` unqualified | Arbitrary code execution risk from untrusted YAML (not a live risk here since the file is self-authored, but it's a one-word fix and a bad habit to model in a portfolio piece) | `yaml.safe_load()` |
| Playwright stealth/evasion plugins (`playwright-stealth`, fingerprint spoofing, CAPTCHA solvers) | Explicitly out of scope per hard constraint; also generally an arms race that breaks on every Playwright/browser update | If a public page requires this to load, drop that source |
| `google-api-python-client` alongside gspread | Redundant — gspread already wraps the same REST API using google-auth under the hood | `gspread.service_account()` |
| Cron | No structured logs, doesn't survive certain reboot/dependency-ordering edge cases as cleanly, weaker interview answer | systemd timer (locked) |

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| Python 3.12 | gspread 6.2.1, discord.py 2.7.1, playwright 1.61.0, PyYAML 6.0.3, requests 2.34.2, pytest 9.1.1, ruff 0.16.0, mypy 2.3.0 | All current releases support 3.12+; no known conflicts as of this research. |
| gspread 6.2.1 | google-auth 2.56.2, google-auth-oauthlib (pulls requests-oauthlib → requests) | Installed automatically via pip's dependency resolution — no manual pinning required, though pinning `google-auth` explicitly aids reproducibility. |
| discord.py 2.7.1 | Python >= 3.8 | Runs as a separate long-lived systemd service per PROJECT.md — confirm it does not share a virtualenv/process lifecycle with the one-shot collector (already decided in PROJECT.md, just noting no version conflict exists to worry about). |

## Sources

- PyPI JSON API (`https://pypi.org/pypi/<package>/json`), queried directly for each package — HIGH confidence, authoritative registry data: httpx, requests, tenacity, pydantic, gspread, google-auth, google-api-python-client, discord.py, ruff, mypy, pytest, PyYAML, python-dotenv, playwright
- `developers.google.com/youtube/v3/docs/channels/list` — direct fetch, verified auth type, quota cost, `forHandle` param — HIGH
- `dev.twitch.tv/docs/api/reference/` (Get Channel Followers, Get Streams, Get Users sections) — direct fetch, verified auth requirements — HIGH
- `dev.twitch.tv/docs/authentication/getting-tokens-oauth/` — direct fetch, client-credentials flow, token lifetime — HIGH
- Twitch Developer Forums (`discuss.dev.twitch.com`), community `view_count` deprecation thread — MEDIUM, cross-checked against forum + GitHub issue reports
- gspread source (`github.com/burnash/gspread/blob/master/gspread/http_client.py`) — direct fetch, confirmed `requests`/`AuthorizedSession` usage — HIGH
- General web search synthesis (playwright.dev browser install docs, systemd/journald logging best-practice blog posts) — MEDIUM, several independent sources agreeing but no single canonical doc fetched verbatim

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
