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

## 2026-08-05 — Day 3: Collector Core, Wave 1 (03-01)

### Decided

- SRC-02 (Twitch) is **blocked, not skipped**. Registering an application in the Twitch Developer
  Console requires 2FA on the account; 2FA enrolment requires a mobile number; the verification SMS
  does not arrive. There is therefore no `TWITCH_CLIENT_ID` and no `TWITCH_CLIENT_SECRET`, therefore
  no app access token, therefore no sanctioned way to record the five Twitch fixtures through
  `scripts/record_fixture.py`. Hand-authoring one is forbidden by this project's own rules — a
  fabricated fixture makes every test that reads it a lie — so the correct outcome is that the five
  fixtures, the live `GET /helix/videos` verification call, and `03-03` itself do not exist yet.
  `REQUIREMENTS.md` marks SRC-02 `BLOCKED-EXTERNAL` with this same reason; the deferred work is
  scoped, reviewed, and left re-executable verbatim in `03-01-PLAN.md`'s `## Deferred` section — one
  substitution (`<deferred-task>` back to `<task>`) once credentials exist.
- What shipped the same day, unblocked by nothing needing that credential: the recorder's
  `--header` flag (validated before any network call, same guard shape as the existing
  `--source`/`--case` check), the four YouTube fixtures (`channel_ok`, `channel_not_found`, and two
  `_derived` hidden-subscriber-count shapes), and the `03-UAT.md` proof scaffold.
- This is the **second** time Twitch has walled this project off at the account/auth layer, not the
  scraping layer — the first was the follower-count endpoint requiring a broadcaster or moderator
  user token (settled decision, `CLAUDE.md`). Neither wall is something to route around; both are
  recorded as external constraints rather than implementation gaps.

### Surprised

- The recorded `channel_not_found.json` (bogus `forHandle`) comes back HTTP 200 with the `items`
  key **absent entirely**, not present as an empty list. `03-CONTEXT.md` D-18 and `03-RESEARCH.md`
  both assumed `items: []`. The distinction still satisfies D-18 — code written as `data["items"]`
  raises `KeyError`, which is still a raise on a not-found channel — but `03-02`'s parser must use
  `data.get("items")` and raise explicitly, not assume the key is always present. Recorded here so
  the wrong assumption doesn't quietly propagate into `03-02`'s implementation.
