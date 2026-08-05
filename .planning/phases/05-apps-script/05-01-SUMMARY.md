---
phase: 05-apps-script
plan: 01
subsystem: infra
tags: [google-apps-script, discord-webhook, installable-trigger, sheets]

requires:
  - phase: 04-playwright-sheets
    provides: "the frozen Dashboard column layout (A-F Python-owned, G human-owned) and the live Sheet the script binds to"
provides:
  - "apps-script/Code.gs and apps-script/appsscript.json — the CreatorPulse menu, the delete-then-recreate trigger installer, the installable onStatusEdit -> Discord webhook path, and the column-F timestamp probe"
  - "the empirical answer to whether column F is a string or a Date under USER_ENTERED, unblocking 05-02's staleness arithmetic"
affects: [05-02-time-driven-watchdog-and-formatting, 05-03-coverage-and-uat]

tech-stack:
  added: []
  patterns:
    - "Installable onEdit trigger bound to a non-onEdit-named function, created only via a menu item that deletes every ScriptApp.getProjectTriggers() entry before creating"
    - "Script Properties for secrets (PropertiesService.getScriptProperties()), throw-on-missing naming the property key and the fix path — never a silent no-op"
    - "Webhook payload built with JSON.stringify (never string concatenation) plus allowed_mentions: {parse: []} to suppress @everyone/@here from untrusted free-text input"

key-files:
  created:
    - apps-script/Code.gs
    - apps-script/appsscript.json
  modified:
    - .planning/phases/04-playwright-sheets/04-PATTERNS.md
    - .planning/phases/04-playwright-sheets/04-REVIEW.md
    - .planning/phases/05-apps-script/05-PATTERNS.md

key-decisions:
  - "Column F lands as a string (not a Date) under USER_ENTERED, and new Date(raw) parses it without NaN — confirmed live via _diagnoseTimestampType() on 2026-08-06. 05-02's checkFreshness() parses the string path; the isNaN guard stays as a backstop for blank/malformed cells, not the hot path."
  - "ruff format . reformats three pre-existing, untouched .planning docs (embedded Python code blocks drifted out of format from a prior session's ruff-0.15-on-PATH run) to restore the green gate, matching the precedent already recorded in STATE.md rather than carving a scope exclusion."

patterns-established:
  - "Any future Apps Script secret follows getWebhookUrl()'s shape: PropertiesService.getScriptProperties().getProperty(KEY), falsy check, throw new Error naming the key and the Project Settings path."

requirements-completed: [SCRIPT-01, SCRIPT-03]

coverage:
  - id: D1
    description: "Opening the Sheet shows a CreatorPulse top-level menu, built without reading any Sheet data, present exactly once after reload"
    requirement: "SCRIPT-01"
    verification:
      - kind: manual_procedural
        ref: "Task 2 step 7 — human reloaded the live Sheet and observed exactly one CreatorPulse menu with one item"
        status: pass
    human_judgment: true
    rationale: "Menu presence/uniqueness is a UI observation; no .gs test framework exists in this stack and adding one would violate the no-new-dependencies rule (05-RESEARCH.md Validation Architecture)."
  - id: D2
    description: "Editing Dashboard!G2:G through the Sheets UI posts to Discord within seconds naming creator/source and both Status values via an installable (not simple) onEdit trigger; clearing posts (cleared); edits outside the guarded range post nothing"
    requirement: "SCRIPT-03"
    verification:
      - kind: manual_procedural
        ref: "Task 2 steps 8-10 — human clicked Install triggers twice (removed 0/created 1, then removed 1/created 1), edited G3 four times observing four verbatim Discord messages, and confirmed three negative-case edits (D3, G1, another tab) produced no message with completed (not errored) Executions runs"
        status: pass
    human_judgment: true
    rationale: "ROADMAP criterion 2 explicitly requires the post be 'observed live, not inferred from logs' — SCRIPT-03 has no mechanical proof possible in this stack (05-01-PLAN.md Flagged Assumptions)."
  - id: D3
    description: "The column F timestamp type is answered empirically via _diagnoseTimestampType() before 05-02 writes staleness arithmetic on top of a guess"
    verification:
      - kind: manual_procedural
        ref: "Task 2 steps 5-6 — human ran _diagnoseTimestampType() from the editor and recorded typeof=string, instanceof Date=false, raw=2026-08-05T18:58:07.869575+00:00, NaN=false"
        status: pass
    human_judgment: true
    rationale: "Apps Script execution-log output; no automated harness reads it, and 05-02 consumes the answer as a design input rather than a pass/fail gate."

duration: ~40min active work (excludes human verification wait time between checkpoint and approval)
completed: 2026-08-06
status: complete
---

# Phase 5 Plan 1: Apps Script Tracer Summary

**Installable onEdit trigger posts Status-column changes to Discord via UrlFetchApp + Script Properties, with a delete-then-recreate duplicate guard and a live-confirmed column-F timestamp type for 05-02**

## Performance

- **Duration:** ~40min active work (excludes the human verification wait between the Task 2 checkpoint and approval)
- **Completed:** 2026-08-06
- **Tasks:** 2 (1 tracer + 1 checkpoint:human-verify)
- **Files modified:** 5 (2 created, 3 reformatted)

## Accomplishments

- `apps-script/Code.gs` (158 lines) and `apps-script/appsscript.json` written and committed: `onOpen` (simple trigger, one-item menu), `installTriggers` (delete-then-recreate duplicate guard), `onStatusEdit` (installable trigger target, correctly not named after the simple-trigger event), `getWebhookUrl` (Script Properties, throws naming the key and fix path), `postToDiscord` (`JSON.stringify` + `allowed_mentions`), `_diagnoseTimestampType` (the Wave 0 probe).
- Live round trip proven end to end in the real Sheet and the real Discord channel: a human edit to `Dashboard!G3` produces a Discord message within seconds naming the row's creator and source and both Status values (SCRIPT-03, ROADMAP criterion 2, ADR D-14/D-15).
- The duplicate-guard is observably correct, not just structurally correct: a second click of *Install triggers* reported "removed 1, created 1" against the first click's "removed 0, created 1" — proof that two clicks leave exactly one trigger, not two.
- The column F timestamp question (RESEARCH.md Pitfall 4, the phase's one genuine empirical unknown) is answered and recorded: a string, not a `Date`, and `new Date(raw)` parses it cleanly — 05-02 can build `checkFreshness()` on an observation instead of a guess.

## Task Commits

1. **Task 1: The manifest and the Status-edit-to-Discord path, end to end** - `05ba0ca` (feat)

**Plan metadata:** committed alongside this SUMMARY.

_Task 2 was `checkpoint:human-verify` (gate: blocking) — no code change, verification only; results recorded below._

## Files Created/Modified

- `apps-script/Code.gs` - onOpen, installTriggers, onStatusEdit, getWebhookUrl, postToDiscord, _diagnoseTimestampType
- `apps-script/appsscript.json` - manifest: Asia/Manila timezone, V8 runtime, STACKDRIVER exception logging
- `.planning/phases/04-playwright-sheets/04-PATTERNS.md`, `04-REVIEW.md`, `.planning/phases/05-apps-script/05-PATTERNS.md` - `ruff format .` reformatting only, pre-existing drift unrelated to this plan's content (see Deviations)

## Decisions Made

- Column F is a string under `USER_ENTERED`, not a `Date`; `new Date(raw)` parses the `+00:00`-suffixed ISO-8601 string without producing `NaN`. 05-02's staleness arithmetic parses the string path; the `isNaN` guard remains a backstop for blank/malformed cells only.
- `DISCORD_WEBHOOK_URL` referenced by name exactly once in the source (the `WEBHOOK_PROPERTY` constant); every other read goes through that constant, keeping the secret's key-name single-sourced the same way the URL value itself is never in the tree.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug/Gate] Fixed pre-existing ruff-format drift blocking the green gate**
- **Found during:** Task 1, running the required four-command gate proof after `apps-script/` existed
- **Issue:** `ruff format --check .` failed on 3 files under `.planning/` (`04-PATTERNS.md`, `04-REVIEW.md`, `05-PATTERNS.md`) — embedded Python code blocks left unformatted by a prior session that ran ruff 0.15 from PATH instead of the locked 0.16 venv (this exact trap is already recorded in STATE.md/PROJECT.md). Confirmed via diff against `HEAD` that these files were untouched by this plan before the fix.
- **Fix:** Ran `ruff format .` (a real reformat, not a scope exclusion) — the same remedy STATE.md already records having used once before on `ARCHITECTURE.md`.
- **Files modified:** the 3 files listed above (formatting only, no content change)
- **Verification:** All four gate commands (`ruff format --check .`, `ruff check .`, `mypy src/`, `pytest`) now exit 0 with `apps-script/` present.
- **Committed in:** `05ba0ca` (part of Task 1's commit)

---

**Total deviations:** 1 auto-fixed (1 gate-blocking, out-of-scope-file formatting)
**Impact on plan:** Necessary to satisfy the plan's own must-have truth that all four gate commands exit 0 with `apps-script/` present. No Python logic, test, or `pyproject.toml` change; `git diff --name-only HEAD -- src/ tests/ pyproject.toml` returns 0 lines.

## Issues Encountered

None beyond the deviation above. All 19 grep-based acceptance criteria and the manual checkpoint verification passed on the first pass after two comment-wording fixes (see below) that were resolved before commit, not after.

- Two acceptance-criteria greps initially over-counted (`getProjectTriggers()` and `allowed_mentions`) because explanatory doc-comments restated the literal tokens the grep was counting. Reworded both comments to describe the mechanism without repeating the literal string, matching the plan's own instruction ("do not restate a forbidden token... for clarity") extended to non-forbidden but grep-counted tokens. No functional change; resolved before the Task 1 commit, not a post-hoc fix.

## User Setup Required

None beyond what Task 2's `user_setup` already covered and the human completed live: pasting `Code.gs`/`appsscript.json` into the Sheet's Apps Script editor, setting `DISCORD_WEBHOOK_URL` in Script Properties (webhook already existed per live environment facts), completing OAuth consent, and clicking *Install triggers*. No further action needed for this plan.

## Next Phase Readiness

- 05-02 (time-driven watchdog + conditional formatting) is unblocked: the column-F timestamp answer (string, `new Date(raw)` clean) is recorded above and in this file's frontmatter for that plan to read.
- The live Dashboard's `Δ Views` column currently holds large negative values for the three seeded creators (yesterday = synthetic seed data, today = real collected metrics — the subtraction is not real day-over-day movement) and a genuinely correct `—` for `mkbhd`. 05-02's conditional-formatting proof should use a hand-typed `500` / `-500` pair to see both color rules fire, not these seeded magnitudes.
- `installTriggers()` currently creates exactly one trigger; 05-02 adds the time-driven trigger to the same function and two more `onOpen` menu items ahead of *Install triggers*, per D-09's stated order. No blockers.

---
*Phase: 05-apps-script*
*Completed: 2026-08-06*

## Self-Check: PASSED
