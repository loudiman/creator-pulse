---
phase: 02-vps-systemd
plan: 03
subsystem: infra
tags: [systemd, timer, uat]

requires:
  - phase: 02-vps-systemd
    plan: 02
    provides: 02-UAT.md entries 2 and 3 pasted, droplet secrets/stripped-env proof
provides:
  - 02-UAT.md entries 1 and 4 with pasted droplet evidence, result pass
  - 02-UAT.md closed (status complete, 5/5 passed)
affects: [03-collector]

tech-stack:
  added: []
  patterns:
    - "UAT evidence: author-pasted block first, agent-executed judgement appended below labelled and separated by a rule (matches 02-02's local convention for this file)"

key-files:
  created: []
  modified: [.planning/phases/02-vps-systemd/02-UAT.md]

key-decisions:
  - "Entry 1 carries a limitation block: this fire ran Phase 1's placeholder collect, so RUN-03 only fully closes in Phase 3"
  - "Reboot catch-up recorded as two attempts (a diagnosed true-negative, then a passing run), not just the passing one — the margin-vs-boot-time failure mode is worth keeping visible"
  - "systemd-analyze calendar validates a CLI string, not the loaded unit, surfaced when a stale test schedule briefly survived a re-check that used the wrong tool; corrected and re-verified with systemctl cat before entry 4 was written"

requirements-completed: [RUN-03]

coverage:
  - id: D1
    description: "Timer fires with nobody logged in; systemctl list-timers shows a populated LAST and journalctl -u creatorpulse.service holds that run's four lines afterwards, NEXT is exact (no jitter)"
    requirement: "RUN-03"
    verification:
      - kind: manual
        ref: "02-UAT.md entry 1, author-pasted list-timers + journalctl, PID distinct from entry 2's manual runs"
        status: pass
    human_judgment: true
    rationale: "Requires a real unattended fire on the droplet; not reproducible on the dev box."
  - id: D2
    description: "systemd-analyze calendar confirms 08:00 Asia/Manila == 00:00 UTC; a reboot across a shifted, missed fire window produces exactly one Persistent=true catch-up run, not one per missed occurrence"
    requirement: "RUN-03"
    verification:
      - kind: manual
        ref: "02-UAT.md entry 4, author-pasted calendar output (unqualified vs Asia/Manila), two reboot attempts, restored-schedule re-check against systemctl cat"
        status: pass
    human_judgment: true
    rationale: "Requires physically rebooting the droplet during a deliberately shifted fire window; not reproducible on the dev box."
  - id: D3
    description: "Author's own written explanation of systemd timer vs cron (already closed in a prior session, untouched by this plan)"
    requirement: "RUN-03"
    verification:
      - kind: manual
        ref: "02-UAT.md entry 5, committed a594de9"
        status: pass
    human_judgment: true
    rationale: "Spoken/written-explanation criterion by definition; carried forward unchanged from the prior commit, not re-graded here."

duration: ~20min
completed: 2026-08-04
status: complete
---

# Phase 2 Plan 3: Unattended timer fire, reboot catch-up, and UAT closure Summary

**Pasted droplet evidence closes ROADMAP criteria 1 and 4 — an overnight fire nobody triggered, and a deliberately missed/reboot-caught-up window with exactly one catch-up run — and 02-UAT.md is closed at 5/5 passed**

## Performance

- **Tasks:** 2 (Task 1 checkpoint:human-action, resolved this session; Task 2 auto)
- **Files modified:** 1 (`02-UAT.md`)

## Accomplishments
- ROADMAP criterion 1 closed: `systemctl list-timers` shows an exact (no-jitter) `NEXT` and a populated `LAST` for a fire the author did not trigger (PID 13392, distinct from entry 2's manual runs); `journalctl -u creatorpulse.service` holds that run's four lines
- ROADMAP criterion 4 closed: `systemd-analyze calendar` confirms the timezone qualifier is load-bearing (unqualified → 08:00 UTC, wrong; `Asia/Manila`-qualified → 00:00 UTC, correct); a deliberately shifted-window reboot produced exactly one `Persistent=true` catch-up run across two attempts (one diagnosed true-negative, one passing catch-up), and the restored schedule was re-verified against the loaded unit, not just the calendar string
- Entry 1 carries a `limitation:` block: this fire ran Phase 1's placeholder `collect`, so RUN-03 is proven for the unattended-timer half here and fully closes in Phase 3 when the real collector is wired
- `02-UAT.md` closed: `status: complete`, `## Current Test` → `[testing complete]`, `## Summary` → `total: 5, passed: 5, pending: 0`
- Green gate re-confirmed after closure: `ruff check .`, `mypy src/`, `pytest` all exit 0

## Task Commits

1. **Task 1: Paste droplet evidence into entries 1 and 4** - `c516334` (docs)
2. **Task 2: Close 02-UAT.md — status complete, 5/5 passed** - `f0e7811` (docs)

## Files Created/Modified
- `.planning/phases/02-vps-systemd/02-UAT.md` - entries 1 and 4 filled with pasted droplet evidence plus agent-executed judgement; frontmatter `status: complete`; `## Current Test` and `## Summary` updated to reflect 5/5 passed

## Decisions Made
- Entry 1's `limitation:` block records RUN-03's partial closure (roadmap's own note, not a gap introduced here)
- Both reboot attempts recorded in entry 4 rather than only the passing one — attempt 1's 76s margin against 52s of actual downtime is a diagnosed true-negative (booted before the window), not a defect, and keeping it visible documents the reboot test's own failure mode (a margin shorter than droplet boot time proves nothing)
- The `systemd-analyze calendar` / loaded-unit gap (the command validates a CLI string, never the unit file) is recorded as a finding rather than silently absorbed, since it is the specific tool D-11's own wording names for re-checking

## Deviations from Plan

None — no code changed, no bugs found. This plan is evidence-and-proof only, exactly as scoped.

### Recorded Findings (not deviations from the task list, but discoveries during execution, per the plan's own instruction to read pastes against documented systemd behaviour)

**1. `AccuracySec` delay, not drift (entry 1).** Timer scheduled `00:00:00`, service logged `00:00:11`. systemd's default `AccuracySec=1min` batches timer wakeups; distinct from `RandomizedDelaySec` jitter, which D-10 declined and which the exact, range-free `NEXT` timestamp confirms is absent.

**2. `systemd-analyze calendar` validates a CLI string, not the unit (entry 4).** After the second reboot attempt, the schedule was first re-checked with `systemd-analyze calendar 'Asia/Manila'`-qualified — which reported the correct answer — while the unit still held the shifted test value (`17:28:00`, unqualified/UTC). The command never reads the unit file; only `systemctl cat`/`list-timers` show what's loaded. Caught and corrected before this entry was written (Part C of entry 4). A documentation-level gap in D-11's own re-check wording, not an execution mistake.

**3. Reboot test has a real failure mode (entry 4).** A margin shorter than droplet boot time produces a true negative indistinguishable from a broken `Persistent=` without cross-checking `uptime -s` against `journalctl --list-boots`. Attempt 1 (76s margin, 52s actual downtime) is exactly this case, diagnosed rather than mistaken for failure; attempt 2 (wider margin) is the clean pass. Both recorded.

## Issues Encountered

None blocking. See Recorded Findings above.

## User Setup Required

None further — Phase 2's droplet work is complete: provisioned, service starts by hand and by timer, timer survives reboot with correct catch-up semantics, and secrets/paths are proven (entries 2/3, prior plan).

## Next Phase Readiness

- All five ROADMAP Phase 2 success criteria are closed; `02-UAT.md` is `status: complete`, 5/5 passed
- RUN-03 is proven for the unattended-timer half; its full closure (real rows from a real collector) is Phase 3's job, already noted in entry 1's `limitation:` block
- No open blockers for Phase 3

---
*Phase: 02-vps-systemd*
*Completed: 2026-08-04*
