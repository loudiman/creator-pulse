# Phase 2: VPS & systemd - Context

**Gathered:** 2026-07-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers a provisioned DigitalOcean droplet that runs `creatorpulse collect` on a systemd
timer, unattended, with its output readable afterwards via `journalctl` and its secrets held in a
file the repository has never seen. Concretely: a non-root service user, the repo cloned and
installed into a venv on the box, a `chmod 600` root-owned `EnvironmentFile`, a `.service` unit, a
`.timer` unit, UFW and SSH hardening, and a swap file.

It also delivers one thing ROADMAP.md's criteria imply but do not name: **environment-variable path
resolution in the application**. The database was placed at `/var/lib/creatorpulse/` during this
discussion, outside the repository, which `WorkingDirectory=` alone cannot express. The unit must
therefore hand the application its paths, and the application must read them. See D-01 for what that
does to this phase's ownership.

**Not in this phase:** any collector logic, any database schema, any source adapter, and any secret
*values* beyond the variable names the env file declares. Phase 2 proves the plumbing carries an
empty payload; Phase 3 fills it.

</domain>

<decisions>
## Implementation Decisions

### Ownership & the one exception

- **D-01:** This phase's owner changes from `human` to `mixed` in ROADMAP.md. The agent writes
  **exactly one thing**: environment-variable path resolution in `src/creatorpulse/`, plus the
  run-start log line that prints the resolved absolute paths. Everything else — the `.service` unit,
  the `.timer` unit, UFW rules, SSH configuration, and `docs/deploy.md` — stays human-built and the
  agent must not generate, draft, outline, or edit it, including when asked. The alternative
  considered was deferring the code to Phase 3, which was rejected because success criterion 2
  (`systemctl start` succeeds "against the same code path that works interactively") is vacuous if the
  code has never once resolved the paths the unit supplies.
  — **Reversibility:** reversible — the split is a note in ROADMAP.md and this file, not a structural
  commitment.

### Filesystem Layout & Service User

- **D-02:** A dedicated non-root user `creatorpulse` owns the deployment, with the repository cloned
  to `/home/creatorpulse/creator-pulse` and the venv inside it. Rejected `/opt/creatorpulse`: it is
  the FHS-conventional location and the one PITFALLS.md uses in its examples, but it is not a home
  directory, so it costs a `chown` step and leaves `$HOME` pointing at a directory that does not
  belong to the service. Phase 4 installs Playwright's Chromium as this user and its cache lands under
  `$HOME`, so a real, writable, service-owned home is worth more here than the convention. The unit
  still sets `Environment=HOME=/home/creatorpulse` explicitly rather than relying on systemd's
  default — PITFALLS.md #1 records `HOME` as not guaranteed for service users.
  — **Reversibility:** costly — the path is written into the human-typed unit, the runbook, and the
  Phase 4 Playwright install step. Moving it means editing a human-built artifact.

- **D-03:** Code reaches the box by `git clone https://github.com/loudiman/creator-pulse.git` as the
  service user; every Phase 3–7 update is `git pull && pip install -e .`. The repo is public, so no
  deploy key is needed. Rejected `rsync` from the Windows box: it works with uncommitted local state,
  which is precisely the property that makes it wrong — nothing on the droplet would identify which
  version is running when a run misbehaves. Rejected tag-based deploys as more ceremony than a
  seven-day solo build repays.
  — **Reversibility:** reversible.

- **D-04:** Secrets live at `/etc/creatorpulse/creatorpulse.env`, owned `root:root`, mode `600`,
  entirely outside the git working tree. systemd parses `EnvironmentFile=` as PID 1 — as root, before
  dropping to `User=creatorpulse` — so the service user never needs read access to its own secrets.
  That is least privilege at no cost, and it satisfies OPS-01's literal `chmod 600` wording. Rejected
  a repo-root `.env`: it is already gitignored, but it would sit inside a working tree that D-03
  updates with `git pull`, where `git clean -xfd` deletes it and `git add -f` commits it. The recovery
  from the second failure is key rotation, not a revert.
  — **Reversibility:** reversible — one `Environment`/`EnvironmentFile` line and a `mv`.

- **D-05:** The SQLite database lives at `/var/lib/creatorpulse/creatorpulse.db`, owned by the service
  user, outside the repository. Metric history is the one thing in this project that cannot be
  regenerated — the APIs report current values only — so it must survive a `git clean -xfd`, a
  re-clone, and a botched deploy. The Phase 6 Discord bot runs as the **same** user in its own unit:
  separate lifecycle and separate failure domain, but no second account, since WAL plus
  `busy_timeout` is the actual coordination mechanism and a filesystem-level reader/writer split would
  add a user and a group to explain for a guarantee SQLite already provides.
  — **Reversibility:** reversible while the DB is empty; effectively `one-way` once real history
  exists, since moving it then means moving live data the project cannot rebuild.

### Path Resolution Under systemd

- **D-06:** The application learns its paths from two environment variables, `CREATORPULSE_CONFIG`
  and `CREATORPULSE_DB`, read from `os.environ` at startup. The unit already carries
  `EnvironmentFile=` for secrets, so environment variables add no new mechanism and no new unit
  directive. Rejected CLI flags in `ExecStart`: `--db` does not exist yet, so the human-typed unit
  would encode a flag Phase 3 must implement, and any later path change would mean editing a
  human-built artifact. Rejected `WorkingDirectory=` with relative paths: it cannot express
  `/var/lib/creatorpulse` and taking it would have meant reopening D-05.
  — **Reversibility:** costly — Phase 3's `db.py` and config loading are written against these
  names, and they appear in a unit the agent may not edit.

- **D-07:** Both variables are set as `Environment=` lines **in the unit**, not in the
  `EnvironmentFile`. The root-owned `600` file then holds only genuine secrets, and
  `systemctl cat creatorpulse.service` still answers "which database is this service writing to?" —
  the first question worth asking when a run reports success and no rows appear. Reads cleanly out
  loud: secrets in the file nobody can read, paths in the unit anyone can.
  — **Reversibility:** reversible.

- **D-08:** When either variable is unset, the application falls back to today's repo-relative
  defaults (`creators.yaml`, and a repo-root database file) so Windows development needs no setup —
  and **every run logs both resolved absolute paths in its run-start output**. A mis-typed
  `Environment=` line then surfaces as a wrong path in the first `journalctl` line rather than as
  missing rows discovered a day later, which is what makes RUN-04's "readable after the fact" carry
  real information. Rejected hard-failing on unset: it protects against nothing that the logged path
  does not already expose, and it breaks local runs. Rejected silent fallback: its failure mode is
  SQLite cheerfully creating an empty database inside the repo on the VPS while the run reports
  success.
  — **Reversibility:** reversible.

### Timer Schedule

- **D-09:** `TimeZone=Asia/Manila` with `OnCalendar` firing daily at **08:00**. 08:00 PHT is exactly
  00:00 UTC, so the UTC `metric_date` (settled, Phase 3) always equals the Manila calendar date of the
  run. The off-by-one that 07:00 would have produced — every run stamping the previous UTC day, and
  the Sheet showing `2026-08-04` for a run watched on the morning of the 5th — simply never arises,
  and the settled UTC rule stays intact. This follows PITFALLS.md #12's "schedule local, store UTC,
  document it" and then removes the thing that needed documenting.
  — **Reversibility:** reversible mechanically, but note the data consequence: rows collected under a
  different fire time would carry a different UTC/local alignment than rows collected under this one.

- **D-10:** No `RandomizedDelaySec`. PITFALLS.md #2 recommends 300s, but its rationale is rate-limit
  collision across many cron-like jobs — this job makes on the order of ten API calls per day against
  a 10,000-unit YouTube quota, from one box nothing else shares. The jitter would buy nothing and
  would turn `systemctl list-timers`' `NEXT` from an exact time you can point at into a five-minute
  range, blurring the one moment in this project worth demonstrating live.
  — **Reversibility:** reversible.

- **D-11:** `Persistent=true`, proven by a **deliberate reboot across a shifted fire window**:
  temporarily set `OnCalendar` a few minutes out, power the droplet off before it fires, boot after
  the window has passed, confirm exactly one catch-up run in `journalctl -u creatorpulse.service`,
  then restore 08:00 and re-check with `systemd-analyze calendar`. Roughly ten minutes, and it is the
  only approach that exercises the missed-window path rather than describing systemd's semantics.
  Understood consequence, not a bug: a catch-up run stamps the current date, so a genuinely missed day
  leaves a gap in the history and the next delta spans two days. Backfill is impossible — the APIs
  expose current values only — so the honest handling is to leave the gap and let Phase 7's `/status`
  staleness reporting surface it.
  — **Reversibility:** reversible.

### Repo Artifacts & Proof of Done

- **D-12:** `deploy/creatorpulse.service` and `deploy/creatorpulse.timer` are committed to the
  repository and copied to `/etc/systemd/system/` by hand. They contain no secrets by construction —
  those live in the root-owned `EnvironmentFile` per D-04 — so there is nothing to redact, and a
  redacted template would strip exactly the details worth reviewing. They survive the droplet being
  destroyed and become diffable when Phase 6 adds a second unit.
  **Binding constraint for every downstream agent: these files may be READ. They must never be
  written, edited, generated, reformatted, or "fixed" — including when asked.** They are the
  human-built artifact this phase exists to produce.
  — **Reversibility:** reversible.

- **D-13:** A short ordered `docs/deploy.md` is written **by hand, by the author, while
  provisioning** — droplet creation, `useradd`, UFW, SSH hardening, swap, clone, venv, env file, unit
  install, timer enable. Writing it during the work is how success criterion 5 ("explain out loud,
  without notes") is actually satisfied; the document is the rehearsal. The agent does not draft it
  and does not outline it: the *ordering of provisioning steps* is precisely the knowledge the
  ownership rule protects.
  — **Reversibility:** reversible.

- **D-14:** `.env.example` is committed at the repo root listing **every variable v1 will need** —
  YouTube API key, Twitch client id and secret, Discord bot token, Discord webhook URL, Google
  service-account JSON path — with names only and values blank. `.gitignore` already carries the
  `!.env.example` negation, so this was anticipated at Phase 1. The real `/etc` file gets the same
  names now, filled in as each later phase earns them, which means `EnvironmentFile=` is wired and
  proven in Phase 2 rather than first exercised in Phase 3, and `docs/deploy.md` can describe the
  file's final shape.
  — **Reversibility:** reversible.

- **D-15:** Phase 2 closes on `02-UAT.md` carrying **pasted command output, one paste per success
  criterion** — `systemd-analyze calendar` for the schedule, `systemctl list-timers` for `NEXT`/`LAST`,
  the `systemctl start` exit status, `journalctl -u creatorpulse.service` showing the run-start /
  not-implemented / run-end lines from D-03 of Phase 1, `stat -c '%a %U:%G'` on the env file, a
  `git log -S` search proving no secret value is in history, and the catch-up reboot journal from
  D-11. Matches the `01-UAT.md` pattern already in the repo. Rejected screenshots: not greppable, not
  diffable, and a picture of `list-timers` cannot be re-checked against the unit six days later.
  — **Reversibility:** reversible.

### Claude's Discretion

- Whether path resolution lives in `src/creatorpulse/config.py` or a new small `paths.py`.
- Log level and exact wording of the resolved-paths line (INFO is the expectation, since it must be
  visible in a normal `journalctl` read).
- Section ordering within `02-UAT.md`, and comment style inside `.env.example`.
- Whether the repo-relative database fallback (D-08) is `creatorpulse.db` at the repo root or under a
  gitignored subdirectory — `*.db`, `*.db-wal`, and `*.db-shm` are already covered by `.gitignore`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Binding project rules
- `.claude/CLAUDE.md` — hand-written "Hard Rules" block above the GSD markers. Names VPS provisioning
  and systemd as human-built and forbids the agent from generating them. Authoritative where it
  conflicts with the generated sections below it in the same file. **D-01 narrows the one exception;
  it does not widen it.**
- `.planning/PROJECT.md` — constraints, the three human-built components, and the Key Decisions table
  including the host decision (DigitalOcean droplet, Singapore, 2 GB, chosen because container
  platforms have no init system and this phase's whole deliverable is a systemd timer).
- `.gitignore` — already covers `.env`, `*.env`, `service-account*.json`, `*.db`/`-wal`/`-shm`, and
  carries the `!.env.example` negation D-14 relies on.

### Scope
- `.planning/ROADMAP.md` §"Phase 2: VPS & systemd" — goal, the five success criteria, and the six
  notes (swap file, Playwright-as-service-user, `systemd-analyze calendar`, never cut this phase).
  **Its `**Owner:** human` line is superseded by D-01 and must be updated to `mixed`.**
- `.planning/ROADMAP.md` §"Definition of Green" and §"Cut Order" — bind every phase.
- `.planning/REQUIREMENTS.md` — RUN-03, RUN-04, OPS-01 are this phase's three requirements. RUN-03
  carries `*(human-built: unit and timer files)*` and only partially closes here; the roadmap notes it
  fully closes in Phase 3 when the real collector is wired.
- `.planning/phases/01-skeleton/01-CONTEXT.md` — D-01 (editable install, so no
  `Environment=PYTHONPATH`), D-02 and D-03 (the `creatorpulse collect` command and its log shape,
  which this phase's `ExecStart` targets and `02-UAT.md` grades), D-19/D-20 (stdout logging that
  journald captures).

### Technical grounding
- `.planning/research/PITFALLS.md` §"Pitfall 1" — the stripped-systemd-environment trap:
  `WorkingDirectory`, `HOME`, absolute `ExecStart`, `EnvironmentFile`, `User=`. Includes the
  `systemd-run --uid=creatorpulse env -i ...` reproduction trick.
- `.planning/research/PITFALLS.md` §"Pitfall 2" — `OnCalendar` and `Persistent=` semantics behind
  D-09/D-10/D-11. Note D-10 deliberately declines its `RandomizedDelaySec` advice, with reasons.
- `.planning/research/PITFALLS.md` §"Pitfall 7" — Playwright browsers installed as the wrong user and
  OOM on a small box. Drives D-02's home-directory choice and the swap file this phase provisions.
- `.planning/research/PITFALLS.md` §"Pitfall 12" — UTC vs local `metric_date`; the source of the
  08:00 alignment in D-09.
- `.planning/research/PITFALLS.md` §"Pitfall 10" — WAL plus `busy_timeout` as the bot/collector
  coordination mechanism D-05 relies on instead of a filesystem split.
- `.planning/research/STACK.md` — locked pins and the "no new dependencies" rule. Path resolution uses
  stdlib `os.environ` and `pathlib`; nothing new is warranted.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`src/creatorpulse/config.py:9`** — `DEFAULT_CONFIG_PATH = Path("creators.yaml")`, relative to the
  current working directory. Under systemd, cwd defaults to `/`. This is the exact line D-06 through
  D-08 exist to address, and it is the scout finding that made path resolution a Phase 2 concern
  rather than a Phase 3 one.
- **`src/creatorpulse/config.py:19`** — `load_creators(path: Path = DEFAULT_CONFIG_PATH)` already
  takes an injectable path, so environment-variable resolution can be layered above it without
  changing the loader's signature or its existing test.
- **`src/creatorpulse/cli.py:22-33`** — `run_collect` already emits the run-start / not-implemented /
  run-end lines. The resolved-paths log from D-08 belongs alongside the existing
  `"Starting collect run using config %s"` line, which already logs the config path and needs only to
  log the resolved absolute plus the database path.
- **`src/creatorpulse/cli.py:40-41`** — `collect` already accepts `--config`. D-06 chose environment
  variables over flags, so the flag stays as the interactive override and the environment variable
  becomes the default source.
- **`.gitignore`** — the `!.env.example` negation is already committed and unused. D-14 is what it was
  written for.
- **`README.md` §Install §Linux (VPS deployment)** — already documents `python3.12 -m venv .venv` and
  `pip install -e .` with no `[dev]` extra. `docs/deploy.md` (D-13) should reference this block rather
  than restate it.

### Established Patterns

- **stdlib `logging` to stdout, plain human-readable format** (Phase 1 D-19/D-20) — systemd captures
  it into the journal automatically. The resolved-paths line follows the same formatter; no structured
  logging, no journald handler.
- **`@dataclass(frozen=True, slots=True)`** in `config.py` — if path resolution grows a small holder
  type, match it.
- **mypy `strict = true` for `src/`** (Phase 1 D-05) — `os.environ.get` returns `str | None` and strict
  mode will insist that be handled, which is the D-08 fallback made explicit by the type checker.
- **No new dependencies** — `os.environ` and `pathlib` only.

### Integration Points

- **The human-typed unit consumes Phase 1 D-02/D-03.** `ExecStart` is
  `/home/creatorpulse/creator-pulse/.venv/bin/creatorpulse collect`, an absolute interpreter path per
  PITFALLS.md #1.
- **The human-typed unit consumes D-06/D-07.** It carries `Environment=CREATORPULSE_CONFIG=...` and
  `Environment=CREATORPULSE_DB=...`, `Environment=HOME=/home/creatorpulse`, and
  `EnvironmentFile=/etc/creatorpulse/creatorpulse.env`.
- **Phase 3 consumes D-05 and D-06.** `db.py` opens the path from `CREATORPULSE_DB` and must not
  invent its own default; the unit is human-built and will not be edited to match.
- **Phase 4 consumes D-02.** Playwright's Chromium is installed as the `creatorpulse` user and caches
  under the `HOME` this phase establishes.
- **Phase 6 consumes D-05.** The bot's own unit runs as the same user and opens the same database
  read-only in practice.
- **Phase 7 consumes D-11 and D-15.** The cold-start narration and the staleness reporting build on
  the catch-up behaviour proven here.

</code_context>

<specifics>
## Specific Ideas

- **`/var/lib/creatorpulse/` must be created by the human during provisioning**, owned
  `creatorpulse:creatorpulse` — the service user cannot `mkdir` inside `/var/lib` itself. Application
  code opens the database file; it must not attempt to create the parent directory, because doing so
  would fail under exactly the conditions it is meant to handle.
- The run-start log line should print resolved absolutes for **both** config and database, so a single
  `journalctl` read answers "what did this run actually use?" without inspecting the unit.
- `02-UAT.md` should paste the `systemd-analyze calendar 'Mon..Sun *-*-* 08:00:00'` output verbatim.
  The roadmap note is explicit that the schedule is verified by running that command, not by reasoning
  about the `OnCalendar` string.
- PITFALLS.md #1's reproduction trick is worth running before trusting the timer:
  `systemd-run --uid=creatorpulse --gid=creatorpulse env -i /home/creatorpulse/creator-pulse/.venv/bin/creatorpulse collect`
  reproduces the stripped environment on demand.

**Open at time of writing — not decided, and no default exists.** These are human-owned provisioning
choices; the researcher may surface options, and the author closes them during the afternoon:

- Swap file size (the roadmap calls for one as insurance against Phase 4 Playwright OOM; the droplet
  is 2 GB, so 1–2 GB is the plausible range).
- UFW rule set and SSH hardening specifics — which ports, key-only authentication, root login policy,
  whether the SSH port moves.
- Whether the venv sits at `.venv` inside the repo or beside it (D-02 assumes inside; nothing depends
  on it except the `ExecStart` path).
- The exact value of `Environment=HOME=` and where Playwright's browser cache is allowed to land.

</specifics>

<deferred>
## Deferred Ideas

- **Actual secret values** — `.env.example` and the real env file declare variable names in Phase 2.
  The YouTube key, Twitch credentials, Discord token and webhook, and the Google service-account JSON
  arrive with the phases that need them (3, 4, 6).
- **RUN-03's full closure** — the timer targets Phase 1's placeholder `collect`. The requirement only
  fully closes in Phase 3, whose criteria carry the check forward. This is the roadmap's own note, not
  a gap introduced here.
- **`journalctl` priority mapping** — V2-OPS-01 in REQUIREMENTS.md. Would need `systemd-python` and
  `libsystemd-dev`; out of scope for v1 and already deferred once in Phase 1.
- **A README deployment section** — `docs/deploy.md` (D-13) is the Phase 2 artifact. Folding
  deployment into the README belongs with OPS-08 in Phase 7, where the architecture diagram lands.
- **Getting a unit edited on the box back into `deploy/`** — no mechanism decided. In practice: edit
  `deploy/`, copy to `/etc/systemd/system/`, `daemon-reload`. If drift becomes a real problem, revisit;
  it is not one at two unit files.

</deferred>

---

*Phase: 2-VPS & systemd*
*Context gathered: 2026-07-31*
