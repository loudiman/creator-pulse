# Phase 2: VPS & systemd - Research

**Researched:** 2026-07-31
**Domain:** systemd unit/timer semantics, stripped-service-environment behavior, `EnvironmentFile=` parsing, and stdlib-only environment-variable path resolution in Python
**Confidence:** HIGH (systemd directive semantics — long-stable, cross-checked against official docs) / MEDIUM (exact CLI output shapes — cross-checked across multiple secondary sources, not a single canonical fetch this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Phase owner changes `human` → `mixed`. The agent writes **exactly one thing**:
  environment-variable path resolution in `src/creatorpulse/`, plus the run-start log line printing
  resolved absolute paths. Everything else (`.service`, `.timer`, UFW, SSH, `docs/deploy.md`) stays
  human-built; the agent must not generate, draft, outline, or edit it, including when asked.
- **D-02:** Dedicated non-root user `creatorpulse`, repo cloned to `/home/creatorpulse/creator-pulse`,
  venv inside it. `Environment=HOME=/home/creatorpulse` set explicitly in the unit (human-built).
- **D-03:** Code reaches the box via `git clone` + `git pull && pip install -e .` as the service user.
  No rsync, no tag-based deploys.
- **D-04:** Secrets at `/etc/creatorpulse/creatorpulse.env`, `root:root`, mode `600`, outside the git
  tree. Parsed by PID 1 as root before dropping to `User=creatorpulse`.
- **D-05:** SQLite DB at `/var/lib/creatorpulse/creatorpulse.db`, owned by the service user, outside
  the repo. Phase 6's bot runs as the **same** user; WAL + `busy_timeout` is the coordination
  mechanism, not a second account.
- **D-06:** Application reads `CREATORPULSE_CONFIG` and `CREATORPULSE_DB` from `os.environ` at
  startup. No CLI flags in `ExecStart`, no `WorkingDirectory=`-relative trick.
- **D-07:** Both variables are `Environment=` lines **in the unit**, not in `EnvironmentFile`. The
  root-owned `600` file holds only genuine secrets.
- **D-08:** When either variable is unset, the application falls back to today's repo-relative
  defaults (`creators.yaml`, repo-root DB file) — Windows dev needs no setup. **Every run logs both
  resolved absolute paths in its run-start output.** No hard-fail on unset; no silent fallback that
  hides the path used.
- **D-09:** `TimeZone=Asia/Manila`, `OnCalendar` daily at **08:00** (= 00:00 UTC, so UTC
  `metric_date` always equals the Manila calendar date).
- **D-10:** No `RandomizedDelaySec` — jitter buys nothing at ~10 API calls/day from one box, and
  blurs the one demoable exact-time moment.
- **D-11:** `Persistent=true`, proven by a **deliberate reboot across a shifted fire window**: set
  `OnCalendar` a few minutes out, power off before it fires, boot after, confirm exactly one catch-up
  run in `journalctl`, restore 08:00, re-verify with `systemd-analyze calendar`.
- **D-12:** `deploy/creatorpulse.service` and `deploy/creatorpulse.timer` are committed, contain no
  secrets. **Binding: these files may be READ, never written/edited/generated/reformatted — including
  when asked.**
- **D-13:** `docs/deploy.md` written by hand, by the author, during provisioning. The agent does not
  draft or outline it.
- **D-14:** `.env.example` committed at repo root, every v1 variable name, values blank.
- **D-15:** `02-UAT.md` carries pasted command output, one paste per success criterion (no
  screenshots).

### Claude's Discretion

- Whether path resolution lives in `src/creatorpulse/config.py` or a new small `paths.py`.
- Log level and exact wording of the resolved-paths line (INFO expected).
- Section ordering within `02-UAT.md`, comment style inside `.env.example`.
- Whether the repo-relative database fallback (D-08) is `creatorpulse.db` at repo root or under a
  gitignored subdirectory.

### Deferred Ideas (OUT OF SCOPE)

- Actual secret values (arrive in Phases 3, 4, 6).
- RUN-03's full closure (Phase 3, when the real collector is wired).
- `journalctl` priority mapping (V2-OPS-01 — needs `systemd-python`/`libsystemd-dev`, out of v1 scope).
- A README deployment section (`docs/deploy.md` is the Phase 2 artifact; README folding is Phase 7).
- Getting a unit edited on the box back into `deploy/` — no mechanism decided; revisit only if drift
  becomes a real problem.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RUN-03 | Collector runs unattended on a daily systemd timer *(human-built: unit/timer files)* | Pitfall 1 + Pitfall 2 sections below explain the directive semantics the human author needs while writing the unit; this requirement only **partially** closes in Phase 2 — it targets Phase 1's placeholder `collect` and fully closes in Phase 3. Research does not produce the unit itself (D-12 forbids it). |
| RUN-04 | Run output readable after the fact via `journalctl -u <unit>` | Closes in Phase 2. Depends on Phase 1's stdout logging (already in place) plus this phase's D-08 resolved-path log line, which is what makes a `journalctl` read answer "what did this run actually use?" See Code Examples and Validation Architecture below. |
| OPS-01 | Secrets load from a `chmod 600` env file via systemd `EnvironmentFile`, never committed | Closes in Phase 2 via D-04/D-07 (human-built unit + file). Research section "`EnvironmentFile=` Semantics" documents the parsing/quoting/dash-prefix behavior the human author needs to get this right, and why PID-1-as-root parsing satisfies least privilege. |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Human-built, agent must not generate/draft/outline, including when asked:** VPS provisioning and
  systemd (SSH config, non-root user, UFW rules, `.service`/`.timer` unit files — Python the units
  *invoke* may be written; the units themselves may not).
- **Merge rule:** nothing enters the repo the author can't explain out loud — outranks speed.
- **No new dependencies without asking.** Path resolution uses stdlib `os.environ` + `pathlib` only.
- No Docker, no web UI, no auth layer, no Postgres, no queues.
- **NULL vs 0** correctness rule (not directly touched by this phase, but the resolved-path log line
  must not paper over an unset variable by silently treating it as "fine" — D-08 already encodes this).
- **Testing:** fixtures only, no live network calls in the suite; green means `ruff check .` **and**
  `mypy src/` **and** `pytest`. Any test-file change during Verify is suspect unless requested.
- **Ethics:** not directly implicated by this phase (no scraping here).

## Summary

Phase 2's code surface is narrow by design: two environment variables read once at startup, a
fallback to the existing repo-relative defaults, and one INFO log line. The actual research weight
sits in what the **human author** needs to know while hand-writing the unit and timer files this
phase forbids the agent from touching — so this document is deliberately split between (a) a small,
concrete Python pattern for the part the agent owns, and (b) systemd *behavior* documentation (not
unit-file drafting) that de-risks the human-built half, because the agent's own success criteria
(2, 4, 5 in ROADMAP.md) depend on that unit working correctly even though the agent never writes it.

The single highest-value fact in this research: **`systemctl start <unit>` reproduces the exact
stripped environment a scheduled timer fire will use** — no `$HOME`, no inherited `$PATH`, `cwd`
defaulting to `/`, no shell profile sourced. Success criterion 2 explicitly requires this path be
exercised, not dodged, which is why D-06/D-07/D-08 exist: `os.environ.get()` with an explicit,
*logged* fallback is the only way application code can behave correctly whether it's invoked from an
interactive Windows shell (nothing set, fallback used, logged) or from the unit (both variables set,
used, logged) — same code path, both success criteria 1 and 2 depend on it being provably the same.

**Primary recommendation:** Read `CREATORPULSE_CONFIG`/`CREATORPULSE_DB` from `os.environ` once at
process start (not lazily per-call), resolve to absolute `Path` objects with the existing
repo-relative constants as fallback, log both resolved absolutes at INFO immediately after
`configure_logging()` runs and before any file I/O — so a run that fails to find its config still
leaves a `journalctl` line proving which path it looked for.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Scheduled unattended execution | OS / systemd (`.timer`) | — | `OnCalendar`/`Persistent=` are kernel-adjacent init-system concerns; no application code schedules itself. Human-built per D-12. |
| Process supervision & restart | OS / systemd (`.service`) | — | `User=`, `ExecStart=`, environment injection all live in the unit, not in Python. Human-built. |
| Secret storage & injection | OS / systemd (`EnvironmentFile=`) | Application (reads via `os.environ`) | PID 1 parses the root-owned `600` file *before* dropping privilege — the secret never touches application code as a file path, only as an already-injected env var. Split: OS owns storage/injection, application owns consumption. |
| Path resolution | Application (`src/creatorpulse/`) | — | The one thing this phase's Python owns. Reads env vars the unit injects; must behave identically whether those vars are present (VPS) or absent (Windows dev). |
| Log capture & retention | OS / journald | Application (emits to stdout) | Application only writes structured, human-readable lines to stdout; journald's automatic unit-stdout capture is what makes `journalctl -u <unit>` work — no journal-specific handler in code. |
| Filesystem layout / ownership | OS / human provisioning | — | `/var/lib/creatorpulse`, `/etc/creatorpulse` creation and `chown` are provisioning steps (D-13), not something application code creates on demand (see Pitfall: parent-directory creation below). |

## Standard Stack

### Core

No new libraries. This phase's entire code surface is stdlib.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `os` (stdlib) | bundled w/ 3.12 | Read `CREATORPULSE_CONFIG`/`CREATORPULSE_DB` via `os.environ.get()` | Zero-dependency, and it's literally what systemd's `Environment=` line populates for the process — nothing else touches this. `[VERIFIED: Python stdlib]` |
| `pathlib` (stdlib) | bundled w/ 3.12 | Resolve to absolute `Path` objects (`Path(x).resolve()`) for the log line and downstream `Path.exists()`/`Path.open()` calls | Already the type used by `config.py`'s `DEFAULT_CONFIG_PATH` and `cli.py`'s `--config` argument (`type=Path`) — matches the existing pattern exactly, no new type introduced. `[VERIFIED: repo grep, src/creatorpulse/config.py:9]` |
| `logging` (stdlib) | bundled w/ 3.12 | Emit the resolved-paths line at INFO | Already configured in `cli.py:configure_logging()` (Phase 1 D-19/D-20); this phase adds one more `logger.info(...)` call, no new configuration. `[VERIFIED: repo grep, src/creatorpulse/cli.py:14]` |

### Supporting

None — this phase adds no supporting libraries.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `os.environ.get(name, default)` per call site | `python-dotenv` / a config-object library | Rejected per CLAUDE.md's "no new dependencies without asking" and STACK.md's precedent (pydantic/tenacity/structlog all rejected for the same reason) — two env vars with a static fallback do not need a library. |
| Fallback baked into each call site | A tiny `@dataclass(frozen=True, slots=True)` `Paths` holder resolved once in `main()` and passed down | Both are reasonable; CONTEXT.md leaves this to Claude's discretion. A holder type matches the existing `Creator` dataclass convention in `config.py` and avoids re-reading `os.environ` at multiple call sites (see Pitfall: repeated env reads below), which is the better default absent a reason not to. |

**Installation:** none — no `pip install` line for this phase.

## Package Legitimacy Audit

Not applicable — this phase installs no external packages. All path-resolution code is stdlib
(`os`, `pathlib`, `logging`), already present in the Python 3.12 runtime locked in Phase 1.

## Architecture Patterns

### System Architecture Diagram

```
                     ┌─────────────────────────────────────────┐
                     │   systemd (PID 1, root)                  │
                     │   parses EnvironmentFile= as root         │
                     │   (secrets: never touch app as a path)    │
                     └───────────────┬───────────────────────────┘
                                      │ injects env into forked process
                                      │ Environment=CREATORPULSE_CONFIG=...
                                      │ Environment=CREATORPULSE_DB=...
                                      │ Environment=HOME=/home/creatorpulse
                                      │ EnvironmentFile=/etc/creatorpulse/creatorpulse.env
                                      ▼
                     ┌─────────────────────────────────────────┐
                     │ User=creatorpulse process starts          │
                     │ ExecStart=<venv>/bin/creatorpulse collect │
                     │ cwd = / (systemd default, NOT the repo)   │
                     └───────────────┬───────────────────────────┘
                                      ▼
                     ┌─────────────────────────────────────────┐
                     │ creatorpulse.cli:main()                   │
                     │ configure_logging()  → stdout              │
                     └───────────────┬───────────────────────────┘
                                      ▼
                     ┌─────────────────────────────────────────┐
                     │ resolve_paths()  (this phase's new code)  │
                     │  config = os.environ.get("CREATORPULSE_   │
                     │           CONFIG") or DEFAULT_CONFIG_PATH  │
                     │  db     = os.environ.get("CREATORPULSE_DB")│
                     │           or DEFAULT_DB_PATH                │
                     │  both .resolve() to absolute Path           │
                     └───────────────┬───────────────────────────┘
                                      ▼
                     ┌─────────────────────────────────────────┐
                     │ logger.info("run-start: config=%s db=%s") │
                     │  ← this line is RUN-04's proof            │
                     └───────────────┬───────────────────────────┘
                                      ▼
                          stdout ──► journald ──► journalctl -u <unit>
                                      │
                                      ▼
                     ┌─────────────────────────────────────────┐
                     │ load_creators(config) / (Phase 3: db open)│
                     └─────────────────────────────────────────┘
```

Data flow to trace for success criterion 2: an operator's interactive Windows shell has neither
`CREATORPULSE_CONFIG` nor `CREATORPULSE_DB` set → `resolve_paths()` falls back to repo-relative
defaults → the log line shows those absolute paths. The same function, invoked under the unit where
both variables *are* set, resolves to `/etc`/`/var/lib` paths instead. No branch in the code
distinguishes "am I on the VPS" — only "is the variable set" — which is what makes it the same code
path per criterion 2's literal wording.

### Recommended Project Structure

Discretion item — either is acceptable; folding into the existing file is the lower-ceremony option
given the size of the change (two env reads, no new class hierarchy):

```
src/creatorpulse/
├── config.py   # existing: Creator dataclass, load_creators() — ADD: resolve_paths() here, or:
├── paths.py    # new, small: only if resolve_paths() + a Paths dataclass feels crowded in config.py
└── cli.py      # existing: main(), run_collect() — calls resolve_paths(), logs the result
```

### Pattern 1: Environment-variable path resolution with logged fallback

**What:** Read an env var once, fall back to a stdlib default, resolve to absolute, log the result —
never branch behavior on "am I under systemd," only on "is the variable present."

**When to use:** Any value a deployment environment must be able to override without editing code or
an `ExecStart` line (per D-06's rejection of CLI flags for values that don't exist as flags yet).

**Example:**
```python
# Illustrative — not the unit file, not deploy/*. Application code only (agent's owned surface).
import os
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("creators.yaml")
DEFAULT_DB_PATH = Path("creatorpulse.db")  # discretion: repo root or gitignored subdir


def resolve_paths() -> tuple[Path, Path]:
    """Resolve config and DB paths from the environment, falling back to repo-relative defaults.

    Mirrors what systemd's Environment= lines inject on the VPS; on an interactive shell with
    neither variable set, the existing repo-relative defaults apply unchanged.
    """
    config_raw: str | None = os.environ.get("CREATORPULSE_CONFIG")
    db_raw: str | None = os.environ.get("CREATORPULSE_DB")

    config_path = Path(config_raw).resolve() if config_raw else DEFAULT_CONFIG_PATH.resolve()
    db_path = Path(db_raw).resolve() if db_raw else DEFAULT_DB_PATH.resolve()
    return config_path, db_path
```

The `str | None` annotation is required, not optional decoration — Phase 1 D-05 turned on mypy
`strict = true` for `src/`, and strict mode rejects `os.environ.get(name)` being implicitly treated as
`str`. This is the exact "NULL vs assumed-present" discipline CLAUDE.md's core correctness rule
already applies to metric values, now applied to the type checker's view of the environment.

### Pattern 2: Run-start log line as the single source of truth for "what did this run use"

**What:** Log both resolved absolute paths at INFO, unconditionally, as the very next line after
`configure_logging()` — before any file I/O that could raise.

**When to use:** Whenever RUN-04-style "readable after the fact" is a requirement and the value being
logged is itself the thing most likely to be silently wrong (a mistyped `Environment=` line producing
a *valid* but *wrong* path is indistinguishable from a correct one except by reading it back).

**Example:**
```python
# Extends the existing run_collect() in cli.py — same file, same function, one more log line.
def run_collect(config_path: Path, db_path: Path) -> int:
    start = time.monotonic()
    logger.info("Starting collect run using config %s, db %s", config_path, db_path)
    ...
```

### Anti-Patterns to Avoid

- **Re-reading `os.environ` at every call site instead of once at startup:** makes it possible for a
  test or a later code path to observe a different value than what was logged at run-start, breaking
  RUN-04's promise that the log line reflects what the run actually used.
- **Creating the parent directory (`/var/lib/creatorpulse`) from application code:** CONTEXT.md's
  Specific Ideas section is explicit that this must fail loudly, not silently `mkdir` — the service
  user cannot create it (its parent `/var/lib` is root-owned), and a `mkdir` fallback would mask a
  provisioning step that's supposed to have already happened.
- **Silent fallback with no log line:** D-08 explicitly rejects this — its failure mode is a run that
  reports success while writing to a fresh empty repo-local database on the VPS.
- **Hard-failing when a variable is unset:** D-08 explicitly rejects this too — it would break every
  local Windows dev run, which has neither variable set by design.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reading an env var with a typed default | A custom `EnvConfig` class with `__getattr__` magic or a settings-loader abstraction | `os.environ.get(name)` + an explicit `if`/`or` fallback, exactly as shown above | Two variables, one fallback shape each. An abstraction here is exactly the kind of unrequested scaffolding CLAUDE.md's merge rule (must be explainable out loud) argues against — STACK.md already rejected pydantic for the much larger `creators.yaml` schema on the same grounds. |
| Verifying a scheduled job actually ran | A custom heartbeat file the app writes on success | `systemctl list-timers` (`LAST` column) + `journalctl -u <unit>` | systemd already persists last-trigger state (`/var/lib/systemd/timers/`) for `Persistent=` to work — duplicating that in application code is redundant state that can drift from the real trigger history. |
| Proving the stripped-environment code path works | Manually SSH in, `su - creatorpulse`, run the command, and hope the shell's inherited environment resembles what systemd would give | `systemd-run --uid=creatorpulse --gid=creatorpulse env -i <path> collect` | `env -i` clears the environment entirely before adding back only what's specified, which is what `su -` does *not* guarantee (login shells source profile files that inject `$PATH`/`$HOME` systemd never would) — this is Pitfall 1 from PITFALLS.md, restated here because it's the actual reproduction technique, not just the risk description. |

**Key insight:** the only thing worth hand-writing in this phase is the ~10-line function above.
Everything else that looks like it needs custom tooling (env-var typing, run-verification, stripped-
environment reproduction) already has a stdlib or systemd-native answer.

## Common Pitfalls

### Pitfall A: `systemctl start` silently exercises a *different* code path than the interactive terminal

**What goes wrong:** A developer runs `creatorpulse collect` by hand from inside the repo directory
on the VPS (as themselves, or even as `creatorpulse` via `su -`), sees it work, and concludes the
service is ready. `systemctl start creatorpulse.service` then fails or behaves differently because
`cwd` defaults to `/`, `$PATH` has none of the interactive shell's entries, `$HOME` may be unset, and
no profile/rc file was sourced.

**Why it happens:** systemd services do not inherit a login shell's environment at all — they get
exactly what the unit's `Environment=`/`EnvironmentFile=` lines and a small systemd-provided default
set specify, nothing more.

**How to avoid:** Reproduce the stripped environment *before* trusting a `systemctl start`:
```
systemd-run --uid=creatorpulse --gid=creatorpulse env -i \
  /home/creatorpulse/creator-pulse/.venv/bin/creatorpulse collect
```
`env -i` clears the environment entirely, so anything that still works here will work under the real
unit. This is a verification technique to run and paste into `02-UAT.md`, not something the agent
executes (it requires the provisioned VPS) — but the plan should schedule it as a UAT step.

**Warning signs:** Works when triggered interactively, `FileNotFoundError`/`ModuleNotFoundError`/a
wrong resolved path in the log line when triggered via `systemctl start`.

*(Fuller treatment: PITFALLS.md §Pitfall 1.)*

---

### Pitfall B: `EnvironmentFile=` typos fail differently than expected

**What goes wrong:** Three distinct failure shapes, easy to conflate:
1. File path wrong, no `-` prefix → systemd refuses to start the unit at all (hard failure, loud).
2. File path wrong, **with** `-` prefix (`EnvironmentFile=-/etc/...`) → missing file is silently
   skipped, no error, no warning — the service starts with those variables simply absent.
3. File exists but a line has a typo (stray quote, missing `=`) → that one line is dropped or
   mis-parsed; the rest of the file still loads, so the failure is partial, not total.

**Why it happens:** The `-` prefix exists specifically for optional files (e.g., an env file that may
not exist on every deployment target) — but it means "missing" and "typo'd path" produce identical
silence. `[CITED: systemd.exec(5), cross-checked via search — freedesktop.org/software/systemd/man/latest/systemd.exec.html]`

**How to avoid:** For `/etc/creatorpulse/creatorpulse.env`, the file's existence is a hard
precondition (D-04) — do not use the `-` prefix for this file. Reserve `-` only for genuinely
optional environment files, if any are ever added. Verify parsing with
`systemctl cat creatorpulse.service` (shows the unit's resolved directives) and
`systemctl show creatorpulse.service -p Environment` (shows what actually got injected, secrets
redacted from typical output review since they're not printed by `cat`/`show` the same way).

**Warning signs:** A secret-dependent code path (Phase 3+) behaves as if the variable is `None`/empty
despite the file existing and looking correct on casual inspection — check for a stray `"` or a line
without `=`.

*(D-04's rationale already covers *why* `EnvironmentFile=` was chosen over an in-repo `.env`; this
pitfall is about the parsing behavior once that choice is made.)*

---

### Pitfall C: `Persistent=true` is misread as "replay every missed day"

**What goes wrong:** D-11's reboot-across-a-fire-window test is designed to prove a specific, narrow
behavior — but if the plan or the UAT narration describes it as "catches up all missed runs," the
claim is wrong and unverifiable, because `Persistent=` does not work that way.

**What actually happens:** systemd stores the last-trigger timestamp on disk (`/var/lib/systemd/timers/`
per current documentation). On the next timer activation opportunity (e.g., boot), if **any** calendar
occurrence was missed while the timer was inactive, the unit fires **once** — not once per missed
occurrence. Miss three days, get one catch-up run, not three.
`[CITED: cross-checked via search against systemd.timer(5) and ArchWiki — MEDIUM confidence, no single canonical doc directly fetched this session]`

**How to avoid:** D-11's own text already gets this right ("a catch-up run stamps the current date... a
genuinely missed day leaves a gap"). The research value here is confirming the plan should phrase the
UAT expectation as **"exactly one catch-up run appears in `journalctl`"** — not "the missed day's data
appears" (impossible; the APIs are current-value-only, per D-11's own note) and not "every missed
occurrence replays."

**Warning signs:** A UAT script or plan step that expects multiple catch-up runs, or expects the
catch-up run's `metric_date` to backdate to the missed day rather than stamping the day it actually ran.

---

### Pitfall D: Testing `os.environ`-driven resolution on Windows without a Linux box

**What goes wrong:** The suite runs on the author's Windows 11 dev machine (per CLAUDE.md's fixtures-
only, no-live-network rule) — there is no systemd here to test against. A naive test might try to
literally set `HOME`/`PATH` the way systemd would, which doesn't map cleanly onto Windows semantics.

**How to avoid:** Test the *function's behavior given environment state*, not the OS-level mechanism
that produces that state — `resolve_paths()` doesn't know or care whether its inputs came from
systemd's `Environment=` or a test harness:

```python
def test_resolve_paths_uses_env_vars_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CREATORPULSE_CONFIG", str(tmp_path / "creators.yaml"))
    monkeypatch.setenv("CREATORPULSE_DB", str(tmp_path / "creatorpulse.db"))
    config_path, db_path = resolve_paths()
    assert config_path == (tmp_path / "creators.yaml").resolve()
    assert db_path == (tmp_path / "creatorpulse.db").resolve()


def test_resolve_paths_falls_back_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CREATORPULSE_CONFIG", raising=False)
    monkeypatch.delenv("CREATORPULSE_DB", raising=False)
    config_path, db_path = resolve_paths()
    assert config_path == DEFAULT_CONFIG_PATH.resolve()
    assert db_path == DEFAULT_DB_PATH.resolve()
```

pytest's built-in `monkeypatch.setenv`/`delenv` fixture (no new dependency — `monkeypatch` ships with
pytest itself) isolates env mutation per-test automatically; no manual `os.environ` save/restore
needed, and nothing here depends on the host OS being Linux. `[VERIFIED: pytest stdlib-shipped fixture, confirmed via repo's existing pytest 9.1.1 pin in STACK.md]`

**Warning signs:** A test that mutates `os.environ` directly without `monkeypatch` and leaks state into
a later test (order-dependent failures) — `monkeypatch` avoids this by construction.

---

### Pitfall E: Silent-failure traps discovered only on the box, not in code review

| Trap | What goes wrong | Why it matters here |
|------|------------------|----------------------|
| `/var/lib/creatorpulse` ownership | If created by root during provisioning without a `chown creatorpulse:creatorpulse`, the service user can open the DB path for read but `sqlite3.connect()`'s write/WAL-file creation fails with `OperationalError: unable to open database file` — not a permissions error message that names the actual cause. | Directly gates OPS-01/DATA-01 in Phase 3; Phase 2's job is to prove the *path resolves correctly*, but the *directory being writable* is a provisioning precondition this research flags for `docs/deploy.md`, not something Python code can detect and fix at runtime (see Anti-Pattern above). |
| SQLite WAL sidecar files (`-wal`, `-shm`) inherit the directory's permissions, not the main DB file's | If `/var/lib/creatorpulse` is `755` but the DB file itself is `600`, WAL mode still creates `-wal`/`-shm` files at the directory's permission level, potentially more permissive than intended. | PITFALLS.md #10 already establishes WAL as the concurrency mechanism between collector and bot; this phase's directory creation (human-built) should set the directory mode deliberately, not rely on `umask` defaults. |
| journald rate limiting | By default journald applies per-service rate limiting (burst + interval); a run that logs unusually verbosely (e.g., a retry storm in Phase 3+) can have lines silently dropped, with only a "N messages suppressed" journal note easy to miss when reading `journalctl -u <unit>` casually. | Directly relevant to RUN-04's "readable after the fact" — a suppressed run-start log line would defeat this phase's entire point. Low risk at this phase's log volume (a handful of lines/run), worth noting for Phase 3+ when retry logging grows. `[ASSUMED — general systemd/journald behavior, not verified against this project's specific journald config this session]` |
| tzdata availability for `TimeZone=Asia/Manila` | Minimal/stripped-down cloud images occasionally ship without the full `tzdata` package, in which case an unrecognized `TimeZone=` value causes the timer to fail validation rather than silently defaulting to UTC. | Directly gates D-09's 08:00 PHT / 00:00 UTC alignment claim. `systemd-analyze calendar 'Mon..Sun *-*-* 08:00:00 Asia/Manila'` (per D-15) is exactly the check that would surface this — if it errors, the fix is installing `tzdata`, not reworking the schedule. `[ASSUMED — most modern DigitalOcean base images (Ubuntu/Debian) ship tzdata by default; not verified against a live droplet this session]` |

## Code Examples

Both examples below are Python, inside the agent's exact writable scope per D-01 — not unit files.

### Resolved-path logging integrated into the existing `run_collect`

```python
# Source: pattern derived from existing src/creatorpulse/cli.py:22-33 (Phase 1), extended per D-08.
def run_collect(config_path: Path, db_path: Path) -> int:
    start = time.monotonic()
    logger.info("Starting collect run using config %s, db %s", config_path, db_path)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        return 1
    creators = load_creators(config_path)
    logger.info("Loaded %d creators", len(creators))
    logger.warning("Collector body is not implemented yet; Phase 3 fills it in")
    elapsed = time.monotonic() - start
    logger.info("Run complete in %.2f seconds", elapsed)
    return 0
```

Note: `db_path` is accepted but unused by `run_collect` itself in Phase 2 (no DB code exists yet per
CONTEXT.md's "not in this phase" boundary) — it is threaded through and logged only, which is exactly
what D-08 requires and exactly what Phase 3's `db.py` will later consume without any signature change
here.

### `main()` wiring — env-resolved paths override the `--config` default

```python
# Source: pattern derived from existing src/creatorpulse/cli.py:36-58; --config stays as an
# interactive override per D-06 ("the flag stays as the interactive override").
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creatorpulse")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--config", type=Path, default=None)  # None = "use env/fallback"

    args = parser.parse_args(argv)
    configure_logging()

    if args.command == "collect":
        env_config, env_db = resolve_paths()
        config_path = args.config.resolve() if args.config else env_config
        return run_collect(config_path, env_db)
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| cron for scheduled jobs | systemd timers (`OnCalendar=`) | Long-settled (systemd is default init on virtually all current mainstream distros; not a recent change) | Already the project's locked decision (ROADMAP §Out of Scope: "Cron"); the operative reason restated here is structured logs via `journalctl` plus `Persistent=`'s reboot-survival, neither of which cron provides natively. No new information vs. what STACK.md/PITFALLS.md already record. |

No deprecated/outdated systemd directives are in play for this phase's scope — `OnCalendar=`,
`Persistent=`, `EnvironmentFile=`, `Environment=`, `User=`, `WorkingDirectory=` are all long-stable,
non-deprecated directives per current `systemd.exec(5)`/`systemd.timer(5)`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | journald's default rate-limiting burst/interval thresholds are unlikely to be hit at this phase's log volume (a handful of INFO lines per run) | Common Pitfalls → Pitfall E | If wrong (e.g., the droplet's journald config is unusually strict), RUN-04's "readable after the fact" could silently lose lines during Phase 3+'s heavier retry logging. Low likelihood at Phase 2's log volume specifically; worth a one-line mention in `docs/deploy.md` if the human author wants to check `journalctl --disk-usage` / rate-limit config during provisioning — not an agent action. |
| A2 | The target DigitalOcean droplet image ships `tzdata` by default (so `TimeZone=Asia/Manila` resolves without an extra install step) | Common Pitfalls → Pitfall E | If wrong, `systemd-analyze calendar` (D-15's own verification step) surfaces it immediately as a parse/validation failure — self-detecting, low risk, easy fix (`apt install tzdata`, a human provisioning step). |
| A3 | `EnvironmentFile=` quoting/dash-prefix/comment-line behavior described in Pitfall B matches the specific systemd version shipped on the chosen droplet image | Common Pitfalls → Pitfall B; Don't Hand-Roll | These semantics have been stable across systemd versions for years; risk of drift is low, but was cross-checked via search summary rather than a single directly-fetched man page this session. |

## Open Questions

1. **Swap file size (1–2 GB range)**
   - What we know: droplet is 2 GB RAM (PROJECT.md); Phase 4's Playwright/Chromium is the OOM risk
     this insures against (PITFALLS.md §7); ROADMAP.md's note says "provision a swap file now."
   - What's unclear: the exact size — this is explicitly a human-owned provisioning choice
     (CONTEXT.md's "Open at time of writing" list), not something research or the plan should default
     for the human.
   - Recommendation: not an agent decision or a planner task — the plan should reference that this
     choice is made during human provisioning (`docs/deploy.md`), not attempt to pick a number.

2. **UFW rule set / SSH hardening specifics**
   - What we know: human-built per CLAUDE.md's hard rule and D-01's unchanged exception boundary.
   - What's unclear: nothing the agent needs to resolve — explicitly out of the agent's writable
     surface, and explicitly out of this document's scope per the hard scope fence.
   - Recommendation: the plan should not contain a task that drafts, outlines, or "helps" with this.

3. **journald rate-limit configuration on the actual droplet**
   - What we know: default systemd/journald ships with `RateLimitIntervalSec`/`RateLimitBurst`
     defaults that are generous enough for a once-daily job with a handful of log lines.
   - What's unclear: whether the specific droplet image's defaults differ meaningfully; not verified
     against a live box this session (no droplet exists yet).
   - Recommendation: low-priority — worth a single `journalctl` sanity check during D-15's UAT pass,
     not a blocking research gap.

## Environment Availability

The target production environment (systemd, journald, UFW, a Linux filesystem) does not exist as a
running box during research or during the agent's own execution — Phase 2's human-built half is
provisioned by the author directly on a droplet outside any agent's operational reach, and that
provisioning is explicitly out of scope for the agent regardless of what's locally available.

The agent's own writable surface (path resolution in `src/creatorpulse/`) has no external dependency
beyond the Python 3.12 runtime and pytest already locked in Phase 1 — both already confirmed present
via `01-UAT.md`'s green gate. No additional environment probing is needed for the code this phase
actually adds.

| Dependency | Required By | Available (dev machine) | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | `resolve_paths()`, tests | ✓ (already confirmed Phase 1) | 3.12 | — |
| pytest / `monkeypatch` fixture | Testing env-var resolution | ✓ (already locked, STACK.md) | 9.1.1 | — |
| systemd / journald / UFW / SSH hardening tools | Human-built unit, timer, provisioning | N/A — not agent's environment, not agent's responsibility | — | Human provisions on the droplet directly; not something the agent's dev environment needs or can substitute for. |

**Missing dependencies with no fallback:** none blocking the agent's actual code.

**Missing dependencies with fallback:** systemd/journald/UFW tooling — fallback is "human provisions
directly," which is the phase's designed ownership split (D-01), not a gap.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (locked, STACK.md) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (established Phase 1) |
| Quick run command | `pytest tests/test_paths.py -x` (new file — see Wave 0 Gaps) |
| Full suite command | `pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| RUN-04 (supporting behavior) | `resolve_paths()` returns repo-relative defaults when env vars are unset | unit | `pytest tests/test_paths.py::test_resolve_paths_falls_back_when_unset -x` | ❌ Wave 0 |
| RUN-04 (supporting behavior) | `resolve_paths()` returns env-supplied absolute paths when both vars are set | unit | `pytest tests/test_paths.py::test_resolve_paths_uses_env_vars_when_set -x` | ❌ Wave 0 |
| RUN-04 | Run-start log line contains both resolved absolute paths | unit (caplog-based) or manual | `pytest tests/test_paths.py::test_run_collect_logs_resolved_paths -x` OR `journalctl -u creatorpulse.service` read during UAT | ❌ Wave 0 (unit) — manual-only for the actual VPS confirmation |
| RUN-03 | Timer fires on schedule with no human present | manual-only | `systemd-analyze calendar` + `systemctl list-timers` (D-15) | N/A — cannot be unit-tested; requires the provisioned VPS |
| OPS-01 | Secrets readable only by root, absent from git history | manual-only | `stat -c '%a %U:%G' /etc/creatorpulse/creatorpulse.env` + `git log -S<secret-name>` (D-15) | N/A — filesystem/git-history assertion, not application logic |

Three of five requirement-supporting behaviors are legitimately manual-only per D-15's own design (the
UAT pattern for this phase is pasted command output, not automated tests) — this is not a Wave 0 gap,
it's the correct test type for infrastructure behavior that has no meaningful unit-test surface.

### Sampling Rate

- **Per task commit:** `pytest tests/test_paths.py -x` (fast — no I/O beyond `tmp_path`)
- **Per wave merge:** `pytest` (full suite, still fast at this project's size)
- **Phase gate:** Full suite green, **plus** all five `02-UAT.md` pasted-output checks (D-15) — the
  automated suite alone does not close this phase; the manual pastes are load-bearing per CONTEXT.md.

### Wave 0 Gaps

- [ ] `tests/test_paths.py` (or `tests/test_cli.py` extended, matching wherever `resolve_paths()` ends
      up living) — covers RUN-04's supporting behavior: env-set case, env-unset fallback case, and a
      `caplog`-based assertion that the run-start log line contains both resolved absolute path
      strings.
- [ ] No new fixtures needed — `tmp_path`/`monkeypatch` (both pytest built-ins) are sufficient; no
      network, no external files.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | This phase has no authentication surface — single-operator, no users. |
| V3 Session Management | No | No sessions in this phase. |
| V4 Access Control | Partially | OS-level: dedicated non-root `creatorpulse` user (D-02), least-privilege `EnvironmentFile=` parsing as root-before-drop (D-04) — both human-built, not application code, but this is the phase's actual access-control story. |
| V5 Input Validation | Yes | `os.environ.get()` values are attacker-uncontrolled in this project's threat model (single operator sets their own unit file) — but `resolve_paths()` should still not blindly trust an env var to be a *safe* path; `Path(...).resolve()` normalizes without executing anything, which is sufficient here (no shell interpolation, no `eval`, no subprocess call built from the value). |
| V6 Cryptography | No | No cryptographic operations in this phase's code. Secret *storage* (mode `600`, root ownership) is a filesystem-permission control, not a cryptographic one. |

### Known Threat Patterns for this phase's stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Secret committed to git before `.gitignore`/before rotation discipline exists | Information Disclosure | Already covered by PITFALLS.md #16 and D-04's design (secrets never enter the repo's working tree at all — `/etc`, not repo-root `.env`); `.env.example` (D-14) ships names only, never values. `git log -S` check in `02-UAT.md` (D-15) is the verification. |
| A malicious/mistaken `CREATORPULSE_DB` value pointing outside the intended directory | Tampering (low severity here) | Single-operator threat model — the unit's `Environment=` lines are human-authored, not attacker-controlled input. `resolve_paths()` normalizing via `Path.resolve()` and logging the result (D-08) is sufficient: any wrong path is immediately visible in `journalctl`, which is the actual mitigation given this isn't a multi-tenant or externally-reachable system. |
| Running the collector as root | Elevation of Privilege | Mitigated by D-02's dedicated non-root `creatorpulse` user — human-built, not application code, but the application must not assume/require root (it doesn't; nothing in `resolve_paths()` or `run_collect()` needs elevated privilege). |

## Sources

### Primary (HIGH confidence)
- This project's own `.planning/research/PITFALLS.md` §Pitfall 1, §Pitfall 2, §Pitfall 7, §Pitfall 10,
  §Pitfall 12 — already-verified, project-specific research; treated as primary per the efficiency
  directive rather than re-derived.
- This project's own `.planning/research/STACK.md` — locked pins, no-new-dependency rationale,
  already verified against PyPI JSON API in a prior session.
- `src/creatorpulse/config.py`, `src/creatorpulse/cli.py` — read directly this session; existing
  patterns this phase extends.

### Secondary (MEDIUM confidence)
- `systemd.exec(5)` — `EnvironmentFile=` dash-prefix/quoting/comment-line rules, cross-checked via
  search against `freedesktop.org/software/systemd/man/latest/systemd.exec.html` and Ubuntu manpages
  mirror.
- `systemd.timer(5)` / ArchWiki "systemd/Timers" — `Persistent=true` single-catch-up-fire semantics,
  `/var/lib/systemd/timers/` storage location, `OnCalendar=`-only applicability.
- `systemctl list-timers` column set (`NEXT`/`LEFT`/`LAST`/`PASSED`/`UNIT`/`ACTIVATES`) — cross-checked
  across ArchWiki, linuxcommandlibrary.com, and SUSE documentation; not fetched from a single
  canonical source this session, hence MEDIUM not HIGH.

### Tertiary (LOW confidence)
- Journald rate-limiting default thresholds and DigitalOcean base-image `tzdata` presence (Assumptions
  A1/A2) — general systemd/journald knowledge, not verified against this project's specific target
  environment this session, since no droplet exists yet to check against.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib-only, directly verified against existing repo code (`config.py`,
  `cli.py`) rather than external claims.
- Architecture: HIGH — the responsibility split (OS/systemd vs. application) is dictated by D-01
  through D-08's already-locked decisions, not a new judgment call.
- Systemd behavior (EnvironmentFile parsing, Persistent= semantics, list-timers output shape): MEDIUM
  — cross-checked across multiple secondary sources this session, not a single directly-fetched
  canonical man page.
- Pitfalls: HIGH for the five already-catalogued in PITFALLS.md (1, 2, 7, 10, 12); MEDIUM for the two
  new ones surfaced this session (EnvironmentFile quoting traps, Persistent= single-catch-up
  clarification).

**Research date:** 2026-07-31
**Valid until:** systemd directive semantics are stable long-term (30+ days, effectively version-
independent for this project's scope); the two MEDIUM-confidence CLI-output-shape claims should be
re-verified live against the actual droplet's systemd version during D-15's UAT pass rather than
trusted blind from this document.

---
*Phase: 2-VPS & systemd*
*Research completed: 2026-07-31*
