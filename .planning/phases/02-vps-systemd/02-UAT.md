---
status: in-progress
phase: 02-vps-systemd
source: [02-CONTEXT.md]
started: 2026-07-31T00:00:00Z
updated: 2026-07-31T00:00:00Z
---

## Current Test

[not started]

## Tests

### 1. A systemd timer fires on schedule with no human present, and the author sees its output afterwards via `journalctl -u <unit>`

expected: `systemctl list-timers creatorpulse.timer` shows the unit with a `NEXT`/`LAST` fire time, and `journalctl -u creatorpulse.service` shows the run's output after an unattended fire.

why_human: Only the author has shell access to the provisioned droplet; no automated check can observe a real unattended timer fire.

Commands whose output belongs in the evidence block:
- `systemctl list-timers creatorpulse.timer`
- `journalctl -u creatorpulse.service`

result: pending

evidence: |

### 2. `systemctl start <unit>` succeeds against the same code path that works interactively — proving the stripped systemd environment (PATH, HOME, cwd) has been handled, not dodged

expected: `systemctl start creatorpulse.service` exits successfully, and `journalctl -u creatorpulse.service` shows the four-line run shape from Phase 1 (D-03) with both resolved absolute paths (config and database) present in the run-start line. The stripped-environment reproduction shows the same behavior outside systemd.

why_human: Requires a real systemd unit running under `systemctl` on the droplet; cannot be simulated on the dev box.

Commands whose output belongs in the evidence block:
- `systemctl start creatorpulse.service` (with its exit status)
- `journalctl -u creatorpulse.service`
- `systemd-run --uid=creatorpulse --gid=creatorpulse env -i /home/creatorpulse/creator-pulse/.venv/bin/creatorpulse collect`

result: pass

evidence: |
  source: author-pasted, droplet (DigitalOcean s-1vcpu-1gb, Ubuntu 24.04.4 LTS, Python 3.12.3, 961 MiB RAM, 2 GB swap)

  `systemctl start creatorpulse.service` with exit status:
  ```
  (.venv) creatorpulse@creatorpulse-vps:~/creator-pulse$ sudo systemctl start creatorpulse.service; echo "exit status: $?"
  exit status: 0
  ```

  `journalctl -u creatorpulse.service -n 20 --no-pager`:
  ```
  Aug 02 16:33:13 creatorpulse-vps creatorpulse[11545]: 2026-08-02 16:33:13,359 INFO creatorpulse: Starting collect run using config /home/creatorpulse/creator-pulse/creators.yaml, database /var/lib/creatorpulse/creatorpulse.db
  Aug 02 16:33:13 creatorpulse-vps creatorpulse[11545]: 2026-08-02 16:33:13,363 INFO creatorpulse: Loaded 3 creators
  Aug 02 16:33:13 creatorpulse-vps creatorpulse[11545]: 2026-08-02 16:33:13,363 WARNING creatorpulse: Collector body is not implemented yet; Phase 3 fills it in
  Aug 02 16:33:13 creatorpulse-vps creatorpulse[11545]: 2026-08-02 16:33:13,363 INFO creatorpulse: Run complete in 0.00 seconds
  ```
  No "messages suppressed" rate-limiter note present in this or either baseline capture below.

  Interactive baseline, same box, env vars matching what the unit injects (comparison for this criterion):
  ```
  (.venv) creatorpulse@creatorpulse-vps:~/creator-pulse$ CREATORPULSE_CONFIG=/home/creatorpulse/creator-pulse/creators.yaml \
  CREATORPULSE_DB=/var/lib/creatorpulse/creatorpulse.db \
  creatorpulse collect
  2026-08-02 16:25:55,334 INFO creatorpulse: Starting collect run using config /home/creatorpulse/creator-pulse/creators.yaml, database /var/lib/creatorpulse/creatorpulse.db
  2026-08-02 16:25:55,338 INFO creatorpulse: Loaded 3 creators
  2026-08-02 16:25:55,339 WARNING creatorpulse: Collector body is not implemented yet; Phase 3 fills it in
  2026-08-02 16:25:55,339 INFO creatorpulse: Run complete in 0.01 seconds
  ```
  Interactive baseline with NO env vars set (shows the D-08 repo-relative fallback):
  ```
  2026-08-02 16:23:36,109 INFO creatorpulse: Starting collect run using config /home/creatorpulse/creator-pulse/creators.yaml, database /home/creatorpulse/creator-pulse/creatorpulse.db
  2026-08-02 16:23:36,115 INFO creatorpulse: Loaded 3 creators
  2026-08-02 16:23:36,115 WARNING creatorpulse: Collector body is not implemented yet; Phase 3 fills it in
  2026-08-02 16:23:36,115 INFO creatorpulse: Run complete in 0.01 seconds
  ```
  Stripped-environment reproduction, `systemd-run --uid=creatorpulse --gid=creatorpulse env -i ...`:
  ```
  (.venv) creatorpulse@creatorpulse-vps:~/creator-pulse$ sudo systemd-run --uid=creatorpulse --gid=creatorpulse env -i \
    /home/creatorpulse/creator-pulse/.venv/bin/creatorpulse collect
  Running as unit: run-r142dd6c878b84ac5ad568c2b8ad683fd.service; invocation ID: c6ca634686aa4833b67cf8e90e7af66a

  (.venv) creatorpulse@creatorpulse-vps:~/creator-pulse$ journalctl -u run-r142dd6c878b84ac5ad568c2b8ad683fd.service -n 20 --no-pager
  Aug 02 16:37:23 creatorpulse-vps env[11620]: 2026-08-02 16:37:23,668 INFO creatorpulse: Starting collect run using config /creators.yaml, database /creatorpulse.db
  Aug 02 16:37:23 creatorpulse-vps env[11620]: 2026-08-02 16:37:23,668 ERROR creatorpulse: Config file not found: /creators.yaml
  ```

  FINDING (recorded, not smoothed over): this reproduction did not fail because of the stripped
  environment as such — it failed because `env -i` also stripped the two `Environment=` lines the real
  unit supplies, so `resolve_paths()` fell back to `DEFAULT_CONFIG_PATH`/`DEFAULT_DB_PATH`, resolved
  against `systemd-run`'s default working directory of `/` (not `/home/creatorpulse/creator-pulse`).
  Paths landed at filesystem root: `/creators.yaml`, `/creatorpulse.db`. This is a property of D-08's
  `resolve_paths()` being cwd-relative rather than repo-relative when both env vars are absent — it
  only *looks* repo-relative in the two baselines above because those were run with cwd already at the
  repo. Production is unaffected: the real unit supplies both `WorkingDirectory=` and both
  `Environment=` path lines, two independent mechanisms, neither of which this `env -i` test exercised.
  Scope correction: this test did not validate "the unit runs without a login shell" (systemd already
  provides none, and `systemctl start` above is the actual proof of that) — it validated only that the
  bare binary with a fully empty environment fails loudly and legibly (clean traceback-free error,
  correct-but-wrong path logged, no silent write to the wrong location), which it did.

### 3. The service reads secrets from a `chmod 600` env file via `EnvironmentFile`, and those values are absent from the repo and from `git log`

expected: The env file is owned `root:root` mode `600`, the unit references it as its environment-file source, and a history search for any secret value returns nothing.

why_human: Requires reading actual file permissions and git history on the real deployment; the file's contents must never be pasted, only its permissions and the unit's reference to it.

Commands whose output belongs in the evidence block:
- `stat -c '%a %U:%G' /etc/creatorpulse/creatorpulse.env`
- `systemctl cat creatorpulse.service`
- `git log --all -S '<secret-value>'` (search proving no secret value reached history)

result: pass

evidence: |
  source: author-pasted, droplet

  `stat -c '%a %U:%G' /etc/creatorpulse/creatorpulse.env`:
  ```
  (.venv) creatorpulse@creatorpulse-vps:~/creator-pulse$ sudo stat -c '%a %U:%G' /etc/creatorpulse/creatorpulse.env
  600 root:root
  ```

  `systemctl cat creatorpulse.service`:
  ```
  # /etc/systemd/system/creatorpulse.service
  [Unit]
  Description=CreatorPulse Collector Service
  After=network.target

  [Service]
  Type=oneshot
  User=creatorpulse
  WorkingDirectory=/home/creatorpulse/creator-pulse
  EnvironmentFile=/etc/creatorpulse/creatorpulse.env
  Environment="HOME=/home/creatorpulse"
  Environment="CREATORPULSE_CONFIG=/home/creatorpulse/creator-pulse/creators.yaml"
  Environment="CREATORPULSE_DB=/var/lib/creatorpulse/creatorpulse.db"
  ExecStart=/home/creatorpulse/creator-pulse/.venv/bin/creatorpulse collect

  [Install]
  WantedBy=multi-user.target
  ```
  No secret value present in the unit file — `EnvironmentFile=` (no `-` prefix, so a missing/mistyped
  path fails the unit loudly per RESEARCH.md Pitfall B) plus the two `Environment=` path lines only.

  ---
  source: agent-executed, repo-side git-history proof (Task 3, run from dev box against full history)
  <!-- populated by Task 3 -->

### 4. The timer survives a reboot and, with `Persistent=true`, catches up a missed run

expected: `systemd-analyze calendar` confirms the schedule, and a reboot across a shifted fire window produces exactly one catch-up run in the journal.

why_human: Requires physically rebooting the droplet during a deliberately shifted fire window and reading the journal afterwards — not reproducible from the dev box.

Commands whose output belongs in the evidence block:
- `systemd-analyze calendar 'Mon..Sun *-*-* 08:00:00'`
- `systemd-analyze calendar 'Mon..Sun *-*-* 08:00:00 Asia/Manila'`
- `journalctl -u creatorpulse.service` (from the shifted-window reboot, showing exactly one catch-up run)

result: pending

evidence: |

### 5. The author can explain out loud, without notes, why systemd timer beats cron here

expected: A written answer in the author's own words, no command output.

why_human: This is a spoken-explanation criterion by definition; no automated check applies.

result: pending

evidence: |

## Decisions

### Task 1: Database location confirmed (02-02-PLAN.md)

Decision: `confirm-var-lib`. D-05 stands as written — `/var/lib/creatorpulse/creatorpulse.db`, owned
by the service user, outside the repository. No change. Recorded here because this was the last free
moment to move it (see 02-02-PLAN.md Task 1, 02-CONTEXT.md D-05).

### Task 2: Author provisioned the droplet, entries 2 and 3 pasted (02-02-PLAN.md)

Deviation: D-03 states the repo is public so no deploy key is needed. At provisioning time the repo
was in fact private — `git clone` prompted for credentials and returned an empty repository, because
41 local commits had never been pushed. The author pushed `main` (now at `1bcdc6b`) and made the repo
public, restoring D-03's stated assumption. No doc change needed; recorded as a deviation encountered
and resolved during Task 2.

## Summary

total: 5
passed: 2
pending: 3

## Gaps
