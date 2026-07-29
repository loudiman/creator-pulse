# Deferred Items — Phase 01 Skeleton

## `.planning/research/ARCHITECTURE.md` fails `ruff format --check .`

- **Found during:** 01-02 Task 1 verification (`ruff format --check .`)
- **Scope:** Pre-existing planning-research doc, unrelated to `tests/` or `scripts/` — out of scope
  for this plan's tasks per the SCOPE BOUNDARY rule (fix only what the current task's changes touch).
- **Status:** Not fixed. `tests/` itself is clean (`ruff format --check tests/` → "2 files already
  formatted").
- **Action:** Leave for a future docs-cleanup task, or note if `.planning/` should be excluded from
  ruff's target scope entirely.
