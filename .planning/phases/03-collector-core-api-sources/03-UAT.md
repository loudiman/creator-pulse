---
status: in-progress
phase: 03-collector-core-api-sources
source: [03-CONTEXT.md]
started: 2026-08-05T00:00:00Z
updated: "2026-08-05T00:00:00Z"
blocked_reason: "Precondition unmet as of 2026-08-05 — /etc/creatorpulse/creatorpulse.env on the droplet holds blank values, Twitch credentials do not exist (SRC-02, BLOCKED-EXTERNAL), and this executor has no SSH access to the droplet. All five entries below are PENDING, not fabricated. See ## Gaps."
---

## Current Test

### 1. The author adds a creator to `creators.yaml`, re-runs the collector, and that creator's row appears — with no code change; a malformed entry instead fails at startup naming the offending creator and field

## Tests

### 1. The author adds a creator to `creators.yaml`, re-runs the collector, and that creator's row appears — with no code change; a malformed entry instead fails at startup naming the offending creator and field

expected: After adding a fourth creator entry to `creators.yaml` and re-running `creatorpulse collect`, a `sqlite3` query shows a row for that creator's id with no code change made. A second run with a malformed fourth entry (e.g. missing/invalid `id` or an unknown platform) instead exits non-zero before any network call, and the failure message names the offending creator and field.

why_human: Requires editing the real `creators.yaml` and running the real collector against the real (or provisioned) database; no automated check substitutes for the author performing the edit and observing both outcomes.

not_closed_reason: No SSH access to the droplet from this executor, and `/etc/creatorpulse/creatorpulse.env` there still holds blank values (SRC-01's `YOUTUBE_API_KEY` unset) — `creatorpulse collect` cannot run against real data.

Commands whose output belongs in the evidence block:
- the diff/addition made to `creators.yaml` (fourth creator)
- `creatorpulse collect` (exit code)
- `sqlite3 <db> "select * from metrics where creator_id = '<new-id>';"`
- the malformed-entry edit to `creators.yaml`
- `creatorpulse collect` against the malformed config (exit code, and the stderr/log line naming creator + field)

result: pending

evidence: |

### 2. Running the collector twice on the same day leaves the total row count unchanged, and yesterday's rows are untouched — the author can see both facts in one `sqlite3` query

expected: A single `sqlite3` query, run before and after a same-day re-run of the collector, shows both the unchanged total row count and yesterday's rows still present and untouched.

why_human: Requires a real database with at least one prior day's history and a real same-day re-run; cannot be reproduced from a fixture-only test suite.

not_closed_reason: Same as entry 1 — no droplet access, no real `creatorpulse.db` with history to re-run against. The automated equivalent (`test_idempotent_rerun_same_day`, `tests/test_collector.py`) is green and proves the same claim in-process, but that is not this criterion.

Commands whose output belongs in the evidence block:
- `sqlite3 <db> "select count(*) from metrics;"` (before)
- `creatorpulse collect` (same-day re-run)
- `sqlite3 <db> "select count(*) from metrics;"` (after — same count)
- `sqlite3 <db> "select * from metrics where metric_date < date('now');"` (yesterday's rows, unchanged)

result: pending

evidence: |

### 3. A source made to fail is logged with creator, source, and cause, counted in that run's `runs` row, and the remaining creators still complete

expected: A fourth `creators.yaml` entry with a real `id`, a real platform key, and an identifier that does not exist causes that one creator/source to fail without aborting the run. `journalctl` (or the equivalent local log) shows the failure line naming creator, source, and cause; the `runs` row for that run shows the failure counted; and the other configured creators still completed successfully in the same run. The file is reverted afterward.

why_human: Requires deliberately breaking one entry in the real config and observing the real run's log and `runs` row — the D-18 bogus-identifier proof is a live-system behavior, not something a fixture-driven unit test can stand in for.

not_closed_reason: Same droplet-access gap as entries 1 and 2. The automated proxy (`test_one_source_failure_does_not_abort_run` and siblings, `tests/test_collector.py`) proves exception isolation against a monkeypatched raise, which is explicitly a different, narrower proof than a real bogus handle meeting the real YouTube/Twitch API (D-18) — the two are deliberately not interchangeable.

Commands whose output belongs in the evidence block:
- the bogus-identifier edit to `creators.yaml` (real `id`, real platform key, nonexistent identifier)
- `creatorpulse collect` (exit code)
- `journalctl -u creatorpulse.service -n 40` (or local run output) showing the failure line: creator, source, cause
- `sqlite3 <db> "select * from runs order by started_at desc limit 1;"` (failure_count > 0)
- `sqlite3 <db> "select * from metrics where metric_date = date('now');"` (other creators' rows present)
- the revert of the bogus-identifier edit

result: pending

evidence: |

### 4. A metric the platform does not expose reads as NULL in the database, never 0 — and the Twitch `followers` column is NULL on every row for exactly this reason

expected: One query proves the Twitch `followers` column is NULL on every Twitch row. A second query shows a real stored `0` somewhere it legitimately belongs (e.g. `views` for an empty archive window, or `failure_count` on a clean run), so NULL and 0 are visibly different values in the same evidence block, not the same value rendered twice.

why_human: Requires reading the real database after a real run against real Twitch/YouTube data; the NULL-vs-0 distinction is exactly the kind of thing that is easy to silently get wrong and needs a human eyeballing actual rows.

not_closed_reason: Split claim, split status — recorded in full rather than glossed over.
**Part A** (real YouTube evidence: three real numbers + two real NULLs in the same row,
`03-05-PLAN.md` Task 3 Entry 4 Part A's two queries) needs a real droplet run and is blocked
by the same access gap as entries 1-3.
**Part B** (the never-COALESCE rule at the storage layer, needing no source/credential/fixture)
is *not* blocked and was run now, for real, on this machine — pasted below, unmodified.
**The Twitch instance** (every Twitch `followers` NULL) is separately blocked on SRC-02
(BLOCKED-EXTERNAL, Twitch 2FA — see `.planning/REQUIREMENTS.md` §Sources) and has no
Twitch rows to query regardless of droplet access, per the author's 2026-08-05 resolution
recorded in `03-05-PLAN.md`'s "Entry 4, resolved by the author" note.
Entry 4 stays `pending` as a whole because Part A — the entry's actual live-database claim —
is unmet; Part B passing does not by itself satisfy "a human watched real API data land."

Commands whose output belongs in the evidence block:
- Part A (still needed): `sqlite3 <db> "select creator_id, followers from metrics where source = 'twitch';"` (all NULL — but see the Twitch-instance note above, this table stays empty until 03-03 runs) and the two queries in `03-05-PLAN.md` Task 3 Entry 4 Part A
- Part B (already run — see evidence below): `pytest tests/test_db.py::test_stored_null_and_zero_round_trip_distinct -v`

result: pending

evidence: |
  Part B only — pytest tests/test_db.py::test_stored_null_and_zero_round_trip_distinct -v
  ============================= test session starts =============================
  platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\loudi\orca\creator-pulse\.venv\Scripts\python.exe
  cachedir: .pytest_cache
  rootdir: C:\Users\loudi\orca\creator-pulse
  configfile: pyproject.toml
  collecting ... collected 1 item

  tests/test_db.py::test_stored_null_and_zero_round_trip_distinct PASSED   [100%]

  ============================== 1 passed in 0.06s ==============================

  Part A (real YouTube evidence from a droplet run) and the Twitch instance are still open —
  see not_closed_reason above.

### 5. Every run appends a `runs` row with start, duration, rows written, and failure count, and the bot can read the database while the collector writes without a lock error

expected: The most recent `runs` row shows start time, finish/duration, rows written, and failure count. While the collector is mid-run, a `select count(*) from metrics;` issued from a second shell against the same database completes without a lock error.

why_human: Requires timing a concurrent read against a real in-progress collector run on the real database — not reproducible from an automated test suite that never touches a live run.

not_closed_reason: Same droplet-access gap as entries 1-3. `test_reader_can_read_while_writer_has_open_transaction` (`tests/test_db.py`) proves the WAL/busy_timeout mechanism single-process; it cannot prove real cross-process concurrency, which is exactly what this entry requires and exactly what DATA-05's flagged assumption in `03-05-PLAN.md` names as unresolved.

Commands whose output belongs in the evidence block:
- `sqlite3 <db> "select * from runs order by started_at desc limit 1;"`
- `sqlite3 <db> 'select count(*) from metrics;'` (run from a second shell while the collector is mid-run)

result: pending

evidence: |

## Summary

total: 5
passed: 0
pending: 5

## Gaps

**Phase 3 closes PARTIAL as of 2026-08-05: automated coverage green, human-observed run
outstanding.** Both gates in `03-05-PLAN.md`'s Definition of Green are distinct and this
phase has closed only one of them:

1. **Automated coverage — CLOSED.** `ruff format --check .`, `ruff check .`, `mypy src/`
   (strict), and `pytest` all exit 0 (63 tests). The eight test names
   `03-VALIDATION.md`'s Per-Task Verification Map fixes for this plan all exist and pass:
   `test_upsert_same_key_updates_not_duplicates`,
   `test_upsert_different_date_does_not_touch_prior_row`,
   `test_create_false_raises_on_missing_table`,
   `test_stored_null_and_zero_round_trip_distinct` (`tests/test_db.py`);
   `test_one_source_failure_does_not_abort_run`,
   `test_all_rows_from_one_run_share_metric_date`,
   `test_runs_row_written_on_crash`, `test_idempotent_rerun_same_day`
   (`tests/test_collector.py`).
2. **Human-observed real-data run — OUTSTANDING.** ROADMAP's Definition of Green requires a
   human-observed end-to-end run against real API data from Phase 3 onward, and no automated
   check substitutes for it. This executor had no SSH access to the droplet and
   `/etc/creatorpulse/creatorpulse.env` there still holds blank values, so none of the five
   `03-UAT.md` entries above could be closed against real data. All five stay `pending`, each
   carrying its own `not_closed_reason` and the exact commands that will close it — usable as
   a checklist in one sitting once droplet access exists.

**SRC-02 (Twitch source) is separately deferred**, not merely a UAT gap: `03-03-PLAN.md` is
written, reviewed, and left unexecuted because Twitch application registration is
BLOCKED-EXTERNAL — the account's 2FA enrolment requires a mobile number and the verification
SMS never arrives, so no client id or secret exists and no Twitch fixtures could be recorded.
See `.planning/REQUIREMENTS.md` §Sources, the SRC-02 note, for the authoritative record. This
is why entry 4's Twitch-followers-NULL instance stays open even once a droplet run happens —
closing it requires SRC-02 to unblock first, which is independent of the droplet-access gap
above.

**What is NOT a gap:** the never-COALESCE principle itself (ROADMAP criterion 4's underlying
claim) is proven today, durably, with no source, no credential, and no droplet — see entry 4's
Part B evidence, `test_stored_null_and_zero_round_trip_distinct`, run and pasted above.
