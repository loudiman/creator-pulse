# Phase 6: Discord Bot - Pattern Map

**Mapped:** 2026-08-06
**Files analyzed:** 8 (5 modified, 2 new, `.env.example` name-only addition not separately classified)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/creatorpulse/bot.py` | service (gateway client) + pure formatters | request-response (commands) + event-driven (task loop, alerts) | `src/creatorpulse/sheets.py` | role-match (same "one integration module, pure core + I/O boundary" shape) |
| `src/creatorpulse/db.py` (DDL + `write_run_row` + moved query) | model / schema | CRUD | `src/creatorpulse/db.py` itself (existing `SCHEMA_DDL`, `UPSERT_METRIC`, `write_run_row`) | exact (same file, additive) |
| `src/creatorpulse/collector.py` (`collect_once` failure accumulation) | service (orchestrator) | batch | `src/creatorpulse/collector.py` itself | exact (same file, same loop shape) |
| `src/creatorpulse/cli.py` (`bot` subcommand body, two webhook call sites) | controller (entry point / dispatch) | request-response | `src/creatorpulse/cli.py` itself (`run_collect`, `run_sync`) | exact |
| `src/creatorpulse/config.py` (`resolve_discord_config`) | config | CRUD (env read + validate) | `resolve_sheets_config()` in the same file | exact |
| `src/creatorpulse/sheets.py` (loses `LATEST_ROWS_SQL`/`LatestRow`/`fetch_latest_rows`) | service | CRUD | itself, pre-move | exact — subtractive edit only |
| `tests/test_bot.py` | test | transform (pure formatter → string) | `tests/test_sheets.py` | exact (temp SQLite, hand-inserted rows, pure function assertions, no mocking framework for the DB parts) |
| `tests/test_db.py`, `tests/test_collector.py`, `tests/test_sheets.py` (edits) | test | CRUD / batch | same files, pre-existing style | exact |

## Pattern Assignments

### `src/creatorpulse/bot.py` (new — gateway client, task loop, slash commands, pure formatters)

**Analog:** `src/creatorpulse/sheets.py` (structural shape) + `src/creatorpulse/config.py` (config validation shape) + `06-RESEARCH.md` Code Examples (discord.py-specific API surface, already vetted against pinned v2.7.1 source)

**Module docstring + logger pattern** (`sheets.py` lines 1-12):
```python
"""The only module that talks to Google. Reads metrics via db.py, writes the Dashboard tab."""

import json
import logging
import sqlite3

...
logger = logging.getLogger("creatorpulse")
```
`bot.py` should open the same way: one-line module purpose, `logger = logging.getLogger("creatorpulse")` — same logger name every other module uses, so journald output is uniform.

**Pure-core-separated-from-I/O-boundary shape** (`sheets.py` lines 66-93 vs 112-159): `fetch_latest_rows()` (pure SQL read) and `build_dashboard_rows()` (pure transform, fixture-testable, no I/O) are separate from `_open_worksheet()`/`sync()` (the actual network calls). `bot.py` must mirror this exactly per D-20: `build_digest_text()`, `build_alert_text()`, `build_trend_text()`, `build_status_text()` are pure functions taking rows/`sqlite3.Connection` and returning `str` — these are what `tests/test_bot.py` exercises. `channel.send()`, the task loop, and the slash command callbacks are the untested I/O boundary, thin wrappers calling the pure functions.

**Named exception style** (`sheets.py` lines 18-25):
```python
class SheetNotShared(Exception):
    """Raised when the Sheet is not shared with the service account, or shared as Viewer
    rather than Editor (D-08, SHEET-07)."""
```
`bot.py`/`config.py` should define `DiscordConfigError` the same way — one short class, docstring naming the decision it satisfies (D-19).

**discord.py-specific shape** (already vetted against pinned v2.7.1 source in `06-RESEARCH.md` — copy verbatim, do not re-derive):
```python
from datetime import time
from zoneinfo import ZoneInfo
from discord.ext import tasks

MANILA = ZoneInfo("Asia/Manila")
DIGEST_TIME = time(hour=8, minute=15, tzinfo=MANILA)


class CreatorPulseBot(commands.Bot):
    @tasks.loop(time=DIGEST_TIME)
    async def digest_loop(self) -> None:
        try:
            await post_digest(self.get_channel(self.channel_id), self.db_path)
        except Exception:
            logger.exception("digest tick failed; next scheduled time will retry")

    @digest_loop.before_loop
    async def _before_digest(self) -> None:
        await self.wait_until_ready()
```
The bare `try/except Exception: logger.exception(...)` inside the loop body is non-negotiable (Pitfall 1) — this is the one place `bot.py` diverges from every other module's narrower except clauses, and the divergence is deliberate and must stay commented as such, the way `sheets.py`'s `_open_worksheet` comments explain its own deliberately-separated try blocks (lines 116-119).

**Short-lived per-command DB connection** (matches `db.connect`/`.close()` discipline already used in `cli.py` lines 74-76, 124-126):
```python
@bot.tree.command(name="status", description="Report last collector run's status")
async def status(interaction: discord.Interaction) -> None:
    conn = db.connect(db_path, create=False)
    try:
        text = build_status_text(conn)
    finally:
        conn.close()
    await interaction.response.send_message(text)
```

---

### `src/creatorpulse/config.py` — `resolve_discord_config()` (new function, same file)

**Analog:** `resolve_sheets_config()`, same file, lines 49-58

```python
def resolve_sheets_config() -> tuple[str, Path] | None:
    """Resolve the two Sheets env vars (D-09). No default exists for either — unlike
    resolve_paths()'s repo-relative fallback, a missing spreadsheet key has no sensible guess.
    Returns None when either is absent or the empty string, so the caller can fail loudly
    before opening anything."""
    sheet_id_env: str | None = os.environ.get("CREATORPULSE_SHEET_ID")
    keyfile_env: str | None = os.environ.get("CREATORPULSE_SHEETS_KEYFILE")
    if not sheet_id_env or not keyfile_env:
        return None
    return sheet_id_env, Path(keyfile_env).resolve()
```

Key convention to copy exactly: `os.environ.get(...)`, empty string treated as unset (the falsy-string check, not `is None`). D-19 diverges deliberately from this return-`None`-and-let-caller-branch shape — Discord config must raise a **named** exception per missing/malformed var rather than return `None`, because D-19 requires failing loudly before connecting with the variable named. `06-RESEARCH.md`'s `resolve_discord_config()` Code Example already implements this divergence correctly (raises `DiscordConfigError` per-field, `int()`-parses the two ID vars with a `ValueError`-to-named-exception translation) — copy it, it is pre-vetted against this exact analog.

---

### `src/creatorpulse/db.py` — `run_failures` DDL, `write_run_row()` returning `lastrowid`, moved query

**Analog:** the same file's existing `SCHEMA_DDL` (lines 9-33) and `_WRITE_RUN_ROW`/`write_run_row()` (lines 51-54, 113-129)

**DDL constant style to match exactly** — `CREATE TABLE IF NOT EXISTS`, inline comment explaining any NULL-worthy column, no separate migration:
```python
CREATE TABLE IF NOT EXISTS runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT    NOT NULL,
    finished_at    TEXT    NOT NULL,
    rows_written   INTEGER NOT NULL,
    failure_count  INTEGER NOT NULL
);
```
`run_failures` should append to the same `SCHEMA_DDL` string, same style, with an FK-shaped `run_id INTEGER NOT NULL` (D-06's four columns: `run_id`, `creator_id`, `source`, `cause`, `message`).

**`write_run_row()` returning the id** — current body (lines 113-129) does `conn.execute(...)` then `conn.commit()` with no return; change to capture the cursor and return `cursor.lastrowid`:
```python
def write_run_row(conn: sqlite3.Connection, ...) -> int:
    cursor = conn.execute(_WRITE_RUN_ROW, {...})
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]  # sqlite3 types lastrowid as int|None
```
(mypy note: `cursor.lastrowid` is typed `int | None` in stdlib stubs; this INSERT always produces a rowid, so either an assert or a narrow ignore is needed — same kind of narrow, explained divergence `sheets.py` already models for its two separated `try` blocks.)

**Moved query** (D-13) — `LATEST_ROWS_SQL`, `LatestRow`, `fetch_latest_rows()` move verbatim from `sheets.py` lines 42-70 into `db.py`, unchanged in content, so `sheets.py`'s `build_dashboard_rows()` and the new `bot.py` formatters both import `from creatorpulse.db import fetch_latest_rows, LatestRow`. Do this as its own commit before anything else, per CONTEXT's explicit instruction.

---

### `src/creatorpulse/collector.py` — failure-detail accumulation

**Analog:** the same file's existing per-pair `try/except` (lines 36-47)

```python
try:
    record = fetch(identifier, metric_date)
except Exception as exc:  # D-15 — one boundary per (creator, source) pair
    failure_count += 1
    logger.error(
        "fetch failed creator=%s source=%s cause=%s: %s",
        creator.id,
        source_name,
        type(exc).__name__,
        str(exc),
    )
    continue  # no cross-pair state, no short-circuit (D-15)
```
D-06 needs this same except block to also append a failure-detail record (`creator_id`, `source`, `cause=type(exc).__name__`, `message=str(exc)`) to a list that `RunResult` then carries — the `type(exc).__name__`/`str(exc)` values are already computed right here for the log line, so the change is capturing what already exists rather than adding a new computation. `RunResult` (`models.py` lines 20-23) needs a new field for the failures list, following the same frozen-dataclass-slots shape as `MetricRecord`.

---

### `src/creatorpulse/cli.py` — `bot` subcommand body + two webhook alert call sites

**Analog:** `run_collect()` and `run_sync()`, same file — the existing docstring-heavy exit-code convention (lines 35-101) and the existing `except (SheetNotShared, SheetsKeyfileUnusable, gspread.exceptions.APIError)` block (lines 90-96) that D-09 extends.

**Sync-failure alert insertion point** (D-09) — one line added before the existing `raise`, log-then-re-raise unchanged:
```python
except (SheetNotShared, SheetsKeyfileUnusable, gspread.exceptions.APIError) as exc:
    logger.error(
        "Sheets sync failed — metric rows and the runs row are already committed; "
        "the next timer run is the retry: %s", exc,
    )
    _post_alert(f"Sheets sync failed: {exc}")  # new — swallows its own failure, never re-raises
    raise
```
The webhook POST helper (`_post_alert` or similar, shared with the D-08 run-failure alert call site) is plain `requests.post(webhook_url, json={"content": message}, timeout=10)` — the exact payload shape Phase 5's `Code.gs postToDiscord()` already uses (`apps-script/Code.gs` lines 145-152: `UrlFetchApp.fetch(webhookUrl, {contentType: 'application/json', payload: JSON.stringify({content: message})})`). Wrap the POST in its own narrow `try/except requests.RequestException: logger.exception(...)` per D-09's "a broken alert channel must never replace the real error in flight" constraint — this is a new, small pattern this codebase hasn't needed before (Phase 5's version runs in Apps Script, not Python), but the payload shape (`{"content": ...}`) and the fail-silently-on-broken-webhook rule are both already decided; nothing to invent.

**`bot` subcommand dispatch** — replaces the stub at lines 155-157:
```python
if args.command == "bot":
    logger.warning("bot is not implemented yet; Phase 6 fills it in")
    return 3
```
becomes a call into `bot.run_bot(db_path)` (or equivalent), following `run_collect`/`run_sync`'s own shape: resolve config first (raises loudly per D-19), then hand off to the long-lived `client.run(token)` call. `configure_logging()` (line 27) is shared, called once in `main()` before dispatch — no change needed there.

---

### `tests/test_bot.py` (new)

**Analog:** `tests/test_sheets.py`, whole-file pattern (temp SQLite DB via `tmp_path`, `upsert_metric()` calls to seed rows, pure function under test, no discord.py imports, no mocking framework beyond `unittest.mock.Mock` used only where an I/O boundary genuinely needs a double)

```python
def _record(**overrides: Any) -> MetricRecord:
    base: dict[str, Any] = {
        "creator_id": "c1",
        "source": "youtube",
        "metric_date": date(2026, 1, 1),
        "followers": 100,
        "views": 200,
        "likes": None,
        "video_count": 5,
        "is_live": None,
        "collected_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return MetricRecord(**base)


def test_null_followers_renders_blank_and_zero_renders_zero(tmp_path: Path) -> None:
    conn = connect(tmp_path / "creatorpulse.db", create=True)
    upsert_metric(conn, _record(creator_id="null-case", followers=None))
    upsert_metric(conn, _record(creator_id="zero-case", followers=0))
    values = build_dashboard_rows(fetch_latest_rows(conn))
    ...
```
`test_bot.py` copies this shape one-for-one for each pure formatter: seed rows with `upsert_metric`/`write_run_row`/a new `write_run_failure` helper, call `build_digest_text()`/`build_status_text()`/`build_trend_text()`, assert on substrings (creator name present, `⚠ STALE` banner present when stale, `DELTA_PLACEHOLDER` present when no baseline, ±20% flag character present/absent). D-12's `—` and D-04's staleness banner should each get their own small, named test function the way `test_null_followers_renders_blank_and_zero_renders_zero` and `test_delta_no_baseline_row_puts_the_marker_and_row_still_appears` already do — one behavior, one test, descriptive snake_case name stating the behavior in full.

**Naming convention to copy:** `test_<subject>_<condition>_<expected outcome>` — verbose, sentence-like test names throughout `test_sheets.py` (e.g. `test_delta_zero_baseline_versus_null_baseline_adjacency`). `test_bot.py` should follow the same naming density; a short name like `test_digest` would be out of step with every existing test file in this repo.

---

## Shared Patterns

### Config validation shape
**Source:** `src/creatorpulse/config.py` `resolve_sheets_config()` (lines 49-58)
**Apply to:** `resolve_discord_config()` in the same file — empty-string-is-unset rule, `os.environ.get()` never `os.environ[...]`, returns/raises before any network call.

### Named exceptions, one line + docstring naming the decision
**Source:** `src/creatorpulse/sheets.py` `SheetNotShared`/`SheetsKeyfileUnusable` (lines 18-25), `src/creatorpulse/db.py` `DatabaseNotInitialized` (lines 57-58)
**Apply to:** `bot.py`'s `DiscordConfigError` (or wherever it lands) — same one-class, one-docstring shape, docstring cites the decision ID (`D-19`).

### Fail loudly, never silently; log-then-re-raise on I/O failure
**Source:** `src/creatorpulse/cli.py` lines 90-96 (Sheets sync except block), `src/creatorpulse/db.py` `connect(create=False)` raising `DatabaseNotInitialized`
**Apply to:** `resolve_discord_config()` (D-19), the channel-fetch preflight in `bot.py`'s `setup_hook` (Pitfall 2), and letting `discord.LoginFailure` propagate uncaught from `client.run()` (Pitfall 3) — do not wrap the run call in a broad `try/except`.

### NULL-vs-0, never coalesced before delta math
**Source:** `src/creatorpulse/sheets.py` `build_dashboard_rows()` (lines 73-93), `DELTA_PLACEHOLDER` constant (line 15)
**Apply to:** every formatter in `bot.py` that renders a views/followers/delta value — import `DELTA_PLACEHOLDER` from `sheets.py`, do not retype the em dash; `None` prev_views or `None` views renders `—`, a real `0` renders `0`.

### Short-lived, per-call database connections — no module-level global
**Source:** `src/creatorpulse/cli.py` `run_collect`/`run_sync` (`connect(...)` then `conn.close()` in the same function body, lines 74-76, 124-126)
**Apply to:** every `bot.py` command handler and the digest loop tick — open, query, close, matching ROADMAP's explicit "no module-level global DB connection in the bot process" note.

### Webhook POST payload shape
**Source:** `apps-script/Code.gs` `postToDiscord()` (lines 145-152) — `{"content": message}` JSON body, `contentType: application/json`, 2xx-or-log status check.
**Apply to:** `cli.py`'s two new D-08/D-09 alert call sites — same JSON shape (`requests.post(url, json={"content": text}, timeout=10)`), same fail-loudly-except-swallow-the-alert-failure-itself rule.

### Verbose, sentence-like pytest test names, one behavior per test
**Source:** `tests/test_sheets.py`, throughout.
**Apply to:** `tests/test_bot.py` in full.

## No Analog Found

None. Every file this phase touches has a strong analog already in the codebase — either the same file pre-edit, or `sheets.py`/`config.py` as the structural template. The one genuinely new surface (discord.py's gateway/task-loop/slash-command API) has no in-repo analog by definition, but `06-RESEARCH.md`'s Code Examples section already contains pre-vetted, pinned-source-verified snippets for exactly this surface — treat that section as the analog for the discord.py-specific plumbing.

## Metadata

**Analog search scope:** `src/creatorpulse/` (all modules), `tests/test_sheets.py`, `apps-script/Code.gs`, `.planning/phases/05-apps-script/COVERAGE.md`, `.planning/phases/06-discord-bot/06-RESEARCH.md`
**Files scanned:** `sheets.py`, `config.py`, `db.py`, `collector.py`, `cli.py`, `models.py`, `sources/youtube.py`, `sources/_retry.py`, `tests/test_sheets.py`, `apps-script/Code.gs`, `05-apps-script/COVERAGE.md`
**Pattern extraction date:** 2026-08-06
