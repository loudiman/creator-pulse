# Build Journal

## 2026-07-30 — Day 1: Skeleton

### Decided

- `src/` layout with an editable install, so `mypy src/` has a real target and systemd needs no
  `PYTHONPATH` hack.
- One console script, `creatorpulse`, with `collect`/`sync`/`bot` subcommands. Phase 2's systemd
  unit hard-codes this name.
- mypy `strict = true` on `src/`, relaxed only for `tests.*`.
- Ruff selection `E, F, I, UP, B, SIM` — bugbear (`B`) earns its place by catching mutable default
  arguments and loop-variable binding, not by style preference.
- Exact `==` pins for all eight locked packages, written directly in `pyproject.toml`.

### Surprised

- `pytest` exits code 5 on a suite that collects zero tests, not 0. The original plan assumed an
  empty test suite would pass the gate; it would have failed the very gate it was meant to
  establish. Fixed by shipping a real test over the `creators.yaml` loader, which also set the
  fixture-in/record-out pattern Phase 3 reuses.
- `ruff format --check .` (added as the gate's fourth command) flagged Python code fences inside
  `.planning/research/ARCHITECTURE.md` — ruff 0.16 formats embedded markdown code blocks, not just
  `.py` files. Fixed with `ruff format .`, not by excluding `.planning/` from ruff's scope.
- mypy strict failed on `import yaml` — PyYAML ships no type stubs, same problem gspread already
  had an override for. Added `"yaml"` to the existing `gspread.*` override's module list rather
  than opening a second override block or adding a `types-PyYAML` dependency outside the locked set.

### Rejected

- A Makefile and paired `check.sh`/`check.ps1` runner scripts, in favor of one documented
  four-command block. Development is on Windows, deployment is Linux; `make` isn't on the Windows
  box, and a script pair drifts into a silent difference between the dev gate and the deploy gate.
- A generated lockfile via pip-tools. Doing it properly needs a new tool; a hand-maintained
  `pip freeze` output is a second source of truth that drifts from `pyproject.toml`.
- tenacity, pydantic, and structlog — each closed against stdlib during research. Retry/backoff is
  a ~15-line hand-rolled decorator; config validation is `dataclasses` plus a manual check;
  logging is stdlib `logging` to stdout, which systemd already captures into the journal.
- TTY-conditional log formatting. Cleverness that would need justifying in review, for no real
  benefit — the same command run by hand on the dev box still needs readable timestamps.
