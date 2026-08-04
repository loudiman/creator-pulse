# Deferred Items — Phase 3

Out-of-scope discoveries logged during plan execution. Not fixed here; scope boundary is per-task.

## 03-01: pre-existing `ruff format --check .` drift, unrelated to this plan's files

`ruff format --check .` (run over the whole tree, as Task 1 and Task 3's acceptance criteria
literally specify) exits 1 because three `.planning/` markdown files carry pre-existing
Python-code-fence formatting drift:

- `.planning/phases/02-vps-systemd/02-PATTERNS.md`
- `.planning/phases/02-vps-systemd/02-RESEARCH.md`
- `.planning/phases/03-collector-core-api-sources/03-RESEARCH.md`

None of these three files are in this plan's `files_modified` list and none were touched by any
task in `03-01-PLAN.md`. This is the same phenomenon `journal.md`'s Day 1 entry already names
("ruff 0.16 formats embedded markdown code blocks, not just `.py` files") — it predates this
plan's execution and reproduces identically before and after every task's changes in this plan.
Confirmed out of scope per the executor's scope boundary rule (only auto-fix issues directly
caused by the current task's changes); not reformatted here. `scripts/record_fixture.py`,
`tests/fixtures/youtube/*.json` (excluded from ruff's default file-discovery glob — confirmed:
`ruff format --check .` only flags `.py`/`.pyi`/`.ipynb` files during a directory walk, and only
formats non-Python files if their path is passed explicitly on the command line), `journal.md`,
and `03-UAT.md` all pass `ruff format --check` individually.
