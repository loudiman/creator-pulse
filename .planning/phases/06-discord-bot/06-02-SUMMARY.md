---
phase: 06-discord-bot
plan: 02
subsystem: collector-failure-alerting
tags: [sqlite, requests, discord-webhook]

requires:
  - phase: 06-discord-bot
    plan: "01"
    provides: "DELTA_PLACEHOLDER moved to db.py, bot.py's MANILA fixed-offset pattern, the collector/bot process split"
provides:
  - "run_failures table + write_run_failures() in db.py — per-failure detail attributed to a runs row"
  - "write_run_row() returning the inserted runs id"
  - "RunFailure model, RunResult.failures — the shared shape the digest and /status will read in 06-03/06-05"
  - "build_alert_text() / _post_alert() in cli.py — the collector's webhook alert path, two call sites in run_collect"
affects: [06-03, 06-05]

tech-stack:
  added: []
  patterns:
    - "requests.post with json={content, allowed_mentions:{parse:[]}} against DISCORD_WEBHOOK_URL — the same payload shape Phase 5's Code.gs postToDiscord() already sends"
    - "alert POST wrapped in a narrow try/except requests.RequestException that logs and returns — never lets a broken webhook replace the exception in flight"

key-files:
  created: []
  modified:
    - src/creatorpulse/db.py
    - src/creatorpulse/models.py
    - src/creatorpulse/collector.py
    - src/creatorpulse/cli.py
    - tests/test_db.py
    - tests/test_collector.py
    - tests/test_bot.py

key-decisions:
  - "build_alert_text/_post_alert live in cli.py, not bot.py or a shared module — cli.py is the collector's controller and must never import bot.py, which would pull discord.py into the collector's import graph (verified: 'discord' not in sys.modules after importing creatorpulse.cli)"
  - "Sheets sync mocked out in the D-08 alert-path tests (sheets.sync patched to a no-op) so assertions about 'alert called exactly once' / 'zero POST calls' aren't entangled with the separate D-09 call site — the two call sites are tested independently"

patterns-established:
  - "Pure formatter (build_alert_text) separated from I/O boundary (_post_alert), mirroring build_digest_text/CreatorPulseBot's split in bot.py — build_alert_text reads only the in-memory RunResult, never the database, so the alert and the runs row cannot disagree about the count (D-08)"

requirements-completed: [BOT-03]

coverage:
  - id: D1
    description: "A run that records failures writes one run_failures row per failure, attributed to the run_id write_run_row returned"
    requirement: "BOT-03"
    verification:
      - kind: unit
        ref: "tests/test_db.py::test_write_run_row_returns_rowid_not_none"
        status: pass
      - kind: unit
        ref: "tests/test_db.py::test_write_run_failures_empty_sequence_writes_nothing_and_does_not_raise"
        status: pass
      - kind: unit
        ref: "tests/test_db.py::test_write_run_failures_round_trip_matches_run_id"
        status: pass
      - kind: unit
        ref: "tests/test_collector.py::test_one_source_failure_produces_one_run_failure_with_cause_and_message"
        status: pass
      - kind: unit
        ref: "tests/test_collector.py::test_registry_miss_writes_no_run_failure_row"
        status: pass
    human_judgment: false
  - id: D2
    description: "One alert per failing run, sent after collect_once returns and the runs row is committed, not from inside the per-pair except; a clean run makes zero POST calls"
    requirement: "BOT-03"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_run_collect_with_one_failure_calls_alert_path_exactly_once_and_still_returns_0"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_run_collect_with_zero_failures_does_not_call_the_alert_path"
        status: pass
    human_judgment: false
  - id: D3
    description: "A Sheets sync failure alerts too, from the except block that already exists, and a broken webhook never replaces the exception in flight"
    requirement: "BOT-03"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_run_collect_sheets_failure_and_broken_webhook_still_propagates_sheet_not_shared"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_post_alert_whose_post_raises_connection_error_logs_and_returns_without_raising"
        status: pass
    human_judgment: false
  - id: D4
    description: "No log record or alert body emitted by the alert path contains the webhook URL value"
    requirement: "BOT-03"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_post_alert_never_logs_the_webhook_url_value"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_post_alert_with_webhook_url_unset_logs_warning_naming_that_variable_and_returns"
        status: pass
    human_judgment: false
  - id: D5
    description: "\"Distinct from and earlier than the scheduled digest\" — the alert fires from the one-shot collector process the moment a failure is recorded, while the digest fires 15 minutes later from the long-lived bot process"
    requirement: "BOT-03"
    verification: []
    human_judgment: true
    rationale: "This is an observation across two processes and cannot be asserted by a unit test (flagged_assumptions in 06-02-PLAN.md). Carried forward to 06-UAT.md by 06-04 with the forced proof CONTEXT names: a bogus handle in creators.yaml, a hand-run collector, both messages in order in one screenshot."

duration: 8min
completed: 2026-08-06
status: complete
---

# Phase 6 Plan 2: Failures stop being a number and become a record Summary

**A new `run_failures` table plus a two-call-site Discord webhook alert path in `cli.py` — a source breaking now writes a queryable row and posts one message per run, immediately, from the collector, using no new dependency.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-06T16:42:54+08:00 (first commit of this plan)
- **Completed:** 2026-08-06T16:50:41+08:00
- **Tasks:** 2 of 2 committed
- **Files modified:** 7 (0 new, 7 modified)

## Accomplishments

- `run_failures` table appended to `SCHEMA_DDL` — no migration script, the live droplet database gains it on the next `connect(create=True)` (D-06)
- `write_run_row()` now returns the inserted `runs.id`; `write_run_failures(conn, run_id, failures)` writes one row per failure via `executemany`, committing once, no-op on an empty sequence
- `RunFailure` (frozen slots dataclass: `creator_id`, `source`, `cause`, `message`) added to `models.py`; `RunResult` gains `failures: tuple[RunFailure, ...]`
- `collect_once()`'s existing per-pair `except` block now captures the `type(exc).__name__` / `str(exc)` it already computed for the log line into a `RunFailure`, instead of discarding it; `finally` writes both the `runs` row and its failure rows in the same transaction context
- `build_alert_text(failures)` — pure formatter, header states the count, one line per failure — and `_post_alert(text)` — reads `DISCORD_WEBHOOK_URL`, POSTs `{content, allowed_mentions: {parse: []}}` with a 10s timeout, swallows its own `requests.RequestException` — both added to `cli.py`, never to `bot.py`
- Two call sites wired into `run_collect()`: after the "Run wrote N rows with M failures" log line (D-08, only when `failure_count > 0`), and inside the existing Sheets-sync `except` block before the `raise` (D-09)
- 12 new tests: 3 in `test_db.py`, 2 in `test_collector.py`, 7 in `test_bot.py` (all tagged so `pytest tests/test_bot.py -k alert` selects them, per the plan's validation command)

## Task Commits

Each task was committed atomically:

1. **Task 1: Failure detail becomes a row — the run_failures table and the collector that fills it** - `84b123f` (feat)
2. **Task 2: One alert per failing run, and one for a failed Sheets sync, neither able to swallow the real error** - `3bf1a35` (feat)

**Plan metadata:** this commit lands with the SUMMARY.

## Files Created/Modified

- `src/creatorpulse/db.py` - `run_failures` DDL, `_WRITE_RUN_FAILURE`, `write_run_failures()`, `write_run_row()` now returns `int`
- `src/creatorpulse/models.py` - `RunFailure` dataclass, `RunResult.failures` field
- `src/creatorpulse/collector.py` - per-pair except appends a `RunFailure`; `finally` captures `write_run_row`'s returned id and calls `write_run_failures`
- `src/creatorpulse/cli.py` - `WEBHOOK_TIMEOUT_SECONDS`, `build_alert_text()`, `_post_alert()`, two call sites in `run_collect()`, one added docstring sentence
- `tests/test_db.py` - 3 new tests for `write_run_row`'s returned id and `write_run_failures`'s empty/round-trip cases
- `tests/test_collector.py` - 2 new tests for `RunFailure` accumulation and the registry-miss-writes-nothing case; 1 existing test gained an invariant assertion (`len(result.failures) == result.failure_count`)
- `tests/test_bot.py` - 7 new tests covering `build_alert_text`, both `run_collect` call sites, `_post_alert`'s unset/failing/no-leak cases, and Sheets-failure-plus-broken-webhook propagation

## Decisions Made

- **The formatter and the POST helper live in `cli.py`, not `bot.py`.** `bot.py` must never import `cli.py`'s Sheets/gspread-adjacent surface, and `cli.py` must never import `bot.py` — doing either would pull `discord.py` or `gspread` across the collector/bot boundary D-02 draws. Verified live: `python -c "import creatorpulse.cli, sys; assert 'discord' not in sys.modules"` exits 0.
- **The D-08 and D-09 alert-path tests mock `sheets.sync` to a no-op** so a test asserting "the D-08 call site fired exactly once" isn't accidentally also exercising the D-09 call site (or vice versa) — the two call sites are independently testable per the plan's `<behavior>` block.

## Deviations from Plan

None — plan executed exactly as written. The only diff beyond the plan's action text is a mechanical `ruff format` pass on two long lines in `cli.py` (an f-string in `build_alert_text` and a `logger.error` call in `_post_alert`), applied automatically by the formatter step of the four-command gate, no behavior change.

## Issues Encountered

None.

## User Setup Required

None new. This plan reads `DISCORD_WEBHOOK_URL`, already set and verified live in Phase 5 (05-UAT.md) and reused unchanged here — no new environment variable, no new credential.

## Next Phase Readiness

- `run_failures` and `RunResult.failures` are the shared shape 06-03's digest banner and 06-05's `/status` command both read — this plan's share of D-06 is complete and does not need revisiting.
- The BOT-03 "distinct from and earlier than the scheduled digest" observation (coverage id D5 above) is deliberately left `human_judgment: true` and unclosed here — 06-04 lifts it into `06-UAT.md` with the forced-proof recipe CONTEXT already names (bogus handle, hand-run collector, one screenshot with both messages in order).
- No blockers for 06-03/06-04/06-05.

---
*Phase: 06-discord-bot*
*Completed: 2026-08-06*

## Self-Check: PASSED

- FOUND: src/creatorpulse/db.py (run_failures table, write_run_failures)
- FOUND: src/creatorpulse/models.py (RunFailure)
- FOUND: src/creatorpulse/collector.py (failures accumulation)
- FOUND: src/creatorpulse/cli.py (build_alert_text, _post_alert)
- FOUND: 84b123f (Task 1 commit)
- FOUND: 3bf1a35 (Task 2 commit)
