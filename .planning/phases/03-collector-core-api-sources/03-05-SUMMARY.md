---
phase: 03-collector-core-api-sources
plan: 05
subsystem: database
tags: [sqlite, failure-isolation, upsert, null-vs-zero]

requires:
  - phase: 03-collector-core-api-sources
    provides: "03-02's tracer (models.py, db.py connect(create=True), collector.py's happy-path loop), 03-04's validate() gate ahead of load_creators()"
provides:
  - "db.py: DatabaseNotInitialized, connect(create=False) — reads never create; WAL + busy_timeout on both branches"
  - "collector.py: one try/except per (creator, source) pair (D-15), a db-write failure propagates through the outer try/finally instead of being counted per-pair (D-16)"
  - "tests/test_db.py: 12 tests — DDL idempotency, upsert-not-duplicate, prior-date immutability, create=False both failure modes, the never-COALESCE round trip, single-process concurrent-read proof"
  - "tests/test_collector.py: 9 new tests — failure isolation, no short-circuit, two-source log lines, empty-message exception, order preservation, registry-miss skip, shared metric_date, crash-guarantee, idempotent same-day rerun"
  - "03-UAT.md: 5 entries recorded PENDING with explicit not_closed_reason and close-later commands; Gaps section records Phase 3 PARTIAL"
affects: [03-03 (still deferred), Phase 6 (bot read path), Phase 7 (/status honesty)]

tech-stack:
  added: []
  patterns:
    - "per-pair try/except wraps only the fetch call, never the upsert — a source's transient failure is isolated per D-15, but a database write failure is systemic and is left to propagate through the outer try/finally so it is never silently counted as one more source failure"
    - "fake two-key in-memory fetcher registry (monkeypatch.setitem on collector.FETCHERS) drives every orchestration test — no real second source, no live network, no credential"

key-files:
  created:
    - tests/test_db.py
  modified:
    - src/creatorpulse/db.py
    - src/creatorpulse/collector.py
    - tests/test_collector.py
    - .planning/phases/03-collector-core-api-sources/03-UAT.md

key-decisions:
  - "upsert_metric is deliberately outside the per-pair try/except boundary. A source-fetch failure is isolated per D-15; a db.upsert_metric failure is not — it propagates out of collect_once (through the try/finally, which still writes the runs row with counts reached so far), because a write failure means every subsequent pair would fail identically and silently swallowing that per-pair would misreport a systemic outage as N independent source failures. Verified by test_runs_row_written_on_crash, which asserts the exception propagates and the runs row reflects only the work done before the crash."
  - "Task 3's precondition (real droplet access, real credentials) was re-checked and confirmed unmet: no SSH access from this executor, no .env file, no YOUTUBE_API_KEY or TWITCH_CLIENT_ID/SECRET anywhere in this environment. Per the plan's unmet-precondition-protocol, all five 03-UAT.md entries were written PENDING with an explicit not_closed_reason and the exact commands that will close each one later, rather than stopping the run or fabricating output."
  - "Entry 4 was further split rather than left as one flat PENDING: Part B (the never-COALESCE round-trip proof, requiring no source/credential/droplet) was actually run on this machine and its real pytest output pasted into the evidence block; Part A (real YouTube evidence from a droplet run) and the Twitch-instance flag stay open. The entry's overall result stays pending because Part A — the entry's live-database claim — is what's actually unmet."

requirements-completed: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, RUN-01, RUN-02, RUN-05, OPS-05, OPS-07]

coverage:
  - id: D1
    description: "connect(create=False) raises DatabaseNotInitialized on a missing file (creating nothing) and on an existing file with no metrics table (closing the connection before raising, not leaving a locked handle)"
    requirement: "DATA-05"
    verification:
      - kind: unit
        ref: "tests/test_db.py#test_connect_create_false_missing_file_raises_and_creates_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_db.py#test_create_false_raises_on_missing_table"
        status: pass
    human_judgment: false
  - id: D2
    description: "A stored 0 and a stored NULL round-trip as distinct and non-equal, proven with four separate identity assertions (never a truthiness check) at the SQL layer, needing no source or fixture"
    requirement: "DATA-02"
    verification:
      - kind: unit
        ref: "tests/test_db.py#test_stored_null_and_zero_round_trip_distinct"
        status: pass
    human_judgment: false
  - id: D3
    description: "Two upserts with the same (creator_id, source, metric_date) leave one row with the second call's values; a different metric_date never touches the prior row"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/test_db.py#test_upsert_same_key_updates_not_duplicates"
        status: pass
      - kind: unit
        ref: "tests/test_db.py#test_upsert_different_date_does_not_touch_prior_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "One try/except boundary per (creator, source) pair: one fetcher raising leaves the rest of the run intact, failure_count counts pairs not creators, and there is no short-circuit after repeated failures of the same source"
    requirement: "RUN-01"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_one_source_failure_does_not_abort_run"
        status: pass
      - kind: unit
        ref: "tests/test_collector.py#test_one_failing_source_fails_every_creator_no_short_circuit"
        status: pass
      - kind: unit
        ref: "tests/test_collector.py#test_processing_order_matches_file_order_after_failure"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every failure names the creator, source, and exception type separately from the message, even when the exception message is empty; two failing sources on one creator produce two distinct log lines"
    requirement: "RUN-02"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_two_failing_sources_on_one_creator_produce_two_log_lines"
        status: pass
      - kind: unit
        ref: "tests/test_collector.py#test_failure_with_empty_message_still_names_creator_and_source"
        status: pass
    human_judgment: false
  - id: D6
    description: "metric_date is computed once before the loop and every row from one run shares it"
    requirement: "RUN-05"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_all_rows_from_one_run_share_metric_date"
        status: pass
    human_judgment: false
  - id: D7
    description: "Once the database is open, a try/finally always appends the runs row with counts reached so far and re-raises the original exception, even when the failure is a database write (not a source fetch)"
    requirement: "DATA-03"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_runs_row_written_on_crash"
        status: pass
    human_judgment: false
  - id: D8
    description: "Running the collector twice with a pinned metric_date leaves the metrics row count unchanged and appends two runs rows, without asserting value equality (a real re-fetch can legitimately differ)"
    requirement: "OPS-05"
    verification:
      - kind: integration
        ref: "tests/test_collector.py#test_idempotent_rerun_same_day"
        status: pass
    human_judgment: false
  - id: D9
    description: "A registry with no entry for a creator's source produces zero rows, zero failures, and one skip line — a skip is neither a row nor a failure"
    requirement: "RUN-01"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_registry_miss_produces_skip_and_no_failure"
        status: pass
    human_judgment: false
  - id: D10
    description: "The failure-isolation unit tests prove exception isolation against a monkeypatched raise; OPS-07's own flagged assumption records that this cannot prove every real failure mode, which is exactly what the deferred D-18 bogus-handle manual gate (03-UAT.md entry 3) exists to close"
    requirement: "OPS-07"
    verification:
      - kind: unit
        ref: "tests/test_collector.py#test_one_source_failure_does_not_abort_run"
        status: pass
    human_judgment: false
  - id: D11
    description: "Five human-observed proofs against real API data on the real droplet database, required by ROADMAP's Definition of Green from Phase 3 onward — a new creator with no code change, twice-daily idempotency, a real bogus-handle failure, NULL-vs-0 on real YouTube rows plus the flagged-open Twitch instance, and a concurrent read during a live write"
    verification: []
    human_judgment: true
    rationale: "No SSH access to the droplet and no real credentials exist in this environment (Task 3's precondition re-checked and confirmed unmet). All five 03-UAT.md entries are recorded PENDING with an explicit not_closed_reason and the exact commands to close each one later — this is a genuine outstanding gate, not a skipped one, and ROADMAP is explicit that no automated check substitutes for it."

duration: 30min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 5: Failure isolation, the crash guarantee, and the reader's door Summary

**`connect(create=False)` raises `DatabaseNotInitialized` instead of silently creating an empty database; `collect_once()` isolates each source's fetch failure per pair while a database write failure propagates through the guaranteed `runs`-row `try`/`finally`; 21 new tests prove it, and 03-UAT.md records honestly that the phase's human-observed real-data gate stays open.**

## Performance

- **Duration:** ~30 min
- **Completed:** 2026-08-05
- **Tasks:** 3 (Task 1: auto/tdd, Task 2: auto/tdd, Task 3: checkpoint:human-verify/advisory, handled per unmet-precondition-protocol)
- **Files modified:** 5 (`db.py`, `collector.py`, `tests/test_collector.py`, `03-UAT.md` modified; `tests/test_db.py` created)

## Accomplishments

- `db.py` — `DatabaseNotInitialized` exception; `connect(create=False)` opens via a `mode=rw` URI, catches `OperationalError` on a missing file, and separately checks `sqlite_master` for the `metrics` table on an existing-but-empty file, closing the connection before raising either way. WAL + `busy_timeout=5000` apply to both branches, set once, before the `if create:` that follows.
- `tests/test_db.py` — 12 tests, all fixtures-only against `tmp_path`: DDL creation and idempotency, upsert-updates-not-duplicates, prior-date immutability (byte-identical row), both `create=False` failure modes plus the success path, both pragmas on both branches, an empty-`creator_id` `ValueError`, NULL-vs-0 distinguishable in SQL, the four-assertion `test_stored_null_and_zero_round_trip_distinct`, and a single-process concurrent-read-without-lock-error proof.
- `collector.py` — the per-pair `try`/`except Exception` now wraps only the `fetch()` call (D-15): on failure it logs `fetch failed creator=%s source=%s cause=%s: %s` and `continue`s, with no short-circuit and no cross-pair state. `upsert_metric` sits outside that boundary; the whole loop is now wrapped in `try`/`finally` so the `runs` row is always appended with counts reached so far, and the original exception (from a source *or* a database write) re-raises afterward (D-16).
- `tests/test_collector.py` — 9 new tests, all driven by a fake two-key in-memory registry (`monkeypatch.setitem` on `collector.FETCHERS`), never the real YouTube fetcher: one-fails-one-succeeds, no-short-circuit-across-creators, two-failures-two-log-lines, empty-exception-message, processing-order-after-failure, registry-miss-is-a-skip, shared-`metric_date`, `runs`-row-on-crash (via a monkeypatched `db.upsert_metric`), and idempotent same-day rerun (clock pinned via a `datetime` subclass, never the real UTC clock).
- `03-UAT.md` — Task 3's precondition was re-checked, not trusted from the note: no SSH access, no `.env`, no credentials anywhere in this environment. All five entries recorded `pending` with an explicit `not_closed_reason` and the exact commands that will close each one, usable as a one-sitting checklist. Entry 4 was split: Part B (the never-COALESCE round trip, needing no droplet) was actually run here and its real `pytest` output pasted; Part A (real YouTube evidence) and the Twitch-instance flag (SRC-02) stay open. A `## Gaps` section records Phase 3 closing PARTIAL.

## Task Commits

1. **Task 1: The reader's door, and the SQL layer proven at the SQL layer** — `37ac9b6` (feat)
2. **Task 2: One boundary per pair, and a runs row even when the job dies** — `9e5aa3b` (feat)
3. **Task 3: The five pasted proofs** — `2b4302e` (docs; unmet-precondition-protocol applied, task not marked verified)

## Files Created/Modified

- `src/creatorpulse/db.py` - `DatabaseNotInitialized`, `connect(create=False)` reader door
- `tests/test_db.py` - 12 new tests, the SQL-layer proofs
- `src/creatorpulse/collector.py` - per-pair `try`/`except`, outer `try`/`finally` guarantee
- `tests/test_collector.py` - 9 new tests, the orchestration proofs
- `.planning/phases/03-collector-core-api-sources/03-UAT.md` - 5 entries PENDING with reasons and close-later commands, `## Gaps` recording PARTIAL

## Decisions Made

- **`upsert_metric` lives outside the per-pair boundary, by design, not oversight.** The plan's `<behavior>` list requires a `db.upsert_metric` failure to propagate out of `collect_once` (proven by `test_runs_row_written_on_crash`), while a source-fetch failure must be isolated per pair (D-15). Wrapping both together would satisfy the "wrap fetch-and-upsert" phrasing in the action text literally, but would then silently count a systemic database outage as N independent source failures — the fixed log-line shape (`fetch failed ...`) and the specific crash-test behavior both point at fetch-only wrapping, so that's what shipped. See key-decisions above for the full reasoning.
- **Task 3's advisory gate was not rubber-stamped.** The plan explicitly instructs re-checking the precondition rather than trusting the note that it's unmet — this executor did check (no SSH, no env file, no credentials found) and confirmed the note's claim independently before writing `03-UAT.md`.
- **Entry 4's Part B was actually executed, not described.** `pytest tests/test_db.py::test_stored_null_and_zero_round_trip_distinct -v` was run for real on this machine and its unmodified output pasted into the evidence block — the one piece of entry 4 that doesn't need a droplet, closed honestly rather than left as a bare PENDING with no evidence at all.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `mode=rw` grep gate tripped by its own explanatory comment**
- **Found during:** Task 1, running the green-gate acceptance checks after the first `connect()` draft.
- **Issue:** The comment above the `create=False` branch originally repeated the literal substring `mode=rw` ("...under a mode=rw URI"), making `grep -c 'mode=rw' src/creatorpulse/db.py` return `2` instead of the required `1` — the same class of negative-grep trip the environment notes flagged as having happened twice already in this phase.
- **Fix:** Reworded the comment to "under this read-only URI" — same meaning, no second match.
- **Files modified:** `src/creatorpulse/db.py`
- **Verification:** `grep -c 'mode=rw' src/creatorpulse/db.py` → `1`; full green gate re-run clean.
- **Committed in:** `37ac9b6` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (a prose grep-gate self-trip, not a behavior bug). 0 architectural changes, 0 checkpoints beyond the plan's own advisory Task 3.
**Impact on plan:** Necessary for the plan's own stated acceptance criteria to pass. No scope creep — no file outside the plan's `files_modified` list was touched.

## Known Stubs

None. Every code path in `db.py` and `collector.py` does real work — no hardcoded empty return, no "coming soon" placeholder. The advisory Task 3 gap (real-data UAT) is not a stub; it is an honestly-recorded outstanding manual verification step, tracked in `03-UAT.md`'s `## Gaps`.

## Issues Encountered

None beyond the one deviation documented above.

## User Setup Required

**Unchanged from prior plans, now the blocking item for phase close.** A real `YOUTUBE_API_KEY` (and, once SRC-02 unblocks, `TWITCH_CLIENT_ID`/`TWITCH_CLIENT_SECRET`) must land in `/etc/creatorpulse/creatorpulse.env` on the droplet, and `creatorpulse collect` must be run there against `/var/lib/creatorpulse/creatorpulse.db`, before any of the five `03-UAT.md` entries can close. See `03-UAT.md`'s `## Gaps` for the full breakdown and the exact commands.

## Next Phase Readiness

- **Phase 3 closes PARTIAL, not complete.** Automated coverage (`ruff format --check .`, `ruff check .`, `mypy src/` strict, `pytest`) is green — 63 tests, ~1-3s. The eight `03-VALIDATION.md`-fixed test names all exist and pass. The human-observed real-data run ROADMAP requires from Phase 3 onward has not happened; it needs droplet access this executor does not have.
- SRC-02 (Twitch) stays separately deferred on account 2FA (BLOCKED-EXTERNAL) — independent of the droplet-access gap above, and named in `REQUIREMENTS.md` §Sources as the authoritative record.
- Whoever has droplet access next can work `03-UAT.md` top to bottom as a checklist: each entry's `not_closed_reason` names exactly what's missing and exactly which commands close it.
- `db.py`'s `connect(create=False)` door is ready for Phase 6's bot to import directly — a mistyped path now raises a named, catchable error instead of silently creating an empty database.
- `tests/fixtures/twitch/` remains absent, as required.

## Self-Check: PASSED

All 5 claimed files found on disk; commit hashes `37ac9b6`, `9e5aa3b`, `2b4302e` found in `git log --oneline --all`.

---
*Phase: 03-collector-core-api-sources*
*Completed: 2026-08-05*
