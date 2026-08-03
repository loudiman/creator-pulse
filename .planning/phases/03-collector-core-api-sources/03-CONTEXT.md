# Phase 3: Collector Core & API Sources - Context

**Gathered:** 2026-08-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers the collector body. Real numbers from YouTube and Twitch land in SQLite with full
daily history, and one broken source cannot stop the run.

Concretely: `models.py` holds the normalized record. `db.py` holds the connection factory, the DDL,
the metric upsert, and the `runs` writer. `config.py` gains a `validate()` pass that names the
offending creator and field. `sources/youtube.py` and `sources/twitch.py` return normalized records.
`sources/__init__.py` holds the `Protocol` and the fetcher registry. `collector.py` orchestrates the
loop, isolates each failure, and writes the `runs` row. `cli.py` replaces its not-implemented line
with a real call. The suite gains the idempotency test (OPS-05), the normalization tests (OPS-06),
and the failure-isolation test (OPS-07).

This phase also closes RUN-03 fully. Phase 2 pointed the timer at a placeholder. Phase 3 puts real
work behind the same command, and the unit file does not change.

**Not in this phase:** the TikTok source (SRC-03, Phase 4), any Sheets code (Phase 4), any delta
computation (Phase 4 owns it, in Python, from the database), any Discord code (Phase 6), and any
Apps Script.

</domain>

<decisions>
## Implementation Decisions

### Record Shape & Schema

- **D-01:** `MetricRecord` and the `metrics` DDL gain two columns: `video_count INTEGER` and
  `is_live INTEGER`. SRC-01 asks for the video count and SRC-02 asks for the live status, and the
  researched record in ARCHITECTURE.md has no slot for either. YouTube fills `video_count` from
  `statistics.videoCount`. TikTok fills it in Phase 4. Twitch fills `is_live` with `1` or `0` from
  `GET /helix/streams`. Every other cell holds NULL, because the platform does not expose the metric.
  The final column set is `creator_id`, `source`, `metric_date`, `followers`, `views`, `likes`,
  `video_count`, `is_live`, `collected_at`.
  — **Reversibility:** one-way — the columns sit inside a table that carries history the APIs cannot
  rebuild. Removing one later means an `ALTER TABLE` against live data, and the Phase 4 Sheet writer
  and the Phase 6 bot both read the shape.

- **D-02:** `engagement_rate` is **removed** from the record and from the DDL. No v1 source can
  compute it. YouTube `channels.list` returns `viewCount`, `subscriberCount`,
  `hiddenSubscriberCount`, and `videoCount`, with no likes and no comments. `GET /helix/videos`
  returns `view_count` and no likes. The TikTok profile page shows total likes and no view total, so
  a rate has no denominator. A column that is NULL on every row would also give NULL a third
  meaning — "not implemented" — which the project rule does not define. The column returns in the
  same commit as the first source that can fill it, and ARCHITECTURE.md's store-do-not-compute rule
  applies then. *(Claude's call — the author chose "you decide".)*
  — **Reversibility:** reversible while the column is absent. Adding it later is one guarded
  `ALTER TABLE ... ADD COLUMN`.

- **D-03:** An absent metric is handled by **two rules, not one**. A documented optional metric maps
  to NULL and the run continues. The concrete case: `hiddenSubscriberCount: true` gives
  `followers = NULL`, never `0`, because a blind parse of the `0` that YouTube reports there is the
  exact false zero PITFALLS.md #13 describes. An undocumented absence raises, and the pair counts as
  a failure. The concrete case: `viewCount` missing means the API shape changed, and PITFALLS.md #8
  says raise, never return `None`. Each source names its own optional fields in its own module, so
  the rule is readable per source. The single-rule alternatives both fail: "absent always means
  NULL" turns a real API change into a silent row of NULLs under a successful run, and "absent
  always raises" fails a creator every day for a legitimate privacy setting, so `failure_count`
  stops being a signal.
  — **Reversibility:** reversible.

- **D-04:** `connect()` takes a `create` flag. The collector calls it with `create=True` and runs the
  idempotent `CREATE TABLE IF NOT EXISTS` block. The bot calls it with `create=False` and raises a
  named error when the `metrics` table is absent. This keeps the collector the only writer in fact
  and not only by convention, and it stops the Phase 6 bot from creating an empty database at a
  mistyped `CREATORPULSE_DB` path and then reporting zero rows as though the collector had failed.
  That is the same silent-wrong-path failure Phase 2 D-08 exists to prevent. There is no `ALTER`
  path and no `schema_version` table, because the DDL is final on the first run: Phase 2 logged the
  database path and never opened it, so no table exists yet on the droplet. WAL mode and
  `busy_timeout = 5000` are set on every connection, both flags included. *(Claude's call — the
  author chose "you decide". ARCHITECTURE.md proposes that both processes run the DDL; this narrows
  it.)*
  — **Reversibility:** reversible.

### Twitch Metric Definition

- **D-05:** The Twitch `views` value is the summed `view_count` of the archives published in the
  last month. One call: `GET /helix/videos` with `user_id`, `type=archive`, `period=month`,
  `first=100`, one page, no pagination. The window is the same length for every creator, so the rows
  compare across creators. A fixed VOD count was rejected: twenty VODs is about twenty days for xQc
  and about twenty weeks for a weekly streamer, so one column would hold a different time span per
  row. Paginating the whole retained archive was rejected as a variable number of calls for a sum
  that still moves.
  **Documented caveat:** Twitch deletes archives after 7 days for a standard account, 14 days for an
  Affiliate or Turbo account, and 60 days for a Partner. The real window is therefore the shorter of
  one month and the account's retention. The sum is a moving window, so the day-over-day delta can
  read negative when an old VOD ages out, with no real loss of views. This is an understood
  consequence, not a defect. Phase 4's delta inherits it, and the README (OPS-08) must record it
  beside the follower auth wall.
  — **Reversibility:** costly — rows collected under a different window carry a different meaning
  than rows collected under this one, and the history cannot be recomputed.

- **D-06:** `video_count` holds **only** "the lifetime number of videos the platform reports". Twitch
  does not report that, so the Twitch row holds NULL. The number of VODs inside the window goes into
  the run's log line instead, so a fall in `views` is still explainable from `journalctl`. Storing the
  window count in `video_count` was rejected: one column would then hold a lifetime total for two
  sources and a window count for a third, and any later cross-source query or Sheet column would be
  wrong by construction. The roadmap calls the normalization boundary the single most important seam
  in the system, and this protects it. *(Claude's call — the author chose "you decide".)*
  — **Reversibility:** reversible.

- **D-07:** `type=archive` only. The value answers one question: "how many views did the broadcasts
  published in this window get?" Highlights and uploads are edited derivatives of the same
  broadcasts, so `type=all` would count views on overlapping content twice and the number would stop
  answering a single question.
  — **Reversibility:** costly — same data consequence as D-05.

- **D-08:** An empty window gives `views = 0`, not NULL. The API answered, and the answer was an
  empty list. A streamer who did not stream this month truly has zero views on this month's
  archives, and the project rule reserves NULL for "the platform does not expose this metric".
  — **Reversibility:** reversible.

### Config Validation & Unimplemented Sources

- **D-09:** Two lists, not one. A **known-platforms** list holds `youtube`, `twitch`, and `tiktok`.
  The **fetcher registry** holds only the implemented sources. An unknown key such as `youtub` fails
  validation at startup and names the creator and the field, which is what CFG-03 asks for. A known
  key with no fetcher logs one skip line, and the run continues. `creators.yaml` therefore keeps its
  `tiktok` entries for xQc, Pokimane, and Kai Cenat unchanged. Phase 4 adds one registry entry and
  the TikTok rows appear with no config change, which demonstrates CFG-01 a second time. Skipping
  every unregistered key was rejected: a typo would then be skipped in silence and the run would
  still report success. Failing on `tiktok` now was rejected: the file would be edited twice for a
  source the roadmap already plans, and the cut order says TikTok may never arrive.
  — **Reversibility:** reversible.

- **D-10:** A skip is neither a row written nor a failure. The `runs` table keeps exactly the four
  fields DATA-03 names: `started_at`, `finished_at`, `rows_written`, `failure_count`. A skip appears
  only as one log line per creator and source — three lines per run in Phase 3, and zero once Phase 4
  lands. A `skipped_count` column was rejected as a second schema addition in a phase that already
  made one, for a value that reads `0` for the rest of the project's life. *(Claude's call — the
  author chose "you decide".)*
  — **Reversibility:** reversible.

- **D-11:** `validate()` walks the whole file, gathers every problem, prints one line per problem
  naming the creator and the field, then exits non-zero **before any network call**. The operator
  fixes every problem in one pass. Failing on the first error was rejected because an operator who
  mistyped two creators would edit, re-run, and edit again. *(Claude's call — the author chose "you
  decide".)*
  — **Reversibility:** reversible.

- **D-12:** The strict rule set. The top-level `creators` key must exist and must hold a non-empty
  list. Each entry needs `id`, `name`, and a non-empty `sources` map. Each `id` must match a slug
  pattern and must be **unique across the file**. Each source key must appear in the
  known-platforms list of D-09. Each identifier must be a non-empty string after whitespace is
  stripped, so an empty value counts as missing rather than as present.
  The unique-`id` check is the load-bearing rule: `creator_id` is part of
  `UNIQUE (creator_id, source, metric_date)`, so two entries that share an `id` upsert over each
  other and one creator's numbers silently replace the other's, every day, with no error anywhere.
  The history cannot be rebuilt, because the APIs report current values only. *(Claude's call — the
  author chose "you decide".)*
  — **Reversibility:** reversible.

### Retry & Failure Handling

- **D-13:** The hand-rolled decorator retries a **narrow list**: `requests.Timeout`,
  `requests.ConnectionError`, and an HTTP status of 429 or 5xx. Three attempts in total. The sleep is
  two seconds, then four. Every other status fails at once, so a 401 from a bad key and a 404 from a
  bad handle appear in the journal within one second instead of seven. Each retry writes a log line
  naming the creator, the source, and the attempt number. Retrying every `requests.RequestException`
  was rejected: a configuration error would then look like a network problem in the log. The
  decorator lives in the source layer, never in the orchestrator (ARCHITECTURE.md, STACK.md gap 2).
  *(Claude's call — the author chose "you decide".)*
  — **Reversibility:** reversible.

- **D-14:** Fixed backoff only. The decorator does not read `Retry-After` and does not read
  `Ratelimit-Reset`. This job makes about six API calls a day against a 10,000-unit YouTube quota,
  from one box that nothing else shares, so a header-aware wait would be code that never runs. Note
  that YouTube reports quota exhaustion as a 403 with reason `quotaExceeded`, not as a 429, so it is
  not retryable under D-13 and fails at once — which is correct, because the quota does not return
  within seven seconds. STACK.md names header handling as the trigger to adopt `tenacity`, so the
  upgrade path stays open and stays documented. *(Claude's call — the author chose "you decide".)*
  — **Reversibility:** reversible.

- **D-15:** Exactly one `try`/`except` boundary per **(creator, source)** pair, with no cross-pair
  state and no short-circuit. A dead YouTube key produces three logged failures and a
  `failure_count` of three, and the Twitch work still completes. Short-circuiting a source after
  repeated failures of one class was rejected: it puts a failure taxonomy and per-source state into
  the orchestrator, which ARCHITECTURE.md's Anti-Pattern 1 warns against, and `failure_count` would
  then under-report how many creator rows are actually missing. At three creators the wasted calls
  cost about one second. *(Claude's call — the author chose "you decide".)*
  — **Reversibility:** reversible.

- **D-16:** Once the database is open, a `try`/`finally` block **always** writes the `runs` row with
  the counts reached so far, and the original exception then re-raises so the exit code stays
  non-zero. A validation failure happens before the database opens (D-11), so it leaves no row — only
  the journal line and the exit code. Phase 6 can then tell three states apart: the timer never
  fired, the job died part way, and the job completed with failures. Writing the row only on a
  complete run was rejected because Phase 7 criterion 2 asks `/status` to report failure honestly
  rather than reporting success from stale data, and a missing row cannot distinguish a dead job from
  a dead timer. *(Claude's call — the author chose "you decide".)*
  — **Reversibility:** reversible.

### Claude's Discretion

- Whether the record lives in a new `models.py` or beside `Creator` in `config.py`. ARCHITECTURE.md
  proposes `models.py`, and `db.py` plus `models.py` are the only two modules both processes import.
- Column order inside the DDL, and whether `collected_at` carries one value per row or one value per
  run. ARCHITECTURE.md puts it on the record.
- The exact exit code a validation failure returns, and the wording of each error line, provided it
  names the creator and the field.
- The wording and level of the skip line (D-09), the retry line (D-13), and the VOD-count line
  (D-06). INFO is the expectation, because the lines must be visible in a normal `journalctl` read.
- Whether the retry decorator is a decorator or a plain helper function, and where it lives.
- Whether `is_live` is typed `int | None` or `bool | None` in Python, given the column is INTEGER.
- **Identifier resolution and quota.** Phase 1 D-11 fixed the contract: the file holds human-friendly
  identifiers and the code resolves them at run time. No cache is needed, and none should be built.
  YouTube needs no resolution call at all, because `channels.list` accepts `forHandle=@handle` and
  returns `statistics` in the same 1-unit call. Twitch needs `GET /helix/users?login=` for the numeric
  `user_id` that Get Videos and Get Streams require. The per-run call budget is therefore three
  YouTube calls and ten Twitch calls, including one token mint.
- Whether the Twitch app access token is minted once per run or cached with its expiry. STACK.md
  favours one fresh mint per run for a daily job, because the token lives about 58 days with no
  refresh token and re-requesting is one cheap call. Phase 7 must exercise the mint path deliberately
  either way (its criterion 5).
- Test file names and fixture case names, within the `tests/fixtures/{source}/{case}.json` layout
  Phase 1 D-15 fixed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Binding project rules

- `.claude/CLAUDE.md` — the hand-written "Hard Rules" block above the GSD markers. It is
  authoritative where it conflicts with the generated sections below it in the same file. It fixes
  three things this phase must obey: the Twitch follower auth wall is settled and must not be
  worked around; the delta is computed on view count, not subscribers; NULL means "this platform does
  not expose this metric" and `0` means "the platform reported zero", so never `COALESCE(x, 0)`
  before delta math. It also forbids weakening a test to reach green.
- `.planning/PROJECT.md` — constraints, the three human-built areas, and the Key Decisions table.
- `.gitignore` — already covers `*.db`, `*.db-wal`, `*.db-shm`, `.env`, and `*.env`. The database
  this phase first creates must never become trackable.

### Scope

- `.planning/ROADMAP.md` §"Phase 3: Collector Core & API Sources" — the goal, the five success
  criteria, and the nine notes. The notes fix the build order (`models.py` and `db.py` first, then
  `config.py` and the two sources, then `collector.py`), the WAL and `busy_timeout` rule, the
  UTC-once-per-run `metric_date` rule, and the no-retries-in-the-orchestrator rule.
- `.planning/ROADMAP.md` §"Definition of Green" — `ruff check .`, `mypy src/`, and `pytest`, plus the
  manual verification gate that starts at this phase: a human-observed end-to-end run with real API
  data reaching the real database. Automated checks alone cannot close Phase 3.
- `.planning/ROADMAP.md` §"Cut Order" — TikTok is cut item 2. D-09 keeps that option open.
- `.planning/REQUIREMENTS.md` — the 18 requirements this phase owns: CFG-01 to CFG-03, SRC-01,
  SRC-02, SRC-04, SRC-05, DATA-01 to DATA-05, RUN-01, RUN-02, RUN-05, OPS-05 to OPS-07. SRC-03 and
  every SHEET requirement belong to Phase 4 and must not be implemented here.
- `.planning/REQUIREMENTS.md` §"Out of Scope" — the Twitch follower count row records the auth wall.

### Prior phase context

- `.planning/phases/02-vps-systemd/02-CONTEXT.md` — D-05 (the database path
  `/var/lib/creatorpulse/creatorpulse.db`), D-06 (`db.py` opens the path from `CREATORPULSE_DB` and
  must not invent its own default, because the unit is human-built and will not be edited to match),
  D-08 (the fallback and the resolved-path log line), and D-09 (the 08:00 Asia/Manila fire time,
  which is 00:00 UTC, so the UTC `metric_date` equals the Manila calendar date). D-12 is binding:
  `deploy/creatorpulse.service` and `deploy/creatorpulse.timer` may be read and must never be
  written, edited, generated, or reformatted.
- `.planning/phases/01-skeleton/01-CONTEXT.md` — D-09 to D-11 (the `creators.yaml` shape, the
  hand-written `id` slug, and human-friendly identifiers resolved at run time), D-05 (mypy
  `strict = true` for `src/`, which is what forces `int | None` to be handled), D-13 and D-15 and
  D-16 (the fixture-in, record-out pattern, the `tests/fixtures/{source}/{case}` layout, and
  `scripts/record_fixture.py` as the only sanctioned way a fixture is created), D-19 and D-20 (plain
  stdlib logging to stdout).

### Technical grounding

- `.planning/research/ARCHITECTURE.md` §"SQLite Schema" — the DDL, the `ON CONFLICT` upsert, the
  TEXT-ISO-8601 date call, and the no-migration-framework call. **D-01 and D-02 amend its
  `MetricRecord`**, and **D-04 narrows its "both processes run the DDL" advice.** Everything else
  stands.
- `.planning/research/ARCHITECTURE.md` §"Pattern 1" — the `Protocol` plus registry dictionary, and
  why an ABC with lifecycle hooks is the wrong shape. §"Pattern 2" — the normalization boundary and
  the NULL-versus-zero rule. §"Pattern 3" — failure isolation per (creator, source) pair, which D-15
  keeps unchanged. §"Build Order" — the dependency order this phase's plans should follow.
- `.planning/research/PITFALLS.md` §"Pitfall 8" — raise on drift, never return `None` silently. The
  source of D-03's second rule.
- `.planning/research/PITFALLS.md` §"Pitfall 10" — WAL plus `busy_timeout` as the reader and writer
  coordination mechanism behind DATA-05 and D-04.
- `.planning/research/PITFALLS.md` §"Pitfall 11" — naive `INSERT` breaks re-runnability. The source
  of the upsert requirement DATA-02 and OPS-05 grade.
- `.planning/research/PITFALLS.md` §"Pitfall 12" — UTC versus local `metric_date` and the
  midnight-slip case behind RUN-05.
- `.planning/research/PITFALLS.md` §"Pitfall 13" — NULL versus `0` corrupts delta math. The source of
  D-03's first rule and of criterion 4.
- `.planning/research/PITFALLS.md` §"Pitfall 17" — fixture rot, and the test-weakening guard the
  Verify step applies.
- `.planning/research/PITFALLS.md` §"Pitfall 19" — the Twitch `client_credentials` token that is
  minted once and never refreshed, and the follower-count endpoint problem.
- `.planning/research/STACK.md` §"7" — the exact YouTube endpoint, the `forHandle` parameter, the
  API-key-only auth, and the 1-unit-per-call quota. §"8" — the Twitch app access token flow, the
  token lifetime, and the endpoint list. §"2" — the hand-rolled retry decorator and why `tenacity`
  is not added. §"1" — `requests`, already transitive through gspread.
  **Its "What NOT to Use" row for `helix/channels/followers` is misleading; `.claude/CLAUDE.md`
  supersedes it.**
- `.planning/STATE.md` §"Blockers/Concerns" — the live-test item repeated under Specific Ideas below.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`src/creatorpulse/config.py:24-30`** — `resolve_paths()` already returns the resolved config and
  database paths from `CREATORPULSE_CONFIG` and `CREATORPULSE_DB`, and already treats an empty string
  as unset. `db.py` consumes its second return value and must not add a default of its own (Phase 2
  D-06).
- **`src/creatorpulse/config.py:33-45`** — `load_creators()` parses `creators.yaml` into
  `list[Creator]` with `yaml.safe_load`, and takes an injectable path. The `validate()` pass of D-11
  and D-12 layers above it without changing its signature or its existing test.
- **`src/creatorpulse/config.py:17-21`** — `Creator` is
  `@dataclass(frozen=True, slots=True)` with `id`, `name`, and `sources: dict[str, str]`. Match this
  form for `MetricRecord`.
- **`src/creatorpulse/cli.py:22-33`** — `run_collect()` already emits the run-start line naming both
  resolved paths, the loaded-creator count, and the run-end line with duration. The
  `logger.warning("Collector body is not implemented yet...")` line at `cli.py:30` is the exact seam
  this phase replaces. The `config_path.exists()` guard above it is where validation attaches.
- **`src/creatorpulse/cli.py:40-41`** — `collect` already accepts `--config` as the interactive
  override. No new flag is needed.
- **`scripts/record_fixture.py`** — the sanctioned fixture recorder (Phase 1 D-16). It validates
  `--source` and `--case` against a slug pattern before any network call, and it raises on a non-2xx
  response rather than saving the body, so a challenge page cannot masquerade as a fixture. Use it to
  record the YouTube and Twitch fixtures. Never call it from `pytest`.
- **`tests/test_config.py`** and **`tests/test_paths.py`** — the existing suite and its style. OPS-05,
  OPS-06, and OPS-07 extend it.
- **`creators.yaml`** — three real creators (xQc, Pokimane, Kai Cenat), each declaring `youtube`,
  `twitch`, and `tiktok`. This is the file D-09 must not force an edit to.
- **`.env.example`** — already declares `YOUTUBE_API_KEY`, `TWITCH_CLIENT_ID`, and
  `TWITCH_CLIENT_SECRET`. Phase 3 fills these three in the real `/etc/creatorpulse/creatorpulse.env`
  and adds no new variable name.

### Established Patterns

- **`@dataclass(frozen=True, slots=True)`** for record types.
- **mypy `strict = true` for `src/`** (Phase 1 D-05). Every metric field is `int | None`, and strict
  mode refuses to let it silently become `int`. This is the project's correctness rule enforced by
  the type checker.
- **`ignore_missing_imports`** is scoped to `gspread.*` and `yaml` only. `requests` ships types, so
  keep it strictly checked.
- **stdlib `logging` to stdout, plain human-readable format** with `asctime` kept (Phase 1 D-19,
  D-20). Every new log line follows it. No structured logging and no journald handler.
- **No new dependencies.** `requests`, stdlib `sqlite3`, stdlib `time`, stdlib `dataclasses`,
  `PyYAML`. Nothing else is warranted.
- **The four-command gate**, in order: `ruff format --check .`, `ruff check .`, `mypy src/`,
  `pytest` (Phase 1 D-04, D-08).

### Integration Points

- **`cli.py` consumes `collector.py`.** The command name, the argument surface, and the log shape are
  fixed by Phase 1 D-02 and D-03 and must not change, because a human-typed unit file targets them.
- **`db.py` consumes Phase 2 D-05 and D-06.** It opens the path `resolve_paths()` returns. It does not
  create the parent directory: `/var/lib/creatorpulse/` is created by hand during provisioning, and an
  application `mkdir` there would fail under exactly the conditions it is meant to handle.
- **Phase 4 consumes D-01, D-05, and D-08.** The Sheet writer reads the column set, and its
  day-over-day delta inherits the moving-window caveat. `sources/tiktok.py` fills `followers`,
  `likes`, and `video_count`, and adds one registry entry per D-09.
- **Phase 6 consumes D-01 and D-04.** The bot opens the same database with `create=False`, holds
  short-lived connections per command, and reads the column set for `/creator` and `/status`.
- **Phase 7 consumes D-16.** `/status` staleness reporting rests on the `runs` row that a dying run
  still writes.

</code_context>

<specifics>
## Specific Ideas

- **Do this before you build the Twitch parser.** Make one live `GET /helix/videos` call with a real
  app access token and confirm that `view_count` is present and non-zero. STATE.md records this as a
  blocker: the reachability was verified indirectly, not live-tested. The followers auth wall is
  verified HIGH, and if this endpoint walls off the same way, the Twitch metric needs rethinking on
  day one rather than on day five.
- The `runs` row and the log line together should answer "what did this run actually do?" without a
  database query: rows written, failures, and the per-source skip and VOD-count lines.
- OPS-06 wants a fixture in and an expected record out, for each source. The most valuable fixtures
  are not the happy paths: record a `channel_hidden_subs.json` for D-03's first rule and a
  `videos_empty.json` for D-08.
- Keep the YouTube call to one request per creator with `part=statistics&forHandle=@handle`. A
  separate resolution call would double the quota cost for no benefit.

**Open at the time of writing — not decided, and recorded so the researcher can surface options:**

- **How the deliberate source failure of criterion 3 is induced.** The OPS-07 test can monkeypatch a
  fetcher to raise. The live manual gate needs a second method — a bogus handle in a temporary
  `creators.yaml`, or an emptied API key for one run. The two are different proofs and the phase
  needs both.
- **What `03-UAT.md` pastes for each of the five criteria.** Phase 2 D-15 set the pattern of one
  pasted command output per criterion, and `02-UAT.md` is the model to follow. Criterion 2 needs a
  single `sqlite3` query that shows the unchanged row count and yesterday's untouched rows at the
  same time.

</specifics>

<deferred>
## Deferred Ideas

- **`engagement_rate`** — removed by D-02. It returns with the first source that can compute both a
  numerator and a denominator, as one guarded `ALTER TABLE ... ADD COLUMN`.
- **`skipped_count` on the `runs` table** — rejected by D-10. Revisit only if `/status` in Phase 6
  turns out to need it, and note the value reads `0` once Phase 4 lands.
- **`Retry-After` and `Ratelimit-Reset` handling** — declined by D-14. STACK.md names this as the
  trigger to adopt `tenacity`. It is not one at six calls a day.
- **Source-wide short-circuit logic** — declined by D-15. It becomes worth revisiting only if the
  creator count grows far past three, which the 3-source and small-list scope does not plan for.
- **The TikTok source (SRC-03)** — Phase 4. D-09 keeps `creators.yaml` ready for it and keeps the cut
  option open.
- **Delta computation** — Phase 4, in Python, from the database, never as a Sheet formula.
- **Rolling averages and multi-day trends** — V2-DATA-01. They need more accumulated history than the
  build window can produce.
- **Historical backfill** — V2-DATA-02. The APIs report current values only, so a missed day stays a
  gap and Phase 7's `/status` staleness reporting surfaces it.
- **`journalctl` priority mapping** — V2-OPS-01. It needs `systemd-python` and `libsystemd-dev`.
  Deferred twice already.

</deferred>

---

*Phase: 3-Collector Core & API Sources*
*Context gathered: 2026-08-04*
