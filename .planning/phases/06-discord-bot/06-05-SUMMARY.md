---
phase: 06-discord-bot
plan: "05"
subsystem: discord-bot
tags: [sqlite, slash-commands, discord]

requires:
  - phase: 06-discord-bot
    plan: "03"
    provides: "db.fetch_last_run()/fetch_run_failures(), bot.FLAG_THRESHOLD/staleness_hours()/STALE_AFTER_HOURS — the shared surface /status reuses"
provides:
  - "db.fetch_known_creators() / db.KNOWN_CREATORS_SQL — the known-slugs list D-15's unknown-name reply names"
  - "db.fetch_creator_trend() / db.CREATOR_TREND_SQL — one creator's full (source, metric_date, views) history, creator_id bound"
  - "bot.build_trend_text() / bot.TREND_LIMIT — /creator's formatter, seven-row-per-source window applied in Python"
  - "bot.build_status_text() — /status's formatter, reusing fetch_last_run/staleness_hours/STALE_AFTER_HOURS so the digest and /status can never disagree about staleness"
  - "/creator and /status registered on CreatorPulseBot's tree"
affects: [06-04]

tech-stack:
  added: []
  patterns:
    - "Case-insensitive exact match via str.lower() against a Python list from fetch_known_creators() — never str.casefold(), because config._SLUG_RE already constrains every creator_id to lowercase ASCII"
    - "Seven-row-per-source trend window applied in Python after one indexed SQL read (WHERE creator_id = ?), not as a SQL LIMIT — a flat LIMIT 7 would interleave two sources into 3.5 days each the moment a creator has more than one source"
    - "Delta computed within the displayed window only: the oldest line shown always carries the em dash, even when older rows exist beyond the seven-row cut"

key-files:
  created: []
  modified:
    - src/creatorpulse/db.py
    - src/creatorpulse/bot.py
    - tests/test_db.py
    - tests/test_bot.py

key-decisions:
  - "The orchestrator's two pre-resolved deviations implemented as directed: seven rows PER SOURCE (not a flat LIMIT 7), and --digest-now ships permanently (already present from 06-01, unchanged by this plan)"
  - "Trend views render blank on NULL (build_dashboard_rows's rule), not the digest's em-dash-for-views rule — matches D-16's 'same NULL rules as the digest' instruction read against the more specific build_dashboard_rows precedent for the views column itself"
  - "build_status_text's failure lines reuse the exact (creator_id, source, cause, message) shape db.fetch_run_failures returns — same rows the digest and the collector's own alert read, so all three surfaces can never disagree about one run's failures"
  - "DatabaseNotInitialized is allowed to propagate uncaught from both command handlers — a bot answering while pointed at a nonexistent database is the failure mode this project refuses at every boundary, not something to paper over with a friendly reply"

patterns-established:
  - "Any future command reading a per-creator or per-run detail should copy fetch_creator_trend's bound-? shape for its own untrusted or semi-trusted input (T-06-01's stated purpose, now demonstrated twice: once on a trusted integer in 06-03, once on Discord user input here)"

requirements-completed: [BOT-04, BOT-05]

coverage:
  - id: D1
    description: "/creator matches a stored slug case-insensitively and exactly (mixed case, whitespace-padded, exact) and never on a substring or a non-ASCII lookalike"
    requirement: "BOT-04"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_matches_mixed_case_name"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_matches_whitespace_padded_name"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_does_not_match_a_substring_of_a_known_slug"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_dotted_capital_i_does_not_match"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unknown name lists every known slug; an empty database says so instead of an empty list"
    requirement: "BOT-04"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_unknown_name_lists_known_slugs"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_empty_database_says_no_creators_recorded_yet"
        status: pass
    human_judgment: false
  - id: D3
    description: "One day renders one line with the em dash; three days render three lines newest-first with the oldest carrying the em dash; more than seven days render exactly seven lines per source with the oldest shown still carrying the em dash"
    requirement: "BOT-04"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_single_day_creator_renders_one_line_with_delta_placeholder"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_three_days_renders_three_lines_newest_first_oldest_placeholder"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_more_than_seven_days_renders_exactly_seven_lines"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_two_sources_render_in_separate_blocks"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_null_views_renders_blank_and_next_day_carries_placeholder"
        status: pass
    human_judgment: false
  - id: D4
    description: "A name containing a quote and a SQL fragment returns the unknown-name reply and raises no database error; CREATOR_TREND_SQL binds creator_id, never interpolates"
    requirement: "BOT-04"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_creator_trend_name_with_quote_and_sql_fragment_returns_unknown_reply"
        status: pass
      - kind: unit
        ref: "tests/test_db.py::test_creator_trend_sql_binds_creator_id_not_interpolated"
        status: pass
      - kind: other
        ref: "test \"$(grep -cE 'f\\\"[^\\\"]*(SELECT|WHERE)' src/creatorpulse/db.py)\" -eq 0 — no f-string SQL in db.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "/status reports no-run-recorded (never a fabricated OK) on an empty runs table; exactly 26.0 hours reads OK and 26h1min reads STALE, the same STALE_AFTER_HOURS constant and comparison the digest banner uses"
    requirement: "BOT-05"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_status_text_no_runs_row_reports_not_recorded_and_no_ok"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_status_text_run_exactly_26_hours_old_reports_ok"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_status_text_run_26_hours_one_minute_old_reports_stale"
        status: pass
      - kind: other
        ref: "grep -v '^ *#' src/creatorpulse/bot.py | grep -c 'STALE_AFTER_HOURS' == 4 (>= 3 required)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Duration renders finished_at-started_at in seconds to one decimal place, including sub-tenth-of-a-second runs; rows_written and failure_count are reported as stored, never recomputed; two failures name both failing sources, a clean run names none"
    requirement: "BOT-05"
    verification:
      - kind: unit
        ref: "tests/test_bot.py::test_status_text_duration_renders_with_exactly_one_decimal_place"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_status_text_duration_under_tenth_of_second_still_renders_a_number"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_status_text_reports_stored_rows_written_and_failure_count"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_status_text_two_failures_names_both_failing_sources"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_status_text_zero_failures_names_no_sources"
        status: pass
      - kind: unit
        ref: "tests/test_bot.py::test_status_text_contains_no_environment_value"
        status: pass
    human_judgment: false

duration: ~15min
completed: 2026-08-06
status: complete
---

# Phase 6 Plan 5: /creator and /status Summary

**Two new slash commands close out the "and the place you ask about them" half of Phase 6 — `/creator <name>` matches a stored slug case-insensitively and exactly, rendering a seven-row-per-source trend with the digest's NULL-vs-0 and em-dash discipline; `/status` reports the last run's timing, rows, failures, and an honest OK/STALE verdict that shares its threshold and comparison direction with the digest banner, so the two surfaces can never disagree.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-08-06 (continuation of Phase 6 execution, plan 4 of 5)
- **Completed:** 2026-08-06
- **Tasks:** 2 of 2 committed
- **Files modified:** 4 (0 new, 4 modified)

## Accomplishments

- `db.fetch_known_creators()` / `db.KNOWN_CREATORS_SQL` — `SELECT DISTINCT creator_id ... ORDER BY creator_id`, the known-slugs list D-15's unknown-name reply names
- `db.fetch_creator_trend()` / `db.CREATOR_TREND_SQL` — `WHERE creator_id = ?` bound, `ORDER BY source, metric_date DESC`, one indexed read against `idx_metrics_creator_date`; the seven-row-per-source cut is applied in Python (`bot.TREND_LIMIT`), not as a SQL `LIMIT`, because a flat limit would silently interleave two sources into 3.5 days each the moment a creator gets a second source — the deviation the orchestrator pre-approved
- `bot.build_trend_text(conn, name)` — `.strip().lower()` fold against `fetch_known_creators()`'s output (never `.casefold()`, `config._SLUG_RE` reasoning documented inline); unknown name lists known slugs or states the database is empty; matched name renders one block per source, newest-first, with delta computed against the next-older row *within the displayed seven-row window* — the oldest line shown always carries the em dash even when older history exists beyond the cut
- `bot.build_status_text(conn, now)` — no `runs` row reports "No run has been recorded yet" and never fabricates OK; otherwise reports finish timestamp, duration (`finished_at - started_at` to one decimal place), rows written, failure count, and a `STALE`/`OK` verdict computed by the same `staleness_hours()` and `STALE_AFTER_HOURS` the digest banner uses — exactly 26.0 hours reads OK on both surfaces
- `/creator` and `/status` registered on `CreatorPulseBot`'s tree via a new `_register_commands()` called from `__init__`; both handlers open a short-lived `db.connect(create=False)`, call one pure formatter, close in a `finally`, and reply with `allowed_mentions=discord.AllowedMentions.none()` — no `defer()`, no module-level connection, `DatabaseNotInitialized` propagates uncaught
- 24 new tests: 4 in `test_db.py` (`fetch_known_creators` empty/alphabetical, `fetch_creator_trend` ordering/grouping, plus a direct `CREATOR_TREND_SQL` bound-parameter assertion), 24 in `test_bot.py` (14 `/creator` behavior tests including a SQL-fragment-in-name injection probe, 10 `/status` behavior tests including the 26.0h/26h1min boundary pair)

## Task Commits

Each task was committed atomically:

1. **Task 1: /creator — exact case-insensitive match, seven-day trend, known-slug list on a miss** - `e4a1d3d` (feat)
2. **Task 2: /status — last run, duration, rows, failures, and an honest verdict** - `31d947d` (feat)

## Files Created/Modified

- `src/creatorpulse/db.py` - `KNOWN_CREATORS_SQL`/`fetch_known_creators()`, `CREATOR_TREND_SQL`/`fetch_creator_trend()`
- `src/creatorpulse/bot.py` - `TREND_LIMIT`, `build_trend_text()`, `build_status_text()`, `_register_commands()` with the `/creator` and `/status` handlers, `app_commands` import
- `tests/test_db.py` - 4 new tests for the two new reads
- `tests/test_bot.py` - 24 new tests (14 `/creator`, 10 `/status`)

## Decisions Made

- **Seven rows per source, not a flat `LIMIT 7`** — the orchestrator's pre-approved deviation from D-16's literal wording, implemented as directed with the required code comment (`db.py`'s `CREATOR_TREND_SQL` comment and `bot.py`'s `TREND_LIMIT` comment both explain why).
- **Trend views render blank on NULL, matching `build_dashboard_rows`'s Sheet-column rule**, not the digest's em-dash-for-views rule — D-16 says "same NULL/`—` rules as the digest," and the more specific precedent for the *views* column specifically is the Sheet's blank-cell rendering; the em dash is reserved for the delta.
- **`--digest-now` already shipped permanently in 06-01** — the orchestrator's second pre-approved point required no action this plan; verified unchanged in `cli.py`.
- **`DatabaseNotInitialized` propagates uncaught from both new handlers**, matching the plan's explicit instruction and the project's fail-loudly discipline — no friendly reply papers over a bot pointed at a nonexistent database.

## Deviations from Plan

None beyond the orchestrator's two pre-resolved decisions, both implemented exactly as directed (see Decisions Made above) — no new deviation was introduced during implementation.

## Issues Encountered

None. The four-command gate passed clean on the first run after each task; `ruff format .` reformatted two multi-line `upsert_metric` calls in a `test_db.py` test into single lines (mechanical, no behavior change).

## User Setup Required

None. This plan adds two read-only queries and two pure formatters over existing tables — no new environment variable, no new credential, no schema change.

## Verbatim rendered command text (for 06-04's 06-UAT.md)

Captured live against the real dev-machine database (`creatorpulse.db`, real collected rows for kaicenat/pokimane/xqc plus the `mkbhd` orphan — see STATE.md's data-shape notes) by calling `build_trend_text()`/`build_status_text()` directly, the same technique 06-03 used for the digest:

**`/creator kaicenat`** (mixed-case input, matches the stored slug `kaicenat`):

```
Recent trend for kaicenat:
kaicenat / youtube
  2026-08-06: 439,535,493 views (Δ +0)
  2026-08-05: 439,535,493 views (Δ -655,464,507)
  2026-08-04: 1,095,000,000 views (Δ —)
```

(The 08-04→08-05 delta is the synthetic seed row giving way to the real collected number, per STATE.md's recorded data-shape note — not a real metric movement. 08-05→08-06 is the YouTube view-count cache not having rolled over, so `Δ +0` — a real zero, never coalesced from NULL.)

**`/creator mkbhd`** (the deliberate bogus-handle orphan — one recorded day, no baseline):

```
Recent trend for mkbhd:
mkbhd / youtube
  2026-08-05: 5,517,991,783 views (Δ —)
```

**`/creator nobody`** (unknown name):

```
No creator named 'nobody' — known creators: kaicenat, mkbhd, pokimane, xqc
```

**`/status`** (against the live database's newest run):

```
Last run finished 2026-08-06T00:00:07.958346+00:00 — OK
Duration: 0.4s
Rows written: 3
Failures: 0
```

## Next Phase Readiness

- Both commands are implemented, tested, and registered on the tree `setup_hook` already syncs guild-scoped — no rework needed for 06-04's `06-UAT.md` entry 4, which can cite the verbatim text above alongside a live Discord screenshot.
- The gate is green: 166 tests, `ruff format --check .` / `ruff check .` / `mypy src/` all clean.
- This plan shares no file with 06-04 (per its own frontmatter) and nothing depends on it — the cut-order item 1 discipline (D-14) held: had time run out, this file could still have been deleted cleanly with zero rework elsewhere.
- No blockers for 06-04 or for closing out Phase 6.

---
*Phase: 06-discord-bot*
*Completed: 2026-08-06*

## Self-Check: PASSED

- FOUND: src/creatorpulse/db.py (fetch_known_creators, fetch_creator_trend)
- FOUND: src/creatorpulse/bot.py (TREND_LIMIT, build_trend_text, build_status_text, _register_commands)
- FOUND: e4a1d3d (Task 1 commit)
- FOUND: 31d947d (Task 2 commit)
