# Phase 5: Apps Script - Pattern Map

**Mapped:** 2026-08-06
**Files analyzed:** 2 (both new)
**Analogs found:** 0 exact / 2 (no in-repo JS precedent exists — see below)

## Headline fact for the planner

This repo is 100% Python. There is no `.gs`, no `.js`, no JavaScript anywhere in the tree.
**Neither new file has a syntactic analog in this codebase.** Do not treat any Python file as a
template for Apps Script syntax — imports, classes, and error types do not translate (Apps Script
has no `import`, no modules, global functions only). What follows is what genuinely transfers: the
data contract Apps Script binds to, and the codebase's conventions (fail-loud, secrets-out,
NULL-vs-placeholder) that the `.gs` code should mirror in spirit, in JS, by hand.

## File Classification

| New File | Role | Data Flow | In-repo Analog | Match Quality |
|----------|------|-----------|-----------------|---------------|
| `apps-script/Code.gs` | controller/event-handler (menu, trigger, webhook) | event-driven + request-response (outbound webhook) | none (no JS in repo) | no analog — see Shared Patterns for the conventions to mirror |
| `apps-script/appsscript.json` | config/manifest | static config | none (no comparable manifest file; closest *spirit* match is `pyproject.toml`'s flat key=value config style) | no analog |

## Pattern Assignments — the Dashboard contract Code.gs must bind to

**Source:** `src/creatorpulse/sheets.py` — read in full, lines 1-191. Do not modify this file.

**Tab name and write range** (lines 14, 173):
```python
DASHBOARD_TAB = "Dashboard"
...
range_name = f"A1:F{len(values)}"
```
Column G is never touched by Python. `Code.gs` reads A, B, E, F and writes formatting to E only.

**Exact header strings, column order A→F** (lines 33-40):
```python
HEADERS: list[str] = [
    "Creator",
    "Source",
    "Followers (coarse)",
    "Views",
    "Δ Views",
    "Last updated (UTC)",
]
```
Column G (`Status`) is not in this list — it's outside the Python write and lives only in the live
Sheet (per CONTEXT.md's frozen contract table). Column indices for `Code.gs` (1-based, `getRange`
style): A=1 Creator, B=2 Source, C=3 Followers, D=4 Views, E=5 Δ Views, F=6 Last updated, G=7 Status.

**`DELTA_PLACEHOLDER`** (line 15, used at line 89):
```python
DELTA_PLACEHOLDER = "—"  # em dash; 04-02 puts a real number beside it
...
(DELTA_PLACEHOLDER if views is None or prev_views is None else views - prev_views,)
```
This is the literal em-dash (U+2014, `—`), written into cell E as **text**, not a number, when no
prior-day baseline exists. This is exactly why SCRIPT-04's `whenNumberGreaterThan`/`whenNumberLessThan`
rules skip those cells by construction (RESEARCH.md Pattern 3 / D-11) — no special-case needed in
`Code.gs`.

**Column F timestamp production** (`sheets.py` reads it from SQL; the value itself is produced in
`src/creatorpulse/sources/youtube.py:49` and `src/creatorpulse/db.py:107`):
```python
collected_at=datetime.now(UTC),          # sources/youtube.py:49 — a datetime object
"collected_at": record.collected_at.isoformat(),   # db.py:107 — serialized for SQLite storage
```
`db.py:19` documents the column as `TEXT NOT NULL, -- ISO-8601 UTC timestamp`. `datetime.isoformat()`
on a UTC-aware datetime produces a string like `2026-08-06T00:12:34.567891+00:00` — `T` separator,
6-digit microseconds, `+00:00` offset (not `Z`). This is exactly RESEARCH.md's Pitfall 4 / Assumption
A1 concern: confirm empirically whether Sheets' `USER_ENTERED` auto-converts this to a `Date` or
leaves it as text before writing `checkFreshness()`'s date math. The `sync()` write itself uses
`value_input_option=ValueInputOption.user_entered` (`sheets.py:176`), which is the API-level knob
that controls this.

**Write call, for context on how F lands** (`sheets.py:176`):
```python
worksheet.update(values, range_name, value_input_option=ValueInputOption.user_entered)
```

## Shared Patterns — conventions to mirror in JS, not code to copy

### 1. Fail loudly on missing configuration, name the fix in the message

**Source:** `src/creatorpulse/config.py` lines 49-58 (`resolve_sheets_config`) and
`src/creatorpulse/sheets.py` lines 18-25, 120-157 (`SheetNotShared`, `SheetsKeyfileUnusable`).

The convention, stated generally: a missing/blank required setting returns a sentinel (`None`) so
the *caller* decides to fail loudly, or — when the failure is deep enough that "return None and let
the caller check" would be awkward — raises a **named exception whose message states which
environment variable or setting is missing and what the fix is**. Example (`sheets.py:124-128`):
```python
except (OSError, json.JSONDecodeError) as exc:
    raise SheetsKeyfileUnusable(
        f"service-account key file {keyfile} is missing or not valid JSON — check "
        f"CREATORPULSE_SHEETS_KEYFILE ({exc})"
    ) from exc
```
**Apply to:** `Code.gs`'s webhook-URL getter (D-13's throw-on-missing-property). RESEARCH.md's own
`getWebhookUrl()` example already follows this shape correctly — treat it as validated against this
codebase's own convention, not just invented for this phase:
```javascript
if (!url) {
  throw new Error(
    'DISCORD_WEBHOOK_URL is not set. Project Settings > Script Properties > add ' +
      'DISCORD_WEBHOOK_URL with the Discord webhook URL.'
  );
}
```
Same shape as Python: name the missing setting, name the fix, in one string.

### 2. NULL vs placeholder vs zero — never merge them

**Source:** `sheets.py` lines 77-80, 87-89 (see excerpt above) — `None` → empty cell, `0` →
literal zero, "no baseline" → the em-dash placeholder. Three distinct states, three distinct
renderings, never coalesced.

**Apply to:** nothing new in `Code.gs` writes data, but the *reading* side must respect this: a cell
holding the em-dash is not "0 delta," it's "no comparison available," and the conditional-format
rule must not attempt to special-case it into green/red — RESEARCH.md's Pattern 3 already gets this
right by relying on non-numeric skip rather than parsing the placeholder.

### 3. Retry conventions — narrow, source-layer only, not a general-purpose library

**Source:** `src/creatorpulse/sources/_retry.py`, full file (56 lines).
```python
_RETRYABLE_EXC = (requests.Timeout, requests.ConnectionError)
_RETRYABLE_STATUS = {429}


def _is_retryable_status(status_code: int) -> bool:
    return status_code in _RETRYABLE_STATUS or status_code >= 500
```
3 attempts, fixed 2s-then-4s backoff (`time.sleep(2.0 * attempt)`), logs each retry, re-raises/returns
on final attempt. This exists because the Python side makes network calls to flaky third-party APIs
across a whole collector run with many creators.

**Does NOT apply to `Code.gs` as-is.** RESEARCH.md's "Don't Hand-Roll" table already reaches the
same conclusion independently: Apps Script's `UrlFetchApp.fetch` call is one POST, at most a
handful of times a day (one watchdog check, occasional Status edits) — not a batch loop over many
creators. The correct posture, matching this repo's *proportionality* judgment (retry cost must be
justified by call volume) rather than its retry *code*, is: no retry loop, `muteHttpExceptions: true`,
log a non-2xx response instead of swallowing it. Do not port `_retry.py`'s logic into `Code.gs`.

### 4. Per-unit failure isolation + guaranteed record of the run

**Source:** `src/creatorpulse/collector.py` lines 1-3, 24, 36-38, 55-57 — a `try/finally` around the
whole run guarantees a `runs` row is written even on a mid-run crash, and a per-(creator, source)
`try/except` (line 38) means one source's failure doesn't take down the others.

**Apply to `Code.gs` only as a naming/scoping precedent**, not literally: `checkFreshness()` should
not let one unparseable timestamp abort the whole newest-timestamp scan (RESEARCH.md's own example
already does this correctly — it skips unparseable rows via the `isNaN` guard rather than throwing).
There's no "guaranteed run record" equivalent needed in Apps Script — the Executions log already
plays that role natively (D-07's reasoning), so nothing needs to be built to replicate `runs`.

### 5. Secrets never enter the repo

**Source:** `.gitignore` (full file, 32 lines) — `.env` / `*.env` blocked, `!.env.example` allowed
through (i.e., a same-named `.example` file with blank values is the tracked, safe artifact),
`service-account*.json`, `credentials*.json`, `token*.json` all blocked. Nothing Sheets- or
Discord-specific is listed because no such secret has ever lived in a repo file — the service
account key lives outside the tree (`CREATORPULSE_SHEETS_KEYFILE` env var, per `config.py:55`) and
now the Discord webhook URL follows the same shape via Script Properties (D-13), a Google-hosted
equivalent of an env var scoped to the Apps Script project.

**Apply to `apps-script/`:** no `.gitignore` entry is needed for `apps-script/Code.gs` or
`appsscript.json` — both are meant to be committed in full (D-04's explicit point: the repo *is*
the artifact). There is no secret-shaped file this phase produces; `DISCORD_WEBHOOK_URL` lives only
in Script Properties, pasted by hand, never written to any file in the tree. Confirm no plan task
proposes committing a `.env`-style file for the webhook URL — that would contradict D-13.

### 6. The four-command gate's reach over `apps-script/`

**Source:** `pyproject.toml`, full file (49 lines) — verbatim:
```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
strict = true

[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false

[[tool.mypy.overrides]]
module = ["gspread.*", "yaml"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```
No `exclude`/`include`/`files` key anywhere. `ruff check .`/`ruff format --check .` discover files by
extension (`.py`, `.pyi`) by default — a bare `[tool.ruff]` block with no `include` does not widen
that to `.gs`/`.json`. `mypy src/` (per ROADMAP's Definition of Green) is invoked with an explicit
`src/` path argument, not a bare `mypy .`, so it never walks into a top-level `apps-script/`
directory regardless of file extension. `pytest`'s `testpaths = ["tests"]` never looks outside
`tests/`. **This confirms RESEARCH.md's Wave-0 assumption from the config alone** — the planner's
one remaining task is to actually *run* `ruff format --check .` and `ruff check .` after
`apps-script/` exists and confirm zero findings, per RESEARCH.md's own recommendation, rather than
trust this reading alone.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `apps-script/Code.gs` | controller/event-handler | event-driven, request-response | No JavaScript exists anywhere in this repo. RESEARCH.md's own Code Examples section (Patterns 1-4, lines ~236-676 of `05-RESEARCH.md`) is the only available syntactic template — sourced from Google's own docs, not from this codebase — and the planner should treat it as the primary reference for `.gs` syntax. |
| `apps-script/appsscript.json` | config manifest | static config | No comparable manifest file exists. RESEARCH.md's Code Examples section has a minimal correct manifest (`timeZone: Asia/Manila`, `runtimeVersion: V8`, `exceptionLogging: STACKDRIVER`) — use that, not any in-repo file, as the template. |

## Metadata

**Analog search scope:** entire `src/creatorpulse/` tree (Python only — confirmed no `.gs`/`.js`
files exist via directory read), `pyproject.toml`, `.gitignore`. No `apps-script/` directory exists
yet (pre-phase state).
**Files read in full:** `src/creatorpulse/sheets.py` (191 lines), `src/creatorpulse/sources/_retry.py`
(56 lines), `pyproject.toml` (49 lines), `.gitignore` (32 lines).
**Files read partially (targeted):** `src/creatorpulse/config.py` (lines 30-95, `resolve_paths`/
`resolve_sheets_config`/`validate`), `src/creatorpulse/collector.py` (grep-located try/except/finally
lines only).
**Pattern extraction date:** 2026-08-06
