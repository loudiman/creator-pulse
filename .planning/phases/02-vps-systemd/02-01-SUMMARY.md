---
phase: 02-vps-systemd
plan: 01
subsystem: infra
tags: [pathlib, os.environ, systemd-env, config, cli]

requires:
  - phase: 01-skeleton
    provides: creatorpulse.config.load_creators, creatorpulse.cli.run_collect/main, logging setup
provides:
  - resolve_paths() resolving CREATORPULSE_CONFIG/CREATORPULSE_DB with repo-relative fallback
  - run_collect logging both resolved absolute paths as its first statement
  - .env.example naming the six v1 secret vars, blank
  - 02-UAT.md proof scaffold, five pending evidence blocks
affects: [02-02, 03-collector]

tech-stack:
  added: []
  patterns:
    - "resolve_paths(): os.environ.get(...) into str | None locals, empty-string treated as unset, no mkdir, no existence check"
    - "run-start log line is first statement after start = time.monotonic(), before any I/O that can raise"

key-files:
  created: [src/creatorpulse/config.py (resolve_paths, DEFAULT_DB_PATH), tests/test_paths.py, .env.example, .planning/phases/02-vps-systemd/02-UAT.md]
  modified: [src/creatorpulse/cli.py]

key-decisions:
  - "Empty-string env var treated as unset, not as cwd — stray `Environment=CREATORPULSE_DB=` in a unit file must not resolve to the working directory"
  - "db_path is logged only, never opened, in this phase — Phase 3 db.py consumes it"
  - "--config flag overrides only the config path, env var is the default source (D-06)"

patterns-established:
  - "Path resolution: read both env vars independently (mixed set/unset supported), fall back to DEFAULT_* per-variable, .resolve() on the winner"

requirements-completed: [RUN-04]

coverage:
  - id: D1
    description: "resolve_paths() decides config+db paths from env with logged repo-relative fallback, no VPS-detection branch"
    requirement: "RUN-04"
    verification:
      - kind: unit
        ref: "tests/test_paths.py"
        status: pass
      - kind: integration
        ref: "python -m creatorpulse.cli collect (env-set / env-unset / empty-string / --config override, all exit 0)"
        status: pass
    human_judgment: false
  - id: D2
    description: ".env.example tracked, six v1 vars named, every value blank"
    requirement: "D-14"
    verification:
      - kind: other
        ref: "grep -Ec '^[A-Z_]+=$' .env.example == 6, git check-ignore -v .env.example exits non-zero"
        status: pass
    human_judgment: false
  - id: D3
    description: "02-UAT.md scaffold, five pending evidence blocks, one per ROADMAP success criterion"
    requirement: "D-15"
    verification: []
    human_judgment: true
    rationale: "Scaffold structure is mechanically checkable, but the actual evidence pastes require the author on a real droplet — not producible by this executor."

duration: ~20min
completed: 2026-07-31
status: complete
---

# Phase 2 Plan 1: Path resolution tracer + pre-droplet artifacts Summary

**resolve_paths() in config.py resolves CREATORPULSE_CONFIG/CREATORPULSE_DB from the environment with a logged repo-relative fallback, threaded into cli.py's run-start log line; plus .env.example and the 02-UAT.md proof scaffold**

## Performance

- **Tasks:** 2 (Task 1 is TDD/tracer: RED + GREEN)
- **Files modified:** 5

## Accomplishments
- One function (`resolve_paths()`) decides both config and DB paths for both dev-box and future-VPS environments, no OS/VPS-detection branch — env var present wins, absent falls back to `DEFAULT_CONFIG_PATH` / new `DEFAULT_DB_PATH`, independently per variable
- `run_collect`'s first log line now names both resolved absolute paths, before any I/O that could raise (RUN-04)
- Proven end-to-end on Windows dev box, not just unit-tested: env-set run, env-unset run, empty-string-treated-as-unset, and `--config` flag override all verified exit 0 with correct paths in stdout
- `.env.example` committed with the six v1 secret variable names, every value blank; `CREATORPULSE_CONFIG`/`CREATORPULSE_DB` correctly excluded (those live in the unit's `Environment=` lines, not the secret file)
- `.planning/phases/02-vps-systemd/02-UAT.md` scaffolded with five pending evidence blocks, one per ROADMAP success criterion, listing only read-only verification commands — no provisioning steps

## Task Commits

1. **Task 1 (RED): Add failing tests for resolve_paths** - `e6114c8` (test)
2. **Task 1 (GREEN): Implement resolve_paths + threaded db_path** - `cf841e8` (feat)
3. **Task 2: .env.example + 02-UAT.md proof scaffold** - `19397fd` (docs)

_Task 1 is `type="tracer" tdd="true"` — RED then GREEN, no refactor commit needed._

## Files Created/Modified
- `src/creatorpulse/config.py` - added `DEFAULT_DB_PATH`, `resolve_paths() -> tuple[Path, Path]`
- `src/creatorpulse/cli.py` - `run_collect` gains `db_path`, run-start log line names both paths, `--config` default changed to `None` sentinel
- `tests/test_paths.py` - env-set, env-unset, mixed, empty-string, and run-start-log coverage
- `.env.example` - six v1 secret variable names, blank values
- `.planning/phases/02-vps-systemd/02-UAT.md` - five-section proof scaffold, `result: pending` x5

## Decisions Made
- Empty-string env var explicitly treated as unset (not cwd) — guards against a stray `Environment=CREATORPULSE_DB=` line in the future unit file
- No `mkdir` of the resolved DB path's parent — `/var/lib/creatorpulse` is human-provisioned; the service user can't create it, so a silent mkdir would mask a missing provisioning step
- `--config` flag stays as interactive override of config path only; env var becomes the default source (D-06)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Deferred Items

- **Pre-existing, out of scope:** `ruff format --check .` at repo root flags `02-PATTERNS.md` and `02-RESEARCH.md` (embedded Python code blocks the markdown formatter wants reflowed). Predates this plan (commits `397b668`, `bdd3a4a`). Not touched — out of this plan's scope fence (`files_modified` is exactly 5 files, none of which are these two).

## User Setup Required

None - no external service configuration required. `.env.example` values remain blank by design; real secrets arrive in Phases 3/4/6, in the human-owned `/etc/creatorpulse/creatorpulse.env`.

## Next Phase Readiness

- `resolve_paths()` and the logged run-start line are the code path `systemctl start` will exercise identically to an interactive run — ROADMAP success criterion 2's "same code path" claim is now backed by one function, not by reasoning about it
- `.env.example` and `02-UAT.md` are on disk and committed, ready for the author before touching a droplet
- `deploy/creatorpulse.service`, `deploy/creatorpulse.timer`, `docs/deploy.md` remain untouched — human-built, next up in 02-02 or the author's own work

---
*Phase: 02-vps-systemd*
*Completed: 2026-07-31*
