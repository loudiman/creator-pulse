---
phase: 02-vps-systemd
plan: 02
subsystem: infra
tags: [systemd, secrets, git-history, uat]

requires:
  - phase: 02-vps-systemd
    plan: 01
    provides: resolve_paths(), run-start log line, .env.example, 02-UAT.md scaffold
provides:
  - 02-UAT.md entries 2 and 3 with pasted droplet evidence, result pass
  - repo-side proof no secret value was ever committed on any branch
affects: [02-03]

tech-stack:
  added: []
  patterns:
    - "UAT evidence: author-pasted block first, agent-executed block appended below labelled and separated by a rule"

key-files:
  created: []
  modified: [.planning/phases/02-vps-systemd/02-UAT.md]

key-decisions:
  - "D-05 confirmed unchanged (Task 1, prior commit 2bcda1f)"
  - "Criterion-wording gap recorded rather than silently absorbed: git log -S per variable hits 2 commits, not the 1 the acceptance criteria predicted, because plan-file prose also names the variables (blank-valued)"

requirements-completed: [OPS-01, RUN-04]

coverage:
  - id: D1
    description: "systemctl start exercises the same code path as an interactive run, both resolved absolute paths present and unit-supplied (not repo-relative fallback)"
    requirement: "RUN-04"
    verification:
      - kind: manual
        ref: "02-UAT.md entry 2, author-pasted systemctl start + journalctl + two interactive baselines"
        status: pass
    human_judgment: true
    rationale: "Requires a real systemd unit on a droplet; not reproducible on the dev box."
  - id: D2
    description: "Secrets file is 600 root:root, referenced via EnvironmentFile with no secret value in the unit"
    requirement: "OPS-01"
    verification:
      - kind: manual
        ref: "02-UAT.md entry 3, author-pasted stat + systemctl cat"
        status: pass
    human_judgment: true
    rationale: "Requires reading real file permissions on the droplet."
  - id: D3
    description: "No env/service-account/credentials/token file, and no real secret value, ever entered git history on any branch"
    requirement: "OPS-01"
    verification:
      - kind: other
        ref: "git ls-files, git log --all --diff-filter=A --name-only, git log --all -S<NAME> per variable"
        status: pass
    human_judgment: false
duration: ~25min
completed: 2026-08-03
status: complete
---

# Phase 2 Plan 2: Droplet secrets and stripped-environment proof Summary

**Author-provisioned droplet evidence pasted into 02-UAT.md entries 2 and 3, cross-checked against 02-01's `resolve_paths()`/logging code; repo-side git-history search confirms no secret value or secret-bearing file was ever committed on any branch**

## Performance

- **Tasks:** 3 (Task 1 checkpoint:decision, prior commit; Task 2 checkpoint:human-action, this session; Task 3 auto)
- **Files modified:** 1 (`02-UAT.md`)

## Accomplishments
- ROADMAP criterion 2 closed: `systemctl start creatorpulse.service` exits 0, journal shows the same four-line run shape as the interactive baseline, both resolved absolute paths (`/home/creatorpulse/creator-pulse/creators.yaml`, `/var/lib/creatorpulse/creatorpulse.db`) are the unit-supplied values, not `resolve_paths()`'s repo-relative fallback
- ROADMAP criterion 3 closed on both halves: `stat` reports `600 root:root` on the droplet; repo-side `git log`/`git ls-files` search across all branches finds no env/service-account/credentials/token file and no real secret value in any commit
- Cross-checked the author's pasted journal against `src/creatorpulse/cli.py`'s actual `logger.info` call and `config.py`'s `resolve_paths()` — the paths match what the code emits, not a plausible-looking but wrong value

## Task Commits

1. **Task 2: Paste droplet evidence into entries 2 and 3** - `4f9679d` (docs)
2. **Task 3: Repo-side git-history proof, cross-check, green gate** - `2d16988` (docs)

_Task 1 was completed and committed in a prior session (`2bcda1f`)._

## Files Created/Modified
- `.planning/phases/02-vps-systemd/02-UAT.md` - entries 2 and 3 filled with pasted droplet evidence plus an agent-executed git-history block; `## Summary` updated to `passed: 2, pending: 3`; `## Gaps` records the criterion-wording finding; `## Decisions` records the D-03 private-repo deviation

## Decisions Made
- D-05 stands unchanged (Task 1, prior session — no new decision here)
- The `env -i` stripped-environment reproduction is recorded with its true scope: it demonstrated a fully empty environment fails loudly at the bare-binary level, not that the unit runs without a login shell (systemd already provides none — `systemctl start`'s success is the actual proof of that)

## Deviations from Plan

### Auto-fixed Issues

None — no code changed, no bugs found. This plan is evidence-and-proof only.

### Recorded Findings (not deviations from the plan's task list, but discoveries during execution)

**1. D-08 cwd-relative fallback, surfaced by `env -i`.** The stripped-environment reproduction's failure
(`/creators.yaml`, `Config file not found`) was caused by `systemd-run`'s default working directory of
`/`, combined with `env -i` also stripping the unit's two `Environment=` lines — not by the absence of a
login shell as such. `resolve_paths()`'s fallback is cwd-relative, not repo-relative; it only looks
repo-relative in the two baseline runs because those ran with cwd already at the repo. Production is
unaffected: the real unit sets both `WorkingDirectory=` and both `Environment=` path lines, two
independent mechanisms neither of which this specific test exercised. Recorded in `02-UAT.md` entry 2 as
a property of D-08, not a defect — no code change made or proposed.

**2. Criterion-wording gap, Task 3 acceptance criteria.** The literal wording ("at most the single commit
that introduced `.env.example`") undercounts by one: `git log --all -S<NAME>` for each of the six
`.env.example` variable names hits exactly 2 commits (`.env.example` itself, blank; and
`02-01-PLAN.md`'s prose naming the variables, also blank), because the criterion did not anticipate the
plan file also naming the variables. No commit anywhere assigns a real value. Recorded in `02-UAT.md`
`## Gaps` as a wording gap, not a security gap — entry 3 stays `result: pass`.

**3. D-03 private-repo deviation, encountered and resolved by the author before this session.** D-03
assumes the repo is public so no deploy key is needed. At provisioning time the repo was in fact private
(41 local commits had never been pushed), so `git clone` prompted for credentials against an empty
remote. The author pushed `main` (now `1bcdc6b`) and made the repo public, restoring D-03's assumption.
No doc change needed. Recorded in `02-UAT.md` `## Decisions`.

## Issues Encountered

None blocking. See Recorded Findings above.

## Notes on the human-built unit (observations only — the unit was not touched)

- `After=network.target` guarantees networking units started, not that the network is usable. Irrelevant
  to Phase 2 (no network calls); worth flagging for Phase 3, where a boot-time catch-up run could fire
  before DNS is ready.
- `[Install] WantedBy=multi-user.target` on a timer-driven oneshot service is unusual — timer-activated
  services typically carry no `[Install]` block, since it's the *timer* unit that gets enabled. Inert
  today because `creatorpulse.timer` (not `.service`) is what's enabled. Noted, not corrected — the unit
  is human-built and out of scope for this agent to edit.

## Deferred Items

None new. Carried forward from 02-01: `ruff format --check .` pre-existing findings on
`02-PATTERNS.md`/`02-RESEARCH.md`, out of scope.

## User Setup Required

None further — the droplet is provisioned, the service starts, the timer is enabled
(`systemctl enable --now creatorpulse.timer` already run by the author per the pasted supporting
context). Nothing else needed from the author for this plan.

## Next Phase Readiness

- ROADMAP success criteria 2 and 3 are closed
- `02-UAT.md` entries 1, 4, and 5 remain `pending` — owned by plan 02-03 (unattended timer fire, reboot
  catch-up, spoken cron-vs-timer explanation)
- No open blockers for 02-03

---
*Phase: 02-vps-systemd*
*Completed: 2026-08-03*
