---
phase: 06-discord-bot
plan: "03"
subsystem: discord-bot
tags: [sqlite, digest-formatting, discord]

requires:
  - phase: 06-discord-bot
    plan: "02"
    provides: "run_failures table, RunFailure model, write_run_failures(), write_run_row() returning the inserted id"
provides:
  - "db.fetch_last_run() / db.LAST_RUN_SQL — the newest runs row, or None on an empty table"
  - "db.fetch_run_failures() / db.RUN_FAILURES_SQL — one run's failure rows, bound by ? parameter"
  - "bot.FLAG_THRESHOLD / bot.MOVER_FLAG / bot.staleness_hours() — the ±20% boundary and the 26h freshness comparison, both usable by 06-05's /status"
  - "build_digest_text() extended with a staleness banner, per-row ±20% flag, and a closing failures section — the complete BOT-01/BOT-02 digest"
affects: [06-04, 06-05]

tech-stack:
  added: []
  patterns:
    - "Fixed 2-char row prefix (MOVER_FLAG+space, or two blank spaces) on every mover row, so the creator/source column stays aligned in Discord's proportional font whether or not a row is flagged"
    - "Three-way freshness branch mirroring Code.gs's checkFreshness: no runs row -> could-not-determine banner, stale (>26h) -> banner naming timestamp+age, fresh -> no banner line at all"

key-files:
  created: []
  modified:
    - src/creatorpulse/db.py
    - src/creatorpulse/bot.py
    - tests/test_db.py
    - tests/test_bot.py

key-decisions:
  - "MOVER_FLAG is a single emoji character; the flagged-row prefix is MOVER_FLAG+space (2 chars) and the unflagged-row prefix is two literal spaces (2 chars) — equal width so Discord's proportional font can't visually stagger the creator/source column depending on which rows are flagged"
  - "The failures section is appended after the mover rows, not interleaved — one header line stating the count, one line per failure in build_alert_text's exact wording (creator / source — cause: message), or an explicit 'none' line on a clean run. Omitted entirely (not even a header) when there is no runs row, because the Task 1 could-not-determine banner already carries that fact and an empty-but-present failures header would misleadingly imply a run happened"
  - "round(hours) for the banner's '(Nh ago)' text, matching Code.gs's Math.round(ageHours) exactly rather than truncating or using .1f precision — the two surfaces render the same number for the same moment"

patterns-established:
  - "Every mover row is comparably column-prefixed regardless of flag state — a formatting discipline future digest sections (trend, status) should inherit if they ever render a similar per-row marker"

requirements-completed: [BOT-01, BOT-02]

coverage:
  - id: D1
    description: "A pair whose absolute day-over-day percent change strictly exceeds ±20% is flagged; a pair sitting at exactly ±20.0% is not — four named boundary tests, one per side"
    requirement: "BOT-02"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_digest_flag_pair_at_exactly_positive_threshold_is_not_flagged"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_flag_pair_one_step_over_positive_threshold_is_flagged"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_flag_pair_at_exactly_negative_threshold_is_not_flagged"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_flag_pair_one_step_over_negative_threshold_is_flagged"
        status: pass
    human_judgment: false
  - id: D2
    description: "The flag and the ordering read percent_change's unrounded float; only format_percent's rendered text is rounded — a row displaying +20.0% that is really +20.04% still carries the flag"
    requirement: "BOT-02"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_digest_flag_reads_the_unrounded_float_not_the_rounded_display_text"
        status: pass
    human_judgment: false
  - id: D3
    description: "A pair with no baseline, or a zero baseline, renders the shared em dash and is never flagged"
    requirement: "BOT-02"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_renders_delta_placeholder_for_missing_and_zero_baseline"
        status: pass
    human_judgment: false
  - id: D4
    description: "The staleness banner: exactly 26.0 hours reads fresh (no banner), 26h1min reads stale and names the timestamp and age, and an empty runs table produces a could-not-determine banner while still listing whatever metric rows exist"
    requirement: "BOT-01"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_staleness_hours_at_exactly_26_reads_fresh_and_digest_has_no_stale_banner"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_staleness_one_minute_past_26_hours_emits_stale_banner_naming_timestamp_and_age"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_on_no_runs_row_but_metrics_present_shows_could_not_determine_banner"
        status: pass
      - kind: unit
        ref: "tests/test_db.py::test_fetch_last_run_on_empty_runs_table_returns_none"
        status: pass
      - kind: unit
        ref: "tests/test_db.py::test_fetch_last_run_after_three_runs_returns_the_newest_one"
        status: pass
    human_judgment: false
  - id: D5
    description: "The digest closes with that run's failures — count, one line per failure naming creator/source/cause/message — or an explicit no-failures line on a clean run; a database with no runs row gets no failures section at all"
    requirement: "BOT-01"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_two_failures_names_both_creators_sources_and_causes"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_clean_run_ends_with_explicit_no_failures_line"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_names_only_the_newer_runs_failures_never_an_older_runs"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_digest_text_with_no_runs_row_has_no_failures_section"
        status: pass
      - kind: unit
        ref: "tests/test_db.py::test_fetch_run_failures_returns_only_rows_for_that_run_id"
        status: pass
      - kind: unit
        ref: "tests/test_db.py::test_fetch_run_failures_on_run_with_no_failures_returns_empty_list"
        status: pass
    human_judgment: false
  - id: D6
    description: "fetch_run_failures binds run_id as a ? parameter, never string-interpolated — the query shape 06-05's user-supplied /creator lookup will copy"
    requirement: "BOT-01"
    verification:
      - kind: other
        ref: "src/creatorpulse/db.py RUN_FAILURES_SQL — contains one ? placeholder, no % operator, f-string, or concatenation; run_id passed via the parameter tuple"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-08-06
status: complete
---

# Phase 6 Plan 3: The ±20% flag, the staleness banner, and the failures section Summary

**`build_digest_text()` now renders a three-way freshness banner (fresh/stale/could-not-determine), flags every mover strictly exceeding ±20% on the unrounded percent, and closes with that run's failure detail or an explicit "none" — the complete BOT-01/BOT-02 message, still one pure function reading only `db.py`.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-06T17:03Z (first commit of this plan)
- **Completed:** 2026-08-06T17:15Z
- **Tasks:** 2 of 2 committed
- **Files modified:** 4 (0 new, 4 modified)

## Accomplishments

- `db.fetch_last_run()` / `db.LAST_RUN_SQL` — newest `runs` row by `id DESC LIMIT 1`, or `None` on an empty table
- `bot.FLAG_THRESHOLD = 0.20`, `bot.MOVER_FLAG`, and a fixed 2-char row prefix (flag+space or two blank spaces) so flagged and unflagged rows stay column-aligned
- `bot.staleness_hours(finished_at, now)` — tz-aware ISO-8601 subtraction, no separate timezone handling needed since `runs.finished_at` already carries its UTC offset
- `build_digest_text()` gains a three-way freshness branch before the mover rows (no runs row → could-not-determine banner; stale → banner naming timestamp and rounded hours; fresh → no banner line), the strict `>FLAG_THRESHOLD` flag on the unrounded `percent_change()` float, and a closing failures section reading `db.fetch_run_failures()`
- `db.fetch_run_failures()` / `db.RUN_FAILURES_SQL` — `run_id` bound as a `?` parameter, ordered by `creator_id, source`
- 3 pre-existing 06-01 digest tests updated (setup-only: seeded a fresh `runs` row and adjusted line-slicing for the new row prefix) so they continue to prove the same ordering/placeholder behavior under the extended function — no assertion was weakened, one assertion was strengthened (added explicit `MOVER_FLAG not in ...` checks)
- 16 new tests: 4 in `test_db.py` (`fetch_last_run` ×2, `fetch_run_failures` ×2), 12 in `test_bot.py` (4 boundary-flag tests, 1 rounding-vs-flag test, 2 staleness tests, 1 no-runs-row banner test, 4 failures-section tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: The ±20% flag and the staleness banner** - `48c795e` (feat)
2. **Task 2: The digest lists that run's failures** - `f554d6b` (feat)

**Plan metadata:** this commit lands with the SUMMARY.

## Files Created/Modified

- `src/creatorpulse/db.py` - `LAST_RUN_SQL`/`fetch_last_run()`, `RUN_FAILURES_SQL`/`fetch_run_failures()`
- `src/creatorpulse/bot.py` - `FLAG_THRESHOLD`, `MOVER_FLAG`, `_UNFLAGGED_PREFIX`, `staleness_hours()`, `build_digest_text()` extended with the banner/flag/failures logic
- `tests/test_db.py` - 4 new tests (`fetch_last_run` empty/newest, `fetch_run_failures` scoped/empty)
- `tests/test_bot.py` - 14 new tests plus 3 pre-existing digest tests updated for the new row prefix

## Decisions Made

- **`MOVER_FLAG` prefix is exactly 2 characters wide in both states** (`"🚨 "` when flagged, `"  "` when not) — a deliberate column-alignment choice so a reader scanning the digest in Discord's proportional font sees a consistent left margin regardless of which rows are flagged, rather than flagged rows visually jumping right.
- **The failures section is entirely omitted (not an empty header) when there is no `runs` row.** The Task 1 could-not-determine banner already states that freshness — and therefore failure attribution — cannot be determined; a "Failures this run: 0" header in that state would misleadingly imply a run happened and simply had none.
- **`round(hours)` for the banner's age**, matching Code.gs's `Math.round(ageHours)` exactly (not `.1f`, not truncation) — the digest and the off-box watchdog report the same integer hour count for the same stale moment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug avoidance / mechanical consequence] Updated 3 pre-existing 06-01 digest tests for the new row prefix and mandatory freshness banner**
- **Found during:** Task 1, first `pytest tests/test_bot.py -x` run after adding the flag prefix
- **Issue:** `build_digest_text()`'s new column-alignment prefix (`"🚨 "` or `"  "` in front of every mover row) changed the first characters of every rendered row. Three tests from 06-01 (`test_digest_text_orders_rows_by_absolute_percent_change_descending`, `test_digest_text_places_row_with_no_computable_percent_after_every_row_that_has_one`, `test_digest_text_renders_delta_placeholder_for_missing_and_zero_baseline`) read the creator_id directly off the start of each line (`line.split(" / ")[0]`, `line.startswith(...)`, `line.split(" ", 1)[0]`) — all three broke immediately once the prefix landed. Separately, none of the three seeded a `runs` row, so the new could-not-determine banner would also have shifted their line indices.
- **Fix:** Added a `_drop_flag_prefix()` test helper (`line[2:]`) and applied it at the read sites; seeded a fresh `write_run_row(conn, now, now, ...)` in each test (same `now` passed to `build_digest_text`) so no banner line appears, keeping the mover rows at the same indices those tests already assumed. No existing assertion's expected value changed — the ordering, placeholder, and startswith checks assert exactly what they asserted in 06-01, against the same rendered content, read through a prefix-aware accessor. One test (`...renders_delta_placeholder...`) gained two additional assertions (`MOVER_FLAG not in ...`) proving the no-baseline/zero-baseline rows are never flagged, per this plan's `<behavior>` block.
- **Files modified:** tests/test_bot.py
- **Verification:** All 3 tests pass; full suite green at 133/133 after Task 1, 139/139 after Task 2.
- **Committed in:** `48c795e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (mechanical test-setup update, required by the plan's own explicit column-alignment and mandatory-banner instructions — not a behavioral weakening)
**Impact on plan:** No production behavior changed beyond what the plan specified. Test-weakening guard satisfied: every pre-existing assertion still checks the same fact against the same data, just reached through a prefix-stripping accessor; nothing was loosened or removed.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None. This plan is pure formatting logic over existing tables — no new environment variable, no new credential, no schema change.

## Verbatim rendered digest text (for 06-04's 06-UAT.md)

**Clean run** (fresh, no failures — `now = 2026-08-06T08:15:00+00:00`):

```
CreatorPulse digest — 2026-08-06
  kaicenat / youtube — 439,535,493 views (Δ +535,493, +0.1%)
  pokimane / youtube — 96,004,740 views (Δ +0, +0.0%)
  xqc / youtube — 1,903,001,878 views (Δ —)
Failures this run: none
```

**Stale run with one failure** (`finished_at = 2026-08-04T00:00:12+00:00`, `now = 2026-08-06T08:15:00+00:00`, 56h ago):

```
CreatorPulse digest — 2026-08-06
⚠ last run finished 2026-08-04T00:00:12+00:00 — STALE (56h ago)
🚨 kaicenat / youtube — 1,250,000 views (Δ +250,000, +25.0%)
Failures this run: 1
   mkbhd / youtube — ChannelNotFound: no channel for handle @mkbhd-typo
```

Both rendered by calling `build_digest_text()` directly against a `tmp_path` database seeded with `write_run_row`/`write_run_failures`/`upsert_metric` — the same technique 06-01's Task 3 checkpoint used for its live-channel proof, applicable unchanged here since the function is pure.

## Next Phase Readiness

- `bot.STALE_AFTER_HOURS`, `bot.staleness_hours()`, and `db.fetch_last_run()`/`db.fetch_run_failures()` are exactly the shared surface 06-05's `/status` command needs (D-17) — no rework required, only a new call site.
- `db.fetch_run_failures()`'s bound-parameter shape is the template 06-05's `/creator <name>` lookup should copy for its own untrusted input (T-06-01's stated purpose).
- The gate is green: 139 tests, `ruff format --check .` / `ruff check .` / `mypy src/` all clean.
- No blockers for 06-04 (UAT authoring) or 06-05 (slash commands).

---
*Phase: 06-discord-bot*
*Completed: 2026-08-06*

## Self-Check: PASSED

- FOUND: src/creatorpulse/db.py (fetch_last_run, fetch_run_failures)
- FOUND: src/creatorpulse/bot.py (FLAG_THRESHOLD, MOVER_FLAG, staleness_hours, extended build_digest_text)
- FOUND: 48c795e (Task 1 commit)
- FOUND: f554d6b (Task 2 commit)
