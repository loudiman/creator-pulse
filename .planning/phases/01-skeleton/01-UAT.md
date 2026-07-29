---
status: testing
phase: 01-skeleton
source: [01-VERIFICATION.md]
started: 2026-07-30T02:30:00Z
updated: 2026-07-30T02:30:00Z
---

## Current Test

number: 1
name: Fresh-clone install-and-gate walkthrough
expected: |
  All four gate commands exit 0 with no correction to the README needed;
  `creatorpulse collect` prints the four expected log lines; `git status` is clean.
awaiting: user response

## Tests

### 1. Fresh-clone install-and-gate walkthrough

expected: All four gate commands exit 0 with no correction to the README needed; `creatorpulse collect` prints the four expected log lines; `git status` is clean.

Steps (from 01-03-PLAN.md Task 2 `<human-check>`):

1. Clone the repository into a new directory, or run `git clean -xdn` and confirm nothing listed is source.
2. Create a venv with the 3.12 interpreter and activate it, following only what the README says.
3. Run `pip install -e ".[dev]"` exactly as the README gives it.
4. Paste the README's four-command block verbatim. All four exit 0.
5. Run `creatorpulse collect`. Read the four log lines aloud — run start, creators loaded, not implemented, run end with a duration. This is the exact output shape Phase 2 will grade in `journalctl -u`, so confirm it reads well spoken, not just parsed.
6. Run `git status`. It is clean.

Confirm the README needed no correction to get through steps 2 through 4. If it did, the README is the bug.

why_human: Every automated check in 01-VERIFICATION.md ran against the existing development tree, which already has a populated `.venv`, `.mypy_cache`, `.ruff_cache`, and `.pytest_cache`. That proves the gate is green today and that the README's commands are textually correct — it does not prove the install step works from zero on an unpopulated clone, which is the literal wording of Success Criterion 1.

result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
