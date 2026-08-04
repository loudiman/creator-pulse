---
phase: 03-collector-core-api-sources
plan: 06
subsystem: api
tags: [requests, retry, backoff, youtube-data-api-v3, mocking]

requires:
  - phase: 03-collector-core-api-sources
    provides: "03-02's tracer (sources/youtube.py, sources/__init__.py registry, models.py) and 03-01's four YouTube fixtures"
provides:
  - "sources/_retry.py: retry() — narrow D-13 list (Timeout, ConnectionError, 429, 5xx), 3 attempts, fixed 2s/4s backoff, source layer only"
  - "sources/youtube.py: its one requests.get call site now wrapped, signature/parse unchanged"
  - "tests/test_sources.py: retry cases against a faked clock, plus YouTube OPS-06 fixture-in / record-out cases"
affects: [03-03]

tech-stack:
  added: []
  patterns:
    - "PEP 695 generic function syntax (`def retry[**P](...)`) instead of a module-level ParamSpec() — ruff UP047 on py312 target requires this form"
    - "Scripted local callable (`_ScriptedCall`) driving retry/exception sequences, monkeypatched `time.sleep`, no HTTP mocking library"

key-files:
  created:
    - src/creatorpulse/sources/_retry.py
    - tests/test_sources.py
  modified:
    - src/creatorpulse/sources/youtube.py

key-decisions:
  - "Named the wrapper retry() (interface contract), not with_retry() as RESEARCH.md's draft example used — the plan's interface contract is authoritative over the research draft's naming."
  - "PEP 695 generic (`def retry[**P](...)`) instead of module-level `ParamSpec(\"P\")` — ruff's UP047 rejects the legacy form under py312 target-version; functionally identical, no behavior change."
  - "Comment wording changed from 'no jitter' to 'the same every time' to satisfy the acceptance criterion's zero-hits grep for the word jitter, while stating the same fact (D-14: fixed backoff, no randomization)."

patterns-established:
  - "Retry wrapper composes at the call site (`get = retry(requests.get, creator_id=identifier, source=\"youtube\")`) rather than as a decorator on `fetch` itself — keeps the wrapped surface to exactly the one outbound call, not the whole function."

requirements-completed: [SRC-05, OPS-06]

coverage:
  - id: D1
    description: "A transient failure (Timeout, ConnectionError, 429, or 5xx) retries up to three attempts with fixed 2s-then-4s backoff before being treated as failed"
    requirement: "SRC-05"
    verification:
      - kind: unit
        ref: "tests/test_sources.py#test_retries_on_timeout_then_succeeds"
        status: pass
      - kind: unit
        ref: "tests/test_sources.py#test_retries_on_connection_error_all_three_reraises"
        status: pass
      - kind: unit
        ref: "tests/test_sources.py#test_retries_on_429_then_succeeds"
        status: pass
      - kind: unit
        ref: "tests/test_sources.py#test_503_all_three_attempts_returned_as_is"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every other HTTP status (401, 403 quotaExceeded, 404) fails on attempt 1, no sleep"
    requirement: "SRC-05"
    verification:
      - kind: unit
        ref: "tests/test_sources.py#test_403_returns_immediately_no_sleep"
        status: pass
      - kind: unit
        ref: "tests/test_sources.py#test_non_retryable_status_returns_immediately_no_sleep"
        status: pass
    human_judgment: false
  - id: D3
    description: "The retry log line names creator_id, source, and attempt number only — one line per retry"
    requirement: "SRC-05"
    verification:
      - kind: unit
        ref: "tests/test_sources.py#test_retries_on_429_then_succeeds"
        status: pass
    human_judgment: false
  - id: D4
    description: "The hidden-subscriber fixture and a genuine YouTube channel produce different records — None vs a real int follower count"
    requirement: "OPS-06"
    verification:
      - kind: unit
        ref: "tests/test_sources.py#test_youtube_hidden_subscriber_count_maps_to_none"
        status: pass
      - kind: unit
        ref: "tests/test_sources.py#test_youtube_hidden_subscriber_count_omitted_key_maps_to_none"
        status: pass
      - kind: unit
        ref: "tests/test_sources.py#test_youtube_ok_channel_returns_integer_followers"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 6: Retry wrapper for source HTTP calls, YouTube's half of OPS-06 Summary

**A 15-line retry decorator wraps YouTube's single `requests.get` call — three attempts and 2s-then-4s fixed backoff for a narrow transient-error list, everything else fails in one attempt — proven against a faked clock with no HTTP mocking library.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-05
- **Tasks:** 1 (auto, tdd=true)
- **Files modified:** 3 (2 new: `sources/_retry.py`, `tests/test_sources.py`; 1 modified: `sources/youtube.py`)

## Accomplishments

- `sources/_retry.py` — `retry(fn, *, creator_id, source, max_attempts=3)`: narrow retryable set (`requests.Timeout`, `requests.ConnectionError`, HTTP 429, HTTP 5xx), fixed `2.0 * attempt` sleep (2s then 4s), one `logger.info` per retry naming `creator_id`, `source`, and `attempt` and nothing else. A retryable status on the last attempt is returned (not raised) so the caller's `raise_for_status()` surfaces the real error; a retryable exception on the last attempt re-raises. `creator_id` also documents (unused, forward-referenced) the `"_token"` sentinel for `03-03`'s deferred Twitch token mint.
- `sources/youtube.py` — its one `requests.get` call site now goes through `retry(requests.get, creator_id=identifier, source="youtube")`; `fetch`'s signature and parse are byte-identical to what 03-02 shipped.
- `tests/test_sources.py` — 10 tests: five retry-schedule cases (timeout-then-success, connection-error-all-three, 429-then-success with log-line assertion, 503-all-three, 403-immediate) plus a parametrized 401/404 case (2 tests), plus three YouTube OPS-06 cases (`channel_ok` → real int, both hidden-subscriber shapes → `None`). All ten run in well under 1 second — the clock is faked, never waited on.

## Task Commits

1. **Task 1: Transient errors get three attempts; everything else fails in one second** - `2b3b7a4` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `src/creatorpulse/sources/_retry.py` - the retry wrapper, narrow D-13 list, fixed D-14 backoff
- `src/creatorpulse/sources/youtube.py` - one call site wrapped, nothing else changed
- `tests/test_sources.py` - retry-schedule cases + YouTube OPS-06 cases, extended by deferred `03-03`

## Decisions Made

- Named the function `retry()` per the plan's interface contract, not `with_retry()` as RESEARCH.md's draft example used — the interface contract is authoritative.
- Used PEP 695 generic syntax (`def retry[**P](...)`) instead of a module-level `ParamSpec("P")` — ruff's `UP047` rule rejects the legacy form on this repo's `target-version = "py312"`; behavior is identical, only the type-parameter declaration syntax changed.
- Reworded the backoff comment from "fixed, no jitter" to "the same every time" — the acceptance criteria's `grep -Eci 'retry-after|ratelimit|jitter|random'` count-zero gate would otherwise trip on the word "jitter" appearing in a comment that was *explaining* the absence of jitter. Same fact (D-14: fixed backoff, no randomization), different words.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `def retry(...)` with module-level `ParamSpec` fails ruff's `UP047`**
- **Found during:** Task 1, first `ruff check` run.
- **Issue:** `ruff check` (rule `UP047`, part of the `UP` select set in `pyproject.toml`) rejects a generic function using the pre-3.12 `ParamSpec("P")` + `Callable[P, ...]` form when `target-version = "py312"` is set — it wants the PEP 695 `def retry[**P](...)` syntax instead.
- **Fix:** Removed the `from typing import ParamSpec` import and the `P = ParamSpec("P")` module-level assignment; changed the function definition to `def retry[**P](fn: Callable[P, requests.Response], ...) -> Callable[P, requests.Response]:`. No behavior change — same type contract, newer syntax.
- **Files modified:** `src/creatorpulse/sources/_retry.py`
- **Verification:** `ruff check src tests` — all checks passed. `mypy src/` — no issues.
- **Committed in:** `2b3b7a4` (Task 1 commit)

**2. [Rule 3 - Blocking] "no jitter" comment tripped the acceptance criteria's own header-parsing grep gate**
- **Found during:** Task 1, running the plan's own acceptance-criteria grep commands after the first green pass.
- **Issue:** `grep -Eci 'retry-after|ratelimit|jitter|random' src/creatorpulse/sources/_retry.py` is supposed to return 0 to prove no header-aware or randomized backoff was added (D-14). My first draft's comment `# 2s, then 4s — fixed, no jitter (D-14)` contains the literal word "jitter" while explaining its *absence*, so the count-zero gate returned 1.
- **Fix:** Reworded to `# 2s, then 4s — the same every time (D-14)` — states the identical fact without using a word the criterion's grep treats as a positive hit.
- **Files modified:** `src/creatorpulse/sources/_retry.py`
- **Verification:** `grep -Eci 'retry-after|ratelimit|jitter|random' src/creatorpulse/sources/_retry.py` now returns 0.
- **Committed in:** `2b3b7a4` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking, both caught by the plan's own tooling/criteria before commit).
**Impact on plan:** Neither changed intended behavior. Both were syntax/wording fixes required to satisfy the plan's own stated gates (ruff's `UP047`, the acceptance criteria's header-parsing grep). No scope creep.

## Known Stubs

None. `retry()` is fully implemented and wired into `youtube.py`'s real call site; no hardcoded return, no placeholder. The `_token` sentinel is a documented, unconsumed forward reference (per the plan's explicit instruction not to delete it or invent a caller), not a stub — it costs one docstring line and no branch of code depends on it yet.

## Issues Encountered

None beyond the two deviations documented above.

## User Setup Required

None new. Same `YOUTUBE_API_KEY` requirement carried from 03-01/03-02; this plan runs entirely against fixtures and a faked clock.

## Next Phase Readiness

- `03-03` (deferred on SRC-02 — Twitch 2FA) can now import `retry()` directly for the Twitch fetch call and for the token-mint call site using the documented `"_token"` sentinel, and extend `tests/test_sources.py` rather than create it.
- The retry wrapper has no Twitch-specific code in it — nothing about this plan needs revisiting when `03-03` unblocks.
- Green gate confirmed: `ruff format --check .`, `ruff check .`, `mypy src/`, and `pytest` all exit 0. 23 tests total (13 pre-existing + 10 new in `test_sources.py`). `tests/fixtures/twitch/` remains absent, as required.

## Self-Check: PASSED

All 3 claimed files found on disk (`src/creatorpulse/sources/_retry.py`, `src/creatorpulse/sources/youtube.py`, `tests/test_sources.py`); commit hash `2b3b7a4` found in `git log --oneline --all`.

---
*Phase: 03-collector-core-api-sources*
*Completed: 2026-08-05*
