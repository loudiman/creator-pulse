# Phase 3: Collector Core & API Sources - Pattern Map

**Mapped:** 2026-08-04
**Files analyzed:** 12 (7 new modules, 1 modified module, 1 modified cli, 4-6 new test files)
**Analogs found:** 5 (weak-to-strong, all in-repo) / 12 — most new files have **no in-repo analog**; this is an honest gap in a ~200-line codebase, not a search failure. RESEARCH.md's "Code Examples" section is the primary pattern source for those files (already verified against official docs / live `.venv`, not invented).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/creatorpulse/models.py` | model | transform | `src/creatorpulse/config.py` (`Creator` dataclass, lines 17-21) | role-match (shape only, no behavior to match) |
| `src/creatorpulse/db.py` | service | CRUD | none in-repo | no analog — RESEARCH.md "Code Examples" is authoritative |
| `src/creatorpulse/config.py` (`validate()` addition) | utility | request-response (fail-fast) | `src/creatorpulse/config.py` (`load_creators()`, lines 33-45, same file) | exact — extends the file it's already in |
| `src/creatorpulse/sources/__init__.py` | config/route | event-driven (registry dispatch) | none in-repo | no analog — RESEARCH.md Pattern 1 is authoritative |
| `src/creatorpulse/sources/youtube.py` | service | request-response | none in-repo | no analog — RESEARCH.md "YouTube fetch" example is authoritative |
| `src/creatorpulse/sources/twitch.py` | service | request-response | `src/creatorpulse/sources/youtube.py` (sibling, once written) | role-match (same phase, same shape) |
| `src/creatorpulse/collector.py` | controller | event-driven (orchestration loop) | `src/creatorpulse/cli.py` (`run_collect()`, lines 22-33) | role-match (logging/timing shape only; no orchestration precedent exists) |
| `src/creatorpulse/cli.py` (modify line 30 seam) | controller | request-response | `src/creatorpulse/cli.py` itself (lines 22-33, existing) | exact — same file, same function, replacing one line |
| `tests/test_db.py` | test | CRUD | `tests/test_paths.py` | role-match (structure/style, not subject) |
| `tests/test_sources.py` | test | request-response (mocked HTTP) | `tests/test_config.py` | role-match (fixture-in/assert-out shape) |
| `tests/test_collector.py` | test | event-driven | `tests/test_paths.py` (`caplog` pattern, lines 61-73) | role-match |
| `tests/test_config.py` (extended with `validate()` cases) | test | request-response | `tests/test_config.py` itself | exact — same file, additive |

## Pattern Assignments

### `src/creatorpulse/models.py` (model, transform)

**Analog:** `src/creatorpulse/config.py:17-21` (`Creator`)

**Dataclass shape to match** (`src/creatorpulse/config.py` lines 17-21):
```python
@dataclass(frozen=True, slots=True)
class Creator:
    id: str
    name: str
    sources: dict[str, str]
```
`MetricRecord` must use the identical decorator form: `@dataclass(frozen=True, slots=True)`. No validation logic inside the dataclass itself — matches `Creator`'s own "shape only" convention. Field types are `int | None` per D-01/D-03 (mypy `strict = true` forces this to be handled, not ignored) — see RESEARCH.md Pattern 2 for the full field list (no analog exists in-repo for the `X | None` metric-field pattern specifically; this file establishes it).

---

### `src/creatorpulse/config.py` — `validate()` addition (utility, request-response)

**Analog:** same file, `load_creators()` (lines 33-45)

**Signature/injectable-path pattern to match** (lines 33-34):
```python
def load_creators(path: Path = DEFAULT_CONFIG_PATH) -> list[Creator]:
```
`validate()` should take the same kind of injectable input (raw parsed dict, per RESEARCH.md's `validate(raw: dict) -> list[str]`) rather than reading the file itself — keep parse and validate as separate concerns, matching the module's existing "parse-only" docstring convention (line 1-4) which validate() now supersedes with a doc update.

**Docstring convention** (lines 1-4): the module docstring says "No validation — see Phase 3 CFG-03." This line must be updated/removed once `validate()` lands — it is a live, load-bearing comment, not decoration.

**Import style** (lines 6-11): plain top-level imports, no path aliases, no barrel file. `validate()` adds `import re` at the top in the same style.

---

### `src/creatorpulse/cli.py` — replace line 30 seam (controller, request-response)

**Analog:** same file, `run_collect()` (lines 22-33)

**Exact seam to replace** (line 30):
```python
logger.warning("Collector body is not implemented yet; Phase 3 fills it in")
```
**Surrounding structure to preserve** (lines 22-33) — timing via `time.monotonic()`, run-start/run-end log lines bracketing the work, return an `int` exit code:
```python
def run_collect(config_path: Path, db_path: Path) -> int:
    start = time.monotonic()
    logger.info("Starting collect run using config %s, database %s", config_path, db_path)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        return 1
    creators = load_creators(config_path)
    logger.info("Loaded %d creators", len(creators))
    # <-- line 30 seam replaced here: validate() call, then collector.run()
    elapsed = time.monotonic() - start
    logger.info("Run complete in %.2f seconds", elapsed)
    return 0
```
D-11 requires `validate()` to run **before** `load_creators()` and before any network call, and to exit non-zero without opening the DB — so the actual insertion point moves earlier than line 30 (validate first, then load, then `db.connect()` + `collector.run()`, wrapped per D-16's try/finally). Do not change the function signature (`config_path: Path, db_path: Path) -> int`) — `tests/test_paths.py::test_run_collect_logs_both_resolved_paths` already asserts against this signature and the two log lines.

**Command surface — do not touch** (lines 40-41, 50-54): `--config` argument and dispatch on `args.command == "collect"` are fixed by Phase 1 decisions; the systemd unit targets this exact command name.

---

### `src/creatorpulse/collector.py` (controller, event-driven orchestration)

**Weak analog:** `src/creatorpulse/cli.py:22-33` for logging/timing shape only — no orchestration-loop precedent exists in this repo.

**Primary pattern source:** RESEARCH.md "Pattern 3: Failure isolation" (full code block, lines 278-322 of 03-RESEARCH.md) — verbatim orchestration shape: `metric_date` computed once via `datetime.now(UTC).date()` before the loop (RUN-05), per-`(creator, source)` try/except with `continue` on failure (D-15/RUN-01), skip-vs-failure distinction via `FETCHER_REGISTRY.get()` returning `None` (D-09/D-10), and `write_run_row()` called once after the loop (DATA-03). Logger name matches existing convention: `logging.getLogger("creatorpulse")` (same string used in `cli.py:11`).

**Logging convention to copy** (`cli.py:11`, applies everywhere):
```python
logger = logging.getLogger("creatorpulse")
```
All %-style lazy logging, never f-strings — confirmed by RESEARCH.md's Security Domain section ("log injection via... never f-string interpolation... the codebase's existing `cli.py`/`test_paths.py` already follow this convention").

---

### `src/creatorpulse/db.py` (service, CRUD) — no in-repo analog

No existing SQL/persistence code exists anywhere in this repo. RESEARCH.md's "Code Examples" §"DDL and upsert" and §"connect(create: bool)" (lines 385-468 of 03-RESEARCH.md) are the authoritative source — both verified live this session against the installed sqlite3 3.49.1, not invented. Key excerpts already vetted:
- `SCHEMA_DDL` with `UNIQUE (creator_id, source, metric_date)` and the amended D-01/D-02 columns.
- `UPSERT_METRIC` using named placeholders (`:creator_id`, etc.) — never string-formatted SQL (RESEARCH.md Security Domain, V5).
- `connect(db_path: Path, *, create: bool) -> sqlite3.Connection` with the `mode=rw` URI branch for `create=False` and `PRAGMA journal_mode = WAL` / `PRAGMA busy_timeout = 5000` on every connection.

Match the module docstring convention from `config.py` line 1 (a one-line purpose statement, no decoration).

---

### `src/creatorpulse/sources/__init__.py` (registry/route, event-driven) — no in-repo analog

RESEARCH.md "Pattern 1" (lines 226-253) is authoritative: `typing.Protocol` for `SourceFetcher`, `KNOWN_PLATFORMS` frozenset (D-09 list 1), `FETCHER_REGISTRY` plain dict (D-09 list 2, only implemented sources). No ABC, no lifecycle hooks — this is explicitly called out in RESEARCH.md as the wrong shape to avoid.

---

### `src/creatorpulse/sources/youtube.py` (service, request-response) — no in-repo analog

RESEARCH.md "YouTube fetch" code example (lines 525-571) is authoritative and verified against `developers.google.com/youtube/v3/docs/channels/list`. Load-bearing details already encoded there: `forHandle` param takes the raw `creators.yaml` value unmodified (no `@`-stripping needed); `hiddenSubscriberCount` checked before trusting `subscriberCount` (D-03 rule 1, Pitfall Y1); empty `items[]` raises `ChannelNotFound` (D-18, Pitfall Y2); `creator_id=""` left blank — filled in by `collector.py`, keeping the source module DB-agnostic.

**Retry decorator to wrap the `requests.get` call:** RESEARCH.md "Retry decorator" (lines 472-521) — narrow retry list (`requests.Timeout`, `requests.ConnectionError`, HTTP 429/5xx), 3 attempts, fixed 2s/4s sleep, lives in the source layer only (never `collector.py`, per Anti-Pattern 1).

---

### `src/creatorpulse/sources/twitch.py` (service, request-response)

**Analog:** `src/creatorpulse/sources/youtube.py` (sibling module, same phase) — same `fetch(identifier, metric_date) -> MetricRecord` signature, same retry-wrapping convention, same DB-agnostic `creator_id=""` placeholder.

RESEARCH.md "Twitch fetch" code example (lines 573-650) is the authoritative source beyond the sibling-shape match: token mint via `_mint_token()` (D-17, no cache), `Get Users` empty `data[]` raises (D-18) vs. `Get Streams` empty `data[]` means offline (not an error) — these look identical in shape but are opposite semantically, flagged explicitly in RESEARCH.md as the trap to avoid. `views` = summed `view_count` over the `type=archive` window (D-05/D-07); empty window → `views=0` not `None` (D-08); `video_count=None` always (D-06); `followers=None` always (settled CLAUDE.md auth wall).

**Before writing this file:** RESEARCH.md's Open Question 1 and the CONTEXT.md "Specifics" section both require one live verification call (with and without `period=month`, diffed) before trusting the parser body — this is a manual step, not a code pattern, but it gates this file's correctness.

---

## Shared Patterns

### Lazy %-style logging (never f-strings)
**Source:** `src/creatorpulse/cli.py:11,24,26,29,32` (established), reaffirmed by RESEARCH.md Security Domain
**Apply to:** every new module that logs — `collector.py`, `db.py`, `sources/youtube.py`, `sources/twitch.py`, `config.py`'s `validate()`
```python
logger.info("Loaded %d creators", len(creators))
logger.error("Config file not found: %s", config_path)
```
Never `logger.info(f"...{value}")` — log-injection concern applies once creator-controlled strings (`creator.id`) enter log lines.

### `@dataclass(frozen=True, slots=True)` for all record/config types
**Source:** `src/creatorpulse/config.py:17-21` (`Creator`)
**Apply to:** `models.py`'s `MetricRecord`. No new dataclass in this phase should deviate from this decorator form.

### Injectable path/input parameters over hardcoded reads
**Source:** `src/creatorpulse/config.py:24` (`resolve_paths()`) and `:33` (`load_creators(path: Path = DEFAULT_CONFIG_PATH)`)
**Apply to:** `db.py`'s `connect(db_path: Path, *, create: bool)` — takes the path `resolve_paths()` returns, never invents its own default (Phase 2 D-06, binding).

### mypy `strict = true` for `src/`, loosened only for `tests/*`
**Source:** `pyproject.toml` lines 37-42
```toml
[tool.mypy]
strict = true

[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false
```
**Apply to:** every metric field typed `int | None` explicitly — strict mode is what forces D-03's NULL-handling to be real code, not an assumption. `ignore_missing_imports` stays scoped to `gspread.*` and `yaml` only (line 44-46) — `requests` ships its own types and must stay strictly checked; do not add an override for it.

### Test style: fixture-driven, `monkeypatch`/`caplog`, no live network
**Source:** `tests/test_config.py` (fixture-file-in, parsed-object-out) and `tests/test_paths.py:61-73` (`caplog.at_level("INFO", logger="creatorpulse")` pattern)
```python
with caplog.at_level("INFO", logger="creatorpulse"):
    run_collect(config_path, db_path)
```
**Apply to:** `test_collector.py` (reuse the `caplog` pattern for skip/retry/failure log-line assertions), `test_sources.py` (reuse `test_config.py`'s fixture-path convention — `Path(__file__).resolve().parent / "fixtures"` — combined with RESEARCH.md's `Mock(spec=requests.Response)` pattern for HTTP faking).

### `scripts/record_fixture.py` — the only sanctioned fixture recorder
**Source:** `scripts/record_fixture.py` (full file, 51 lines)
**Apply to:** recording every fixture under `tests/fixtures/youtube/*.json` and `tests/fixtures/twitch/*.json`. Guard rails already in place and must not be bypassed: `--source`/`--case` validated against `^[a-z0-9_]+$` before any network call (lines 30-33), path-containment check against `FIXTURES_ROOT` (lines 35-38), and `response.raise_for_status()` before saving (line 41) — a non-2xx response (e.g. a CAPTCHA/challenge page) is never saved as a fixture. Never invoked from `pytest` (module docstring, line 5).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/creatorpulse/db.py` | service | CRUD | No persistence code exists anywhere in the repo yet. RESEARCH.md's verified DDL/upsert/connect examples are the source of truth. |
| `src/creatorpulse/sources/__init__.py` | route/registry | event-driven | No `Protocol`-based registry pattern exists yet. RESEARCH.md Pattern 1 is authoritative. |
| `src/creatorpulse/sources/youtube.py` | service | request-response | First HTTP-integration module in the repo. RESEARCH.md's verified-against-official-docs example is authoritative. |
| `src/creatorpulse/collector.py` | controller | event-driven | First orchestration-loop module; only `cli.py`'s linear run_collect() exists as a loose logging/timing precedent. |
| `tests/test_db.py` | test | CRUD | No SQL test precedent exists; build from RESEARCH.md's Validation Architecture test map, following `tests/test_paths.py`'s general style (imports, `tmp_path` fixture usage) only. |

## Metadata

**Analog search scope:** `src/creatorpulse/` (3 existing files: `__init__.py`, `cli.py`, `config.py`), `tests/` (2 existing files: `test_config.py`, `test_paths.py`), `scripts/` (1 file: `record_fixture.py`), `pyproject.toml`.
**Files scanned:** 6 (entire existing codebase — this repo has no other source to search).
**Pattern extraction date:** 2026-08-04
