# Architecture Research

**Domain:** Unattended scheduled-collector on one VPS (Python 3.12 → SQLite → Google Sheet → Discord)
**Researched:** 2026-07-29
**Confidence:** MEDIUM-HIGH (SQLite/systemd mechanics cross-checked against sqlite.org and multiple independent sources; Protocol-vs-ABC and gspread rate-limit guidance are well-established community consensus, not vendor-authoritative)

## Standard Architecture

### System Overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│  systemd TIMER (daily)                    systemd SERVICE (always-on)     │
│       │                                          │                        │
│       ▼                                          ▼                       │
│  ┌─────────────────┐                       ┌──────────────────┐          │
│  │  collector run   │                       │   discord bot    │          │
│  │  (one-shot)      │                       │   (long-lived)   │          │
│  └────────┬─────────┘                       └────────┬─────────┘          │
│           │ writes                                    │ reads             │
│           ▼                                            ▼                 │
│  ┌───────────────────────────────────────────────────────────┐            │
│  │            creatorpulse.db  (single SQLite file, WAL)      │           │
│  │   metrics table  │  runs table                             │          │
│  └───────────────────────────────────────────────────────────┘            │
│           ▲                                                                │
│           │ read (own run's rows) + write                                 │
│  ┌────────┴─────────┐                                                     │
│  │  sources/         │  youtube.py (API)                                  │
│  │  adapters         │  twitch.py  (API)                                  │
│  │                   │  tiktok.py  (Playwright)                          │
│  └───────────────────┘                                                     │
│           │                                                                │
│           ▼                                                                │
│  ┌───────────────────┐        ┌────────────────────┐                     │
│  │  sheets sync step  │──────▶│  Google Sheet        │                    │
│  │  (gspread, batched)│       │  Dashboard + History │                    │
│  └───────────────────┘        └────────────────────┘                     │
└───────────────────────────────────────────────────────────────────────────┘
```

Both processes are separate OS processes with separate lifecycles. They share nothing at runtime except the DB file, the config file, and a `core` Python package (models + db helpers). No IPC, no shared memory, no message queue — the SQLite file *is* the integration point.

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `sources/*` adapters | Fetch raw data for one platform, return normalized records | Plain functions or small classes behind a `Protocol`, one module per source |
| `collector` (orchestrator) | Loop creators × sources, catch failures per-unit, write metrics + runs row | One-shot script/entrypoint, no persistent state |
| `db` module | Schema DDL, connection factory (WAL + busy_timeout), upsert helpers | Thin wrapper over stdlib `sqlite3`, no ORM |
| `sheets` module | Read latest DB state, compute deltas, batch-write Dashboard + History | `gspread`, called from collector run or standalone CLI |
| `discord` bot | Long-lived gateway connection, slash commands read DB read-only | `discord.py` `commands.Bot`, separate process |
| `config` (`creators.yaml` + env) | Declare creators/sources without code changes; secrets from env file | `pyyaml` load + `pydantic`/dataclass validation |

## Recommended Project Structure

```
src/
└── creatorpulse/
    ├── __init__.py
    ├── config.py            # load creators.yaml + env, validate shapes
    ├── models.py             # MetricRecord, Creator dataclasses (shared)
    ├── db.py                 # connection factory, schema DDL, upsert(), migrations()
    ├── sources/
    │   ├── __init__.py       # Source Protocol + SOURCES registry dict
    │   ├── youtube.py        # API-backed
    │   ├── twitch.py         # API-backed
    │   └── tiktok.py         # Playwright-backed, owns its own browser lifecycle
    ├── collector.py          # orchestration: loop creators/sources, failure isolation, runs row
    ├── sheets.py             # gspread client, Dashboard/History writers, delta calc
    ├── bot/
    │   ├── __init__.py
    │   ├── client.py         # bot construction, cog loading
    │   └── commands.py       # /creator, /status
    └── cli.py                 # console-script entrypoints: collect, sync-sheet, bot

creators.yaml                  # repo root or /etc/creatorpulse/, config not code
tests/
├── fixtures/                  # saved JSON (YouTube/Twitch) + HTML (TikTok)
├── test_sources.py
├── test_db.py
├── test_collector.py
└── test_sheets.py
```

### Structure Rationale

- **`src/` layout:** standard, forces `pip install -e .` / import-from-installed-package discipline instead of accidental relative-path imports — cheap to set up, avoids the classic "works locally, breaks under systemd cwd" bug.
- **`sources/` as a flat package, not a plugin-discovery framework:** three sources, hard-capped at three by the project's own scope. A registry dict (`SOURCES = {"youtube": fetch_youtube, ...}`) beats `pkgutil`/`entry_points` plugin discovery — that machinery pays for itself past ~10 pluggable backends or third-party plugin authors, neither applies here.
- **`models.py` and `db.py` are the only modules both processes import** — keep them free of source-specific and Discord-specific logic so the shared surface stays small and obviously safe to import from either lifecycle.
- **`bot/` as a subpackage, not a peer top-level:** it is one of two entrypoints, not the center of the codebase; nesting it signals "optional consumer of `db`/`models`," not "the app."
- **`cli.py` single entrypoint module with subcommands** (`creatorpulse collect`, `creatorpulse sync-sheet`, `creatorpulse bot`) rather than three separate console-script names — one `pyproject.toml` entry point, `argv[1]` dispatch, less packaging surface.

## Architectural Patterns

### Pattern 1: Source adapter as `Protocol` + plain function, not ABC

**What:** Define the contract as a `typing.Protocol` (structurally checked, no inheritance), implement each source as a module-level function with that signature, not a class hierarchy.

**When to use:** Small, fixed number of heterogeneous implementations that don't share concrete behavior. Exactly this project: YouTube and Twitch adapters share nothing but a return type; TikTok shares even less (it owns a browser).

**Trade-offs:** ABC would force a common base class that has no shared methods to offer — dead coupling. A Protocol costs nothing at runtime, gives `mypy` real structural checking, and a 4th source is "write a function with this signature, add one line to the registry," with no subclassing ritual.

**Example:**
```python
# sources/__init__.py
from typing import Protocol
from creatorpulse.models import MetricRecord, Creator


class SourceFetcher(Protocol):
    def __call__(self, creator: Creator) -> MetricRecord: ...


# each adapter fetches ONE creator's metrics for the current run;
# the collector owns the loop over creators, not the adapter.
from creatorpulse.sources import youtube, twitch, tiktok

SOURCES: dict[str, SourceFetcher] = {
    "youtube": youtube.fetch,
    "twitch": twitch.fetch,
    "tiktok": tiktok.fetch,
}
```

**Handling the Playwright lifecycle mismatch:** don't let the `Protocol` grow a `setup()`/`teardown()` pair just to accommodate one adapter — that leaks Playwright's shape into the two API adapters that don't need it. Instead, give TikTok's own module a context manager that the *collector* invokes only for that source, keyed off the registry:

```python
# sources/tiktok.py
from contextlib import contextmanager
from playwright.sync_api import sync_playwright


@contextmanager
def browser_session():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            yield browser
        finally:
            browser.close()


def fetch(creator: Creator, *, browser) -> MetricRecord:
    page = browser.new_page()
    ...
```

```python
# collector.py — orchestrator branches ONCE, not inside the shared loop signature
def run_source(name: str, creators: list[Creator]) -> list[MetricRecord]:
    if name == "tiktok":
        with tiktok.browser_session() as browser:
            return [safe_fetch(lambda c: tiktok.fetch(c, browser=browser), c) for c in creators]
    fetch = SOURCES[name]
    return [safe_fetch(fetch, c) for c in creators]
```

This keeps `SourceFetcher` itself simple (`creator -> MetricRecord`) for the common case, and confines the one browser-lifecycle special case to the one place that needs to know about it (the orchestrator's per-source dispatch), not to every adapter's type signature. Adding a 4th API-backed source touches zero orchestrator code; adding a 4th *browser-backed* source means one more `if name == ...` branch, which is an acceptable, visible cost given the cap is 3 sources total.

### Pattern 2: Normalization boundary — one record type, NULL for "doesn't exist"

**What:** Every adapter returns the same `MetricRecord` shape; adapter-internal parsing/HTML-scraping/pagination never crosses into `collector.py` or `db.py`.

**When to use:** Always, in a multi-source collector — it's what makes the DB schema, the delta computation, and the Sheet writer source-agnostic.

**Trade-offs:** none real — this is the one non-negotiable seam in the system.

```python
# models.py
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class MetricRecord:
    creator_id: str
    source: str  # "youtube" | "twitch" | "tiktok"
    metric_date: date
    followers: int | None
    views: int | None
    likes: int | None
    engagement_rate: float | None
    collected_at: datetime
```

**NULL vs 0 vs omit — decision:** use `None` (SQL `NULL`) for "this metric does not exist on this platform," and a real `0` only for "the platform reports zero." Never omit the field — the record type has all five metric slots for every source, always. Rationale: `0` is a valid, meaningful observation (a channel really can have 0 views on a video); `NULL` means "not applicable, don't compute deltas or averages over this," which is exactly SQL's own NULL semantics (`NULL - NULL = NULL`, `AVG` skips NULLs, `SUM` treats them as 0-contribution). Concretely for this project: TikTok's public profile page has no "views" figure comparable to YouTube's — that field is `None` for every TikTok row, forever, not `0`. Delta computation (`today - yesterday`) then naturally yields `NULL` for that cell instead of a false "+0" trend, and the Sheet formula/format can render `NULL` as `—` rather than a misleading zero.

### Pattern 3: Failure isolation — try/except at the leaf, aggregate at the run

**What:** Wrap each *(creator, source)* fetch individually; the orchestrator never lets one exception unwind past that single unit. Record failures into an in-memory tally for the `runs` row and log each one to stderr (captured by journald) with enough context to grep.

**When to use:** Any per-unit batch job where partial success beats all-or-nothing.

**Trade-offs:** slightly more boilerplate per adapter call than a bare loop; the payoff is that one platform's outage or rate limit never blanks the whole day's data.

```python
def safe_fetch(fetch, creator: Creator) -> MetricRecord | None:
    try:
        return fetch(creator)
    except Exception:
        logging.exception("fetch failed creator=%s source=%s", creator.id, fetch.__name__)
        return None


def run() -> RunResult:
    started = datetime.now(UTC)
    rows_written = 0
    failures = 0
    for source_name, creators in creators_by_source().items():
        for record in run_source(source_name, creators):
            if record is None:
                failures += 1
                continue
            upsert_metric(conn, record)
            rows_written += 1
    write_run_row(conn, started, datetime.now(UTC), rows_written, failures)
```

No retries inside the run — a failed fetch is recorded-and-skipped, not retried, because the *next day's timer run* is the retry (daily cadence makes same-run retries low value and adds complexity/flakiness risk for a 7-day build). If a specific transient-error class turns out to be worth one immediate retry (e.g. a single HTTP 429), add a bounded retry *inside* the adapter function itself (2 attempts, short backoff) — never in the orchestrator, which should stay ignorant of per-source error taxonomies.

The try/except boundary is per-*(creator, source)* pair, not per-source and not per-creator separately — one creator's TikTok scrape failing must not skip that creator's YouTube fetch, and one source's global outage must not corrupt other creators' rows for that source. A single boundary at the smallest unit gets both for free; splitting it into two nested boundaries (per-source *and* per-creator) is the same protection with more code.

## Data Flow

### Collector run flow

```
systemd timer fires
    ↓
cli.py "collect"
    ↓
load creators.yaml + env → Creator[] grouped by source
    ↓
for each source: run_source() → safe_fetch() per creator → MetricRecord | None
    ↓
upsert_metric() per non-None record → metrics table (WAL-mode SQLite)
    ↓
write_run_row() → runs table (start, duration, rows_written, failures)
    ↓
sheets sync step: read latest+prior metrics rows → compute deltas → batch write Dashboard + History
    ↓
discord webhook/bot: post daily digest summarizing the run
```

### Bot query flow (independent, on-demand)

```
Discord user runs /creator <name>
    ↓
bot.py handler → SELECT latest + prior row for creator from metrics (read-only connection)
    ↓
format embed → reply
```

### Key Data Flows

1. **Collector write path:** raw source → `MetricRecord` (normalize) → `upsert_metric` (idempotent by `(creator_id, source, metric_date)`) → `runs` row. One-directional, no read-modify-write races because the collector is the only writer and runs once daily, non-overlapping (systemd timer + oneshot guarantees this).
2. **Sheet path:** DB → Sheet, never Sheet → DB, except the human-edited Status column, which is preserved by *not* being sourced from the DB at all (see Sheets Sync Boundary below) — it survives a Dashboard rewrite because the rewrite never touches that column's range.
3. **Bot read path:** DB → Discord, read-only, decoupled in time from the collector — the bot can be queried any time, including mid-run, because WAL mode lets readers proceed without blocking on the writer.

## SQLite Schema

Validated: the user's proposed `metrics` shape is correct and complete for this project's needs. Concrete DDL, indexes, and upsert below.

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;  -- set on every new connection, not just once

CREATE TABLE IF NOT EXISTS metrics (
    creator_id       TEXT    NOT NULL,
    source           TEXT    NOT NULL,
    metric_date      TEXT    NOT NULL,   -- ISO-8601 'YYYY-MM-DD'
    followers        INTEGER,            -- NULL = not applicable for this source
    views            INTEGER,
    likes            INTEGER,
    engagement_rate  REAL,
    collected_at     TEXT    NOT NULL,   -- ISO-8601 UTC timestamp, e.g. '2026-07-29T06:00:03+00:00'
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
```

**Upsert (verified against sqlite.org UPSERT syntax, added SQLite 3.24.0, well within any 3.12-bundled sqlite3 version):**

```sql
INSERT INTO metrics
    (creator_id, source, metric_date, followers, views, likes, engagement_rate, collected_at)
VALUES
    (:creator_id, :source, :metric_date, :followers, :views, :likes, :engagement_rate, :collected_at)
ON CONFLICT (creator_id, source, metric_date) DO UPDATE SET
    followers       = excluded.followers,
    views           = excluded.views,
    likes           = excluded.likes,
    engagement_rate = excluded.engagement_rate,
    collected_at    = excluded.collected_at;
```

The `ON CONFLICT (creator_id, source, metric_date)` conflict target must name exactly the columns of the `UNIQUE` constraint — SQLite matches it against that index, not by column order or a subset.

**Design calls:**

- **Dates as TEXT ISO-8601, not INTEGER epoch.** SQLite has no native date type; TEXT ISO-8601 sorts and compares correctly as strings (`'2026-07-29' < '2026-07-30'`), is directly usable in `date()`/`strftime()` functions, and — the deciding factor for this project — is human-readable when someone opens the `.db` file with a GUI tool during debugging or in the README screenshot. Epoch integers are marginally more compact and comparison-cheap, but that only matters at row counts this project will never reach (a handful of creators × 3 sources × 365 days/year is a few thousand rows).
- **`engagement_rate`: store it, don't compute-on-read.** It is a per-source-defined formula (YouTube: (likes+comments)/views; Twitch/TikTok differ or may be unavailable) that only the adapter, at fetch time, has the raw numerator/denominator to compute correctly and consistently with what the platform itself would call "engagement." Recomputing it in a SQL view or in `sheets.py` means re-deriving each source's formula in a second place — a correctness bug waiting to diverge. Store it as `REAL`, `NULL` when the source doesn't support it.
- **No Alembic, no migration framework.** For a one-file, single-owner, 7-day-build DB: put all DDL in one idempotent `CREATE TABLE IF NOT EXISTS` block executed at startup (both by the collector and, defensively, by the bot). If a schema change is needed later (e.g. adding a column), hand-write a one-off guarded `ALTER TABLE ... ADD COLUMN` behind a check against `PRAGMA table_info(metrics)`, run once, and delete the guard code afterward — a `schema_version` pragma/table is overkill for a schema that, per the project's own scope, is expected to change zero or one times in its life.

```python
# db.py
import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5.0)  # sets busy_timeout equivalent
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(SCHEMA_DDL)  # both CREATE TABLE IF NOT EXISTS statements
    return conn
```

## Process Split: Collector (timer) vs Bot (service)

**Shared:** the SQLite file, `creators.yaml`, the env file, and the `models.py` + `db.py` modules (same package, imported by both). Nothing else — the bot does not import `sources/` or `sheets.py`; the collector does not import `bot/`.

**SQLite concurrency implications, verified:** WAL mode's explicit promise is readers don't block writers and a writer doesn't block readers — reading and writing proceed concurrently; only one writer is allowed at a time (irrelevant here since the collector is the sole writer and never runs concurrently with itself, guaranteed by systemd `Type=oneshot` timer semantics). Concretely:

- Set `PRAGMA journal_mode = WAL` once (persists in the DB file header — safe to also set it every connection, it's a no-op after the first).
- Set `PRAGMA busy_timeout = 5000` (or pass `timeout=5.0` to `sqlite3.connect`) on **every** connection, bot included — this is the guard against a rare bot-query/collector-write overlap raising `database is locked` instead of just waiting a few hundred ms.
- The bot should open **short-lived connections per query**, not hold one connection open for its whole process lifetime — a long-held read transaction in WAL mode can itself block the writer's checkpoint. Cheapest fix: `with sqlite3.connect(...) as conn: ...` inside each command handler, not a module-level global connection.
- No connection pool, no async DB driver needed — query volume here is a handful of Discord command invocations per day plus one write per day. `discord.py`'s async command handlers can call the synchronous `sqlite3` API directly (queries are single-digit milliseconds); wrapping it in `asyncio.to_thread` is a nice-to-have, not required at this scale — skip it unless a real handler feels slow.

## Sheets Sync Boundary

**Sync is a step inside the collector run, not a separate systemd-scheduled entrypoint** — but implemented as its own function/CLI subcommand (`cli.py sync-sheet`) so it *can* be invoked standalone for manual re-syncs or debugging without re-running the whole collection. The daily flow calls it automatically at the end of `collect`; nothing schedules it independently. Reasoning: the Sheet only needs to reflect what the DB just collected, once a day — a second timer/service for this is pure scope for a 7-day build with zero benefit (avoid speculative operational surface).

**Dashboard tab (one row per creator, latest + delta):**
- Read latest `metric_date` row and the prior day's row per creator from `metrics` (two indexed queries using `idx_metrics_creator_date`, or one query with a window function / self-join keyed on `metric_date`).
- Compute delta in Python (`today.followers - yesterday.followers`, `None` if either side is `None`), not in a Sheet formula — keeps the Sheet a pure rendered view, consistent with "DB is source of truth."
- Write the whole Dashboard range in one `worksheet.update(range, values)` or `spreadsheet.values_batch_update(...)` call — never per-cell (confirmed both by gspread's own docs and by Sheets API v4's per-project/per-user rate limits, which per-cell writes burn through fast).

**History tab (append-only):** one `worksheet.append_rows(rows, value_input_option="USER_ENTERED")` call per sync, appending that day's new rows for all creators/sources in a single request — never row-by-row.

**Preserving the human-edited Status column across a Dashboard rewrite:** the rewrite must target only the DB-owned columns' range (e.g. `A2:F{n}` if Status lives in column G), never the full row width. Concretely: fix a stable column layout where Status (and any other human-editable column) is always the last column, and write with an explicit range (`update("A2:F11", values)`) rather than `update(values)` with an implicit range starting at A1 that could stomp column G. As a second, cheap safety net, read the current Status column's values before the write and re-assert them if the write call ever does target the full row (defense in depth, but the range-restriction is the real fix — don't rely on read-then-rewrite as the primary mechanism, since it's a race if Apps Script's `onEdit` fires between the read and the write).

## Anti-Patterns

### Anti-Pattern 1: A `Source` ABC with `setup()`/`teardown()` lifecycle hooks on every adapter

**What people do:** Add abstract `connect()`/`disconnect()` methods to a base class so the Playwright adapter's browser lifecycle "fits the interface," then make YouTube/Twitch implement no-op versions.
**Why it's wrong:** leaks one adapter's implementation detail into the shared contract; the two API adapters now carry dead methods that exist only to satisfy an interface neither needs. It's the textbook shape of an abstraction built for a case with n=1.
**Do this instead:** keep the shared contract to `creator -> MetricRecord`; give the browser-lifecycle special case its own context manager in its own module, and let the orchestrator dispatch on source name once (see Pattern 1 above).

### Anti-Pattern 2: A generic migration framework (Alembic) or `schema_version` table for a single, hand-owned SQLite file

**What people do:** Reach for Alembic (or hand-roll a numbered-migrations directory) because "that's how you do DB schema changes."
**Why it's wrong:** Alembic assumes a team, multiple environments, and a schema that changes often enough to need auditable, reversible, ordered migrations. Here there is one DB file, one operator, and a schema this project's own scope expects to touch rarely if ever. The framework's setup cost (config, versioning table, migration script scaffolding) exceeds the entire cost of the schema changes it would ever apply.
**Do this instead:** idempotent `CREATE TABLE IF NOT EXISTS` DDL run at every startup; hand-written, one-off `ALTER TABLE` guarded by `PRAGMA table_info` checks for the rare actual schema change.

### Anti-Pattern 3: One shared long-lived process for both collection and the bot

**What people do:** Run the collector's daily job as a scheduled `asyncio` task inside the same process as the Discord bot, to "save a systemd unit."
**Why it's wrong:** couples two very different failure/restart semantics — a Playwright crash or a hung HTTP call in the collector now risks killing (or hanging) the bot's gateway connection too, and a bot crash/restart cycle risks skipping or double-running the daily collection. systemd's timer + oneshot model gives the collector "run to completion, exit, never overlap" guarantees for free; a bot process is explicitly the opposite shape ("stay alive, reconnect on drop"). This is exactly why the project's own Key Decisions table already calls for a separate systemd service for the bot — the research confirms that call, it doesn't revise it.
**Do this instead:** two systemd units, as already decided; share only the DB file and the `models`/`db` modules.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| YouTube Data API v3 | REST via `requests`/`httpx`, API key, one call per channel per run | Free quota is finite (10k units/day default) — batch-friendly `channels.list` with `part=statistics` is cheap per call; test against saved JSON fixtures, never live in `pytest` |
| Twitch Helix API | REST, app access token (client credentials OAuth), refresh token before expiry | Token has ~60-day life; cache it (e.g. in the env-loaded config or a tiny local cache file) rather than fetching a new one every run |
| TikTok public profile pages | Playwright (Chromium), no auth, respects `robots.txt`, public HTML only | Fragile to markup changes by nature — isolate all TikTok-specific selectors inside `sources/tiktok.py` so a TikTok markup change is a one-file fix |
| Google Sheets API v4 | `gspread` + service account JSON, batch reads/writes only | Rate limits ~300 req/60s per project, ~60 req/60s per user — the entire reason batching is mandatory, not just tidy |
| Discord | `discord.py` gateway (bot) for slash commands; a webhook (from Apps Script's `onEdit`) is a separate, human-built integration outside the Python codebase | Bot process needs its own token/intents, set up in the Discord Developer Portal (human-built, out of scope for this codebase) |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `sources/*` ↔ `collector.py` | direct function call, `MetricRecord` return value | No source module ever imports `db.py` or `sheets.py` — one-directional dependency, sources know nothing about persistence |
| `collector.py` ↔ `db.py` | direct function call (`upsert_metric`, `write_run_row`) | Collector owns *when* to write; `db.py` owns *how* |
| `collector.py` ↔ `sheets.py` | direct function call at end of run, or standalone CLI invocation | `sheets.py` only ever reads from `db.py`, never from `sources/*` |
| `bot/*` ↔ `db.py` | direct function call, read-only queries, short-lived connections per command | Bot never imports `sources/*`, `collector.py`, or `sheets.py` — it has no reason to know how data got into the DB |
| Apps Script (human-built) ↔ Discord webhook | HTTP POST from `onEdit` trigger | Entirely outside this codebase; the Python side's only obligation is that the Status column's location/format stays stable so the human-built script keeps working |

## Build Order

Dependency-ordered; items in the same numbered step have no dependency on each other and can be built in parallel.

1. **`models.py` + `db.py`** (schema DDL, connection factory, `upsert_metric`, `write_run_row`) — everything else depends on the `MetricRecord` shape and the DB being writable. Build and test this first, alone, with a throwaway fixture record.
2. **In parallel, once step 1's `MetricRecord` shape is fixed:**
   - **`sources/youtube.py`** and **`sources/twitch.py`** (API-backed, no browser dependency, fastest to fixture-test)
   - **`sources/tiktok.py`** (Playwright-backed) — can start in parallel with the API sources since it only depends on the same `MetricRecord` contract, but budget more time: Playwright setup, selector-writing against saved HTML fixtures, and `robots.txt` verification are the slowest part of the whole build
   - **`config.py`** (`creators.yaml` loader + validation) — independent of both, blocks nothing but is needed before `collector.py` can be wired end to end
3. **`collector.py`** — depends on steps 1 and 2 (needs at least one real source and the config loader to do anything meaningful; can be scaffolded with a stub source earlier if parallelism is tight). This is where failure isolation and the `runs` row get built and tested (idempotency test, failure-isolation test belong here).
4. **`sheets.py`** — depends on step 1 (reads from `db.py`) and conceptually on step 3 (it's invoked at the end of a real run), but can be developed and tested against a fixture DB in parallel with finishing `collector.py`, then wired in last.
5. **`bot/`** — depends only on step 1 (`db.py`/`models.py`); can be built any time after step 1, fully in parallel with steps 2–4, since it never touches sources, the collector, or sheets. Good candidate for the *first* parallel track if two people/sessions are working simultaneously, since it has the shallowest dependency chain after the DB layer.
6. **systemd units, Apps Script, Discord Developer Portal setup** — human-built per the project's own scope; the Python side only needs to expose stable entrypoints (`creatorpulse collect`, `creatorpulse sync-sheet`, `creatorpulse bot`) and a documented env-file contract for these to be wired against. Do this integration pass last, after steps 1–5 are individually verified with fixtures, so the human-built layer is wired against working code rather than a moving target.

**Practical grouping for a 7-day part-time solo build:** Day 1 = step 1 + `config.py`. Days 2–3 = the three sources in sequence (YouTube/Twitch first since they're fast wins and validate the collector/db plumbing; TikTok/Playwright last since it's the highest-risk, highest-effort piece and the project's own cut-order already treats it as first-to-drop if behind). Day 4 = `collector.py` + failure-isolation/idempotency tests. Day 5 = `sheets.py`. Day 6 = `bot/`. Day 7 = systemd/Apps Script/Discord Portal integration pass + README. This ordering front-loads the highest-risk component (TikTok) early enough that cutting it (per the project's own documented cut order) still leaves a fully working, tested system.

## Sources

- [SQLite UPSERT (lang_upsert)](https://sqlite.org/lang_upsert.html) — official syntax reference, verified `ON CONFLICT ... DO UPDATE SET ... excluded.col` form
- [SQLite WAL concurrency behavior — Runnable SQLite Docs](https://coddy.tech/docs/sqlite/wal-mode-and-concurrency) and [Bert Hubert on SQLITE_BUSY/busy_timeout](https://berthub.eu/articles/posts/a-brief-post-on-sqlite3-database-locked-despite-timeout/) — cross-checked WAL reader/writer promises and `busy_timeout`/`BEGIN IMMEDIATE` guidance against multiple independent sources
- [typing.Protocol spec](https://typing.python.org/en/latest/spec/protocol.html) and community writeups on Protocol-vs-ABC for plugin/adapter shapes — structural vs nominal typing tradeoff, confirmed consistent across sources
- [gspread API reference and rate-limit issue discussion](https://docs.gspread.org/en/master/api/models/spreadsheet.html) — batch_update/values_batch_update as the mechanism to stay under Sheets API v4's per-project/per-user quotas
- Community comparisons of systemd timers vs cron for `Type=oneshot` Python jobs — overlap prevention, journald logging, `Persistent=true` catch-up semantics, consistent across multiple independent writeups
- Project's own `.planning/PROJECT.md` — schema shape, process split, and source list were already partially decided there; this document validates and extends those decisions rather than re-litigating them

---
*Architecture research for: unattended scheduled-collector systems (Python/SQLite/Sheets/Discord on a single VPS)*
*Researched: 2026-07-29*
