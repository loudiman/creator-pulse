---
status: in-progress
phase: 03-collector-core-api-sources
source: [03-CONTEXT.md]
started: 2026-08-05T00:00:00Z
updated: "2026-08-05T00:00:00Z"
---

## Current Test

### 1. The author adds a creator to `creators.yaml`, re-runs the collector, and that creator's row appears — with no code change; a malformed entry instead fails at startup naming the offending creator and field

## Tests

### 1. The author adds a creator to `creators.yaml`, re-runs the collector, and that creator's row appears — with no code change; a malformed entry instead fails at startup naming the offending creator and field

expected: After adding a fourth creator entry to `creators.yaml` and re-running `creatorpulse collect`, a `sqlite3` query shows a row for that creator's id with no code change made. A second run with a malformed fourth entry (e.g. missing/invalid `id` or an unknown platform) instead exits non-zero before any network call, and the failure message names the offending creator and field.

why_human: Requires editing the real `creators.yaml` and running the real collector against the real (or provisioned) database; no automated check substitutes for the author performing the edit and observing both outcomes.

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

Commands whose output belongs in the evidence block:
- `sqlite3 <db> "select creator_id, followers from metrics where source = 'twitch';"` (all NULL)
- `sqlite3 <db> "select creator_id, source, views from metrics where views = 0;"` or equivalent showing a genuine stored `0`

result: pending

evidence: |

### 5. Every run appends a `runs` row with start, duration, rows written, and failure count, and the bot can read the database while the collector writes without a lock error

expected: The most recent `runs` row shows start time, finish/duration, rows written, and failure count. While the collector is mid-run, a `select count(*) from metrics;` issued from a second shell against the same database completes without a lock error.

why_human: Requires timing a concurrent read against a real in-progress collector run on the real database — not reproducible from an automated test suite that never touches a live run.

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
