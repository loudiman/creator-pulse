---
phase: 02-vps-systemd
verified: 2026-08-04T00:00:00Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 2: VPS & systemd Verification Report

**Phase Goal:** A rented Linux box runs scheduled work unattended, logs it, and holds secrets the repo never sees
**Verified:** 2026-08-04T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Notes on method

This phase's `Owner` is `mixed` (D-01): the agent wrote only `resolve_paths()` and its wiring in
`src/creatorpulse/`; the systemd unit, timer, UFW, SSH, and `docs/deploy.md` are human-built per
`.claude/CLAUDE.md`'s hard rule and are correctly absent from the repo's writable surface — their
absence is not treated as a gap below. Four of five ROADMAP criteria are droplet facts provable
only by the author's pasted terminal output in `02-UAT.md`; that document (`status: complete`,
5/5 `result: pass`) is the human-verification artifact this project's own process (D-15) designates
for exactly this purpose, so it is read as completed evidence, not as an open human-verification
item still owed. Verification below (a) independently reproduced the two checks that don't require
a droplet — the git-history secret search and the code/test green gate — and (b) cross-read every
pasted evidence block against the actual `src/creatorpulse/` code and against documented systemd
semantics, rather than accepting the SUMMARY narrative.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A systemd timer fires on schedule with no human present, output readable via `journalctl -u <unit>` | VERIFIED | `02-UAT.md` entry 1: `systemctl list-timers` shows `LAST` populated for PID 13392, distinct from the manual-run PIDs in entry 2; `journalctl -u creatorpulse.service` holds that run's four lines. Exact (jitter-free) `NEXT` confirms D-10. Carries an honest `limitation:` block: this fire ran Phase 1's placeholder collector, not real data — RUN-03 fully closes in Phase 3 (roadmap's own note, verified present in ROADMAP.md line 128). |
| 2 | `systemctl start <unit>` succeeds against the same code path that works interactively | VERIFIED | `02-UAT.md` entry 2: exit status 0, four-line run shape matches Phase 1 shape, both resolved absolute paths present and unit-supplied (`/home/creatorpulse/creator-pulse/creators.yaml`, `/var/lib/creatorpulse/creatorpulse.db`) — cross-checked against `src/creatorpulse/cli.py:24`'s actual `logger.info` call, which does emit exactly this line. `env -i` stripped-env reproduction failed loudly and legibly as designed, with its real scope (cwd-relative fallback, not "no login shell") honestly recorded rather than overclaimed. |
| 3 | Service reads secrets from a `chmod 600` env file via `EnvironmentFile`, values absent from repo and `git log` | VERIFIED | Droplet half: `02-UAT.md` entry 3 pastes `stat` → `600 root:root` and `systemctl cat` → `EnvironmentFile=/etc/creatorpulse/creatorpulse.env` plus two `Environment=` path lines, no secret value. Repo half independently reproduced by this verifier (not just trusted from the SUMMARY): `git ls-files \| grep -E '(env\|service-account\|credentials\|token)'` → only `.env.example`; `git log --all --diff-filter=A --name-only` → no secret-pattern path ever added on any branch; `git log --all -S<NAME>` for all six `.env.example` variable names → only doc/scaffold commits, each confirmed blank-valued by reading the diff of `19397fd` directly (`.env.example` shows `YOUTUBE_API_KEY=` etc., no `CREATORPULSE_*` lines). |
| 4 | Timer survives a reboot and, with `Persistent=true`, catches up a missed run | VERIFIED | `02-UAT.md` entry 4: `systemd-analyze calendar` confirms `Asia/Manila` 08:00 = 00:00 UTC (D-09); two reboot attempts recorded — attempt 1 a diagnosed true negative (boot margin shorter than the missed window, correctly zero catch-up), attempt 2 a clean single catch-up run 8 minutes after the missed window, `systemctl cat`-verified schedule restoration afterward. Matches `Persistent=`'s documented single-fire semantics; the reviewer's own re-check tool gap (`systemd-analyze calendar` validates a CLI string, not the loaded unit) is caught and corrected in the same entry, not glossed over. |
| 5 | The author can explain out loud, without notes, why systemd timer beats cron here | VERIFIED | `02-UAT.md` entry 5: verbatim transcribed answer citing timezone-awareness and `Persistent=` catch-up (both technically correct and evidence-backed by entries 2 and 4), with the weak "modern" point and the uncited stronger arguments (journald capture, `After=` ordering) explicitly flagged to the author pre-interview rather than smoothed over. |

**Score:** 5/5 truths verified (0 present-but-behavior-unverified — all five are backed by the droplet evidence this phase's own process designates as proof, not left as an open human item)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/creatorpulse/config.py` | `resolve_paths()`, `DEFAULT_DB_PATH` | VERIFIED | Present, both env vars read independently into `str \| None`, empty-string treated as unset, no mkdir, no existence check — matches D-08 exactly (config.py:24-30) |
| `src/creatorpulse/cli.py` | `run_collect(config_path, db_path)` logging both paths first | VERIFIED | Signature changed as specified; `logger.info` at line 24 names both paths before any I/O that can raise (cli.py:22-27) |
| `tests/test_paths.py` | env-set/unset/mixed/empty/log-line coverage | VERIFIED | 5 tests, all green; `pytest` 6/6 passed repo-wide |
| `.env.example` | six blank v1 secret vars, no `CREATORPULSE_*` | VERIFIED | Confirmed via `gsd-tools verify.artifacts` (non-stub) and by reading commit `19397fd`'s diff directly: `YOUTUBE_API_KEY=`, `TWITCH_CLIENT_ID=`, `TWITCH_CLIENT_SECRET=`, `DISCORD_BOT_TOKEN=`, `DISCORD_WEBHOOK_URL=`, `GOOGLE_SERVICE_ACCOUNT_FILE=`, all blank, no `CREATORPULSE_*` lines |
| `.planning/phases/02-vps-systemd/02-UAT.md` | five-section proof, `status: complete` | VERIFIED | `status: complete`, `total: 5, passed: 5, pending: 0`, five `result: pass` entries |
| `deploy/creatorpulse.service`, `deploy/creatorpulse.timer`, `docs/deploy.md` | human-built, out of agent scope | N/A — correctly absent | No plan promised the agent would create these (D-01, D-12, D-13); confirmed not present via `git ls-files \| grep -E '^(deploy/\|docs/)'` (no matches) — this is not scored as a gap per the phase's own ownership split, but see note below |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/creatorpulse/cli.py` | `src/creatorpulse/config.py` | `main()` calls `resolve_paths()`, threads both results into `run_collect()` | WIRED | `gsd-tools query verify.key-links` reported a false negative (regex-escaping artifact in the tool call, "Invalid regex pattern"), so verified manually: `cli.py:51` calls `resolve_paths()`, `cli.py:54` passes `(config_path, db_path)` into `run_collect(config_path, db_path)` |
| `02-UAT.md` pasted `journalctl` output | `src/creatorpulse/cli.py`'s `logger.info` call | the run-start line's shape | WIRED | Pasted line `Starting collect run using config ..., database ...` matches `cli.py:24`'s format string exactly; both resolved paths in the paste are the unit-supplied absolutes, not the repo-relative fallback |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RUN-03 | 02-03 | Collector runs unattended on a daily systemd timer (human-built unit/timer) | SATISFIED | `02-UAT.md` entry 1, with an honest limitation that the fired job is Phase 1's placeholder — matches ROADMAP.md's own line 128 note that RUN-03 fully closes in Phase 3 |
| RUN-04 | 02-01, 02-02 | Run output readable after the fact via `journalctl -u <unit>` | SATISFIED | `02-UAT.md` entries 1, 2, 4 all show readable journal output; `resolve_paths()` + logging code independently confirmed in source |
| OPS-01 | 02-02 | Secrets load from `chmod 600` env file via `EnvironmentFile`, never committed | SATISFIED | `02-UAT.md` entry 3 (droplet) + independently reproduced git-history search (this verification) |

No orphaned requirements: REQUIREMENTS.md maps exactly RUN-03, RUN-04, OPS-01 to Phase 2, and all three are claimed across the three plans' `requirements` frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/creatorpulse/cli.py` | 50-54 | `--config` CLI override branch (`args.config is not None`) has zero test coverage (WR-01, `02-REVIEW.md`) | ⚠️ Warning | Advisory. The systemd unit's `ExecStart` does not pass `--config` (confirmed via `02-UAT.md` entry 3's `systemctl cat` paste), so this untested branch is not exercised in production — does not undermine any of the 5 success criteria. Worth a test before this flag sees real interactive use. |
| `src/creatorpulse/cli.py` | 25-28 | `config_path.exists()` is `True` for directories; a misconfigured directory path raises unhandled `IsADirectoryError` instead of a clean logged error (WR-02, `02-REVIEW.md`) | ⚠️ Warning | Advisory, pre-existing (not new in this diff's `+/-` lines) but now more load-bearing. Does not affect any of the 5 verified criteria — the actual pasted evidence uses correct file paths throughout. Contradicts the phase's own "first log line explains what happened" design intent in the one misconfiguration case it doesn't cover. |
| — | — | No `TBD`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` markers found in any file touched this phase | Info | Clean |

**Observation (not scored as a gap, per this task's explicit instruction not to treat `deploy/`/`docs/` absence as an agent deliverable gap):** D-12 in `02-CONTEXT.md` states the two unit files "are committed to the repository." `git ls-files` shows no `deploy/` directory tracked at all. This is the author's own decision to fulfil, not a plan deliverable, and none of the 5 ROADMAP criteria depend on the files being in the repo (only on the droplet, which the pasted `systemctl cat` output already proves). Flagging for the author's awareness ahead of the interview, where "diffable unit files" was D-12's stated rationale.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite green | `pytest` | 6 passed | ✓ PASS |
| Lint clean | `ruff check .` | All checks passed | ✓ PASS |
| Type-check clean | `mypy src/` | Success: no issues in 3 source files | ✓ PASS |
| No dependency added | `git log -- pyproject.toml` since phase start | Last touched in Phase 1 (`c7842e2`), untouched since | ✓ PASS |
| No secret-bearing file ever committed | `git ls-files` / `git log --all --diff-filter=A` against `.env`/service-account/credentials/token patterns | No matches besides `.env.example` | ✓ PASS |
| `.env.example` values genuinely blank | Direct read of commit `19397fd`'s diff | Six `KEY=` lines, all blank, no `CREATORPULSE_*` | ✓ PASS |

### Human Verification Required

None. All droplet-only facts are already proven by the author's pasted evidence in `02-UAT.md` (`status: complete`, 5/5 `result: pass`), which this verification cross-checked against the actual code and against documented systemd semantics rather than accepting on narrative alone.

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are backed by pasted droplet evidence that has been
cross-checked (not merely trusted) against the actual `src/creatorpulse/` code, git history, and
documented systemd behavior. The two code-review warnings (WR-01, WR-02) are real but advisory —
neither is exercised by the production unit's `ExecStart` or by any of the paste evidence, and
neither was a stated must-have of this phase's plans. The RUN-03 "placeholder collector" scope
limit is the roadmap's own explicitly documented and accepted boundary, not an undisclosed shortfall
— `02-UAT.md` entry 1 states it plainly.

---

*Verified: 2026-08-04T00:00:00Z*
*Verifier: Claude (gsd-verifier)*
