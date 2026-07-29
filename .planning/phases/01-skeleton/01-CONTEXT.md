# Phase 1: Skeleton - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers the repo's shape and its quality gate — the single set of commands by which every
later phase is judged pass/fail. Concretely: a `src/` package layout installed editably, a
`pyproject.toml` pinning the locked dependency set, tool configuration for ruff and mypy, a
`creators.yaml` that loads but is not yet consumed, a test suite with one real test, a
`journal.md` with a day-one entry, and an extension of the existing `.gitignore`.

It also delivers one thing ROADMAP.md's criteria imply but do not name: **a working `creatorpulse
collect` command** that logs and exits 0. Phase 2 is human-built and its systemd `ExecStart` points
at this command. Phase 1 owns that contract so Phase 2 does not have to invent it and Phase 3 does
not have to break it.

**Not in this phase:** any collection logic, any database, any source adapter, any Sheets or
Discord code, and any `creators.yaml` *validation* (CFG-01/02/03 belong to Phase 3 — Phase 1 only
parses).

</domain>

<decisions>
## Implementation Decisions

### Package Layout & Entrypoint

- **D-01:** `src/creatorpulse/` layout, installed with `pip install -e .` into a venv. Chosen so
  `mypy src/` — the literal wording of the agreed definition of green — has a real target, imports
  are absolute everywhere, and systemd needs no `Environment=PYTHONPATH`. That last point matters:
  PITFALLS.md lists the stripped-systemd-environment failure as a Phase 2 trap, and an editable
  install sidesteps it entirely rather than working around it.
  — **Reversibility:** costly — undoing it means rewriting import paths across every module, the
  mypy target in the definition of green, and the README install step.

- **D-02:** A single console script `creatorpulse` with subcommands: `collect`, `sync`, `bot`.
  Rejected separate `creatorpulse-collect` / `creatorpulse-bot` scripts. ARCHITECTURE.md wants the
  Sheets sync callable standalone for re-syncs without re-collecting; subcommands provide that
  without a third entry point.
  — **Reversibility:** costly — the command name and invocation form are baked into a
  human-written systemd unit on the VPS after Phase 2. Changing it means editing a human-built
  artifact, which the ownership rule exists to prevent.

- **D-03:** Phase 1 ships `creatorpulse collect` as a **real CLI shell**, not a hello-world script:
  it emits a structured run-start line, a "not implemented" line, and a run-end line with duration,
  then exits 0. Phase 2 therefore verifies the exact `journalctl` output shape it will see for the
  rest of the project, and Phase 3 fills in the body without the unit file changing.
  — **Reversibility:** reversible — the body changes in Phase 3 by design; only the command name
  (D-02) is load-bearing.

- **D-04:** The green gate is a documented block of literal commands in the README, not a Makefile
  and not shell scripts. Development happens on Windows and deployment on Linux; `make` is not
  present on the Windows box, and paired `check.sh`/`check.ps1` scripts drift into a silent
  dev-vs-prod gate difference.
  — **Reversibility:** reversible.

### Lint & Type Strictness

- **D-05:** mypy `strict = true` for `src/`, with a `[[tool.mypy.overrides]]` block relaxing
  `tests.*`. Strict costs nothing on an empty repo and encodes the project's most important
  correctness rule into the type system: a metric that a platform does not expose is `int | None`,
  and strict mode refuses to let it silently become `int`. Tests stay relaxed so fixture dictionaries
  do not require annotation work.
  — **Reversibility:** costly — retrofitting strict-clean annotations after Phase 3 and Phase 4 have
  landed is a multi-hour job inside a seven-day window.

- **D-06:** `ignore_missing_imports = true` scoped to `gspread.*` only. gspread ships no type stubs;
  discord.py and playwright do, and should stay strictly checked. A global ignore would also swallow a
  genuine typo in an import path.
  — **Reversibility:** reversible.

- **D-07:** Ruff rule selection `E, F, I, UP, B, SIM` — pycodestyle, pyflakes, isort, pyupgrade,
  bugbear, simplify. Bugbear specifically earns its place: it catches mutable default arguments and
  loop-variable binding, both of which are real defects rather than style. Rejected `select = ["ALL"]`
  plus an ignore list, which reads as cargo cult rather than judgment.
  — **Reversibility:** reversible.

- **D-08:** `ruff format --check .` is added to the gate as a fourth command. This **extends** the
  definition of green recorded in ROADMAP.md (`ruff check .`, `mypy src/`, `pytest`). Formatting drift
  never reaches a diff, and one command fixes it.
  — **Reversibility:** reversible.

### creators.yaml Schema

- **D-09:** One entry per **creator**, with a nested `sources:` map — not a flat list of
  platform/identifier pairs and not top-level grouping by platform. This mirrors the database's
  `(creator_id, source)` key exactly, and it is what lets BOT-04's `/creator <name>` roll a single
  person up across YouTube and TikTok. The flat and grouped alternatives both make that rollup a join
  the config does not express.
  — **Reversibility:** costly — Phase 3's loader, validator, and collector iteration are all written
  against this shape.

- **D-10:** `creator_id` is an explicit hand-written slug per entry (e.g. `id: mkbhd`), never derived
  from the display name and never auto-assigned. It is a primary key in a table carrying history: it
  must survive a display-name change, a handle change, and a rebrand without orphaning prior rows.
  — **Reversibility:** one-way — once metrics rows exist, changing the id scheme requires a data
  migration of the `metrics` table, since `creator_id` is part of its unique constraint.

- **D-11:** Identifiers in the file are the **human-friendly** form — `@mkbhd`, a Twitch login name, a
  TikTok username — and code resolves them to API identifiers at runtime (YouTube `forHandle` →
  channel ID at 1 quota unit; Twitch Get Users → the numeric `user_id` that Get Videos requires).
  Requiring raw `UC…` strings and numeric Twitch ids would make adding a creator a lookup errand
  first, which is precisely the friction CFG-01 exists to remove.
  — **Reversibility:** costly — removing runtime resolution later means hand-editing every entry in
  `creators.yaml` to raw ids.

- **D-12:** `creators.yaml` is committed with real public handles. Nothing in it is sensitive — these
  are public accounts — and a stranger cloning the repo can then read exactly what it tracks and run
  it, with README examples that are real rather than placeholders.
  — **Reversibility:** reversible.

### Tests & Fixtures

- **D-13:** Phase 1 ships **at least one real test**, covering the `creators.yaml` loader.
  ROADMAP.md criterion 1 requires `pytest` to pass on a fresh clone, and the original brief assumed an
  empty suite would satisfy that — **it does not: pytest exits code 5 on zero collected tests, not 0.**
  An empty suite fails the very gate it is meant to establish. Testing the loader (which criterion 3
  already requires to exist) gives real coverage and establishes the fixture-in/record-out pattern that
  OPS-06 reuses in Phase 3.
  — **Reversibility:** reversible.

- **D-14:** `tests/` at the repo root, outside the package. It therefore does not ship with the
  editable install onto the VPS, and `mypy src/` naturally excludes it — which is exactly what D-05's
  strict-src/relaxed-tests split needs. Placing tests inside the package would contradict D-05.
  — **Reversibility:** reversible.

- **D-15:** Fixtures live at `tests/fixtures/{source}/{case}.{json,html}` — e.g.
  `tests/fixtures/youtube/channel_ok.json`, `tests/fixtures/tiktok/profile_ok.html`. This scales to the
  failure cases Phases 3 and 4 need (`channel_missing.json`, `profile_js_shell.html`) without renaming,
  and makes it obvious where a new source's files belong.
  — **Reversibility:** reversible.

- **D-16:** A committed `scripts/record_fixture.py` is the sanctioned way fixtures get created: it
  makes a live call and writes into `tests/fixtures/`. It is run by hand and **never** by pytest, so
  OPS-04's ban on live network calls inside the suite holds. It also makes stale fixtures
  re-recordable, which for TikTok is a when rather than an if.
  — **Reversibility:** reversible.

### Packaging & Logging

- **D-17:** Exact `==` pins for every dependency, written directly in `pyproject.toml`. This is an
  application deployed to exactly one machine, not a library with downstream consumers, so
  reproducibility beats flexibility and the VPS resolves identically to the development box. Rejected a
  separate lockfile: generating one properly wants pip-tools, which is a new dependency, and a
  hand-maintained `pip freeze` output is a second source of truth that drifts.
  — **Reversibility:** reversible.

- **D-18:** Development tools (ruff, mypy, pytest) live in `[project.optional-dependencies]` under a
  `dev` extra. Local install is `pip install -e ".[dev]"`; the VPS installs plain `pip install -e .`
  and never receives the toolchain.
  — **Reversibility:** reversible.

- **D-19:** Log lines are plain human-readable — level, logger name, message — configured via stdlib
  `logging` to stdout, which systemd captures into the journal automatically. Rejected key=value and
  JSON: nothing in this system consumes log structure, and both are materially harder to read aloud
  while narrating `journalctl -f` during a demo, which is a Phase 7 success criterion.
  — **Reversibility:** reversible.

- **D-20:** The formatter **keeps** `asctime`, accepting that it duplicates journald's own timestamp.
  The same command run by hand on the Windows development box then still shows timing — including how
  long a collection took — which is how most debugging will actually happen. Rejected TTY-conditional
  formatting as cleverness that would need justifying in review.
  — **Reversibility:** reversible.

### Claude's Discretion

- Exact `journal.md` structure and the wording of its day-one entry.
- Specific additional `.gitignore` entries beyond those already committed.
- README section ordering and depth, beyond the mandatory documented gate commands (D-04) and install
  steps (D-18).
- Internal module file names within `src/creatorpulse/` for Phase 1's skeleton (the CLI entry point and
  the config loader), provided D-02's command surface is honoured.
- `requires-python` value and other pyproject metadata not covered by D-17/D-18.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Binding project rules
- `.claude/CLAUDE.md` — hand-written "Hard Rules" block above the GSD markers. Human-built areas,
  the merge rule, settled decisions, the test-weakening prohibition. Authoritative where it conflicts
  with the generated sections below it in the same file.
- `.planning/PROJECT.md` — constraints, ownership boundaries, Key Decisions table.
- `.gitignore` — already committed. Phase 1 extends it; it does not create it.

### Scope
- `.planning/ROADMAP.md` §"Phase 1: Skeleton" — goal, owner, the four success criteria, and the three
  notes. Also §"Definition of Green" and §"Cut Order", which bind every phase.
- `.planning/ROADMAP.md` §"Phase 2: VPS & systemd" — read for the `ExecStart` / placeholder-entrypoint
  contract that D-02 and D-03 satisfy.
- `.planning/REQUIREMENTS.md` — OPS-02, OPS-03, OPS-04 are this phase's requirements. CFG-01/02/03 are
  Phase 3's and must NOT be implemented here.

### Technical grounding
- `.planning/research/STACK.md` — exact pinned versions for D-17, the eight closed dependency gaps, and
  the "no new dependencies" rationale. Note: its §"What NOT to Use" row for
  `helix/channels/followers` is stale — `.claude/CLAUDE.md` supersedes it.
- `.planning/research/ARCHITECTURE.md` — repository layout, module boundaries, and the standalone-sync
  rationale behind D-02.
- `.planning/research/PITFALLS.md` — the stripped-systemd-environment trap that D-01 avoids, and the
  secrets-before-`.gitignore` trap.
- `.planning/research/SUMMARY.md` — settled decisions and the phase-mapped implications digest.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

None. The repository contains no source code — only `.gitignore`, `.claude/CLAUDE.md`, and
`.planning/`. Phase 1 establishes every pattern from zero; there is nothing to match or reuse.

### Established Patterns

None in code. The binding conventions are the decisions above plus the documents under
`<canonical_refs>`.

### Integration Points

- **Phase 2 (human-built) consumes D-02 and D-03.** The systemd unit's `ExecStart` will be
  `<venv>/bin/creatorpulse collect`. This command must exist and exit 0 when Phase 1 closes.
- **Phase 3 consumes D-09 through D-11.** Its loader, validator, and collector are written against the
  `creators.yaml` shape fixed here.
- **Phases 3 and 4 consume D-15 and D-16.** Fixture layout and the recording script are set here and
  reused rather than reinvented.
- **Every later phase consumes D-04 through D-08.** The gate defined here is what "green" means for the
  rest of the project.

</code_context>

<specifics>
## Specific Ideas

- The `collect` placeholder should emit enough that Phase 2 can grade `journalctl` output honestly: a
  run-start line, a clearly-marked not-implemented line, and a run-end line carrying duration. The
  point is that the *shape* of the output is final even though the body is not.
- The gate is four commands, in this order: `ruff format --check .`, `ruff check .`, `mypy src/`,
  `pytest`. Documented literally in the README so the same block works on Windows and on the VPS.

</specifics>

<deferred>
## Deferred Ideas

- **`creators.yaml` validation with named-field error messages** (CFG-03) — Phase 1 parses only.
  Validation is Phase 3's, where the loader gains a `validate()` pass built on stdlib dataclasses per
  STACK.md.
- **Identifier resolution implementation** (D-11 decides the *contract*; the YouTube `forHandle` and
  Twitch Get Users calls that implement it are Phase 3 work, alongside caching so resolution does not
  burn quota on every run).
- **Retry/backoff helper** (SRC-05) — the hand-rolled decorator STACK.md specifies is Phase 3's, not
  part of the skeleton.
- **`journalctl` priority mapping** — noted as V2-OPS-01 in REQUIREMENTS.md. Would need
  `systemd-python` and `libsystemd-dev`; explicitly out of scope for v1 and not a Phase 1 concern.

</deferred>

---

*Phase: 1-Skeleton*
*Context gathered: 2026-07-30*
