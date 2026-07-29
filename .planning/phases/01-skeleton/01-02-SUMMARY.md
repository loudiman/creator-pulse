---
phase: 01-skeleton
plan: 02
subsystem: testing
tags: [pytest, requests, fixtures]

requires:
  - phase: 01-01
    provides: installable creatorpulse package, Creator dataclass, load_creators loader
provides:
  - real pytest suite covering the creators.yaml loader (no longer an empty-suite exit 5)
  - tests/fixtures/ root with the {source}/{case}.{ext} convention documented
  - scripts/record_fixture.py hand-run recorder, outside pytest collection
affects: [01-03, phase-3-collector-core, phase-4-tiktok]

tech-stack:
  added: []
  patterns:
    - "tests/ at repo root, outside src/ package — keeps suite out of editable install and out of mypy src/ target"
    - "fixture-in / record-out: tests assert on parsed objects, fixtures are recorded by hand, never fetched at test time"
    - "name-segment validation before any network call — regex allowlist plus resolved-path containment as a second belt"

key-files:
  created:
    - tests/test_config.py
    - tests/fixtures/README.md
    - scripts/record_fixture.py
  modified: []

key-decisions:
  - "record_fixture.py validates --source/--case against ^[a-z0-9_]+$ before opening any connection, then re-checks the resolved target path is inside tests/fixtures/ as a second belt"
  - "recorder raises on non-2xx instead of saving the body, so a blocked/challenge response can never masquerade as a real fixture"

patterns-established:
  - "Pattern: any script writing to a path built from untrusted-shaped CLI args validates both a name-charset regex and a resolved-path containment check, in that order, before touching the network or filesystem"

requirements-completed: [OPS-04]

coverage:
  - id: D1
    description: "pytest collects and passes a real test over the committed creators.yaml (non-empty list, unique ids, non-empty sources) instead of exiting 5 on an empty suite"
    requirement: "OPS-04"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_committed_creators_yaml_loads"
        status: pass
    human_judgment: false
  - id: D2
    description: "tests/fixtures/ exists in git with README.md documenting the {source}/{case}.{ext} layout Phases 3 and 4 reuse"
    verification:
      - kind: other
        ref: "manual: tests/fixtures/README.md content review"
        status: pass
    human_judgment: false
  - id: D3
    description: "scripts/record_fixture.py rejects an escaping --source (e.g. ../escape, Bad-Name) with exit 2 before any network request, and stays outside pytest collection"
    requirement: "OPS-04"
    verification:
      - kind: integration
        ref: "manual invocation: python scripts/record_fixture.py --source ../escape --case ok --url https://example.com -> exit 2"
        status: pass
      - kind: integration
        ref: "manual invocation: pytest -q still collects exactly 1 test after the script is added"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-07-30
status: complete
---

# Phase 1 Plan 2: Test Suite and Fixture Recorder Summary

**Real pytest coverage over `creators.yaml` (dup-id check, non-empty fields) plus a committed `tests/fixtures/` layout and a hand-run `record_fixture.py` recorder that validates path segments before any network call.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-30T02:11Z (approx)
- **Completed:** 2026-07-30T02:12:35Z
- **Tasks:** 2
- **Files modified:** 3 (tests/test_config.py, tests/fixtures/README.md, scripts/record_fixture.py)

## Accomplishments
- `pytest -q` exits 0 with 1 real test, up from an empty-suite exit 5 (OPS-04, D-13)
- `test_committed_creators_yaml_loads` asserts non-empty `id`/`name`/`sources` on every parsed `Creator`, plus uniqueness of `id` across the file — catches a slug collision before it reaches Phase 3's unique constraint
- `tests/fixtures/README.md` documents the `{source}/{case}.{ext}` convention (D-15) that Phases 3 and 4 will write into
- `scripts/record_fixture.py` is the sole sanctioned way to populate fixtures (D-16): validates `--source`/`--case` against `^[a-z0-9_]+$` before opening any connection, backs that with a resolved-path containment check, fetches with `requests` under an explicit 30s timeout, and raises on non-2xx rather than saving an error page as a fixture
- No networking library (`requests`, `gspread`, `playwright`, `discord`) is imported anywhere under `tests/`; the recorder lives in `scripts/` and is outside `testpaths`, so it is never collected

## Task Commits

1. **Task 1: One real test over the committed creators.yaml, plus the fixture root** - `facc29c` (test)
2. **Task 2: The hand-run fixture recorder** - `05d6bb0` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `tests/test_config.py` - `test_committed_creators_yaml_loads`; imports `load_creators`/`Creator` from `creatorpulse.config`, resolves `creators.yaml` from `__file__`
- `tests/fixtures/README.md` - documents `tests/fixtures/{source}/{case}.{json,html}` layout
- `scripts/record_fixture.py` - `main(argv)`; `argparse` with `--source`/`--case`/`--url`/`--ext`; validates both name segments before any request; `requests.get` with explicit timeout; raises on non-2xx; writes response text as UTF-8

## Decisions Made
- Validate-then-fetch ordering in the recorder: regex check first (costs nothing, touches no network), path-containment check second, network call last — see key-decisions above
- Kept the recorder to pure fetch-and-save with zero platform knowledge per the plan's explicit scope boundary — no YouTube/Twitch/TikTok endpoint, no response parsing, no playwright import

## Deviations from Plan

None — plan executed exactly as written for both tasks. One out-of-scope pre-existing issue was noted but not touched (see below).

### Out-of-scope finding (not fixed, logged per SCOPE BOUNDARY)

`ruff format --check .` run repo-wide fails on `.planning/research/ARCHITECTURE.md` (a pre-existing planning doc last touched in commit `160a51d`, before this phase started). This is unrelated to `tests/` or `scripts/` — the new files themselves are clean (`ruff format --check tests/ scripts/` → all formatted). Logged to `.planning/phases/01-skeleton/deferred-items.md` rather than fixed, per the SCOPE BOUNDARY rule (only auto-fix issues directly caused by the current task's changes).

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 01-03 (README, journal.md) is unblocked
- Phase 3's collector-core work has a fixture root and recorder ready to populate `tests/fixtures/youtube/` and `tests/fixtures/twitch/`
- Phase 4's TikTok work has the same recorder available for `tests/fixtures/tiktok/*.html`

---
*Phase: 01-skeleton*
*Completed: 2026-07-30*

## Self-Check: PASSED

All created files found on disk; both task commit hashes found in git log (verified below).
