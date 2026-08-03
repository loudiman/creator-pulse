# Phase 3: Collector Core & API Sources - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-04
**Phase:** 3-Collector Core & API Sources
**Areas discussed:** Record shape gaps, Twitch VOD window, TikTok key in Phase 3, Retry and failure rules

---

## Record shape gaps

### Q1 — How does the record hold the video count and the Twitch live status?

| Option | Description | Selected |
|--------|-------------|----------|
| Add both columns | `video_count INTEGER` and `is_live INTEGER` on the record and the DDL | ✓ |
| Add `video_count` only | Live status returned by the source but only logged, never stored | |
| You decide | | |

**User's choice:** Add both columns
**Notes:** Raised because the researched `MetricRecord` in ARCHITECTURE.md has no slot for either,
while SRC-01 asks for the video count and SRC-02 asks for the live status. Rated one-way: the columns
sit in a table holding history the APIs cannot rebuild.

### Q2 — What happens to `engagement_rate`, which no v1 source can fill?

| Option | Description | Selected |
|--------|-------------|----------|
| Remove it | Drop from the record and the DDL; add it back with the first source that can compute it | |
| Keep it, always NULL | Keep the column, NULL on every v1 row | |
| You decide | | ✓ |

**User's choice:** You decide → Claude removed it
**Notes:** No v1 source has both a numerator and a denominator. A column NULL on every row would give
NULL a third meaning, "not implemented", which the project rule does not define.

### Q3 — What does a source do when a metric is absent from a valid response?

| Option | Description | Selected |
|--------|-------------|----------|
| Split the two cases | Documented optional metric maps to NULL; undocumented absence raises | ✓ |
| Absent always means NULL | Simple, never fails a creator | |
| Absent always raises | Catches drift on the first run | |

**User's choice:** Split the two cases
**Notes:** The concrete cases named during discussion: `hiddenSubscriberCount: true` gives
`followers = NULL`, never `0` (PITFALLS.md #13); a missing `viewCount` means the API shape changed and
must raise (PITFALLS.md #8). The single-rule alternatives each break one of those two pitfalls.

### Q4 — Who runs the schema DDL, and is there an ALTER path?

| Option | Description | Selected |
|--------|-------------|----------|
| Collector only creates | `connect(create=...)`; the bot raises a named error if the table is absent | |
| Both run the DDL | ARCHITECTURE.md as written | |
| You decide | | ✓ |

**User's choice:** You decide → Claude picked collector-only create
**Notes:** ARCHITECTURE.md proposes that both processes run the DDL. That lets a mistyped
`CREATORPULSE_DB` in Phase 6 create an empty database and report zero rows, which is the silent
wrong-path failure Phase 2 D-08 exists to prevent. No ALTER path is needed: Phase 2 logged the
database path and never opened it, so no table exists yet.

---

## Twitch VOD window

### Q1 — Which set of VODs sums into the Twitch `views` value?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed time window | `type=archive`, `period=month`, `first=100`, one page | ✓ |
| Fixed VOD count | `sort=time`, `first=20` — the 20 most recent VODs | |
| Whole retained archive | Paginate `period=all` until the pages end | |

**User's choice:** Fixed time window
**Notes:** The fixed count was rejected because 20 VODs spans about 20 days for xQc and about 20 weeks
for a weekly streamer, so one column would hold a different time span per row. The retention caveat
was stated and accepted: Twitch deletes archives after 7, 14, or 60 days depending on account tier, so
the real window is the shorter of one month and retention, and a moving window can produce a negative
delta with no real loss of views.

### Q2 — Does the Twitch row put the window's VOD count into `video_count`?

| Option | Description | Selected |
|--------|-------------|----------|
| No, keep one meaning | `video_count` means a lifetime total only; NULL on Twitch rows; VOD count to the log | |
| Yes, store the window count | Explains a fall in views from the database alone | |
| You decide | | ✓ |

**User's choice:** You decide → Claude kept one meaning per column
**Notes:** Mixing a lifetime total and a window count in one column would make any later cross-source
query wrong by construction. The roadmap calls the normalization boundary the most important seam in
the system.

### Q3 — Which video types enter the sum?

| Option | Description | Selected |
|--------|-------------|----------|
| Archives only | `type=archive` | ✓ |
| All video types | `type=all`, adding highlights and uploads | |
| You decide | | |

**User's choice:** Archives only
**Notes:** A highlight is cut from an archive, so `type=all` would count views on overlapping content
twice.

### Q4 — The window holds no VODs. What does `views` hold?

| Option | Description | Selected |
|--------|-------------|----------|
| Zero | The API answered with an empty list, so 0 is a real observation | ✓ |
| NULL | Avoids a large negative delta when a creator stops streaming | |

**User's choice:** Zero
**Notes:** NULL is reserved for "the platform does not expose this metric", and Twitch did expose it.

---

## TikTok key in Phase 3

### Q1 — What does the collector do with a declared source it does not implement?

| Option | Description | Selected |
|--------|-------------|----------|
| Split known from unknown | Known-platforms list fails on typos; known-but-unimplemented keys log a skip | ✓ |
| Skip any unimplemented key | No second list needed | |
| Fail validation on `tiktok` now | Config always matches the code exactly | |

**User's choice:** Split known from unknown
**Notes:** `creators.yaml` already declares `tiktok` for all three creators. Skipping every
unregistered key would let a typo such as `youtub` pass in silence under a successful run. Failing now
would edit the file twice for a source the roadmap already plans and may cut.

### Q2 — Does the `runs` row count skipped sources?

| Option | Description | Selected |
|--------|-------------|----------|
| No, log only | Keep exactly the four fields DATA-03 names | |
| Add a `skipped` column | Queryable by Phase 6 `/status` | |
| You decide | | ✓ |

**User's choice:** You decide → Claude kept the four DATA-03 fields
**Notes:** The value would read `0` for the rest of the project once Phase 4 lands, and this phase
already made one schema addition.

### Q3 — How does validation report more than one bad entry?

| Option | Description | Selected |
|--------|-------------|----------|
| Collect every error | One line per problem, then exit non-zero before any network call | |
| Fail on the first error | Shorter code, shorter message | |
| You decide | | ✓ |

**User's choice:** You decide → Claude collects every error
**Notes:** Fail-fast makes an operator with two typos edit, re-run, and edit again.

### Q4 — What rule set does validation apply?

| Option | Description | Selected |
|--------|-------------|----------|
| Strict rule set | Required keys, slug pattern, unique `id`, known platform keys, non-empty identifiers | |
| Minimal rule set | Required keys and non-empty identifiers only | |
| You decide | | ✓ |

**User's choice:** You decide → Claude applied the strict rule set
**Notes:** The unique-`id` check is load-bearing. `creator_id` is part of
`UNIQUE (creator_id, source, metric_date)`, so two entries sharing an `id` overwrite each other daily
with no error, and the history cannot be rebuilt.

---

## Retry and failure rules

### Q1 — Which errors count as transient?

| Option | Description | Selected |
|--------|-------------|----------|
| Narrow list | `Timeout`, `ConnectionError`, 429, 5xx; 3 attempts; 2s then 4s | |
| Any request exception | Retry on `requests.RequestException` | |
| You decide | | ✓ |

**User's choice:** You decide → Claude picked the narrow list
**Notes:** A broad list makes a 401 from a bad key look like a network problem and delays it by seven
seconds.

### Q2 — Does the retry read the rate-limit headers?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed backoff only | Ignore `Retry-After` and `Ratelimit-Reset` | |
| Honour the headers | Sleep for the requested interval, up to a cap | |
| You decide | | ✓ |

**User's choice:** You decide → Claude picked fixed backoff
**Notes:** About six calls a day against a 10,000-unit quota cannot reach a rate limit. YouTube
reports quota exhaustion as a 403 `quotaExceeded`, not a 429, so it fails at once — correct, because
the quota does not return within seven seconds. STACK.md names header handling as the `tenacity`
trigger.

### Q3 — Does the collector short-circuit a source after a source-wide failure?

| Option | Description | Selected |
|--------|-------------|----------|
| No, one boundary per pair | ARCHITECTURE.md Pattern 3 unchanged, no cross-pair state | |
| Short-circuit after repeats | Saves calls and quota on a bad day | |
| You decide | | ✓ |

**User's choice:** You decide → Claude kept one boundary per pair
**Notes:** Short-circuiting puts a failure taxonomy into the orchestrator, which ARCHITECTURE.md's
Anti-Pattern section warns against, and `failure_count` would under-report the missing rows.

### Q4 — Does a run that dies part way still write its `runs` row?

| Option | Description | Selected |
|--------|-------------|----------|
| Write it in a `finally` block | Row written once the database is open; exception re-raises | |
| Only on a complete run | Every stored row is a complete run | |
| You decide | | ✓ |

**User's choice:** You decide → Claude picked the `finally` block
**Notes:** Phase 7 criterion 2 asks `/status` to report failure honestly. Without the row, a dead job
and a dead timer read the same.

---

## Claude's Discretion

The author answered "you decide" on nine of the sixteen questions. Each resolved call is recorded in
CONTEXT.md with its rationale: D-02, D-04, D-06, D-10, D-11, D-12, D-13, D-14, D-15, D-16.

Genuine open discretion, recorded in CONTEXT.md §"Claude's Discretion": module placement of the record
type, DDL column order, `collected_at` per row against per run, the validation exit code and message
wording, log line wording and level, the retry helper's form and location, the Python type of
`is_live`, identifier resolution and the per-run call budget, Twitch token minting against caching,
and test and fixture file names.

## Deferred Ideas

- `engagement_rate` returns with the first source that can compute it.
- `skipped_count` on `runs` — rejected; revisit only if Phase 6 `/status` needs it.
- `Retry-After` and `Ratelimit-Reset` handling — the documented `tenacity` trigger.
- Source-wide short-circuit logic — revisit only far past three creators.
- The TikTok source, SRC-03 — Phase 4.
- Delta computation — Phase 4, in Python, from the database.
- Rolling averages and trends, V2-DATA-01; historical backfill, V2-DATA-02; `journalctl` priority
  mapping, V2-OPS-01.

Two items were left explicitly open rather than deferred, and are recorded in CONTEXT.md §Specifics:
how the deliberate source failure of criterion 3 is induced, and what `03-UAT.md` pastes for each of
the five criteria.
