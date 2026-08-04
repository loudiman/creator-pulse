# Phase 3: Collector Core & API Sources - Research

**Researched:** 2026-08-04
**Domain:** SQLite persistence + two REST API integrations (YouTube Data API v3, Twitch Helix) behind a normalized record shape, orchestrated by a failure-isolating collector loop
**Confidence:** HIGH on schema/upsert/WAL mechanics and YouTube endpoint shape (verified live against this repo's own `.venv` and official docs). MEDIUM on two Twitch specifics flagged below — one of them (`period` filtering on Get Videos) is a **real, multi-year-old documented bug**, not a hypothetical.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

19 decisions (D-01 through D-19) are locked in `03-CONTEXT.md` and are **not re-litigated here**. Summary for quick reference (full text is in CONTEXT.md, which is binding):

- **D-01/D-02:** `MetricRecord` columns are `creator_id, source, metric_date, followers, views, likes, video_count, is_live, collected_at`. `engagement_rate` is removed.
- **D-03:** Two absence rules — a *documented* optional field (e.g. `hiddenSubscriberCount`) maps to NULL and the run continues; an *undocumented* absence (API shape changed) raises and counts as a failure.
- **D-04:** `connect(create: bool)`. Collector calls with `create=True` (runs `CREATE TABLE IF NOT EXISTS`). Bot calls with `create=False` and raises a named error if `metrics` is absent. WAL + `busy_timeout=5000` on every connection. No migration framework, no `schema_version` table.
- **D-05/D-06/D-07/D-08:** Twitch `views` = summed `view_count` from one call to `GET /helix/videos` with `user_id`, `type=archive`, `period=month`, `first=100`, one page. `video_count` is NULL for Twitch (lifetime count only; window VOD count goes to the log line, not the DB). Empty window → `views=0`, not NULL.
- **D-09:** Two lists — known-platforms (`youtube`, `twitch`, `tiktok`) vs. the fetcher registry (only implemented sources). Unknown key fails validation; known-but-unregistered key (`tiktok` today) logs one skip line, run continues.
- **D-10:** A skip is neither a row nor a failure — no `skipped_count` column.
- **D-11/D-12:** `validate()` walks the whole file, collects every problem, prints one line per problem naming creator+field, exits non-zero before any network call. Strict rule set: `creators` non-empty list; `id`, `name`, non-empty `sources` map per entry; `id` matches a slug pattern and is unique across the file; each source key is in the known-platforms list; every identifier is non-empty after `.strip()`.
- **D-13/D-14:** Retry list is narrow — `requests.Timeout`, `requests.ConnectionError`, HTTP 429, HTTP 5xx. 3 attempts, fixed sleep 2s then 4s. No `Retry-After`/`Ratelimit-Reset` parsing. Lives in the source layer, never the orchestrator.
- **D-15:** One `try`/`except` boundary per **(creator, source)** pair. No cross-pair state, no short-circuit.
- **D-16:** Once the DB is open, `try`/`finally` always writes the `runs` row, then the original exception re-raises.
- **D-17:** Twitch app access token minted fresh every run. No cache, no expiry tracking.
- **D-18:** Each source must **raise** on an empty result set (`items: []` / `data: []`) — an empty result means "no such channel," which is not the same as D-03's documented-absent-metric case and must not become a row of NULLs.
- **D-19:** `03-UAT.md` follows the `02-UAT.md` pattern — one pasted command output per success criterion, five entries.

### Claude's Discretion

- `models.py` vs. folding the record into `config.py` (lean `models.py` — matches ARCHITECTURE.md, and it's the shared import surface both processes touch).
- DDL column order; whether `collected_at` is per-row or per-run (ARCHITECTURE.md puts it on the record — per-row).
- Exact validation exit code and error-line wording, provided creator+field are named.
- Wording/level of the skip line, retry line, VOD-count line — INFO level, visible in a normal `journalctl` read.
- Retry decorator vs. plain helper function, and where it lives.
- `is_live` typed `int | None` or `bool | None` in Python (column is INTEGER).
- Identifier resolution: no cache. YouTube needs zero resolution calls (`forHandle` does it in the same 1-unit call). Twitch needs `GET /helix/users?login=` for the numeric `user_id` that Get Videos/Get Streams require. Per-run budget: 3 YouTube calls, 10 Twitch calls (incl. one token mint).
- Test file/fixture case names within `tests/fixtures/{source}/{case}.json`.

### Deferred Ideas (OUT OF SCOPE for this phase)

- `engagement_rate` — returns with the first source that can compute numerator+denominator (guarded `ALTER TABLE ADD COLUMN`).
- `skipped_count` on `runs` — revisit only if `/status` (Phase 6) needs it.
- `Retry-After`/`Ratelimit-Reset` handling — the trigger to adopt `tenacity`, not applicable at 6 calls/day.
- Source-wide short-circuit logic — revisit only if creator count grows far past three.
- TikTok source (SRC-03) — Phase 4. `creators.yaml`'s `tiktok` entries stay as-is per D-09.
- Delta computation — Phase 4, in Python, from the database.
- Rolling averages, historical backfill, `journalctl` priority mapping — all V2, not this milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CFG-01 | Add a creator via `creators.yaml`, no code change | D-09's two-list design; registry pattern in Architecture Patterns §1 |
| CFG-02 | Each entry declares platform + identifier | Already satisfied by existing `Creator` dataclass; `validate()` (D-11/D-12) enforces shape |
| CFG-03 | Invalid/incomplete config fails at startup naming creator+field | `validate()` design below; D-11/D-12 rule set |
| SRC-01 | YouTube returns subscribers, views, video count via API key | Verified endpoint/params/quota in Code Examples §YouTube |
| SRC-02 | Twitch returns summed VOD views + live status via app token | Verified (with caveats) endpoint/params in Code Examples §Twitch; **period-filter bug flagged in Pitfall T1** |
| SRC-04 | Normalized record shape; absent metric is NULL never 0 | Architecture Patterns §2 (amended `MetricRecord`); D-01–D-03 |
| SRC-05 | Transient-error retry with backoff before counted as failed | Code Examples §Retry decorator; D-13/D-14 |
| DATA-01 | One row per creator/source/date | DDL below (unchanged shape from ARCHITECTURE.md, amended columns) |
| DATA-02 | Re-run same day updates, doesn't duplicate | `ON CONFLICT ... DO UPDATE` upsert, verified against installed sqlite3 3.49.1 |
| DATA-03 | Every run writes `runs` row: start, duration, rows written, failures | `write_run_row()` in Code Examples; D-16's try/finally |
| DATA-04 | Previous days' rows never overwritten | Guaranteed by `UNIQUE(creator_id, source, metric_date)` conflict target — different `metric_date` never conflicts |
| DATA-05 | Collector (writer) and bot (reader) concurrent, no lock errors | WAL + `busy_timeout=5000`, verified live against installed sqlite3; `connect(create=False)` URI pattern verified live |
| RUN-01 | One creator/source failing doesn't abort the run | Architecture Patterns §3 (D-15's per-pair boundary) |
| RUN-02 | Failure logged with creator, source, cause; counted in `runs` row | Same pattern, `failure_count` tally |
| RUN-05 | `metric_date` computed once per run in UTC | Collector orchestration example — one `date.today()` equivalent computed before the loop, threaded through |
| OPS-05 | Idempotency test — run twice, row count unchanged | Validation Architecture §Test Map |
| OPS-06 | Normalization test — fixture in, record out, per source | Validation Architecture §Test Map; `unittest.mock` pattern verified live |
| OPS-07 | Failure isolation test — one source raises, run completes, failure logged | Validation Architecture §Test Map |
</phase_requirements>

## Summary

This phase has three real unknowns, and I ran all three down rather than assuming: (1) whether YouTube's `hiddenSubscriberCount` case returns `subscriberCount` as a literal `"0"` or omits the field, (2) whether Twitch's Get Videos endpoint honors an app access token and its `period` parameter, and (3) the exact stdlib SQLite pattern for `connect(create=False)`. Two of these confirm the locked decisions are correctly grounded. **The third — `period` on Get Videos — is a genuine, multi-year, Twitch-acknowledged-in-forums bug: the parameter is reported ignored, returning all videos regardless of window.** This does not overturn D-05/D-07/D-08 (they're locked), but it changes what those decisions actually produce in practice: the "one month window" is likely *not* enforced by the API at all, and the real bound on `views` is whatever Twitch's VOD retention already limits it to (7/14/60 days depending on account tier) — which D-05's own caveat already anticipated for a different reason. The planner should add the live verification call (already flagged in ROADMAP.md and STATE.md) as literally the first task in this phase, and it should check `period` behavior specifically, not just token/field reachability.

Everything else is comparatively mechanical: `sqlite3.connect("file:...?mode=rw", uri=True)` on a missing file raises `OperationalError: unable to open database file` — verified live in this repo's own venv, which is exactly the "named error" D-04 asks the bot side to raise on top of. The `ON CONFLICT` upsert syntax works as documented against the installed SQLite 3.49.1 (well past the 3.24.0 minimum). `unittest.mock.Mock(spec=requests.Response)` is sufficient to fake HTTP responses for OPS-06 with zero new dependencies.

**Primary recommendation:** Build `models.py` + `db.py` first exactly as ARCHITECTURE.md's Build Order prescribes, with D-01/D-02/D-04's amendments applied to the DDL and `MetricRecord` from the first line written — don't build the unamended version and patch it. Make the live Twitch verification call (token mint → Get Videos, no `period`, then with `period=month`, diff the two result sets) before writing `sources/twitch.py`'s parser, and record what you find in the build journal regardless of outcome — it is a defensible, checkable claim either way.

## Architectural Responsibility Map

This project has no browser/frontend/CDN tiers — it is a single-process, one-shot backend batch job. The relevant "tiers" are internal module boundaries, not deployment tiers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Record shape definition | `models.py` | — | Both processes (collector, bot) import it; must have zero source-specific or DB-specific logic |
| Schema DDL, connection factory, upsert, `runs` writer | `db.py` | — | Only module that touches SQL; owns WAL/`busy_timeout`/`create` flag |
| Config parsing (existing) | `config.py` | — | Already built (Phase 1) — parse-only |
| Config validation (new, this phase) | `config.py` | `cli.py` (calls it, decides exit code) | D-11/D-12 layer on top of the existing parse without changing its signature |
| HTTP fetch + retry | `sources/youtube.py`, `sources/twitch.py` | — | Retry lives in the source layer per D-13, never the orchestrator |
| Response → `MetricRecord` normalization | `sources/*` | — | The NULL-vs-0-vs-raise boundary (D-03, D-18) is enforced here, once per source |
| Fetcher registry / `Protocol` | `sources/__init__.py` | `collector.py` (consumes it) | D-09's known-platforms vs. registered-fetchers split lives here |
| Per-(creator,source) failure isolation, `metric_date` computed once, `runs` row write | `collector.py` | — | Orchestration only — no HTTP knowledge, no parsing knowledge (Anti-Pattern 1 in ARCHITECTURE.md) |
| CLI wiring | `cli.py` | — | Replaces the `logger.warning(...)` seam at `cli.py:30`; argument surface unchanged |

## Standard Stack

No new dependencies this phase. Every library below is already locked (Phase 1/2) and verified installed in this repo's `.venv`.

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.10 | Runtime | `[VERIFIED: local .venv]` — matches `pyproject.toml`'s `>=3.12,<3.13` pin |
| sqlite3 (stdlib) | 3.49.1 (bundled) | Persistence | `[VERIFIED: local .venv]` — well past the 3.24.0 minimum for `ON CONFLICT` upsert syntax |
| requests | 2.34.2 | HTTP client for YouTube + Twitch | `[VERIFIED: local .venv]` — already transitive via gspread (STACK.md §1), used directly here for the app's own two call sites |
| PyYAML | 6.0.3 | `creators.yaml` parsing (existing) | `[VERIFIED: local .venv]` — `yaml.safe_load` only, already in use |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.mock` (stdlib) | bundled | Fake `requests.Response` objects for OPS-06 | Verified live this session — `Mock(spec=requests.Response)` with `.json.return_value` / `.status_code` / `.raise_for_status.return_value` covers every fixture-in/record-out test without a new dependency |
| `dataclasses` (stdlib) | bundled | `MetricRecord`, `Creator` (existing) | `@dataclass(frozen=True, slots=True)`, matching the existing `Creator` shape |
| `time.sleep` (stdlib) | bundled | Fixed-backoff retry decorator | D-13/D-14's 2s-then-4s fixed sleep, no `tenacity` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled retry decorator | `tenacity` | Rejected by D-13/D-14 — revisit only if header-aware backoff becomes necessary |
| `unittest.mock` for fixture tests | `responses` / `requests-mock` libraries | Both are reasonable, neither is installed, and the hard constraint is zero new dependencies — `unittest.mock` alone is sufficient at this call-site count |
| stdlib `dataclasses` for `MetricRecord` | `pydantic` | Rejected by STACK.md gap 3 for the same reason as `Creator` — internal, single-operator, flat shape |

**Installation:** none — nothing new to install this phase.

**Version verification:** confirmed live against this repo's `.venv` (see Sources) rather than PyPI metadata alone, since the packages are already pinned and installed — this is the more authoritative check for "what will actually run."

## Package Legitimacy Audit

**No new external packages are introduced in this phase.** Every library used (`requests`, `PyYAML`, stdlib `sqlite3`/`dataclasses`/`unittest.mock`/`time`) was already audited and locked in Phase 1/STACK.md and is confirmed installed and importable in the project's own `.venv` (see Standard Stack table above — each entry is `[VERIFIED: local .venv]`, the strongest tier available: the package isn't just claimed to exist on the registry, it is the exact pinned artifact already resolved into this project's environment).

**Packages removed due to [SLOP] verdict:** none — no new packages proposed.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
systemd timer fires (Phase 2, unchanged)
        │
        ▼
cli.py "collect" ──► config.validate() ──► exit non-zero, name creator+field
        │                                   (before any network call, D-11)
        │ (validation passes)
        ▼
config.load_creators() ──► list[Creator]
        │
        ▼
collector.run()
    │
    ├─ metric_date = utcnow().date()   ◄── computed ONCE, threaded through (RUN-05)
    │
    ├─ db.connect(db_path, create=True)  ── WAL + busy_timeout=5000 (D-04)
    │       │
    │       ▼ (try/finally wraps everything below — D-16)
    │
    ├─ for creator in creators:
    │     for source_name, identifier in creator.sources.items():
    │         │
    │         ├─ source_name not in KNOWN_PLATFORMS?  ──► validate() already caught this
    │         ├─ source_name not in FETCHER_REGISTRY?  ──► log skip line, continue (D-09/D-10)
    │         │
    │         └─ try:
    │                fetch = FETCHER_REGISTRY[source_name]      # sources/__init__.py
    │                record = fetch(identifier, metric_date)     # sources/youtube.py | twitch.py
    │                    │
    │                    ├─ HTTP call (retry decorator wraps this — D-13/D-14, source layer only)
    │                    ├─ empty result set (items:[] / data:[])? ──► raise (D-18)
    │                    ├─ documented-absent field? ──► None in that MetricRecord slot (D-03 rule 1)
    │                    └─ undocumented-absent field? ──► raise (D-03 rule 2)
    │                │
    │                db.upsert_metric(conn, record)   # ON CONFLICT(creator_id,source,metric_date)
    │                rows_written += 1
    │            except Exception:
    │                log.error("fetch failed creator=%s source=%s cause=%s", ...)  # RUN-02
    │                failures += 1                                                  # RUN-01 continues
    │
    └─ finally: db.write_run_row(conn, started, finished, rows_written, failures)  # DATA-03, D-16
              (re-raises original exception if one occurred, after the row is written)
        │
        ▼
cli.py returns exit code (0 if failures==0, else non-zero — Claude's discretion on exact code)

[independent, any time] Phase 6 bot ──► db.connect(db_path, create=False)
                                         raises named error if 'metrics' table absent (D-04)
                                         reads concurrently — WAL lets this proceed without
                                         blocking the writer above (DATA-05)
```

### Recommended Project Structure

```
src/creatorpulse/
├── cli.py              # existing — replaces logger.warning() seam at line 30
├── config.py            # existing load_creators() + NEW validate()
├── models.py             # NEW — MetricRecord (amended: video_count, is_live; no engagement_rate)
├── db.py                 # NEW — connect(create), DDL, upsert_metric, write_run_row
├── sources/
│   ├── __init__.py       # NEW — SourceFetcher Protocol, KNOWN_PLATFORMS, FETCHER_REGISTRY
│   ├── youtube.py         # NEW — fetch(), retry decorator applied here
│   └── twitch.py           # NEW — token mint (D-17), fetch(), retry decorator applied here
└── collector.py           # NEW — orchestration loop, failure isolation, runs row

tests/
├── fixtures/
│   ├── youtube/
│   │   ├── channel_ok.json
│   │   ├── channel_hidden_subs.json      # D-03 rule 1 case
│   │   └── channel_not_found.json         # D-18 case — empty items[]
│   └── twitch/
│       ├── videos_ok.json
│       ├── videos_empty.json               # D-08 case — empty window
│       ├── users_not_found.json             # D-18 case — empty data[]
│       └── streams_live.json / streams_offline.json
├── test_config.py         # existing, extended with validate() cases (CFG-03)
├── test_db.py               # NEW — DDL, upsert idempotency at the SQL layer
├── test_sources.py           # NEW — fixture-in/record-out per source (OPS-06)
└── test_collector.py           # NEW — idempotency (OPS-05), failure isolation (OPS-07), metric_date-once
```

### Pattern 1: Source adapter as `Protocol` + plain function (unchanged from ARCHITECTURE.md)

**What:** `typing.Protocol` for the fetcher contract; each source is a module-level function; a plain dict is the registry.

**When to use:** Exactly this project's shape — two heterogeneous, small adapters sharing only a return type.

```python
# sources/__init__.py
from typing import Protocol
from creatorpulse.models import MetricRecord
from datetime import date

KNOWN_PLATFORMS = frozenset({"youtube", "twitch", "tiktok"})  # D-09 list 1


class SourceFetcher(Protocol):
    def __call__(self, identifier: str, metric_date: date) -> MetricRecord: ...


from creatorpulse.sources import youtube, twitch  # noqa: E402

FETCHER_REGISTRY: dict[str, SourceFetcher] = {  # D-09 list 2 — only implemented sources
    "youtube": youtube.fetch,
    "twitch": twitch.fetch,
}
```

Note the fetcher signature takes `identifier: str` (the raw `creators.yaml` value, e.g. `"@xQcOW"`) and the run's single `metric_date`, not the whole `Creator` object — `creator_id` for the DB row is attached by the caller (`collector.py`), keeping the source module ignorant of the DB schema entirely (source modules never import `db.py`, per ARCHITECTURE.md's Internal Boundaries table).

### Pattern 2: Normalization boundary — amended `MetricRecord`

```python
# models.py
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class MetricRecord:
    creator_id: str
    source: str            # "youtube" | "twitch" | "tiktok"
    metric_date: date
    followers: int | None
    views: int | None
    likes: int | None
    video_count: int | None   # D-01 — lifetime count only; Twitch always NULL (D-06)
    is_live: int | None       # D-01 — 1/0 for Twitch, NULL elsewhere; INTEGER column, `int | None` under strict mypy
    collected_at: datetime
```

`engagement_rate` is gone (D-02). `is_live` typed `int | None`, not `bool | None`: the DDL column is `INTEGER`, and Python's `bool` is a subtype of `int` so `1`/`0` round-trip cleanly through `sqlite3` either way — but keeping the Python type aligned with the column's declared SQL type avoids a silent `bool→INTEGER` implicit-conversion question under `mypy --strict`, and it matches how `followers`/`views`/etc. are already typed. (Claude's discretion per CONTEXT.md — documenting the reasoning since either typing is defensible.)

### Pattern 3: Failure isolation — one boundary per (creator, source)

```python
# collector.py
import logging
from datetime import UTC, datetime

from creatorpulse.config import Creator
from creatorpulse.db import upsert_metric, write_run_row
from creatorpulse.sources import FETCHER_REGISTRY

logger = logging.getLogger("creatorpulse")


def run(conn, creators: list[Creator]) -> tuple[int, int]:
    metric_date = datetime.now(UTC).date()   # RUN-05 — computed ONCE, before the loop
    started_at = datetime.now(UTC)
    rows_written = 0
    failures = 0

    for creator in creators:
        for source_name, identifier in creator.sources.items():
            fetch = FETCHER_REGISTRY.get(source_name)
            if fetch is None:
                logger.info(
                    "skip creator=%s source=%s reason=no_fetcher_registered",
                    creator.id, source_name,
                )
                continue  # D-09/D-10 — not a row, not a failure
            try:
                record = fetch(identifier, metric_date)
            except Exception as exc:
                logger.error(
                    "fetch failed creator=%s source=%s cause=%s",
                    creator.id, source_name, exc,
                )
                failures += 1
                continue  # RUN-01 — remaining (creator, source) pairs still run
            upsert_metric(conn, creator.id, record)
            rows_written += 1

    finished_at = datetime.now(UTC)
    write_run_row(conn, started_at, finished_at, rows_written, failures)  # DATA-03
    return rows_written, failures
```

The `try`/`finally` around the `runs` write (D-16) belongs one layer up, in `cli.py`, wrapping the `connect()` → `run()` → close sequence, so that a raise *inside* `db.connect()` itself (e.g. the bot's `create=False` case) correctly produces no row at all — matching D-16's "a validation failure ... leaves no row" logic extended to a connect-time failure.

### Anti-Patterns to Avoid

- **Retrying in `collector.py`:** ARCHITECTURE.md's Anti-Pattern 1 and D-13 both forbid this — the orchestrator must stay ignorant of per-source error taxonomies (HTTP status codes, `requests` exception types). Retry logic belongs entirely inside `sources/youtube.py` / `sources/twitch.py`.
- **Coalescing NULL to 0 anywhere before the DB write or in the collector:** violates D-03 and the project's hard CLAUDE.md rule. If a metric slot is `None`, it stays `None` all the way into the `sqlite3` parameter binding (which correctly produces SQL `NULL`).
- **A second `try`/`except` layer split by creator and by source separately:** D-15 is explicit that one boundary at the `(creator, source)` pair level gets full isolation; nesting two boundaries is the same protection with more code.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Upsert-on-conflict | A `SELECT` then `UPDATE`-or-`INSERT` branch in Python | SQLite's native `INSERT ... ON CONFLICT(...) DO UPDATE SET ...` | Atomic, race-free even though this project has one writer; verified working against installed sqlite3 3.49.1 |
| Reader/writer coordination | A file lock, a `flock()`, a manual retry-on-`OperationalError` loop | `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000` on every connection | This is exactly what WAL mode exists for; hand-rolled locking would duplicate SQLite's own concurrency model incorrectly |
| Fixture faking for HTTP calls | A local test HTTP server, a new mocking library | `unittest.mock.Mock(spec=requests.Response)` patched over `requests.get` | Verified sufficient this session; adding a dependency for this is exactly what the project's "no new deps" rule exists to prevent |
| Config schema validation | A hand-rolled recursive validator with custom error classes per field type | One `validate(raw: list[dict]) -> list[str]` function returning a list of `"creator=<id> field=<name>: <problem>"` strings, per D-11's "gather every problem" requirement | A flat, small, single-operator YAML file doesn't need more machinery than a function that walks it once |

**Key insight:** every "don't hand-roll" item in this phase is really the same insight once: SQLite and `requests`/`unittest.mock` already solve the two hard problems here (concurrent access, fake HTTP), and reaching past them into either custom code or a new dependency is worse in both directions — a custom lock is a bug waiting to happen, an unaudited new dependency is a slopsquat risk for zero benefit.

## Common Pitfalls

### Pitfall T1: Twitch Get Videos' `period` parameter is documented-but-reportedly-ignored

**What goes wrong:** `GET /helix/videos?user_id=...&type=archive&period=month&first=100` may return the same result set as if `period` were omitted entirely — i.e., all videos matching `type=archive` up to `first=100`, not filtered to the last month.

**Why it happens:** This is a long-standing, Twitch-forum-documented bug, not a misunderstanding of the docs. Multiple independent threads on Twitch's own developer forum report it: one from 2018, one from 2021, and one from March 2025 — spanning nearly the entire life of the Helix API. One reporter explicitly notes the bug has persisted "for almost 6 years" and suggests Twitch simply remove the parameter from the docs since it doesn't work. `[CITED: discuss.dev.twitch.com/t/helix-videos-period-parameter-ignored/63086, discuss.dev.twitch.com/t/helix-api-period-parameter-is-ignored-in-videos/15431, discuss.dev.twitch.com/t/period-query-parameter-in-videos-endpoint/30071]`

**How to avoid:** This doesn't change D-05/D-07/D-08 — they're locked, and in practice Twitch's own VOD retention window (7/14/60 days depending on account tier) already bounds the result set to something shorter than "all videos ever," which is close to D-05's intended one-month cap for most accounts anyway. What changes is what to verify and how to talk about it: **the live verification call this phase already plans (STATE.md's blocker, ROADMAP.md's "confirm early" note) must include a second call without `period` and diff the two result sets**, not just confirm `view_count` is non-zero. If they're identical, that's the bug manifesting, and the build journal (OPS-09) should record it as an observed, cited platform bug — not as an implementation mistake — with the honest caveat that the "month" framing in D-05 is aspirational for accounts whose retention exceeds 30 days (Partners, 60-day retention) until/unless Twitch fixes it.

**Warning signs:** VODs older than 30 days appear in the summed `views` total; the result set is identical with and without `period=month` in a live test call.

### Pitfall T2: An app access token cannot read `Get Channel Followers`, but *can* read `Get Videos`

**What goes wrong:** Conflating these two endpoints' auth requirements. The CLAUDE.md-settled follower auth wall (app tokens rejected outright by `Get Channel Followers`) does **not** generalize to Get Videos.

**Why it happens:** Both are "Twitch Helix" and both involve a token; it's easy to assume one auth failure means the whole API surface is closed to app tokens.

**How to avoid:** Get Videos' official documentation states an app access token is sufficient (no scope required) — confirmed via search against `dev.twitch.tv/docs/api/videos/`. `[CITED: dev.twitch.tv/docs/api/videos/]` This is consistent with STACK.md §8's own list of what app tokens *can* reach (`/helix/streams`, `/helix/users`, `/helix/channels`) simply not enumerating Get Videos one way or the other — it wasn't tested there. Confirm with the live call above before writing the parser, as CONTEXT.md's "Specifics" section already directs.

### Pitfall Y1: `hiddenSubscriberCount: true` — `subscriberCount` comes back as the string `"0"`, not omitted

**What goes wrong:** Treating a present-but-zero `subscriberCount` field as a real zero-subscriber channel, or expecting the field to be absent from the JSON entirely and writing brittle `dict.get()` logic that never triggers.

**Why it happens:** The field is *always* present in the `statistics` object shape; YouTube's InnerTube layer simply doesn't send the underlying subscriber-count text through when the creator has hidden it, and the API layer defaults that slot to `"0"` rather than omitting the key.

**How to avoid:** D-03's rule 1 is correctly grounded — `sources/youtube.py` must check `hiddenSubscriberCount` **before** trusting `subscriberCount`, and map to `None` when hidden is `true`, regardless of what numeric string is present. `[CITED: community reports cross-referencing YouTube's InnerTube subscriberCountText behavior — MEDIUM confidence, no single canonical Google doc states this explicitly, but multiple independent sources agree and it matches this project's own PITFALLS.md #13 framing]`

**Warning signs:** A channel known to hide its subscriber count shows `followers=0` in the database instead of `NULL`.

### Pitfall Y2/T3: Empty result set is HTTP 200, not 404 — both platforms (verified consistent with D-18)

**What goes wrong:** Treating a 200 response as automatically "success, write the record."

**Why it happens:** Both YouTube `channels.list` and Twitch `Get Users`/`Get Videos` return a 200 with an empty array (`items: []` / `data: []`) for "no such resource," never a 404. This is standard REST-collection-endpoint behavior for both platforms — a list endpoint that matches zero resources is not itself an error.

**How to avoid:** Already required by D-18. Confirmed via search cross-referencing both platforms' documented collection-response shape: `[CITED: developers.google.com/youtube/v3/docs/channels/list — "returns a collection of zero or more channel resources"]` and `[CITED: community reports confirming Twitch's `{"data":[]}` + 200 pattern for Get Users on a nonexistent login — MEDIUM confidence, forum-sourced]`. Each source's `fetch()` must explicitly check `len(items) == 0` / `len(data) == 0` and raise before attempting to read any field off a result that doesn't exist.

**Warning signs:** A bogus handle/login produces a row of all-NULL metrics instead of a raised exception and a logged failure.

## Code Examples

### DDL and upsert (amended for D-01/D-02, verified syntax against installed sqlite3 3.49.1)

```python
# db.py
SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS metrics (
    creator_id    TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    metric_date   TEXT    NOT NULL,   -- ISO-8601 'YYYY-MM-DD'
    followers     INTEGER,            -- NULL = platform doesn't expose this metric
    views         INTEGER,
    likes         INTEGER,
    video_count   INTEGER,
    is_live       INTEGER,
    collected_at  TEXT    NOT NULL,   -- ISO-8601 UTC timestamp
    UNIQUE (creator_id, source, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_metrics_creator_date
    ON metrics (creator_id, metric_date);

CREATE TABLE IF NOT EXISTS runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT    NOT NULL,
    finished_at    TEXT    NOT NULL,
    rows_written   INTEGER NOT NULL,
    failure_count  INTEGER NOT NULL
);
"""

UPSERT_METRIC = """
INSERT INTO metrics
    (creator_id, source, metric_date, followers, views, likes, video_count, is_live, collected_at)
VALUES
    (:creator_id, :source, :metric_date, :followers, :views, :likes, :video_count, :is_live, :collected_at)
ON CONFLICT (creator_id, source, metric_date) DO UPDATE SET
    followers    = excluded.followers,
    views        = excluded.views,
    likes        = excluded.likes,
    video_count  = excluded.video_count,
    is_live      = excluded.is_live,
    collected_at = excluded.collected_at;
"""
```

### `connect(create: bool)` — verified live this session

```python
# db.py
import sqlite3
from pathlib import Path


class DatabaseNotInitialized(Exception):
    """Raised when create=False and the metrics table doesn't exist yet (D-04)."""


def connect(db_path: Path, *, create: bool) -> sqlite3.Connection:
    if create:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
    else:
        # verified live: sqlite3.connect raises OperationalError on a missing file
        # under mode=rw URI — this IS the "raise a named error" mechanism D-04 asks for.
        uri = f"file:{db_path.as_posix()}?mode=rw"
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        except sqlite3.OperationalError as exc:
            raise DatabaseNotInitialized(f"database file not found: {db_path}") from exc

    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")

    if create:
        conn.executescript(SCHEMA_DDL)
    else:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
        )
        if cursor.fetchone() is None:
            conn.close()
            raise DatabaseNotInitialized(f"metrics table not found in {db_path}")

    return conn
```

Verified this session (throwaway script against a real file, then cleaned up): opening a nonexistent file with `mode=rw` raises `sqlite3.OperationalError: unable to open database file`; opening an existing file with an empty schema and checking `sqlite_master` for a table that was never created correctly returns `None` from `fetchone()`. Both branches of the `create=False` path are exercised.

### Retry decorator (D-13/D-14 — narrow list, fixed backoff, source layer only)

```python
# sources/_retry.py (or inline per-source — Claude's discretion on location)
import logging
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

import requests

logger = logging.getLogger("creatorpulse")

P = ParamSpec("P")
R = TypeVar("R")

_RETRYABLE_EXC = (requests.Timeout, requests.ConnectionError)
_RETRYABLE_STATUS = {429}


def _is_retryable_status(status_code: int) -> bool:
    return status_code in _RETRYABLE_STATUS or status_code >= 500


def with_retry(
    fn: Callable[P, requests.Response],
    *,
    creator_id: str,
    source: str,
    max_attempts: int = 3,
) -> Callable[P, requests.Response]:
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> requests.Response:
        for attempt in range(1, max_attempts + 1):
            try:
                response = fn(*args, **kwargs)
                if response.status_code < 400 or not _is_retryable_status(response.status_code):
                    return response  # success OR a non-retryable error (401/403/404/...)
                if attempt == max_attempts:
                    return response  # let the caller's .raise_for_status() surface it
            except _RETRYABLE_EXC:
                if attempt == max_attempts:
                    raise
            logger.info(
                "retry creator=%s source=%s attempt=%d", creator_id, source, attempt
            )
            time.sleep(2.0 * attempt)  # 2s, then 4s — fixed, no jitter (D-14)
        raise AssertionError("unreachable")  # loop always returns or raises above

    return wrapped
```

This wraps a plain `requests.get(...)` call; a 403 with `reason=quotaExceeded` (YouTube quota exhaustion) has `status_code=403`, which is neither `429` nor `>=500`, so it correctly returns immediately on attempt 1 without retrying — matching D-14's explicit call-out that quota exhaustion must fail fast.

### YouTube fetch — verified endpoint/params against official docs

```python
# sources/youtube.py
import os
from datetime import UTC, date, datetime

import requests

from creatorpulse.models import MetricRecord

_BASE_URL = "https://www.googleapis.com/youtube/v3/channels"


class ChannelNotFound(Exception):
    pass


def fetch(handle: str, metric_date: date) -> MetricRecord:
    api_key = os.environ["YOUTUBE_API_KEY"]
    params = {"part": "statistics", "forHandle": handle, "key": api_key}
    response = requests.get(_BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    body = response.json()

    items = body["items"]
    if not items:  # D-18 — HTTP 200, empty items[], means "no such channel" — must raise
        raise ChannelNotFound(f"forHandle={handle!r} matched zero channels")

    stats = items[0]["statistics"]
    hidden = stats["hiddenSubscriberCount"]  # documented field — always present
    followers = None if hidden else int(stats["subscriberCount"])  # D-03 rule 1

    return MetricRecord(
        creator_id="",  # filled in by collector.py, source module stays DB-agnostic
        source="youtube",
        metric_date=metric_date,
        followers=followers,
        views=int(stats["viewCount"]),
        likes=None,           # not exposed by this endpoint — D-01/D-02
        video_count=int(stats["videoCount"]),
        is_live=None,         # YouTube live status is not fetched in this phase's scope
        collected_at=datetime.now(UTC),
    )
```

Note: `handle` here is the raw `creators.yaml` value (e.g. `"@xQcOW"`), passed straight to `forHandle` — official docs confirm both `"GoogleDevelopers"` and `"@GoogleDevelopers"` are accepted, so no stripping of the `@` is needed. `[VERIFIED: developers.google.com/youtube/v3/docs/channels/list]`

### Twitch fetch — token mint, user_id resolution, videos sum, live status

```python
# sources/twitch.py
import os
from datetime import UTC, date, datetime

import requests

from creatorpulse.models import MetricRecord

_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
_USERS_URL = "https://api.twitch.tv/helix/users"
_VIDEOS_URL = "https://api.twitch.tv/helix/videos"
_STREAMS_URL = "https://api.twitch.tv/helix/streams"


class ChannelNotFound(Exception):
    pass


def _mint_token() -> str:  # D-17 — fresh every run, no cache
    response = requests.post(
        _TOKEN_URL,
        data={
            "client_id": os.environ["TWITCH_CLIENT_ID"],
            "client_secret": os.environ["TWITCH_CLIENT_SECRET"],
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


def fetch(login: str, metric_date: date) -> MetricRecord:
    token = _mint_token()
    client_id = os.environ["TWITCH_CLIENT_ID"]
    headers = {"Authorization": f"Bearer {token}", "Client-Id": client_id}

    users_resp = requests.get(_USERS_URL, params={"login": login}, headers=headers, timeout=10)
    users_resp.raise_for_status()
    users_data = users_resp.json()["data"]
    if not users_data:  # D-18
        raise ChannelNotFound(f"login={login!r} matched zero users")
    user_id = users_data[0]["id"]

    videos_resp = requests.get(
        _VIDEOS_URL,
        params={"user_id": user_id, "type": "archive", "period": "month", "first": "100"},
        headers=headers,
        timeout=10,
    )
    videos_resp.raise_for_status()
    videos_data = videos_resp.json()["data"]
    # D-08: empty window -> views=0, not None. len==0 here is a real "no VODs this window",
    # distinct from D-18's "no such user" case already handled above via Get Users.
    views = sum(int(v["view_count"]) for v in videos_data)
    vod_count_in_window = len(videos_data)  # D-06 -> log line only, never the DB

    streams_resp = requests.get(
        _STREAMS_URL, params={"user_login": login}, headers=headers, timeout=10
    )
    streams_resp.raise_for_status()
    is_live = 1 if streams_resp.json()["data"] else 0  # empty data[] here means "offline", not "not found"

    return MetricRecord(
        creator_id="",
        source="twitch",
        metric_date=metric_date,
        followers=None,        # settled auth wall — NULL on every Twitch row, always
        views=views,
        likes=None,
        video_count=None,      # D-06 — Twitch has no lifetime video count
        is_live=is_live,
        collected_at=datetime.now(UTC),
    )
```

Note the asymmetry between Get Users' empty `data[]` (raise — D-18, "no such channel") and Get Streams' empty `data[]` (means "offline," a real, expected, non-error state) — these look identical in shape but mean opposite things, because Get Streams' empty result is documented as the live/offline signal itself, not a not-found signal. Log the `vod_count_in_window` value at INFO level per CONTEXT.md's discretion note ("the VOD-count line") — this is what makes a `views` drop explainable from `journalctl` without a DB query.

### `validate()` — D-11/D-12

```python
# config.py addition
import re

_SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def validate(raw: dict) -> list[str]:
    """Gather every problem in creators.yaml. Returns a list of error strings, empty if valid.
    D-11: walks the WHOLE file, never stops at the first error."""
    problems: list[str] = []
    creators = raw.get("creators")
    if not creators or not isinstance(creators, list):
        return ["creators: missing or not a non-empty list"]

    seen_ids: set[str] = set()
    for entry in creators:
        cid = str(entry.get("id", "")).strip()
        name = str(entry.get("name", "")).strip()
        sources = entry.get("sources")

        if not cid or not _SLUG_RE.match(cid):
            problems.append(f"creator={entry.get('id', '<missing>')!r} field=id: invalid or missing slug")
        elif cid in seen_ids:
            problems.append(f"creator={cid} field=id: duplicate id (also used by another entry)")
        else:
            seen_ids.add(cid)

        if not name:
            problems.append(f"creator={cid or '<unknown>'} field=name: missing or empty")

        if not sources or not isinstance(sources, dict):
            problems.append(f"creator={cid or '<unknown>'} field=sources: missing or empty map")
        else:
            for platform, identifier in sources.items():
                if platform not in KNOWN_PLATFORMS:  # from sources/__init__.py, D-09 list 1
                    problems.append(f"creator={cid or '<unknown>'} field=sources.{platform}: unknown platform")
                if not str(identifier).strip():
                    problems.append(f"creator={cid or '<unknown>'} field=sources.{platform}: empty identifier")

    return problems
```

`cli.py`'s `run_collect` calls this before `load_creators()`, prints one line per problem, and returns non-zero without opening the database — matching D-11's "before any network call" and D-16's "leaves no row" for validation failures.

### Fixture-based test pattern for OPS-06 — verified live this session

```python
# tests/test_sources.py
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from creatorpulse.sources import youtube

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fake_response(fixture_path: Path, status_code: int = 200) -> Mock:
    resp = Mock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json.loads(fixture_path.read_text(encoding="utf-8"))
    resp.raise_for_status.return_value = None
    return resp


def test_youtube_hidden_subscriber_count_maps_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    fixture = FIXTURES / "youtube" / "channel_hidden_subs.json"
    monkeypatch.setattr(
        "creatorpulse.sources.youtube.requests.get",
        lambda *a, **kw: _fake_response(fixture),
    )

    record = youtube.fetch("@somehandle", metric_date=__import__("datetime").date(2026, 8, 4))

    assert record.followers is None  # D-03 rule 1 — never 0


def test_youtube_not_found_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key-for-test")
    fixture = FIXTURES / "youtube" / "channel_not_found.json"
    monkeypatch.setattr(
        "creatorpulse.sources.youtube.requests.get",
        lambda *a, **kw: _fake_response(fixture),
    )

    with pytest.raises(youtube.ChannelNotFound):
        youtube.fetch("@doesnotexist", metric_date=__import__("datetime").date(2026, 8, 4))
```

Verified live this session: `Mock(spec=requests.Response)` with `.json.return_value` set to parsed fixture JSON and `.raise_for_status.return_value = None` behaves exactly like a real 200 response for every call site above — no new dependency, no live network call, satisfies OPS-04's existing hard constraint.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `helix/users/follows` for follower data | `helix/channels/followers` (with its own user-token auth wall — see CLAUDE.md) | Removed/returns 410 Gone since Sept 2023 | Already reflected correctly in this project's settled decisions; no action needed, just don't let old tutorials/blog posts about the removed endpoint influence implementation |
| Assuming Twitch `Get Users.view_count` is a real metric | Deprecated since April 2022, always returns `0` | April 2022 | Already correctly excluded from this project's `MetricRecord` — not referenced anywhere in the locked design |

**Deprecated/outdated:** none newly discovered this session beyond what STACK.md/PITFALLS.md already documented.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `hiddenSubscriberCount: true` causes `subscriberCount` to be the literal string `"0"` rather than an omitted key | Pitfall Y1, YouTube fetch example | If wrong (field actually omitted), `stats["subscriberCount"]` would `KeyError` instead of silently reading `"0"` — this is actually a safe-fail direction (raises loudly rather than mis-parsing), so the risk is low, but the code as written assumes the key exists. Verify against `channel_hidden_subs.json` fixture once recorded, before trusting the parser. |
| A2 | Get Videos accepts an app access token with no scope required | Pitfall T2 | If wrong, every Twitch `views` fetch fails with 401/403 on every run — this is exactly why STATE.md flags it as a blocker to verify live before building the parser, and this research strengthens (doesn't replace) that live-verification requirement |
| A3 | Twitch's `period=month` parameter is silently ignored (documented forum bug persists in the current API version) | Pitfall T1 | If Twitch has since fixed it, the window is correctly one month and no caveat is needed beyond D-05's own retention-window caveat — low risk either way since D-05/D-07/D-08 don't change; only the honest characterization of what the number represents changes |

**If this table is empty:** not applicable — three claims above are all `[CITED]`, not blind `[ASSUMED]`, but are flagged here anyway because they rest on forum/community sources rather than a single official doc fetched verbatim this session (direct fetches to `dev.twitch.tv` returned `ECONNRESET` repeatedly — see Sources). The live verification call already planned for this phase (STATE.md blocker, ROADMAP.md note, CONTEXT.md "Specifics") is the actual confirmation step; treat that call's output, not this document, as authoritative once it runs.

## Open Questions

1. **Does the live verification call confirm or refute the `period` bug (Pitfall T1)?**
   - What we know: multiple independent forum threads spanning 2018–2025 report it ignored.
   - What's unclear: whether Twitch has silently fixed it since the most recent (March 2025) report, or whether it's still broken as of this build.
   - Recommendation: make the call with and without `period=month` and diff the result sets, as the first task of this phase, before writing `sources/twitch.py`'s parser body. Record the outcome in the build journal either way — it's a specific, checkable, defensible claim for the interview regardless of which way it comes out.

2. **Should the retry decorator apply to the token-mint call (`_mint_token`) itself?**
   - What we know: D-13's retry list is scoped to fetches, and D-13's log line format assumes a `(creator, source)` pair — but the token mint happens once per Twitch fetch call, before any creator-specific work, and isn't naturally "for" one creator.
   - What's unclear: whether a transient network blip on the token endpoint should retry with the same 3-attempt/2s-4s policy, and what to log in place of `creator_id` if so.
   - Recommendation: apply the same retry wrapper with `creator_id="_token"` (or similar sentinel) as the log-line placeholder — cheaper than inventing a second retry policy, and D-14's fixed-backoff reasoning applies identically to this call site. Flag for the author's sign-off during planning since CONTEXT.md doesn't address this specific call site explicitly.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Everything | ✓ | 3.12.10 | — |
| stdlib `sqlite3` | `db.py` | ✓ | 3.49.1 (bundled) | — |
| `requests` | `sources/*` | ✓ | 2.34.2 | — |
| `PyYAML` | `config.py` | ✓ | 6.0.3 | — |
| `YOUTUBE_API_KEY` (real value) | `sources/youtube.py` live calls | ✗ (not verifiable from this session — env file is gitignored and not readable from the agent's sandbox) | — | None — this is a real Google Cloud Console credential the author must obtain by hand before D-18's manual gate can run. Not one of CLAUDE.md's three human-built areas, but still an unavoidable manual step outside code generation. |
| `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` (real values) | `sources/twitch.py` live calls, incl. the live verification call above | ✗ (same reason) | — | Same — Twitch Developer Console app registration is a manual step. |
| `dev.twitch.tv` direct fetch | This research session's own verification | ✗ (repeated `ECONNRESET` this session) | — | Used WebSearch cross-referencing multiple independent sources instead; the actual live-API verification (not the docs site) still needs to happen from the VPS or dev machine as planned |

**Missing dependencies with no fallback:** none that block writing code — the two credential values only block the *manual verification gate* (ROADMAP.md's Phase 3 note), not building/testing against fixtures. The author must obtain both before the D-18 manual proof and before the live Twitch verification call this research recommends running first.

**Missing dependencies with fallback:** `dev.twitch.tv` direct-fetch failures were worked around via WebSearch this session — no impact on the phase itself, only on how this document's Twitch claims are sourced (hence the `[CITED]` rather than `[VERIFIED]` tagging throughout the Twitch sections).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_collector.py tests/test_sources.py -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CFG-03 | Malformed entry fails naming creator+field | unit | `pytest tests/test_config.py::test_validate_reports_every_problem -x` | ❌ Wave 0 |
| SRC-04 | Absent metric → NULL, never 0 | unit | `pytest tests/test_sources.py::test_youtube_hidden_subscriber_count_maps_to_none -x` | ❌ Wave 0 |
| SRC-05 | Retry before failing | unit | `pytest tests/test_sources.py::test_retries_on_429_then_succeeds -x` | ❌ Wave 0 |
| DATA-01/DATA-02 | One row per (creator,source,date); re-run updates not duplicates | unit | `pytest tests/test_db.py::test_upsert_same_key_updates_not_duplicates -x` | ❌ Wave 0 |
| DATA-04 | Prior days untouched | unit | `pytest tests/test_db.py::test_upsert_different_date_does_not_touch_prior_row -x` | ❌ Wave 0 |
| RUN-01/RUN-02/OPS-07 | One source fails, run completes, failure logged+counted | unit | `pytest tests/test_collector.py::test_one_source_failure_does_not_abort_run -x` | ❌ Wave 0 |
| RUN-05 | `metric_date` identical across every row in one run | unit | `pytest tests/test_collector.py::test_all_rows_from_one_run_share_metric_date -x` | ❌ Wave 0 |
| OPS-05 | Run twice same day, row count unchanged | integration | `pytest tests/test_collector.py::test_idempotent_rerun_same_day -x` | ❌ Wave 0 |
| OPS-06 | Fixture in, expected record out, per source | unit | `pytest tests/test_sources.py -x` | ❌ Wave 0 |
| DATA-05 | Concurrent read (bot, `create=False`) + write (collector) | manual + unit | unit: `pytest tests/test_db.py::test_create_false_raises_on_missing_table -x`; manual: D-19 criterion 5 (`sqlite3` query while collector writes) | ❌ Wave 0 (unit) / manual gate (concurrency itself) |

### Sampling Rate

- **Per task commit:** `pytest tests/test_collector.py tests/test_sources.py -x`
- **Per wave merge:** `pytest` (full suite, includes existing `test_config.py`/`test_paths.py`)
- **Phase gate:** full suite green, plus the D-18 manual gate (bogus-handle run, journal output pasted into `03-UAT.md`) — this phase's Definition of Green explicitly requires the human-observed real-API run in addition to automated checks (ROADMAP.md).

### Wave 0 Gaps

- [ ] `tests/fixtures/youtube/channel_ok.json`, `channel_hidden_subs.json`, `channel_not_found.json` — record with `scripts/record_fixture.py` once `YOUTUBE_API_KEY` is available
- [ ] `tests/fixtures/twitch/videos_ok.json`, `videos_empty.json`, `users_not_found.json`, `streams_live.json`, `streams_offline.json` — same, once Twitch credentials are available; recording `videos_ok.json` is also the live verification call this research recommends running first (kill two birds)
- [ ] `tests/test_db.py` — DDL + upsert unit tests, no fixture dependency, can be written before any credential is available
- [ ] `tests/test_sources.py` — fixture-in/record-out tests, blocked on the fixtures above
- [ ] `tests/test_collector.py` — orchestration tests (idempotency, failure isolation, metric_date-once), can use a fake in-memory `FETCHER_REGISTRY` and doesn't need real fixtures
- [ ] `tests/test_config.py` extension — `validate()` cases, no fixture dependency

## Security Domain

`security_enforcement: true`, ASVS level 1 (from `.planning/config.json`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This is a single-operator batch job with no end-user login; outbound API credentials (YouTube key, Twitch client id/secret) are service-to-service, not app authentication |
| V3 Session Management | No | No sessions — one-shot process per run |
| V4 Access Control | No | Single operator, single machine, no roles |
| V5 Input Validation | Yes | `creators.yaml` — `yaml.safe_load` (already in use, never `yaml.load`), plus the new `validate()` pass (D-11/D-12) rejecting malformed entries before any network call; SQL parameters bound via named placeholders (`:creator_id` etc.), never string-formatted into the query |
| V6 Cryptography | No | No cryptographic operations performed by this codebase — TLS to the two APIs is handled by `requests`/the OS trust store, and the Twitch app token is a bearer credential handled in-memory only (D-17, no persistence) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via `creator_id`/metric values | Tampering | Named-placeholder parameterized queries (`INSERT ... VALUES (:creator_id, ...)`) — never f-string/`.format()` into SQL text |
| YAML deserialization RCE | Tampering / Elevation of Privilege | `yaml.safe_load` only — already the case in `config.py`, unchanged this phase |
| Log injection via attacker-controlled creator name/id embedding format specifiers or newlines | Tampering | `%`-style lazy logging (`logger.error("...%s...", creator.id)`), never f-string interpolation of untrusted values into the format string itself — the codebase's existing `cli.py`/`test_paths.py` already follow this convention |
| Secret exposure in logs or exception messages | Information Disclosure | Never log the full `Authorization` header, API key, or token value; the retry decorator's log line names creator/source/attempt only, never the request headers or params dict |
| Path traversal in fixture recording | Tampering | Already mitigated in `scripts/record_fixture.py` (regex-validated `--source`/`--case`, resolved-path containment check) — not touched this phase, but the same discipline applies if this phase adds any new file-writing code |

## Sources

### Primary (HIGH confidence)
- Local `.venv` — `requests.__version__`, `sys.version`, `sqlite3.sqlite_version`, `pip show gspread PyYAML discord.py playwright` — verified live this session, all match `pyproject.toml`/STACK.md pins exactly
- Local throwaway script — `sqlite3.connect("file:...?mode=rw", uri=True)` on a missing file raises `OperationalError: unable to open database file`; on an existing DB, `sqlite_master` lookup correctly distinguishes present vs. absent tables — verified live this session, cleaned up afterward, confirmed no residue via `git status --short`
- Local throwaway script — `unittest.mock.Mock(spec=requests.Response)` with `.json.return_value` behaves as a fake 200 response — verified live this session
- `developers.google.com/youtube/v3/docs/channels/list` — WebFetch this session, confirmed: 1-unit quota cost, `forHandle` accepts both `"Handle"` and `"@Handle"`, collection response returns zero-or-more items (implies 200+empty for no match)

### Secondary (MEDIUM confidence)
- `discuss.dev.twitch.com` (three separate threads, 2018/2021/2025) — WebSearch-summarized, could not direct-fetch (`ECONNRESET`) — the `period`-ignored bug on Get Videos, cross-referenced across three independent report dates
- `dev.twitch.tv/docs/api/videos/` — WebSearch-summarized (direct fetch failed) — app access token sufficient for Get Videos, no scope required; `type`/`period`/`user_id` parameter semantics; example response body shape including `view_count`, `type: "archive"`
- Community sources (search-summarized) — `hiddenSubscriberCount: true` → `subscriberCount` returns `"0"` rather than omitting the field, tied to YouTube's InnerTube `subscriberCountText` behavior
- Community sources (search-summarized) — Twitch Get Users on a nonexistent `login` returns HTTP 200 with an empty `data` array, not a 404

### Tertiary (LOW confidence)
- None used unqualified — every Twitch claim above is cross-referenced across at least two independent sources before inclusion, given `dev.twitch.tv` was unreachable via direct WebFetch this session

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified live against the installed `.venv`, not just PyPI metadata
- Architecture (schema/upsert/WAL/`connect(create)`): HIGH — SQL/Python mechanics verified live this session against the exact installed sqlite3 version
- YouTube integration: HIGH on endpoint/params/quota (direct official-doc fetch), MEDIUM on the `hiddenSubscriberCount`→`"0"` specific behavior (community-sourced, consistent across sources, no single canonical Google doc states it explicitly)
- Twitch integration: MEDIUM — `dev.twitch.tv` was unreachable via direct fetch this session; all Twitch-specific claims rest on WebSearch cross-referencing 2-3 independent sources rather than a single authoritative fetch. **The `period`-ignored finding (Pitfall T1) is itself well-corroborated (three independent forum threads spanning 7 years) despite the fetch failures** — the live verification call this phase already plans is the actual authoritative check, and should be run before trusting `sources/twitch.py`'s summed-views logic
- Pitfalls: HIGH — cross-referenced against this project's own existing PITFALLS.md #8/#10/#11/#12/#13/#17/#19, all of which remain accurate for this phase; two new pitfalls (T1, T2) added this session

**Research date:** 2026-08-04
**Valid until:** ~30 days for the stdlib/SQLite/YouTube findings (stable, unlikely to change); ~7 days for the Twitch `period` bug status specifically, since it's the kind of thing that could get silently fixed or could get worse — re-verify with the live call at the start of this phase regardless of this document's age.
