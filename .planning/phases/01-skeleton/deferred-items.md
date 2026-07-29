# Deferred Items — Phase 01 Skeleton

## `.planning/research/ARCHITECTURE.md` fails `ruff format --check .`

- **Found during:** 01-02 Task 1 verification (`ruff format --check .`)
- **Status:** Resolved in 01-03 Task 2. Ran `ruff format .` (no `--check`) which reformatted the
  embedded Python code fences in `ARCHITECTURE.md` to ruff 0.16's standard. `.planning/` was not
  excluded from ruff's scope, and no rule was removed from the selection.
