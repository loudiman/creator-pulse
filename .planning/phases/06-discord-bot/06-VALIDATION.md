---
phase: 6
slug: discord-bot
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-06
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `06-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (already locked in `pyproject.toml` `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` (`testpaths = ["tests"]`) |
| **Quick run command** | `pytest tests/test_bot.py -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~2 seconds (93 tests currently pass in 1.70s) |

**Interpreter note:** the session's default `python` resolves to a global 3.14 install without project
dependencies. Use `.venv/Scripts/python.exe -m pytest` on this machine, or activate the venv first.
Recorded during quick task `260806-k5w`.

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_bot.py -x`, plus `tests/test_db.py` /
  `tests/test_collector.py` when that commit touched D-06 or D-13 surfaces
- **After every plan wave:** `pytest` (full suite)
- **Before `/gsd-verify-work`:** full suite green, **plus** the human-observed real-data gate ROADMAP
  requires — a real scheduled digest and a real failure alert landing in the real channel
- **Max feedback latency:** ~2 seconds

---

## Per-Task Verification Map

Task IDs are filled in by the planner. Requirement→behavior mapping is fixed here.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01 T1 | 06-01 | 1 | — (D-13 refactor) | — | N/A | unit | `pytest tests/test_sheets.py tests/test_db.py -x` | ✅ | ⬜ pending |
| 06-01 T2 | 06-01 | 1 | BOT-01, BOT-06 | T-06-02, T-06-04, T-06-05 | Config errors name the variable, never the value; the digest loop body catches its own exceptions; `Intents.default()` only | unit | `pytest tests/test_bot.py -k "digest or config" -x` | ❌ W0 | ⬜ pending |
| 06-01 T3 | 06-01 | 1 | BOT-01 | — | Human gate — a real digest in the real channel | manual | — | N/A | ⬜ pending |
| 06-02 T1 | 06-02 | 2 | BOT-03 (D-06 schema) | T-06-08 | Alert count and `runs` row are built from the same result | unit | `pytest tests/test_db.py tests/test_collector.py -x` | ✅ | ⬜ pending |
| 06-02 T2 | 06-02 | 2 | BOT-03 | T-06-03, T-06-06, T-06-07 | No log record holds the webhook URL; `allowed_mentions` suppresses pings; a failed POST never replaces the error in flight | unit | `pytest tests/test_bot.py -k alert -x` | ❌ W0 | ⬜ pending |
| 06-03 T1 | 06-03 | 3 | BOT-02 | T-06-04, T-06-09 | Strict `>` at ±20% and at 26h, matching `Code.gs`; new reads sit inside the loop guard | unit | `pytest tests/test_bot.py -k "flag or stale" -x` | ❌ W0 | ⬜ pending |
| 06-03 T2 | 06-03 | 3 | BOT-01 | T-06-01 | `WHERE run_id = ?` bound, never interpolated | unit | `pytest tests/test_bot.py -k "digest or failure" -x` | ❌ W0 | ⬜ pending |
| 06-04 T1 | 06-04 | 4 | BOT-07 | T-06-02, T-06-05 | COVERAGE.md records the surface, never a credential; the three privileged intents each get their own opt-out row | doc | `test "$(grep -c '^\| capability \| decision \| reason \|$' .planning/phases/06-discord-bot/COVERAGE.md)" -eq 1` | ❌ W0 | ⬜ pending |
| 06-04 T2 | 06-04 | 4 | BOT-06 | T-06-10 | No entry closed without traceable evidence; systemd install recorded as a human step, not performed | doc | `test "$(grep -c '^### ' .planning/phases/06-discord-bot/06-UAT.md)" -eq 5` | ❌ W0 | ⬜ pending |
| 06-05 T1 | 06-05 | 4 | BOT-04 | T-06-01, T-06-02 | `WHERE creator_id = ?` bound, never f-string interpolated; no reply derives from configuration | unit | `pytest tests/test_bot.py -k creator -x` | ❌ W0 | ⬜ pending |
| 06-05 T2 | 06-05 | 4 | BOT-05 | T-06-04, T-06-11 | Short-lived per-handler connection; guild membership is the access control, accepted | unit | `pytest tests/test_bot.py -k status -x` | ❌ W0 | ⬜ pending |
| — | 06-04 | — | BOT-06 | — | Unit runs as `creatorpulse`, reads `EnvironmentFile` | manual | — | N/A | ⬜ pending |
| — | 06-04 | — | BOT-07 | T-06-05 | Zero privileged intents; View Channel + Send Messages only | manual | — | N/A | ✅ done 2026-08-06 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_bot.py` — **new file.** Covers the pure formatters (digest text, trend text, status
      text, ±20% flag, percent computation, staleness verdict) against a temporary SQLite database.
      Copies the pattern `tests/test_sheets.py` already establishes for `build_dashboard_rows()`.
- [ ] `tests/test_db.py` — extend for the `run_failures` table DDL and `write_run_row()` returning
      `cursor.lastrowid` (D-06)
- [ ] `tests/test_collector.py` — extend for `collect_once()` accumulating failure detail (creator,
      source, cause, message), not just a count (D-06)
- [ ] `tests/test_sheets.py` — imports follow `LATEST_ROWS_SQL` / `LatestRow` / `fetch_latest_rows()`
      to `db.py` (D-13). **Mechanical import change only** — the test-weakening guard applies and the
      diff must show nothing else.

No new test framework, fixture root, or dependency is needed. `pytest`, `tmp_path`, and the
temp-SQLite pattern are wired from Phase 1 onward.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A scheduled digest posts itself with no human trigger | BOT-01 | Requires a live gateway connection and a real 08:15 fire; fixtures-only rule forbids network in the suite | Watch the real channel at 08:15 Asia/Manila. For a forced proof, call the digest coroutine directly rather than waiting for the slot |
| ±20% flag visible in a real digest | BOT-02 | Same — the rendering is unit-tested, the *posting* is not | Read the posted message |
| Failure alert lands immediately, earlier than the digest | BOT-03 | Ordering across two processes and a real webhook | Break one source (bogus handle in `creators.yaml`), run the collector by hand, watch the alert land, then watch the 08:15 digest arrive separately listing that failure. Both messages, in order, one screenshot |
| `/creator` and `/status` answer in-channel | BOT-04, BOT-05 | Slash-command dispatch needs a real gateway and a real guild | Type each command in the guild |
| Bot survives a reboot as its own service | BOT-06 | Requires the droplet and systemd | `systemctl enable --now creatorpulse-bot`, reboot, confirm the bot reconnects. **Only after `creatorpulse bot` is implemented** — the current stub exits 3 and would restart-loop every 10s |
| Author explains which intents are requested and why none are privileged | BOT-06 criterion 5 | Human knowledge check, unfakeable by a test | Author writes the explanation into `06-UAT.md` unaided. **Do not let this join Phase 5's still-PENDING equivalent** |

**Coverage boundary, stated deliberately (D-20):** pytest covers the pure formatters. The gateway
client, the task loop, and command registration are **not** tested. That gap is a recorded decision,
not an oversight — the human-observed gate above is what proves the plumbing.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without an automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] Digest-loop exception guard is present and tested — see `06-RESEARCH.md` Pitfall 1: an
      unhandled non-network exception inside a `tasks.loop` body kills the loop permanently
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
