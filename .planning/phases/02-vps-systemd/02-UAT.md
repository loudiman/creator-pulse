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

result: pending

evidence: |

### 3. The service reads secrets from a `chmod 600` env file via `EnvironmentFile`, and those values are absent from the repo and from `git log`

expected: The env file is owned `root:root` mode `600`, the unit references it as its environment-file source, and a history search for any secret value returns nothing.

why_human: Requires reading actual file permissions and git history on the real deployment; the file's contents must never be pasted, only its permissions and the unit's reference to it.

Commands whose output belongs in the evidence block:
- `stat -c '%a %U:%G' /etc/creatorpulse/creatorpulse.env`
- `systemctl cat creatorpulse.service`
- `git log --all -S '<secret-value>'` (search proving no secret value reached history)

result: pending

evidence: |

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

## Summary

total: 5
passed: 0
pending: 5

## Gaps
