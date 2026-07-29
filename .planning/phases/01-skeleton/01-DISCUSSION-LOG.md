# Phase 1: Skeleton - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 1-Skeleton
**Areas discussed:** Package layout & entrypoint, Lint & type strictness, creators.yaml schema, Test & fixture layout, Pinning & log format

---

## Package Layout & Entrypoint

### Q1 — Package layout and install mode

| Option | Description | Selected |
|--------|-------------|----------|
| `src/creatorpulse/` + editable install | `pip install -e .` into a venv. `mypy src/` has a real target, absolute imports, no PYTHONPATH under systemd | ✓ |
| `src/` layout, no install, PYTHONPATH | Skips packaging metadata; unit needs `Environment=PYTHONPATH=...`, the stripped-systemd trap | |
| Flat `creatorpulse/` at repo root | Simplest; `mypy src/` would point at nothing | |

**User's choice:** src/creatorpulse/ + editable install
**Notes:** Chosen partly because it avoids the Phase 2 systemd environment trap by construction rather than by workaround.

### Q2 — Collector invocation (becomes Phase 2's ExecStart)

| Option | Description | Selected |
|--------|-------------|----------|
| One CLI, subcommands | `creatorpulse collect` / `sync` / `bot`. Stable absolute path; standalone sync for free | ✓ |
| Separate console scripts | `creatorpulse-collect`, `creatorpulse-bot`. Two names to sync, third needed for standalone sync | |
| `python -m creatorpulse.collect` | No console-script metadata; noisier unit file and `ps` output | |

**User's choice:** One CLI, subcommands
**Notes:** ARCHITECTURE.md's standalone-resync requirement was the deciding factor.

### Q3 — Placeholder entrypoint for Phase 2

| Option | Description | Selected |
|--------|-------------|----------|
| Real CLI shell that logs and exits 0 | Structured start / not-implemented / end lines. Phase 2 grades the final output shape; Phase 3 fills the body without touching the unit file | ✓ |
| Trivial hello-world script | Proves the timer fires; unit file gets rewritten in Phase 3 | |
| Nothing — Phase 2 invents its own | Phase 2 is human-built and would guess the contract | |

**User's choice:** Real CLI shell that logs and exits 0
**Notes:** Surfaced during analysis — ROADMAP.md's Phase 2 notes assume this placeholder exists, but Phase 1's success criteria never named it. Gap closed here.

### Q4 — Running the green gate across Windows dev / Linux prod

| Option | Description | Selected |
|--------|-------------|----------|
| Documented command block in README | Literal commands, zero new deps, identical on both platforms | ✓ |
| Makefile with setup/check targets | `make check` ergonomics; `make` absent on Windows dev box | |
| `scripts/check.sh` + `scripts/check.ps1` | One command per platform; two files that drift into a silent gate difference | |

**User's choice:** Documented command block in README

---

## Lint & Type Strictness

### Q1 — mypy strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Strict on `src/`, relaxed on `tests/` | Strict free on an empty repo; forces `int \| None` discipline into the type system. Tests loose for fixture dicts | ✓ |
| Strict everywhere including tests | Maximum rigor; annotation cost on fixture-heavy tests for little correctness gain | |
| Permissive baseline, tighten later | Fastest start; "later" inside 7 days means never | |

**User's choice:** Strict on src/, relaxed on tests/
**Notes:** Directly serves the NULL-vs-0 correctness rule — strict mode refuses to let an absent metric become `int`.

### Q2 — Untyped third-party imports under strict

| Option | Description | Selected |
|--------|-------------|----------|
| Per-module override for `gspread` only | One-line scoped `ignore_missing_imports`; discord.py and playwright stay strict (they ship types) | ✓ |
| Global `ignore_missing_imports` | One setting; also swallows genuine import typos and disables strictness where it's earned | |
| Write local stubs for gspread | Most correct; not worth a day of a 7-day window | |

**User's choice:** Per-module override for gspread only

### Q3 — Ruff rule selection

| Option | Description | Selected |
|--------|-------------|----------|
| Curated `E,F,I,UP,B,SIM` | pycodestyle, pyflakes, isort, pyupgrade, bugbear, simplify. Every rule justifiable | ✓ |
| Ruff defaults (`E,F`) | Quiet; leaves imports unmanaged, misses bugbear-class defects | |
| `select = ["ALL"]` then ignore | Long day-one ignore list reads as cargo cult | |

**User's choice:** Curated set
**Notes:** Bugbear specifically — mutable defaults and loop-variable binding are real defects, not style.

### Q4 — Formatting in the gate

| Option | Description | Selected |
|--------|-------------|----------|
| Add `ruff format --check .` | Extends the gate by one line; drift never reaches a diff | ✓ |
| Formatting stays advisory | Keeps ROADMAP.md's three-command definition of green exactly as written | |

**User's choice:** Add `ruff format --check .`
**Notes:** This intentionally extends the definition of green recorded in ROADMAP.md from three commands to four.

---

## creators.yaml Schema

### Q1 — Creator vs person-platform pair

| Option | Description | Selected |
|--------|-------------|----------|
| One creator, nested `sources:` map | Mirrors the `(creator_id, source)` DB key; `/creator <name>` rolls up across platforms | ✓ |
| Flat list of platform+identifier pairs | Simplest parse; conflates creator with source, no cross-platform rollup | |
| Grouped by platform at top level | Easy per-source iteration; same rollup problem, plus edits in up to three places | |

**User's choice:** One creator, nested sources map
**Notes:** BOT-04 (`/creator <name>` with trend) was the deciding requirement.

### Q2 — Source of `creator_id`

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit hand-written slug | Survives display-name, handle, and rebrand changes without orphaning history | ✓ |
| Derived from display name | One less field; a rename silently forks history into two ids | |
| Auto-assigned integer | Unique and thoughtless; opaque in hand-run SQL and in the Sheet | |

**User's choice:** Explicit slug per entry
**Notes:** Rated one-way in CONTEXT.md — it's part of the metrics table's unique constraint, so changing it after data exists needs a migration.

### Q3 — Identifier form in the file

| Option | Description | Selected |
|--------|-------------|----------|
| Human-friendly, resolved at runtime | `@mkbhd`, `pokimane`. Code resolves handle→channel ID and login→user_id | ✓ |
| Raw API IDs only | No resolution code or calls; adding a creator becomes a lookup errand first | |
| Accept either, detect by prefix | Flexible; the `UC…` heuristic fails on a handle that legitimately starts with UC | |

**User's choice:** Human-friendly form, resolve at runtime
**Notes:** Twitch's Get Videos needs a numeric `user_id`, not the login you'd type — resolution isn't optional there, only its location is.

### Q4 — Committing the real creator list

| Option | Description | Selected |
|--------|-------------|----------|
| Commit with real public handles | Nothing sensitive; a stranger can read and run it, README examples are real | ✓ |
| Commit `creators.example.yaml`, gitignore the real one | Clean config/code split; fresh clone does nothing until authored | |
| Commit both | Two files saying nearly the same thing; they drift | |

**User's choice:** Commit it with real public handles

---

## Test & Fixture Layout

**Raised before questioning:** ROADMAP.md criterion 1 requires `pytest` to pass on a fresh clone, and the original brief assumed an empty suite would satisfy it. It does not — pytest exits code 5 on zero collected tests. An empty suite fails the gate it exists to establish.

### Q1 — The day-one test

| Option | Description | Selected |
|--------|-------------|----------|
| Test the `creators.yaml` loader | Real coverage of code criterion 3 already requires; establishes the fixture pattern OPS-06 reuses | ✓ |
| Trivial `test_imports.py` | Clears exit-5 in three lines; a smoke test wearing a suite's clothes | |
| Configure pytest to tolerate an empty suite | conftest hook rewriting exit 5 to 0; hides "no tests collected" forever | |

**User's choice:** Test the creators.yaml loader

### Q2 — Test location

| Option | Description | Selected |
|--------|-------------|----------|
| `tests/` at repo root | Doesn't ship with the editable install; `mypy src/` excludes it naturally, matching the strict/relaxed split | ✓ |
| `src/creatorpulse/tests/` | Tests travel with the package; also installs onto the VPS and contradicts the mypy override | |

**User's choice:** tests/ at repo root

### Q3 — Fixture organization

| Option | Description | Selected |
|--------|-------------|----------|
| `tests/fixtures/{source}/{case}.{json,html}` | Scales to failure cases without renaming; obvious where a new source goes | ✓ |
| Flat `tests/fixtures/` | Fine at six files; the prefix becomes the directory you didn't create | |

**User's choice:** Per-source subdirectories

### Q4 — How fixtures get recorded

| Option | Description | Selected |
|--------|-------------|----------|
| Committed `scripts/record_fixture.py` | Live call by hand, never by pytest, so OPS-04 holds. Re-recordable when a source changes | ✓ |
| Save responses by hand | No code to maintain; tedious for rendered HTML and not repeatable | |
| Defer to Phase 3 | Phase 1 sets the layout those fixtures land in — deciding now costs nothing | |

**User's choice:** Committed scripts/record_fixture.py
**Notes:** Also answers "how do you know your fixtures aren't stale?" — a likely interview question given fixture-based testing is a stated design decision.

---

## Pinning & Log Format

*Surfaced after the four initially-selected areas; user chose to explore both rather than leave them to discretion.*

### Q1 — Dependency pinning

| Option | Description | Selected |
|--------|-------------|----------|
| Exact `==` pins in pyproject | One deployment target, no consumers; VPS resolves identically to the dev box | ✓ |
| Compatible-release `~=` | Picks up patch fixes; laptop and VPS can diverge — "works on my machine" during a demo | |
| Loose pyproject + committed `requirements.lock` | Conventional app answer; wants pip-tools (a new dep) or a drifting hand-maintained freeze | |

**User's choice:** Exact `==` pins in pyproject

### Q2 — Dev dependency location

| Option | Description | Selected |
|--------|-------------|----------|
| `[project.optional-dependencies]` dev extra | `pip install -e ".[dev]"` locally, plain install on the VPS; toolchain stays off the server | ✓ |
| Separate `requirements-dev.txt` | Conventional; splits dependency truth across two files and two pinning styles | |
| All in main dependencies | One command everywhere; ships ruff/mypy/pytest to production | |

**User's choice:** dev extra in optional-dependencies

### Q3 — Log line format

| Option | Description | Selected |
|--------|-------------|----------|
| Plain human-readable | Level, logger, message. Reads aloud cleanly during a `journalctl -f` demo | ✓ |
| key=value structured | Greppable; nothing here parses it, harder to narrate | |
| JSON lines | Max parseability, worst terminal readability, no consumer | |

**User's choice:** Plain human-readable
**Notes:** Phase 7's success criteria include narrating a live `journalctl -f` tail — readability is a graded property, not a preference.

### Q4 — asctime vs journald's own timestamp

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `asctime` in the formatter | Duplicated under journalctl; hand-run output on Windows still shows timing | ✓ |
| Drop `asctime`, let journald own it | Cleanest journalctl output; local runs lose all timing information | |
| Conditional on TTY detection | Best of both; cleverness in logging setup that needs justifying in review | |

**User's choice:** Keep asctime

---

## Claude's Discretion

- `journal.md` structure and day-one entry wording
- Additional `.gitignore` entries beyond those already committed
- README section ordering and depth, beyond the mandatory gate commands and install steps
- Internal module file names within `src/creatorpulse/`, provided the CLI command surface is honoured
- `requires-python` and other pyproject metadata not covered by the pinning decisions

## Deferred Ideas

- `creators.yaml` validation with named-field errors (CFG-03) — Phase 3
- Identifier resolution implementation and quota-safe caching — Phase 3
- Hand-rolled retry/backoff helper (SRC-05) — Phase 3
- `journalctl` priority mapping (V2-OPS-01) — needs `systemd-python`, out of scope for v1
