# Phase 4: Playwright & Sheets - Pattern Map

**Mapped:** 2026-08-05
**Files analyzed:** 3 (1 new module, 1 modified module, 1 new test file)
**Analogs found:** 3 / 3

## Scope note

Phase is Sheets-only (SRC-03 TikTok/Playwright and SHEET-04 History tab cut). No `sources/tiktok.py`,
no Playwright analogs mapped.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/creatorpulse/sheets.py` | service | request-response (read DB, compute, batch-write external API) | `src/creatorpulse/sources/youtube.py` (call-external-API/normalize/raise-named-exception shape) + `src/creatorpulse/db.py` (read side) | role-match (composite: no existing "write to external API" module exists; youtube.py is closest for the API-call/exception half, db.py for the query half) |
| `src/creatorpulse/config.py` (modified: extend `resolve_paths()`) | config | transform | `src/creatorpulse/config.py:40-46` itself | exact (extend in place, not a new pattern) |
| `src/creatorpulse/cli.py` (modified: implement `sync` subcommand) | controller/CLI | request-response | `src/creatorpulse/cli.py:24-65` (`run_collect`) | exact |
| `tests/test_sheets.py` | test | transform (pure function tests) + event-driven (fixture/mock injection) | `tests/test_sources.py` + `tests/test_db.py`/`tests/test_collector.py` in-memory setup | exact |

## Pattern Assignments

### `src/creatorpulse/sheets.py` (service, read-DB / compute-delta / batch-write)

**Analog 1 — read side:** `src/creatorpulse/db.py:61-89` (`connect`)

Open read-only, `create=False`, so a bad path raises the existing named exception rather than
silently creating an empty DB:
```python
conn = connect(db_path, create=False)  # raises DatabaseNotInitialized (db.py) — do not catch and mask it
```
Use the existing index for the delta query — `db.py:23-24`:
```sql
CREATE INDEX IF NOT EXISTS idx_metrics_creator_date
    ON metrics (creator_id, metric_date);
```
D-01's row-list query (write directly in `sheets.py`, no new function needed in `db.py` per the
`sheets.py` ↔ `db.py` boundary — `sheets.py` may issue its own `SELECT`s against the connection
`db.py` hands back, it does not need every query pre-wrapped):
```sql
SELECT DISTINCT creator_id, source FROM metrics ORDER BY creator_id, source;
```

**Analog 2 — external-API-call / normalize / named-exception shape:** `src/creatorpulse/sources/youtube.py:1-50`

Named exception at module scope, raised on a specific failure condition rather than a bare
exception bubbling up — mirror this exact shape for SHEET-07:
```python
class ChannelNotFound(Exception):
    """Raised when forHandle matches zero channels (D-18) — HTTP 200 with no usable items."""
```
becomes, in `sheets.py`:
```python
class SheetNotShared(Exception):
    """Raised when open_by_key fails — message carries client_email to share the Sheet with (D-08)."""
```
The call/guard/raise sequence to mirror (youtube.py:19-32 — call, check, raise-named):
```python
response = get(_BASE_URL, params=params, timeout=10)
response.raise_for_status()
body: dict[str, Any] = response.json()
items = body.get("items")
if not items:
    raise ChannelNotFound(f"forHandle={identifier!r} matched zero channels")
```
For SHEET-07, the gspread equivalent (D-08) — wrap `open_by_key`, catch `APIError` /
`SpreadsheetNotFound`, read `client_email` from the service-account JSON already loaded for auth,
raise `SheetNotShared` with that email in the message. No fixture exists for gspread's exceptions
yet — construct via `unittest.mock` in tests (see test section below), matching how `test_sources.py`
builds `Mock(spec=requests.Response)`.

**MetricRecord field reference for column mapping** — `src/creatorpulse/models.py:7-17`, the nine
fields D-03's Dashboard columns select from (`creator_id`, `source`, `followers`, `views`,
`collected_at` are the five actually used; `likes`, `video_count`, `is_live`, `metric_date` are not
Dashboard columns but `metric_date` drives the delta join).

**Module layout freedom:** CONTEXT.md leaves function count at planner's discretion. Given
`youtube.py`'s one-function-does-fetch-and-normalize shape and `db.py`'s one-function-per-concern
shape, a reasonable split mirroring both: `_fetch_rows(conn) -> rows`, `build_dashboard_rows(rows) ->
list[list[object]]` (the pure, fixture-testable core CONTEXT.md names explicitly), `_open_worksheet(sheet_id,
keyfile) -> Worksheet` (raises `SheetNotShared`), `sync(conn, sheet_id, keyfile) -> int` (row count,
orchestrates the three and calls `worksheet.update`).

**Error handling / D-07:** log then re-raise, no `try/except` swallow — this deviates from
`collector.py`'s per-pair swallow-and-continue (`collector.py:36-47`); D-07 explicitly wants the
opposite for the Sheets write, so do NOT copy the per-pair swallow pattern here, only the log-line
shape:
```python
logger.error("fetch failed creator=%s source=%s cause=%s: %s", creator.id, source_name, type(exc).__name__, str(exc))
```
becomes, in `sheets.py` (log then re-raise, not continue):
```python
logger.error("sheets sync failed cause=%s: %s", type(exc).__name__, str(exc))
raise
```

---

### `src/creatorpulse/config.py` (extend `resolve_paths()`, D-09)

**Analog:** itself, `config.py:40-46`

```python
def resolve_paths() -> tuple[Path, Path]:
    """Resolve config and db paths from the environment, falling back to repo-relative defaults."""
    config_env: str | None = os.environ.get("CREATORPULSE_CONFIG")
    db_env: str | None = os.environ.get("CREATORPULSE_DB")
    config_path = Path(config_env) if config_env else DEFAULT_CONFIG_PATH
    db_path = Path(db_env) if db_env else DEFAULT_DB_PATH
    return config_path.resolve(), db_path.resolve()
```
D-09 says follow the exact same empty-string-means-unset treatment for
`CREATORPULSE_SHEET_ID` / `CREATORPULSE_SHEETS_KEYFILE`. Unlike `CREATORPULSE_CONFIG`/`CREATORPULSE_DB`,
these two have **no default** — decide at the call site (cli.py) whether unset means "skip sync" or
"error"; D-06/D-07 imply sync always runs, so an unset value should raise/log clearly rather than
silently no-op. Either add a second function (`resolve_sheets_config() -> tuple[str, Path] | None`)
or extend the tuple returned by `resolve_paths()` — planner's call, but keep the empty-string-unset
idiom identical:
```python
sheet_id_env: str | None = os.environ.get("CREATORPULSE_SHEET_ID")
keyfile_env: str | None = os.environ.get("CREATORPULSE_SHEETS_KEYFILE")
```

---

### `src/creatorpulse/cli.py` (implement `sync` subcommand + call from `run_collect`, D-06)

**Analog:** `cli.py:24-65` (`run_collect`) for shape; the existing stub at `cli.py:87-89` is the
attachment point to replace:
```python
if args.command == "sync":
    logger.warning("sync is not implemented yet; Phase 4 fills it in")
    return 3
```
Mirror `run_collect`'s structure — resolve paths, log start, open DB with `connect(..., create=False)`
(NOT `create=True` — this is the reader path, per db.py analog above), call `sheets.sync(...)`, log
row count and duration, return 0. Reuse the existing timing pattern (`cli.py:43,63-64`):
```python
start = time.monotonic()
...
elapsed = time.monotonic() - start
logger.info("Run complete in %.2f seconds", elapsed)
```
D-06's second call site — attach at the end of `run_collect`, after `collect_once` returns
(`cli.py:60-64`), so the Phase 2 `ExecStart` unit is untouched (only `run_collect`'s body changes,
not its signature or the `collect` subparser).

**Do not touch:** `collect` subcommand's name/flags/log shape (Phase 1 D-02/D-03, human-built unit
targets it) and `deploy/creatorpulse.service`/`.timer` (Phase 2 D-12) — read-only, never edit.

---

### `tests/test_sheets.py` (test, pure-function + mock-injection)

**Analog 1 — fixture/mock-injection style:** `tests/test_sources.py:22-49` (`_response`,
`_youtube_response` builders; `Mock(spec=...)` pattern):
```python
def _response(status_code: int) -> Mock:
    resp = Mock(spec=requests.Response)
    resp.status_code = status_code
    return resp
```
Mirror for a fake gspread `Worksheet`:
```python
def _worksheet() -> Mock:
    ws = Mock(spec=gspread.Worksheet)
    return ws
```
And `monkeypatch.setattr` to intercept the client-construction call, same idiom as
`test_sources.py:142`:
```python
monkeypatch.setattr("creatorpulse.sources.youtube.requests.get", lambda *a, **kw: resp)
```
becomes:
```python
monkeypatch.setattr("creatorpulse.sheets._open_worksheet", lambda *a, **kw: fake_ws)
```

**Analog 2 — in-memory SQLite setup:** check `tests/test_db.py` / `tests/test_collector.py` for the
exact fixture (likely `sqlite3.connect(":memory:")` + `db.SCHEMA_DDL` executed directly, or
`connect(tmp_path / "test.db", create=True)`) — reuse whichever helper/fixture those files already
define rather than writing a third variant. `sheets.py` tests need real rows in `metrics` to exercise
`build_dashboard_rows`, so seed via `db.upsert_metric` with `MetricRecord` instances, not raw SQL,
to stay consistent with how the rest of the suite writes fixtures.

**Test file location/naming:** `tests/test_sheets.py`, following Phase 1 D-15's established
`tests/test_{module}.py` convention (`test_db.py`, `test_collector.py`, `test_sources.py` all match
module names 1:1).

---

## Shared Patterns

### Named exceptions at module scope, message carries the actionable detail
**Source:** `src/creatorpulse/sources/youtube.py:15-16` (`ChannelNotFound`), `src/creatorpulse/db.py:57-58`
(`DatabaseNotInitialized`)
**Apply to:** `sheets.py`'s `SheetNotShared` (D-08) — message must contain the literal `client_email`
string, not just a generic "share it" instruction.

### stdlib logging, INFO, human-readable, no f-string in the format arg (lazy %-formatting)
**Source:** `src/creatorpulse/cli.py:16-21`, `collector.py:29-33,40-46`
**Apply to:** all new log lines in `sheets.py` and the `sync` subcommand — resolved Sheet ID, row
count written, sync duration (CONTEXT.md's discretion item, INFO level, matching Phase 1 D-19/D-20).
```python
logger.info("Starting collect run using config %s, database %s", config_path, db_path)
```

### Read-only DB open uses `create=False`
**Source:** `src/creatorpulse/db.py:61-89`
**Apply to:** both `sheets.py` (as a library call) and the `sync` CLI subcommand — never `create=True`
on the reader path; that combination is reserved for `collect`.

### `@dataclass(frozen=True, slots=True)` for any new record type
**Source:** `src/creatorpulse/models.py:7-17`, `20-23`
**Apply to:** only if a new small value type is introduced (e.g. a `DashboardRow` tuple substitute) —
likely unnecessary; a `list[object]` row is what `worksheet.update` wants directly per D-04, so don't
manufacture a dataclass just to immediately flatten it (YAGNI per project's own ladder).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| gspread client construction / `open_by_key` wrapper | service (auth) | request-response | No existing module calls an external *write* API or does service-account auth; `youtube.py` is API-key-only. Build directly from `gspread.service_account(filename=...)` per STACK.md §6 — no analog needed, the library call is one line. |

## Metadata

**Analog search scope:** `src/creatorpulse/` (all modules), `tests/` (test_db.py, test_collector.py,
test_sources.py)
**Files scanned:** `db.py`, `collector.py`, `sources/youtube.py`, `config.py`, `cli.py`, `models.py`,
`tests/test_sources.py`
**Pattern extraction date:** 2026-08-05
</content>
