---
phase: 03-collector-core-api-sources
plan: 02
subsystem: database
tags: [sqlite, youtube-data-api-v3, requests, dataclasses, upsert]

requires:
  - phase: 03-collector-core-api-sources
    provides: "03-01's four YouTube fixtures (channel_ok, channel_not_found, two hidden-subs derived) and the channel_not_found items-key-absent finding"
provides:
  - "models.py: MetricRecord (nine fields, D-01/D-02 columns), RunResult"
  - "db.py: SCHEMA_DDL, UPSERT_METRIC, connect(create=True), upsert_metric, write_run_row — WAL + busy_timeout on every connection"
  - "sources/__init__.py: KNOWN_PLATFORMS, SourceFetcher Protocol, FETCHERS registry (youtube only)"
  - "sources/youtube.py: fetch() — flag-first hidden-subscriber-count parse, ChannelNotFound on empty/absent items"
  - "collector.py: collect_once() — metric_date computed once, per-pair loop, registry-miss skip, runs row"
  - "cli.py: real collect command — connect + collect_once + close + exit code from failure_count"
affects: [03-03, 03-04, 03-05]

tech-stack:
  added: []
  patterns:
    - "flag-first normalization: read the documented boolean field before the value field it gates, so both possible API shapes of the gated field collapse to the same NULL outcome"
    - "data.get('items') + explicit named exception, never data['items'] — an absent collection key is a real API shape, not a bug to KeyError on"

key-files:
  created:
    - src/creatorpulse/models.py
    - src/creatorpulse/db.py
    - src/creatorpulse/sources/__init__.py
    - src/creatorpulse/sources/youtube.py
    - src/creatorpulse/collector.py
    - tests/test_collector.py
  modified:
    - src/creatorpulse/cli.py
    - tests/test_paths.py

key-decisions:
  - "Task 1 (D-01/D-02 confirmation gate): option-a selected — advisory gate, pre-resolved 2026-08-05, not re-litigated. Ship the nine-column metrics shape with video_count and is_live, engagement_rate removed."
  - "youtube.py reads data.get('items'), not data['items'] — the recorded channel_not_found.json fixture has no items key at all (pageInfo.totalResults=0), contradicting the RESEARCH.md/D-18 empty-list assumption. Both shapes (absent key, empty list) now raise the same named ChannelNotFound."
  - "tests/test_paths.py::test_run_collect_logs_both_resolved_paths needed the same fixture+env-var mocking test_collector.py uses — cli.py's seam is no longer a stub, so the pre-existing test would otherwise make a live YouTube call (or KeyError on a missing YOUTUBE_API_KEY) inside pytest."
  - "Tracer feedback gate ran automated: Phase 3 was explicitly authorised for unattended execution (Task 1's pre-resolved note), so the four-command green gate stood in for the interactive human-verify stop and this plan completed in one pass rather than pausing after committing the tracer."

patterns-established:
  - "Source module normalization boundary: branch on the documented flag, never on the value it gates — a conditional expression (`None if hidden else int(...)`) so the gated field is never evaluated on the hidden path, not a read-then-branch."

requirements-completed: [SRC-01, SRC-04, DATA-01, DATA-02, DATA-03, DATA-04, RUN-05]

coverage:
  - id: D1
    description: "One creatorpulse collect walk: creators.yaml -> registry -> real YouTube parse -> SQLite metrics row -> one runs row, proven end to end with only the HTTP socket faked"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_end_to_end_collect_once_writes_metrics_and_one_run"
        status: pass
    human_judgment: false
  - id: D2
    description: "Re-running the same collection leaves the metrics row count unchanged and appends a second runs row"
    requirement: "DATA-02"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_idempotent_rerun_same_date_leaves_metrics_count_unchanged"
        status: pass
    human_judgment: false
  - id: D3
    description: "A row at an earlier metric_date survives a later run untouched"
    requirement: "DATA-04"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_row_at_earlier_metric_date_survives_untouched"
        status: pass
    human_judgment: false
  - id: D4
    description: "hiddenSubscriberCount=true maps followers to NULL under both API shapes (subscriberCount present as \"0\", and subscriberCount key absent) — the flag is read before the value on both paths"
    requirement: "SRC-04"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_youtube_hidden_subscriber_count_maps_to_none"
        status: pass
      - kind: unit
        ref: "tests/test_collector.py#test_youtube_hidden_subscriber_count_omitted_key_maps_to_none"
        status: pass
    human_judgment: false
  - id: D5
    description: "An empty/absent items collection (bogus handle) raises ChannelNotFound rather than becoming a row of NULLs"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_youtube_not_found_raises"
        status: pass
    human_judgment: false
  - id: D6
    description: "An undocumented missing field (viewCount absent) raises rather than silently returning a partial record"
    requirement: "SRC-04"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_youtube_missing_view_count_raises"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 2: The tracer — one creator, one source, one real row end to end Summary

**`creators.yaml` reads through a registry dispatch to a real YouTube Data API v3 parse, lands in SQLite via a named-placeholder upsert, and closes with a `runs` row — six new modules and one CLI seam, proven by one test that drives all of them at once.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-08-05
- **Tasks:** 2 (Task 1: checkpoint:decision, advisory, no commit; Task 2: tracer, tdd=true)
- **Files modified:** 8 (6 new source/test files, 2 modified: `cli.py`, `tests/test_paths.py`)

## Accomplishments

- `models.py` — `MetricRecord` (nine fields, D-01/D-02 columns: `video_count`, `is_live` added, `engagement_rate` removed) and `RunResult`, both `@dataclass(frozen=True, slots=True)` matching `Creator`'s form.
- `db.py` — `SCHEMA_DDL` (the `metrics`/`runs` tables, `UNIQUE (creator_id, source, metric_date)`), `UPSERT_METRIC` (named placeholders only), `connect(create=True)` (WAL + `busy_timeout=5000` on every connection, no default path invented, no `mkdir`), `upsert_metric` (raises on blank `creator_id`, never substitutes zero for `None`), `write_run_row`.
- `sources/__init__.py` — `KNOWN_PLATFORMS` frozenset, `SourceFetcher` Protocol, `FETCHERS` dict holding only `"youtube"` (twitch/tiktok stay unregistered).
- `sources/youtube.py` — `fetch()` reads `hiddenSubscriberCount` before ever touching `subscriberCount`, so both possible API shapes of a hidden count collapse to `followers=None`; raises `ChannelNotFound` on an absent/empty `items` collection; raises `KeyError` on an undocumented missing field (`viewCount`).
- `collector.py` — `collect_once()`: `metric_date` computed once before the loop (RUN-05), one registry-miss skip line per unregistered source, `upsert_metric` + `write_run_row` per D-01 shape. No HTTP or retry knowledge (deferred to 03-05).
- `cli.py` — the `logger.warning("Collector body is not implemented yet...")` seam is gone; `run_collect` now opens the database, runs the collector, and returns `0`/`1` from `failure_count`.
- `tests/test_collector.py` — 7 tests: the end-to-end slice, idempotent re-run, prior-date survival, both hidden-subscriber-count shapes, not-found raise, undocumented-field raise.

## Task Commits

1. **Task 1: Confirm the metrics column set (advisory, pre-resolved)** — no commit (decision recorded only, no file changes; see Decisions Made)
2. **Task 2: One creator, one source, one real row — end to end** - `e7baef1` (feat)

## Files Created/Modified

- `src/creatorpulse/models.py` - `MetricRecord`, `RunResult`
- `src/creatorpulse/db.py` - schema, upsert, connect(create=True), write_run_row
- `src/creatorpulse/sources/__init__.py` - registry + Protocol
- `src/creatorpulse/sources/youtube.py` - fetch() and the normalization boundary
- `src/creatorpulse/collector.py` - collect_once() orchestration loop
- `src/creatorpulse/cli.py` - real `collect` seam
- `tests/test_collector.py` - the 7-test end-to-end slice
- `tests/test_paths.py` - added fixture/env mocking so the pre-existing `run_collect` test doesn't hit a live call now that the seam is real

## Decisions Made

- **Task 1, option-a selected.** The nine-column `metrics` shape ships as D-01/D-02 wrote it: `creator_id, source, metric_date, followers, views, likes, video_count, is_live, collected_at`. This is a confirmation of an already-locked decision (03-CONTEXT.md D-01), not a new choice — the gate was downgraded to advisory on 2026-08-05 and this plan did not stop for it, per the pre-resolved note in the plan text.
- **Wave 1 finding applied.** `channel_not_found.json` has no `items` key at all (not an empty list), contradicting RESEARCH.md/D-18's assumption. `sources/youtube.py` uses `body.get("items")` and raises a named `ChannelNotFound` — both the absent-key shape and a hypothetical empty-list shape now produce the same explicit error instead of a bare `KeyError`.
- **`tests/test_paths.py` fixture-mocking added.** Not in the plan's `files_modified` list, but required: `cli.py`'s seam is no longer a stub, so the existing `test_run_collect_logs_both_resolved_paths` test would otherwise call `os.environ["YOUTUBE_API_KEY"]` inside pytest with no such variable set (`KeyError`), or attempt a live network call if it were set — both forbidden. Fixed by reusing the exact `Mock(spec=requests.Response)` + `monkeypatch.setenv` pattern `test_collector.py` uses. This is not a weakened assertion; the test's own assertions (both resolved paths appear in the log) are unchanged.
- **Tracer feedback gate ran automated, not interactively.** Phase 3 was explicitly authorised for unattended execution (Task 1's pre-resolved note: "authorised unattended execution of Phase 3" on 2026-08-05). The tracer's own `<verify>` (the four-command green gate) was re-run end to end and passed, so this plan completed in one pass — logged here rather than pausing with a separate `checkpoint:human-verify` after the Task 2 commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `youtube.fetch` uses `data.get("items")` with an explicit raise, not `data["items"]`**
- **Found during:** Task 2, before writing any code — flagged by the Wave 1 finding in this executor's own prompt, confirmed independently by reading `tests/fixtures/youtube/channel_not_found.json` (no `items` key, `pageInfo.totalResults: 0`).
- **Issue:** RESEARCH.md's verified code example and D-18 both assumed a bogus handle returns HTTP 200 with an empty `items: []` list. The recorded fixture shows the key is absent entirely. `data["items"]` would raise `KeyError`, which technically satisfies "raise on a bogus channel" but produces a confusing failure message at 3am instead of a named `ChannelNotFound`.
- **Fix:** `items = body.get("items")`, then `if not items: raise ChannelNotFound(...)`. Handles both the absent-key shape (proven) and a hypothetical empty-list shape (never observed, but harmless to also cover) identically.
- **Files modified:** `src/creatorpulse/sources/youtube.py`
- **Verification:** `tests/test_collector.py::test_youtube_not_found_raises` reads the real recorded fixture and asserts `ChannelNotFound` is raised.
- **Committed in:** `e7baef1` (Task 2 commit)

**2. [Rule 3 - Blocking] `tests/test_paths.py` needed fixture/env mocking to avoid a live call**
- **Found during:** Task 2, running `pytest tests/test_paths.py -x` after wiring `cli.py`'s real seam.
- **Issue:** `test_run_collect_logs_both_resolved_paths` calls the real `run_collect(config_path, db_path)` with no HTTP mocking and no `YOUTUBE_API_KEY` set. With the seam now real, this crashed with `KeyError: 'YOUTUBE_API_KEY'` inside `os.environ["YOUTUBE_API_KEY"]` — a hard block on the plan's own acceptance criterion "`pytest tests/test_paths.py -x` exits 0."
- **Fix:** Added the same `monkeypatch.setenv("YOUTUBE_API_KEY", ...)` + `Mock(spec=requests.Response)` pattern `test_collector.py` uses, patched onto `creatorpulse.sources.youtube.requests.get`. The test's original assertions (both resolved paths appear in the caplog) are untouched.
- **Files modified:** `tests/test_paths.py`
- **Verification:** `pytest tests/test_paths.py -x` exits 0 (5 passed).
- **Committed in:** `e7baef1` (Task 2 commit)

**3. [Rule 1 - Bug] Test's "prior date" fixture computed with the wrong clock**
- **Found during:** Task 2, first run of `test_row_at_earlier_metric_date_survives_untouched` — failed with `2500000 == 111`.
- **Issue:** The test computed `yesterday = date.today() - timedelta(days=1)` using the local (PHT, UTC+8) clock, while `collect_once` computes `metric_date` from `datetime.now(UTC).date()` (RUN-05). Near local midnight the two dates can be the same UTC day, so the "prior date" row collided with and was overwritten by the run's own upsert — exactly the false-negative the test exists to catch, caused by the test's own clock choice rather than the code under test.
- **Fix:** Compute `yesterday` from `datetime.now(UTC).date() - timedelta(days=1)` — the same clock the collector uses — guaranteeing the fixture date is always strictly earlier than the run's `metric_date`.
- **Files modified:** `tests/test_collector.py`
- **Verification:** `pytest tests/test_collector.py -x` — all 7 pass.
- **Committed in:** `e7baef1` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 bug in the source module found via the Wave 1 finding, 1 blocking test-infrastructure gap, 1 bug in the new test's own clock choice). 0 architectural changes, 0 checkpoints beyond the plan's own advisory Task 1.
**Impact on plan:** All three were necessary for correctness or for the plan's own stated acceptance criteria to pass. No scope creep — no file outside the plan's dependency-order build list was touched except `tests/test_paths.py`, which was a direct, unavoidable consequence of the seam becoming real.

## Known Stubs

None. Every code path in this task's `<files>` list does real work — no hardcoded empty return, no "coming soon" placeholder, no component wired to mock data. Twitch and TikTok remain genuinely unregistered (D-09's known-but-unimplemented case, logged as a skip line, not stubbed as a fetcher that returns fake data).

## Issues Encountered

None beyond the three deviations documented above, all resolved within Task 2.

## User Setup Required

None new. A real `YOUTUBE_API_KEY` is still required for a live (non-fixture) run of `creatorpulse collect` on the VPS — already noted as outstanding in 03-01's SUMMARY and unchanged by this plan, which runs entirely against fixtures.

## Next Phase Readiness

- 03-03 (Twitch source, SRC-05 retry) can now follow `sources/youtube.py` as its sibling-shape analog, and register `FETCHERS["twitch"]` alongside the existing `"youtube"` entry without touching `collector.py`.
- 03-04 (`config.validate()`) attaches ahead of `load_creators()` in `cli.py`, in the space the plan text deliberately left open.
- 03-05 (`connect(create=False)`, the per-pair `try`/`except` failure counter, and the `try`/`finally` runs-row guarantee) has a clean seam: `collector.py`'s loop currently has no exception handling by design, and `db.py`'s `connect(create=False)` branch currently raises `NotImplementedError` naming 03-05.
- The green gate (`ruff format --check .`, `ruff check .`, `mypy src/`, `pytest`) passes with 13 tests total (6 pre-existing + 7 new). `tests/fixtures/twitch/` remains absent, as required.
- No live YouTube call has been made yet in this phase — the manual D-18 gate (bogus-handle run, journal output pasted into `03-UAT.md`) is still pending and belongs to a later plan or the phase's manual verification step.

## Self-Check: PASSED

All 8 claimed files found on disk; commit hash `e7baef1` found in `git log --oneline --all`.

---
*Phase: 03-collector-core-api-sources*
*Completed: 2026-08-05*
