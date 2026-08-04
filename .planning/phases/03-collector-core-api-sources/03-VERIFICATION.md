---
phase: 03-collector-core-api-sources
verified: 2026-08-05T00:00:00Z
status: human_needed
score: 5/5 must-haves verified (automated); 5/5 UAT criteria honestly pending human/droplet evidence
behavior_unverified: 0
overrides_applied: 0
---

# Phase 3: Collector Core & API Sources Verification Report

**Phase Goal:** Real numbers from YouTube and Twitch land in SQLite with history, and one broken
source cannot take the run down
**Verified:** 2026-08-05
**Status:** human_needed (automated coverage is fully green; ROADMAP's Definition of Green also
requires a human-observed real-data run, which is honestly recorded as not yet performed)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Adding a creator to `creators.yaml` produces a row with no code change; a malformed entry fails at startup naming creator+field | VERIFIED | `test_run_collect_fourth_creator_needs_no_code_change` (tests/test_config.py:241) appends a 4th entry, runs `run_collect`, asserts exit 0 and a row for `fourth-creator`. `test_run_collect_exit_code_2_on_validation_failure` proves exit 2, no db file created, and a `field=` log line naming the problem. `config.py:56-91` `validate()` implements D-11/D-12. |
| 2 | Re-running same day leaves row count unchanged; prior days untouched | VERIFIED | `test_idempotent_rerun_same_day` (tests/test_collector.py:395) and `test_idempotent_rerun_same_date_leaves_metrics_count_unchanged` (tests/test_collector.py:71) both green. `test_upsert_different_date_does_not_touch_prior_row` (tests/test_db.py:122) asserts byte-identical prior row. `db.py`'s `UPSERT_METRIC` targets exactly `ON CONFLICT (creator_id, source, metric_date)`. |
| 3 | A source failure is logged (creator/source/cause), counted in `runs`, other creators still complete | VERIFIED | `test_one_source_failure_does_not_abort_run`, `test_one_failing_source_fails_every_creator_no_short_circuit`, `test_processing_order_matches_file_order_after_failure` (tests/test_collector.py) — all use **two distinct fake source keys** (`source_a`/`source_b`) per the verification brief's requirement, proving isolation is not an artifact of a single-source test. `collector.py:36-47` shows one `try/except` per `(creator, source)` pair, `continue` on failure, no shared state read or written across iterations. |
| 4 | NULL vs 0 — a metric the platform doesn't expose is NULL, never 0 | VERIFIED | `test_stored_null_and_zero_round_trip_distinct` (tests/test_db.py:168) — four separate identity assertions, no truthiness check. `youtube.py:37-38` reads `hiddenSubscriberCount` **before** `subscriberCount` and only reads the latter in the `else` branch (branches on the flag, never the value) — confirmed by `test_youtube_hidden_subscriber_count_maps_to_none` and the `_omitted_derived` variant (subscriberCount key entirely absent, still `None`). No `COALESCE` anywhere in `src/` or `tests/` (grep, zero matches). |
| 5 | Every run appends a `runs` row (start/duration/rows/failures); reader coexists with writer | VERIFIED (single-process) | `test_runs_row_written_on_crash` (tests/test_collector.py:364) proves the `try/finally` in `collect_once` (`collector.py:24-60`) writes the row with counts-so-far and re-raises. `test_reader_can_read_while_writer_has_open_transaction` (tests/test_db.py:183) proves WAL + `busy_timeout=5000` let a reader proceed against an uncommitted writer transaction, single-process. Real cross-process concurrency is explicitly NOT provable this way — see Human Verification. |

**Score:** 5/5 truths verified at the code/automated-test level.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/creatorpulse/models.py` | `MetricRecord`, `RunResult` | VERIFIED | Frozen/slots dataclasses, all metric fields `int \| None` per mypy strict. |
| `src/creatorpulse/db.py` | Connection factory, DDL, upsert, `runs` writer, `create=False` reader door | VERIFIED | `connect()` never invents a default path (takes `db_path: Path` param only) and never `mkdir`s (grep confirms zero `mkdir` calls in `src/creatorpulse/`). |
| `src/creatorpulse/config.py` | `validate()` naming creator+field, D-12 rule set | VERIFIED | Unique-id check, slug pattern, known-platform check, non-empty identifier check all present and tested. |
| `src/creatorpulse/sources/__init__.py` | `Protocol` + `FETCHERS` registry, `KNOWN_PLATFORMS` | VERIFIED | Two-list design (D-09) exactly as specified; only `youtube` registered. |
| `src/creatorpulse/sources/youtube.py` | Normalized fetch, raise-on-empty (D-18), NULL-vs-0 | VERIFIED | `ChannelNotFound` raised on empty `items`; retry-wrapped `requests.get`. |
| `src/creatorpulse/sources/_retry.py` | Narrow retryable list, fixed 2s/4s backoff, 3 attempts | VERIFIED | `_RETRYABLE_EXC = (Timeout, ConnectionError)`, `_RETRYABLE_STATUS = {429}` plus `>=500`; matches D-13/D-14 exactly. Lives in source layer, not imported by `collector.py`. |
| `src/creatorpulse/collector.py` | Per-pair isolation, outer `try/finally` runs-row guarantee | VERIFIED | See Truths 3 and 5 above. |
| `src/creatorpulse/cli.py` | Real `collect` call replacing the not-implemented line | VERIFIED | `run_collect()` wires `validate()` → `load_creators()` → `connect(create=True)` → `collect_once()`; exit codes 0/1/2 documented and tested. |
| `src/creatorpulse/sources/twitch.py` | — | **INTENTIONALLY ABSENT** | SRC-02 deferred, BLOCKED-EXTERNAL. `03-03-PLAN.md` carries `deferred: true`, unexecuted, no `03-03-SUMMARY.md`. Confirmed correct per known-gap list. |
| `tests/fixtures/twitch/` | — | **INTENTIONALLY ABSENT** | Confirmed does not exist (`ls` → No such file or directory). Correct per known-gap list — recording is blocked on Twitch 2FA credentials. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `cli.py` | `config.validate()` | called before `load_creators()`, before `connect()` | WIRED | `cli.py:37-42` — validation runs and returns exit 2 before any DB open or network call. |
| `cli.py` | `collector.collect_once()` | `connect(create=True)` then `collect_once(conn, creators)` | WIRED | `cli.py:46-47`. |
| `collector.py` | `sources.FETCHERS` | `FETCHERS.get(source_name)` per (creator, source) | WIRED | `collector.py:27`. |
| `collector.py` | `db.upsert_metric` / `db.write_run_row` | direct calls, `upsert_metric` outside per-pair try/except, `write_run_row` in `finally` | WIRED | `collector.py:53,60`. |
| `sources/youtube.py` | `sources/_retry.py` | `retry(requests.get, ...)` wraps every outbound call | WIRED | `youtube.py:22`. |

### Design Call Under Scrutiny: `upsert_metric` Outside the Per-Pair Boundary

`collector.py:49-54` places `upsert_metric(conn, record)` **outside** the `try/except Exception` that
wraps `fetch()` (lines 36-47). A database write failure therefore propagates out of `collect_once`
entirely, is caught only by the outer `try/finally` (which writes the `runs` row with counts reached
so far and then re-raises), rather than being counted as one more per-pair failure.

**This matches `ARCHITECTURE.md`'s own reference implementation** (`ARCHITECTURE.md:197-217`,
`safe_fetch()` wraps only the fetch call; `upsert_metric` is called unwrapped in the outer loop).

**Assessment: I agree with this design.** A `requests`/API failure is per-source and transient by
nature — isolating it protects the rest of the run. A SQLite write failure (disk full, permissions,
corruption) is systemic: every subsequent write in the same run would fail identically. Swallowing
it into `failure_count` would misreport "the database is broken" as "N independent source outages,"
which is a materially worse signal for the Phase 6 bot's `/status` and a worse `journalctl` read.
Letting it crash the process (after the `runs` row is written with an honest partial count) is the
correct behavior, and it is proven by `test_runs_row_written_on_crash`, which asserts `rows_written
== 1` (not 0, not 2) and that the exception re-raises with non-zero exit code implied.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|---|---|---|---|
| CFG-01 | Add creator, no code change | SATISFIED | `test_run_collect_fourth_creator_needs_no_code_change` |
| CFG-02 | Entry declares platform + identifier | SATISFIED | `Creator.sources: dict[str, str]`, validated |
| CFG-03 | Invalid config fails at startup naming creator+field | SATISFIED | `validate()`, exit code 2, `test_run_collect_exit_code_2_on_validation_failure` |
| SRC-01 | YouTube subscriber/view/video counts via API key | SATISFIED | `youtube.py`, live fixture-driven tests |
| SRC-02 | Twitch views + live status | **BLOCKED-EXTERNAL** | Correctly recorded not-Complete in REQUIREMENTS.md; `03-03-PLAN.md` deferred, unexecuted |
| SRC-04 | Same normalized shape; NULL not 0 | SATISFIED | `MetricRecord`, NULL-vs-0 tests |
| SRC-05 | Transient-error retry with backoff | SATISFIED | `_retry.py`, 6 retry tests |
| DATA-01 | One row per creator/source/date | SATISFIED | `UNIQUE(creator_id, source, metric_date)`, upsert tests |
| DATA-02 | Re-run same day updates, not duplicates | SATISFIED | idempotency tests |
| DATA-03 | `runs` row every run (start/duration/rows/failures) | SATISFIED | `write_run_row`, crash test |
| DATA-04 | Prior days never overwritten | SATISFIED | `test_upsert_different_date_does_not_touch_prior_row` |
| DATA-05 | Writer/reader concurrency without lock errors | SATISFIED (single-process only) | WAL+busy_timeout test; real cross-process case is UAT-pending (honestly recorded) |
| RUN-01 | One failure doesn't abort run | SATISFIED | per-pair isolation tests |
| RUN-02 | Failure logged w/ creator, source, cause, counted | SATISFIED | log-line assertions |
| RUN-05 | `metric_date` computed once per run in UTC | SATISFIED | `collect_once` line 19, shared-date tests |
| OPS-05 | Idempotency test | SATISFIED | present and green |
| OPS-06 | Normalization test, fixture-in/record-out, per source | SATISFIED for YouTube; Twitch deferred with SRC-02 | 4 YouTube fixtures + tests |
| OPS-07 | Failure isolation test | SATISFIED | present and green |

No orphaned requirements found — all 18 Phase 3 requirement IDs from ROADMAP.md appear in the plan
frontmatter `requirements-completed` fields across 03-02/03-04/03-05/03-06, and SRC-02 is the one
correctly left unchecked.

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers, no empty-return stubs, no
hardcoded-empty data flowing to output, no `console.log`-only handlers, in any of the phase's
modified/created source files (`models.py`, `db.py`, `config.py`, `sources/__init__.py`,
`sources/youtube.py`, `sources/_retry.py`, `collector.py`, `cli.py`).

### Behavioral Spot-Checks / Green Gate

Ran all four Definition-of-Green commands directly (not trusting SUMMARY claims):

| Command | Result | Status |
|---|---|---|
| `ruff format --check .` | "75 files already formatted", exit 0 | PASS |
| `ruff check .` | "All checks passed!", exit 0 | PASS |
| `mypy src/` | "Success: no issues found in 9 source files", exit 0 | PASS |
| `pytest` | "63 passed in 1.13s", exit 0 | PASS |

### Hard Rules Held

| Rule | Status | Evidence |
|---|---|---|
| No new dependency in `pyproject.toml` | HELD | `dependencies = [gspread, discord.py, playwright, PyYAML, requests]` — unchanged from Phase 1/2 locked set. |
| No live network call reachable from `pytest` | HELD | Every `requests.get`/`.post` site in `tests/` is behind `monkeypatch`/`Mock`; grep for unmocked call sites found none. |
| `deploy/creatorpulse.service`, `deploy/creatorpulse.timer` unmodified | HELD | `git log --all -- deploy/` returns zero commits — the files were never touched by any commit in this repo's history, confirming Phase 3 (an agent-owned phase) left them alone. |
| `db.py` invents no default path, never `mkdir`s | HELD | `connect(db_path: Path, *, create: bool)` takes the path as a required parameter; `resolve_paths()` (config.py) is the only path-resolution logic and lives outside db.py per Phase 2 D-06; zero `mkdir` calls anywhere in `src/creatorpulse/`. |

### Known-and-Intentional Gaps (confirmed, not defects)

1. **SRC-02 (Twitch) deferred, BLOCKED-EXTERNAL.** Confirmed: `03-03-PLAN.md` frontmatter carries
   `deferred: true`; no `03-03-SUMMARY.md` exists; `tests/fixtures/twitch/` does not exist;
   `REQUIREMENTS.md` records the reason (2FA/SMS wall) accurately and does not mark SRC-02 complete;
   `ROADMAP.md`'s Phase 3 section carries the same note. Recorded honestly.

2. **Phase closes PARTIAL — the human-observed real-data run has not happened.** `03-UAT.md`'s five
   entries are all `result: pending`, each with a specific `not_closed_reason` (no droplet SSH access,
   blank `/etc/creatorpulse/creatorpulse.env`) and the exact commands to close them later. No pasted
   output was invented for entries 1, 2, 3, 5, or Entry 4 Part A / the Twitch instance. **Entry 4 Part
   B is the one legitimate exception** — it required no droplet/credential/source, was actually run
   (`pytest tests/test_db.py::test_stored_null_and_zero_round_trip_distinct -v`), and its real,
   unmodified output is pasted in the evidence block. Independently re-ran this exact test myself
   during this verification (all 63 tests including this one passed) — the pasted output is genuine,
   not fabricated.

## Human Verification Required

These five items are ROADMAP's mandatory manual verification gate for Phase 3 (real API data reaching
the real database) and cannot be closed by any automated check. They are already tracked, with
evidence-collection commands, in `03-UAT.md` — reproduced here per the verifier's Step 8 requirement.

### 1. New creator + malformed entry against real data

**Test:** Add a 4th creator to the real `creators.yaml` on the droplet, run `creatorpulse collect`,
query the row. Then break the 4th entry and re-run.
**Expected:** Row appears with no code change; malformed entry exits non-zero before any network call,
naming the creator and field.
**Why human:** Requires the real droplet, real `YOUTUBE_API_KEY`, and a human editing the real config.

### 2. Idempotency against real data

**Test:** Run the collector twice same day against the real droplet database; one `sqlite3` query
before/after.
**Expected:** Total row count unchanged; yesterday's rows present and untouched.
**Why human:** Needs a real database with real prior-day history.

### 3. Real bogus-handle failure (D-18)

**Test:** Add a 4th `creators.yaml` entry with a real id/platform and a nonexistent identifier; run
once; check `journalctl`/log and the `runs` row; revert.
**Expected:** Failure logged naming creator/source/cause; `runs.failure_count > 0`; other creators
still complete.
**Why human:** Needs a real bad handle meeting the real YouTube/Twitch API — the unit test only proves
exception-isolation against a monkeypatched raise, a deliberately narrower and different proof.

### 4. NULL-vs-0 on real data, and Twitch followers NULL (Part A)

**Test:** Query real YouTube rows for a NULL and a real stored 0 in the same evidence block; query
Twitch `followers` (currently impossible — no Twitch rows exist, SRC-02 blocked).
**Expected:** NULL and 0 visibly distinct in real data.
**Why human:** Needs a real run against real API data. (Part B, the storage-layer proof, is already
closed — see above.)

### 5. Cross-process concurrent read/write

**Test:** Query `select count(*) from metrics` from a second shell while the collector is mid-run on
the real droplet.
**Expected:** No lock error.
**Why human:** Real cross-process concurrency cannot be proven by a single-process unit test — the
existing `test_reader_can_read_while_writer_has_open_transaction` proves the WAL/busy_timeout
mechanism only within one process.

## Gaps Summary

**No code defects found.** Every truth the roadmap requires is backed by real, wired, tested
implementation — not a stub, not a placeholder, not a partial wiring. The failure-isolation claim
(the goal's second half) is specifically proven with two distinct fake source keys
(`test_processing_order_matches_file_order_after_failure` et al.), not a single-source test, satisfying
the verification brief's sharpest scrutiny point. The NULL-vs-0 rule is proven both at the storage
layer and at the YouTube source's read-order (`hiddenSubscriberCount` read before, never after,
`subscriberCount`). The `runs`-row crash guarantee and its asymmetric no-row-on-validation-failure
behavior are both proven. Idempotency and prior-day immutability are both proven. The four-command
green gate passes when run directly, not merely claimed. No new dependency, no live network call in
`pytest`, no touched `deploy/` files, no invented default path or `mkdir` in `db.py`.

The **only** reason this phase is not `status: passed` is the honestly-recorded, still-outstanding
human-observed real-data run that ROADMAP.md's Definition of Green explicitly requires from Phase 3
onward — a gate this executor cannot close without droplet SSH access and a populated
`/etc/creatorpulse/creatorpulse.env`. This is not a defect in the phase's work; it is exactly what
`03-UAT.md` says it is: five pending items with clear close-later instructions, one item (Entry 4 Part
B) genuinely already closed with real, verified-here pasted output. SRC-02 (Twitch) is a second,
independent, correctly-recorded external blocker (2FA/SMS), not a quality gap.

**Recommendation:** Proceed to Phase 4 is reasonable from a code-quality standpoint (nothing here
blocks Phase 4's dependencies — `models.py`/`db.py` shape, `FETCHERS` registry, and `collector.py` are
all real and stable). However, per ROADMAP's own stated rule, Phase 3 should not be marked fully
`Complete` in ROADMAP.md's Progress table until the droplet run happens and `03-UAT.md`'s five entries
are closed for real — the author should decide whether to run that gate now, defer it (tracked), or
accept the automated-only closure as sufficient given schedule pressure.

---

_Verified: 2026-08-05_
_Verifier: Claude (gsd-verifier)_
