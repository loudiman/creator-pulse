---
phase: 3
slug: collector-core-api-sources
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-04
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `pytest tests/test_collector.py tests/test_sources.py -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~5 seconds (fixtures only, no network, no browser) |

Note: this phase's Definition of Green is four commands, not one — `ruff format --check .`,
`ruff check .`, `mypy src/`, `pytest` (Phase 1 D-04/D-08). The sampling rate below governs `pytest`
only; the other three run at wave merge.

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_collector.py tests/test_sources.py -x`
- **After every plan wave:** Run `pytest`, then `ruff format --check .`, `ruff check .`, `mypy src/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

Task IDs are seeded by the planner. Rows below are keyed by requirement until plans exist; the
executor fills the Task ID and Plan columns as each plan lands.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 1 | DATA-01, DATA-02 | T-03-01 | Named-placeholder bind, never f-string SQL | unit | `pytest tests/test_db.py::test_upsert_same_key_updates_not_duplicates -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | DATA-04 | — | N/A | unit | `pytest tests/test_db.py::test_upsert_different_date_does_not_touch_prior_row -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | DATA-05 | — | Bot opens `create=False`; missing table raises, never auto-creates | unit | `pytest tests/test_db.py::test_create_false_raises_on_missing_table -x` | ❌ W0 | ⬜ pending |
| TBD | 03-05 | 4 | DATA-02 | — | Never `COALESCE(x, 0)` — a stored `0` and a stored `NULL` round-trip distinct and non-equal | unit | `pytest tests/test_db.py::test_stored_null_and_zero_round_trip_distinct -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | SRC-04 | — | N/A | unit | `pytest tests/test_models.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | CFG-01, CFG-02 | — | N/A | unit | `pytest tests/test_config.py -x` | ✅ (file exists, cases missing) | ⬜ pending |
| TBD | TBD | 2 | CFG-03 | T-03-02 | `yaml.safe_load` only; validation runs before any network call | unit | `pytest tests/test_config.py::test_validate_reports_every_problem -x` | ✅ (file exists, cases missing) | ⬜ pending |
| TBD | 03-06 | 3 | SRC-01, SRC-04, OPS-06 | T-03-03 | Lazy `%`-style logging of creator id, never f-string | unit | `pytest tests/test_sources.py::test_youtube_hidden_subscriber_count_maps_to_none -x` | ❌ W0 | ⬜ pending |
| TBD | 03-03 | 4 | SRC-02, SRC-04, OPS-06 | T-03-04 | Token and headers never logged | unit | `pytest tests/test_sources.py -x -k twitch` | ❌ W0 | ⬜ deferred — SRC-02 blocked on Twitch 2FA; no client id, so the 5 Twitch fixtures cannot be recorded and 03-03 is unexecuted (REQUIREMENTS.md §Sources) |
| TBD | 03-06 | 3 | SRC-05 | T-03-04 | Retry line carries identifier, source, attempt number — never headers, params, key, or bearer | unit | `pytest tests/test_sources.py::test_retries_on_429_then_succeeds -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | RUN-01, RUN-02, OPS-07 | — | N/A | unit | `pytest tests/test_collector.py::test_one_source_failure_does_not_abort_run -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | RUN-05 | — | N/A | unit | `pytest tests/test_collector.py::test_all_rows_from_one_run_share_metric_date -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | DATA-03 | — | N/A | unit | `pytest tests/test_collector.py::test_runs_row_written_on_crash -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | OPS-05 | — | N/A | integration | `pytest tests/test_collector.py::test_idempotent_rerun_same_day -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · ⬜ deferred (planned, blocked externally, not dropped)*

---

## Wave 0 Requirements

- [ ] `tests/test_db.py` — DDL, upsert, and `connect(create=...)` tests. No fixture dependency and no
      credential dependency; can be written first.
- [ ] `tests/test_collector.py` — orchestration tests (idempotency, failure isolation,
      `metric_date`-once, `runs`-row-on-crash). Uses a fake in-memory fetcher registry, so it needs
      no recorded fixtures and no credentials.
- [ ] `tests/test_sources.py` — created by `03-06` (wave 3) with the retry cases and the YouTube
      fixture-in / record-out cases, then *extended* by `03-03` with the Twitch cases. The retry half
      needs no fixture at all (scripted local callable, faked clock); the YouTube half reads the four
      fixtures below; only the Twitch half is blocked.
- [ ] `tests/test_config.py` — extend the existing file with `validate()` cases. No fixture
      dependency.
- [ ] `tests/fixtures/youtube/channel_ok.json`, `channel_not_found.json` — record with
      `scripts/record_fixture.py`. Needs a real `YOUTUBE_API_KEY`. Then
      `channel_hidden_subs_derived.json` and `channel_hidden_subs_omitted_derived.json` — *derived*
      from the recorded `channel_ok.json` body by a hand-run step (03-01 Task 2 step E), with only
      `statistics.hiddenSubscriberCount` and `statistics.subscriberCount` changed, because no such
      channel is available to record. The two cover both shapes RESEARCH.md A1 leaves open.
- [ ] **BLOCKED ON CREDENTIALS (2026-08-05) — kept in the list, not dropped.**
      `tests/fixtures/twitch/videos_ok.json`, `videos_empty.json`, `users_not_found.json`,
      `streams_live.json`, `streams_offline.json` — record with `scripts/record_fixture.py`. Needs
      real Twitch credentials. Recording `videos_ok.json` is the same call as the live verification
      below, so run it first and record it once.
      Blocked: registering a Twitch application requires 2FA, 2FA enrolment requires a mobile number,
      and the verification SMS does not arrive — so no client id, no secret, no app access token.
      Recording is the only sanctioned way to produce these five; hand-authoring is forbidden and the
      blockage creates no exception. Re-executable verbatim from `03-01-PLAN.md`
      §"Deferred — blocked on Twitch credentials (SRC-02)". See `REQUIREMENTS.md` §Sources.

No framework install is needed — pytest 9.1.1 is already pinned and installed, and `tests/` already
holds two passing files.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| **⬜ DEFERRED (2026-08-05)** — `GET /helix/videos` returns a usable `view_count` under an app access token | SRC-02 | No fixture can prove an auth wall does not exist. STATE.md records this as a blocker, verified indirectly only. RESEARCH.md assumption A2 rests on community sources because `dev.twitch.tv` was unreachable. **Deferred, not dropped:** no client id or secret can be obtained (Twitch 2FA requires a mobile number; the SMS does not arrive), so no app token can be minted. This blocker stays open and the instructions stay verbatim for later. | Mint an app token, then call `GET /helix/videos?user_id=<xqc>&type=archive&first=100` with and without `period=month`. Diff the two result sets. Record both outcomes in `journal.md`. Run this before writing the parser body. |
| **⬜ DEFERRED (2026-08-05)** — `period=month` actually filters by publish date | SRC-02 (D-05) | RESEARCH.md Pitfall T1 — three independent forum reports (2018, 2021, March 2025) say the parameter is ignored. Only a live call settles it. **Deferred with the row above, same cause, same credential.** | Same call as above. If `period` is ignored, D-05's window is Twitch's retention window instead of one month. The decision does not change; the caveat in the README (OPS-08) and `journal.md` does. |
| Real API data reaches the real database | Phase gate | ROADMAP.md §"Definition of Green" — from Phase 3 onward every phase needs a human-observed end-to-end run. Automated checks cannot close this phase. | Run `creatorpulse collect` on the droplet against real credentials. Paste the journal output and a `sqlite3` query into `03-UAT.md`, one paste per criterion (D-19). |
| One source made to fail is logged, counted, and does not stop the run | Criterion 3 | The unit test monkeypatches a raise. The manual gate must meet a real bad input on the real code path. | Add a fourth `creators.yaml` entry with a real `id` and a handle that does not exist (D-18). Run once. Paste the journal. Revert the file. |
| Reader and writer share the database without a lock error | DATA-05, criterion 5 | Real concurrency across two processes cannot be proven by a single-process unit test. | Run `sqlite3 /var/lib/creatorpulse/creatorpulse.db 'select count(*) from metrics;'` while the collector is mid-run. Paste both outputs. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
