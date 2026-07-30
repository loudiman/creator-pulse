# Phase 2: VPS & systemd - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-31
**Phase:** 2-VPS & systemd
**Areas discussed:** Box layout & secrets placement, Path resolution under systemd, Timer schedule semantics, Repo artifacts & proof of done

---

## Box layout & secrets placement

### Q1 — Where does the code live on the droplet, and under which user?

| Option | Description | Selected |
|--------|-------------|----------|
| `/home/creatorpulse/creator-pulse` | Dedicated non-root user, repo in its own home, venv inside. No chown, no root-owned paths, and `$HOME` is a real writable dir where Playwright drops its Chromium cache in Phase 4 | ✓ |
| `/opt/creatorpulse` | FHS-conventional, the path PITFALLS.md uses. Costs a chown and forces `Environment=HOME=` since /opt is not a home directory | |
| Own login user's home | Fewest steps, but the service would run as an account with sudo and criterion 5 has nothing to say about least privilege | |

**User's choice:** `/home/creatorpulse/creator-pulse`
**Notes:** Unit still sets `Environment=HOME=` explicitly rather than trusting systemd's default — PITFALLS.md #1 records HOME as not guaranteed.

### Q2 — How does code get onto the box, and how do Phase 3–7 updates reach it?

| Option | Description | Selected |
|--------|-------------|----------|
| git clone + pull | Clone the public repo as the service user; updates are `git pull && pip install -e .`. Box state is a printable commit SHA | ✓ |
| rsync from Windows | No git on the server, works with uncommitted state — which is the problem: nothing identifies the running version | |
| git clone, deploy from tags | Box tracks tags, demo runs from a frozen commit. More ceremony than a 7-day solo build repays | |

**User's choice:** git clone + pull
**Notes:** Repo is public (`github.com/loudiman/creator-pulse`), so no deploy key needed.

### Q3 — Where does the secrets file live, and who owns it?

| Option | Description | Selected |
|--------|-------------|----------|
| `/etc/creatorpulse/creatorpulse.env`, root:root 600 | Outside the working tree. systemd parses EnvironmentFile as PID 1 before dropping to `User=`, so the service user never needs read access. Safe from `git clean -xfd` | ✓ |
| `/home/creatorpulse/.env`, creatorpulse:creatorpulse 600 | Outside the repo, one less directory. Service user can read its own secrets — weaker for no gain | |
| Repo root `.env`, 600 | Same path as local dev, already gitignored. `git clean -xfd` deletes it; `git add -f` commits it, and recovery from that is key rotation | |

**User's choice:** `/etc/creatorpulse/creatorpulse.env`, root:root 600
**Notes:** Satisfies OPS-01's literal `chmod 600` wording.

### Q4 — Where does the SQLite file live, and does the Phase 6 bot share this user?

| Option | Description | Selected |
|--------|-------------|----------|
| `/var/lib/creatorpulse/`, same user for both | Survives `git clean -xfd` and re-clone — history is the one thing that cannot be regenerated. Bot in its own unit, same user; WAL + busy_timeout is the real coordination | ✓ |
| Repo root, same user for both | One directory holds everything, already gitignored. A `git clean -xfd` during a messy deploy silently deletes all collected history | |
| `/var/lib/creatorpulse/`, separate bot user | Reader-only enforced at the filesystem layer. One more account and group to get the permission bits right on | |

**User's choice:** `/var/lib/creatorpulse/`, same user for both

---

## Path resolution under systemd

Framing: `config.py:9` uses a relative `Path("creators.yaml")` and systemd's cwd defaults to `/`. The previous area placed the DB at `/var/lib/creatorpulse`, outside the repo, which `WorkingDirectory=` cannot express — so this question was forced by the layout answer.

### Q1 — How does the app learn where creators.yaml and the SQLite file are?

| Option | Description | Selected |
|--------|-------------|----------|
| Env vars | `CREATORPULSE_CONFIG` / `CREATORPULSE_DB` from `os.environ`. No new mechanism (EnvironmentFile already present), no new unit directive, and the unit never changes again | ✓ |
| CLI flags in ExecStart | Fully visible in `systemctl cat`. But `--db` does not exist yet, so the human-typed unit would encode a flag Phase 3 must implement | |
| WorkingDirectory only | Zero code change, what PITFALLS.md #1 prescribes. Cannot express `/var/lib/creatorpulse` — taking it reopens the DB placement | |

**User's choice:** Env vars

### Q2 — Where are those path env vars set?

| Option | Description | Selected |
|--------|-------------|----------|
| `Environment=` lines in the unit | Non-secret config visible in `systemctl cat`; the 600 file holds only secrets. Cost: path change means unit edit plus daemon-reload | ✓ |
| In the EnvironmentFile | One place for everything, no unit edit ever again. But `systemctl cat` no longer says which database the service writes to | |
| Split by whether it changes | Paths in the unit, a second non-secret EnvironmentFile for tunables. Two files for a service with ~4 settings | |

**User's choice:** `Environment=` lines in the unit

### Q3 — What happens when a path env var is unset?

| Option | Description | Selected |
|--------|-------------|----------|
| Fall back, log resolved paths | Repo-relative fallback so Windows dev needs no setup; every run logs resolved absolutes, so a mis-typed unit shows up in the first journalctl line | ✓ |
| Hard-fail if unset | Cannot write to the wrong place, but Windows dev needs both vars exported every session | |
| Fall back silently | Smallest change. Failure mode: SQLite creates an empty DB inside the repo, run reports success, discovered when deltas are blank | |

**User's choice:** Fall back, log resolved paths

### Q4 — Where does the agent-owned path-resolution code get written, given Phase 2's owner is `human`?

| Option | Description | Selected |
|--------|-------------|----------|
| Agent plan inside Phase 2, owner becomes `mixed` | Human writes the unit against code that genuinely reads the vars, so criterion 2 tests something real. Units/timer/UFW/SSH stay human-only | ✓ |
| Defer the code to Phase 3 | Phase 2 stays purely human, ownership table untouched — but a day's deliverable rests on paths never once resolved | |
| `/gsd-quick` before Phase 2 | Same code, same day, no ownership edit — at the cost of Phase 2 work living outside its phase record | |

**User's choice:** Agent plan inside Phase 2, owner becomes `mixed`
**Notes:** Requires editing `**Owner:** human` → `mixed` in ROADMAP.md §"Phase 2". Same shape Phase 6 already has.

---

## Timer schedule semantics

### Q1 — Which clock does the timer run on?

| Option | Description | Selected |
|--------|-------------|----------|
| `TimeZone=Asia/Manila` | "Runs every morning" is literally true; metric_date stays UTC and the split is documented. PITFALLS.md #12's prescription | ✓ |
| UTC everywhere | One clock, nothing to reconcile. Any morning-in-Manila time becomes a UTC expression to convert on every read | |
| UTC expression, Manila-morning effect | 23:00 UTC = 07:00 PHT. Same result, but a unit saying 23:00 for a job described as morning | |

**User's choice:** `TimeZone=Asia/Manila`

### Q2 — What fire time, and is there a RandomizedDelaySec?

| Option | Description | Selected |
|--------|-------------|----------|
| 07:00 Manila, no jitter | Exact `NEXT` you can point at during a demo. PITFALLS.md #2 suggests jitter, but its rationale is rate-limit collision — ~10 calls/day against a 10,000-unit quota from one box | ✓ (fire time superseded by Q3) |
| 07:00 Manila, RandomizedDelaySec=300 | Follows the pitfall guidance as written. `NEXT` becomes a 5-minute range, blurring the live demo moment | |
| 06:00 Manila, no jitter | Extra hour of slack, but earlier than you are likely awake to watch a real unattended fire | |

**User's choice:** no jitter (fire time revised to 08:00 in Q3)

### Q3 — How should the fire time and the UTC metric_date line up?

Raised mid-area: 07:00 PHT is 23:00 UTC the previous day, so every run would stamp yesterday's UTC date. Harmless to deltas, visible in the Sheet.

| Option | Description | Selected |
|--------|-------------|----------|
| Move to 08:00 Manila | 08:00 PHT is exactly 00:00 UTC, so metric_date always equals the Manila calendar date. Removes the caveat rather than documenting it. Costs one hour | ✓ |
| Keep 07:00, label everything UTC | Numbers land an hour earlier; the off-by-one is labelled in the Sheet, digest, /status and README. A caveat carried into every demo | |
| Keep 07:00, stamp metric_date locally | Dates match what you see — contradicts the settled UTC rule and reintroduces the naive/aware mixing PITFALLS.md #12 exists to prevent. Recorded as considered and rejected | |

**User's choice:** Move to 08:00 Manila

### Q4 — How do you prove Persistent=true catch-up without waiting a day?

| Option | Description | Selected |
|--------|-------------|----------|
| Deliberate reboot across a fire time | Shift OnCalendar minutes out, power off before it fires, boot after the window, confirm one catch-up run, restore 08:00. ~10 min, and the only option that exercises the missed-window path | ✓ |
| Watch a near-term fire, reason about catch-up | Proves firing and re-enablement, never the missed-window path criterion 4 names | |
| systemd-analyze plus documentation | Fast; leaves criterion 4 resting on an explanation rather than an observation | |

**User's choice:** Deliberate reboot across a fire time

---

## Repo artifacts & proof of done

### Q1 — Do the hand-typed unit and timer files get committed?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, under `deploy/` | Survives droplet destruction, diffable when Phase 6 adds a second unit, README has something to point at. No secrets by construction | ✓ |
| Box only, described in prose | Zero risk of an agent touching them; rebuilding means retyping from memory and no reviewer sees the deliverable | |
| Committed as redacted templates | Standard when units carry secrets — these do not, so redaction removes the reviewable details | |

**User's choice:** Yes, under `deploy/`
**Notes:** CONTEXT.md records the binding constraint — agents may read these files and must never write, edit, generate, or reformat them.

### Q2 — Is there a provisioning runbook, and who writes it?

| Option | Description | Selected |
|--------|-------------|----------|
| Author writes `docs/deploy.md` while provisioning | Writing it during the work is how criterion 5 gets satisfied — the doc is the rehearsal. Agent does not draft, outline, or fill gaps | ✓ |
| journal.md entry only | Feeds OPS-09 directly, less to maintain. Rebuild means reading a narrative, and the interview answer has no artifact behind it | |
| Agent drafts headings, author fills lines | Faster to start — but the ordering of provisioning steps is exactly the knowledge the ownership rule protects | |

**User's choice:** Author writes `docs/deploy.md` as you go

### Q3 — What goes in `.env.example` and the real env file now?

| Option | Description | Selected |
|--------|-------------|----------|
| All v1 var names now, values empty | `.gitignore` already carries the `!.env.example` negation. EnvironmentFile is wired and proven in Phase 2 rather than first exercised in Phase 3 | ✓ |
| Only what each phase needs | Nothing speculative — but the file's shape is unknown at Phase 2 and each later phase reopens a root-owned file | |
| No `.env.example`, document in deploy.md | One less file to drift; one more thing a stranger has to read prose to discover | |

**User's choice:** All v1 var names now, values empty

### Q4 — Phase 2 has no automated tests. What evidence closes it?

| Option | Description | Selected |
|--------|-------------|----------|
| `02-UAT.md` with pasted command output | One paste per success criterion: systemd-analyze calendar, list-timers, systemctl start status, journalctl, stat on the env file, `git log -S`, catch-up reboot journal. Matches the existing `01-UAT.md` pattern | ✓ |
| Narrative journal.md entry | Feeds OPS-09 — but criterion 3 becomes a claim rather than a pasted `git log -S` result | |
| Screenshots of the terminal | Visual proof, easy to capture. Not greppable, not diffable, cannot be re-checked six days later | |

**User's choice:** `02-UAT.md` with pasted command output

---

## Claude's Discretion

- Whether path resolution lives in `config.py` or a new small `paths.py`.
- Log level and wording of the resolved-paths line (INFO expected).
- Section ordering in `02-UAT.md`; comment style in `.env.example`.
- Whether the repo-relative DB fallback is at the repo root or a gitignored subdirectory.

## Open, not decided (human-owned, closed during provisioning)

- Swap file size (1–2 GB plausible on a 2 GB droplet).
- UFW rule set and SSH hardening specifics.
- Venv location — inside the repo at `.venv` (assumed) or beside it.
- Exact `Environment=HOME=` value and where Playwright's browser cache lands.

## Deferred Ideas

- Actual secret values — names in Phase 2, values arrive with Phases 3, 4, 6.
- RUN-03's full closure — timer targets Phase 1's placeholder; closes in Phase 3.
- `journalctl` priority mapping — V2-OPS-01, needs `systemd-python`; deferred once already in Phase 1.
- A README deployment section — belongs with OPS-08 in Phase 7.
- Getting a unit edited on the box back into `deploy/` — no mechanism decided; not a problem at two files.
