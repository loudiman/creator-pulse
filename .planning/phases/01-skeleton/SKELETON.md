# Walking Skeleton — CreatorPulse

**Phase:** 1
**Generated:** 2026-07-30

## Capability Proven End-to-End

An operator with a fresh clone can install the package, run `creatorpulse collect`, and watch it read
the committed `creators.yaml` and log a complete run — start, creators loaded, not-implemented,
end-with-duration — before exiting 0.

That is the whole slice: **installed package → `creatorpulse collect` invoked → config file read →
structured log lines emitted → exit 0.**

## Template Adaptation (read this before comparing against the generic skeleton)

The Walking Skeleton template is written for web applications and asks for project scaffold, routing,
one real DB read/write, one real UI interaction, and a dev deployment. **CreatorPulse has no routing,
no UI, and no database in Phase 1.** The intent — *prove the thinnest path through every layer the
project actually has* — was translated rather than copied:

| Template item | CreatorPulse translation |
|---|---|
| Project scaffold (framework, build, lint, test runner) | `pyproject.toml` — src layout, pinned deps, dev extra, ruff + mypy + pytest config |
| Routing — at least one real route | The `creatorpulse` console script and its `collect` / `sync` / `bot` subcommand surface |
| Database — one real read AND one real write | **Dropped.** SQLite is Phase 3. The persistence layer's stand-in is the `creators.yaml` read, the only real I/O this phase has. |
| UI — one interactive element wired to the API | **Dropped.** There is no UI in this project at all; the Google Sheet is the UI and arrives in Phase 4. Its stand-in is the stdout log stream, which is the operator-facing surface Phase 2 grades in `journalctl`. |
| Deployment to dev environment | **Dropped from Phase 1 — it is Phase 2, and human-built.** The stand-in is the documented local full-stack run command: `creatorpulse collect`. Phase 1's obligation is to make that command exist and be stable so the human-written systemd unit can point `ExecStart` at it. |

## Architectural Decisions

These are the contract later phases build on. Changing one is not a Phase-N refactor; it is a
renegotiation.

| Decision | Choice | Rationale | Reversibility |
|---|---|---|---|
| Package layout | `src/creatorpulse/`, installed with `pip install -e .` into a venv | `mypy src/` gets a real target, imports are absolute everywhere, and systemd needs no `Environment=PYTHONPATH` — sidestepping the stripped-environment trap rather than working around it (D-01) | costly — undoing it rewrites import paths, the mypy target, and the README install step |
| Entry point | One console script `creatorpulse` with subcommands `collect`, `sync`, `bot` | The Sheets sync must be callable standalone for re-syncs without re-collecting; subcommands give that without a third entry point (D-02) | costly — the command name is baked into a human-written systemd unit after Phase 2 |
| Run shape | `collect` is a real CLI shell from day one: run-start line, creators-loaded line, not-implemented line, run-end line with duration, exit 0 | Phase 2 verifies the exact `journalctl` output shape it will see for the rest of the project; Phase 3 fills the body without the unit file changing (D-03) | reversible — the body changes in Phase 3 by design |
| Quality gate | Four literal commands documented in the README: `ruff format --check .`, `ruff check .`, `mypy src/`, `pytest` | Development is Windows, deployment is Linux. `make` is absent on the dev box, and paired per-platform scripts drift into a silent dev-vs-prod gate difference (D-04, D-08) | reversible |
| Type strictness | mypy `strict = true` on `src/`, relaxed for `tests.*`, missing-imports tolerated for `gspread.*` only | Strict costs nothing on an empty repo and encodes the project's most important correctness rule into the type system: a metric a platform does not expose is `int \| None`, and strict refuses to let it silently become `int` (D-05, D-06) | costly — retrofitting strict-clean annotations after Phases 3 and 4 land is a multi-hour job inside a seven-day window |
| Lint selection | ruff `E, F, I, UP, B, SIM` | Bugbear earns its place by catching mutable default arguments and loop-variable binding — real defects, not style. `select = ["ALL"]` plus an ignore list reads as cargo cult (D-07) | reversible |
| Config shape | One entry per creator with a nested `sources:` map, keyed by platform | Mirrors the database's `(creator_id, source)` key exactly, and is what lets `/creator <name>` roll one person up across platforms without a join the config does not express (D-09) | costly — Phase 3's loader, validator and collector iteration are all written against this shape |
| Creator identity | `creator_id` is an explicit hand-written slug per entry | It is a primary key in a table carrying history: it must survive a display-name change, a handle change, and a rebrand without orphaning prior rows (D-10) | **one-way** — once metrics rows exist, changing the scheme requires migrating the `metrics` table, since `creator_id` is part of its unique constraint |
| Identifier form | Human-friendly identifiers in the file (`@mkbhd`, a Twitch login, a TikTok username), resolved to API ids at runtime | Requiring raw `UC…` strings and numeric Twitch ids would make adding a creator a lookup errand first — precisely the friction CFG-01 exists to remove (D-11) | costly — removing runtime resolution later means hand-editing every entry to raw ids |
| Dependencies | Exact `==` pins written directly in `pyproject.toml`; dev tools behind a `dev` extra | One machine, not a library with downstream consumers — reproducibility beats flexibility. A generated lockfile wants a new tool; a hand-maintained freeze is a second source of truth that drifts (D-17, D-18) | reversible |
| Logging | stdlib `logging` to stdout, plain human-readable format, `asctime` kept | systemd captures unit stdout into the journal automatically. Nothing consumes log structure, and key=value or JSON is materially harder to read aloud while narrating `journalctl -f` — a Phase 7 success criterion (D-19, D-20) | reversible |
| Test placement | `tests/` at the repository root, outside the package | It does not ship with the editable install onto the VPS, and `mypy src/` naturally excludes it — exactly what the strict-src / relaxed-tests split needs (D-14) | reversible |
| Fixture layout | `tests/fixtures/{source}/{case}.{json,html}`, populated by a hand-run `scripts/record_fixture.py` | Scales to the failure cases Phases 3 and 4 need without renaming, and keeps live calls outside the pytest suite (D-15, D-16) | reversible |

## Stack Touched in Phase 1

- [ ] Project scaffold — `pyproject.toml` with pinned deps, dev extra, console script, ruff + mypy + pytest configuration
- [ ] Entry point — the `creatorpulse` console script with `collect` / `sync` / `bot` subcommands
- [ ] Config read — `creators.yaml` parsed into `Creator` objects by `load_creators`
- [ ] Observability — stdlib logging to stdout, the exact line shape Phase 2 grades in `journalctl`
- [ ] Quality gate — four commands, documented literally, green on the repository as committed
- [ ] Full-stack run command — `creatorpulse collect` from the repo root, exit 0

## Out of Scope (Deferred to Later Slices)

Explicit, so a later phase does not re-litigate Phase 1's minimalism, and so this phase does not
overrun its boundary:

- **Any SQLite schema, database file, connection helper, or migration** — Phase 3
- **Any source adapter, HTTP call to a platform API, API client, or Playwright code** — Phases 3 and 4
- **Any Google Sheets or Discord code** — Phases 4 and 6
- **`creators.yaml` validation with named-field error messages (CFG-03)** — Phase 3. Phase 1 parses only; the loader gains a `validate()` pass built on stdlib dataclasses there.
- **Identifier resolution implementation** — D-11 fixes the *contract* here; the YouTube `forHandle` and Twitch Get Users calls that implement it, plus caching so resolution does not burn quota every run, are Phase 3
- **Retry/backoff helper (SRC-05)** — Phase 3
- **systemd unit and timer files** — Phase 2, and **human-built: the agent must not generate these**
- **Architecture diagram and the full decision record in the README (OPS-08)** — Phase 7
- **`journalctl` priority mapping** — V2-OPS-01, out of scope for v1

`scripts/record_fixture.py` is the one deliberate edge of the boundary: D-16 places it in Phase 1, and
it does make a live call. It stays in scope because it is a generic fetch-and-save utility with zero
platform knowledge — no endpoint, no parsing, no browser — run by hand and never by pytest. It is not a
source adapter.

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural
decisions:

- **Phase 2 (human):** the timer fires `creatorpulse collect` unattended on the VPS and the output is readable in `journalctl` afterwards
- **Phase 3:** real YouTube and Twitch numbers land idempotently in SQLite, and one broken source cannot take the run down
- **Phase 4:** TikTok is scraped without an API, and the Google Sheet becomes a readable view of the database
- **Phase 5 (human):** the Sheet gains a menu, conditional formatting, and a Status-edit round trip back to Discord
- **Phase 6 (mixed):** Discord posts the daily digest, alerts on failures, and answers `/creator` and `/status` from the database
- **Phase 7 (mixed):** the whole loop runs cold and unattended while someone watches, and a stranger can read the README
