---
phase: 05-apps-script
plan: 02
subsystem: infra
tags: [google-apps-script, discord-webhook, time-driven-trigger, conditional-formatting, sheets]

requires:
  - phase: 05-apps-script
    provides: "05-01's proven onOpen/installTriggers/onStatusEdit/getWebhookUrl/postToDiscord shape and the live-confirmed column-F timestamp type (string, new Date(raw) parses clean)"
provides:
  - "checkFreshness() — the stale-data watchdog with three independently-proven outcomes: stale alert, distinct cannot-determine alert, and silence backed by a Completed Executions run"
  - "applyFormatting() — sign-keyed conditional formatting on Δ Views (E2:E1000), whole-array replace, idempotent under repeated clicks including recovery from a foreign rule"
  - "the daily 09:00 Asia/Manila time-driven trigger, installed and confirmed pinned to GMT+08:00 in the live Triggers panel"
  - "the completed D-09 three-item menu order: Check freshness now, Re-apply formatting, Install triggers"
affects: [05-03-coverage-and-uat]

tech-stack:
  added: []
  patterns:
    - "Time-driven trigger via ScriptApp.newTrigger().timeBased().atHour(WATCHDOG_HOUR).everyDays(1).inTimezone(SCRIPT_TIMEZONE) — .inTimezone() is what actually pins atHour() to local time, not the manifest's timeZone fallback"
    - "Conditional-format rules built as a fresh array literal every call and passed whole to setConditionalFormatRules() — never read-then-append. Proven live: a foreign third rule introduced by a stray UI interaction was wiped by a single Re-apply formatting click"
    - "toast() is a Spreadsheet method, not a Sheet method — hoist SpreadsheetApp.getActive() once and call .toast() on that handle, matching installTriggers()'s existing shape"

key-files:
  created: []
  modified:
    - apps-script/Code.gs

key-decisions:
  - "checkFreshness()'s NaN guard discards a candidate at parse time, before it can win the newest-timestamp comparison — an unguarded NaN would make the strict '>' comparison false forever, the failure direction that looks identical to a healthy day under D-07."
  - "applyFormatting() had a Sheet-vs-Spreadsheet toast() receiver bug (getSheetByName() returns a Sheet, which has no toast method) — found in orchestrator review before the human pasted the code into the live editor, fixed in a dedicated commit (180dc07) hoisting ss = SpreadsheetApp.getActive() to match installTriggers()'s existing pattern. Live verification (the '2 conditional format rule(s) applied' toast) confirms the fix; pre-fix this call path would have thrown TypeError after the rules had already applied, showing a red Executions run and misleading the user into thinking formatting failed."

patterns-established:
  - "Any future toast() call in this file must be on the Spreadsheet handle (ss), never on a Sheet handle — the two classes are easy to conflate since getSheetByName() and getActive() are both single-token calls."

requirements-completed: [SCRIPT-01, SCRIPT-02, SCRIPT-04]

coverage:
  - id: D1
    description: "The CreatorPulse menu carries D-09's full three items in order — Check freshness now, Re-apply formatting, Install triggers — completing SCRIPT-01 beyond 05-01's single-item state"
    requirement: "SCRIPT-01"
    verification:
      - kind: manual_procedural
        ref: "Task 3 step 1 — human reloaded the live Sheet after re-pasting Code.gs and observed exactly three menu items in the stated order"
        status: pass
    human_judgment: true
    rationale: "Menu presence/order is a UI observation; no .gs test framework exists in this stack (05-RESEARCH.md Validation Architecture)."
  - id: D2
    description: "installTriggers() creates a daily time-driven trigger targeting checkFreshness, confirmed in the live Triggers panel as Day timer, 9am-10am, timezone GMT+08:00 (Asia/Manila) — .inTimezone(SCRIPT_TIMEZONE) took effect rather than falling back to the browser's zone"
    requirement: "SCRIPT-02"
    verification:
      - kind: manual_procedural
        ref: "Task 3 step 2 — human clicked Install triggers (toast: removed 1, created 2), Triggers panel showed exactly 2 triggers (onStatusEdit on-edit, checkFreshness time-driven), and the Edit dialog for the time-driven trigger confirmed 9am-10am / GMT+08:00"
        status: pass
    human_judgment: true
    rationale: "Trigger configuration is read from the live Triggers panel UI; no .gs test framework covers this (05-RESEARCH.md Validation Architecture)."
  - id: D3
    description: "checkFreshness()'s three outcomes proven independently against the live Sheet and Discord channel: (1) forced-stale alert naming the timestamp and age in hours, (2) a distinct cannot-determine alert when all of column F is unparseable, and (3) silence on fresh data backed by a Completed run in the Executions log, closing D-07's 'silent unless broken' as verified rather than assumed"
    requirement: "SCRIPT-02"
    verification:
      - kind: manual_procedural
        ref: "Task 3 steps 5-8 — every F2:F5 cell set to 2026-07-01T00:00:00+00:00 produced 'Watchdog: the collector has not run since 2026-07-01T00:00:00.000Z (862h ago).' on three repeated clicks (one message per click, no duplication); clearing all of F2:F5 produced the distinct 'Watchdog: could not determine freshness — no cell in column F of \"Dashboard\" parsed to a real date.'; restoring column F and clicking again produced silence with Executions log entry 'checkFreshness | Menu | Aug 6, 2026, 5:53:22 AM | 0.923 s | Completed'"
        status: pass
    human_judgment: true
    rationale: "ROADMAP criterion 4 names the Executions log specifically as the liveness proof — a live observation, not a mechanically-checkable assertion in this stack."
  - id: D4
    description: "applyFormatting() colors Δ Views by sign (green >0, red <0, — unformatted by construction) over a fixed E2:E1000 range, and is idempotent under repeated clicks via whole-array replace — proven not just by a stable rule count across three clicks but by the replace semantics actively wiping a foreign third rule introduced by a stray UI interaction during verification"
    requirement: "SCRIPT-04"
    verification:
      - kind: manual_procedural
        ref: "Task 3 steps 3-4 — Re-apply formatting rendered E2/E4/E5 (all negative live deltas) red and left the em-dash cell E3 unformatted; three repeated clicks left exactly 2 rules in Format > Conditional formatting; a stray manually-added 'Cell is not empty' rule on E1 was removed by a single Re-apply formatting click, demonstrating the whole-array replace live rather than only by code inspection"
        status: pass
    human_judgment: true
    rationale: "Color rendering and Format-menu rule count are visual/UI observations (ROADMAP criterion 3); no .gs test framework covers this."
  - id: D5
    description: "applyFormatting()'s toast() Sheet-vs-Spreadsheet defect (getSheetByName() returns a Sheet, which has no toast method) — found in orchestrator review before the human pasted the code, fixed by hoisting ss = SpreadsheetApp.getActive(), and confirmed live: the 'CreatorPulse — 2 conditional format rule(s) applied to E2:E1000.' toast fired without error"
    verification:
      - kind: manual_procedural
        ref: "Task 3 step 3 — toast observed live after the fix (commit 180dc07); pre-fix this call path would have thrown TypeError after the rules had already been set, showing a red Executions run"
        status: pass
    human_judgment: true
    rationale: "Confirmation that a specific runtime fix behaves correctly under live execution — a live observation, not a unit-testable assertion in this stack (no .gs test framework)."
  - id: D6
    description: "The natural 09:00 Asia/Manila fire of checkFreshness, visible in the Executions log as opportunistic (not required) evidence for criterion 4 — D-08's 'proven twice: forced, then natural' second half"
    requirement: "SCRIPT-02"
    verification:
      - kind: manual_procedural
        ref: "Not yet arrived at verification time (~06:00 Asia/Manila, trigger fires 09:00-10:00). D2 and D3 above already satisfy criterion 4 with forced-run evidence; this entry is bonus evidence, not a gate."
        status: unknown
    human_judgment: true
    rationale: "Pending a real clock event roughly 3 hours after this plan's checkpoint closed; the human is expected to add this observation to 05-UAT.md (05-03's artifact) after 09:00 Manila. Not required for this plan's completion per D-08 and the plan's own acceptance criteria, which are satisfied by the forced proof alone."

duration: ~55min active work (excludes human verification wait time between checkpoints and approval)
completed: 2026-08-06
status: complete
---

# Phase 5 Plan 2: Time-Driven Watchdog and Conditional Formatting Summary

**checkFreshness() stale-data watchdog (three independently-proven outcomes) plus applyFormatting()'s sign-keyed conditional formatting on Δ Views, both live-verified against the real Sheet and Discord channel**

## Performance

- **Duration:** ~55min active work (excludes the human verification wait between the Task 3 checkpoint, the review-found defect fix, and final approval)
- **Completed:** 2026-08-06
- **Tasks:** 3 (2 auto + 1 checkpoint:human-verify), plus one review-found fix commit against Task 2's deliverable
- **Files modified:** 2 (apps-script/Code.gs across four commits; this SUMMARY)

## Accomplishments

- `checkFreshness()` written and live-verified with all three outcomes proven independently: a forced-stale alert naming the exact timestamp and age in hours, a distinct cannot-determine alert when column F holds nothing parseable, and silence on fresh data backed by a Completed run in the Executions log — closing D-07's "silent unless broken" as an observed property rather than an assumed one.
- `applyFormatting()` written, live-verified to color Δ Views by sign and leave the em-dash placeholder untouched, and proven idempotent under repeated clicks — including an unplanned real-world proof where a stray foreign conditional-format rule was wiped by a single re-apply click, demonstrating the whole-array-replace semantics against the live Sheet rather than only by code inspection.
- The daily 09:00 Asia/Manila time-driven trigger is installed and confirmed in the live Triggers panel as pinned to GMT+08:00 — `.inTimezone(SCRIPT_TIMEZONE)` took effect rather than falling back to the browser's zone.
- The `CreatorPulse` menu now carries D-09's complete three-item order, live-confirmed after reload.
- A `toast()`-receiver defect in `applyFormatting()` (called on a `Sheet` instead of the `Spreadsheet`) was caught in orchestrator review before the human pasted the code, fixed, and the fix's correctness was itself confirmed live by the exact toast the defect had been blocking.

## Task Commits

1. **Task 1: The stale-data watchdog and its daily trigger** - `6645cc2` (feat)
2. **Task 2: Conditional formatting on the delta column** - `f974f21` (feat)
3. **Review fix: `applyFormatting` toast() receiver corrected (Sheet → Spreadsheet)** - `180dc07` (fix)

**Plan metadata:** committed alongside this SUMMARY.

_Task 3 was `checkpoint:human-verify` (gate: blocking) — no code change of its own, verification only; results recorded below._

## Files Created/Modified

- `apps-script/Code.gs` - added `checkFreshness()`, `applyFormatting()`, `LAST_UPDATED_COLUMN`/`STALE_THRESHOLD_HOURS`/`WATCHDOG_HOUR`/`SCRIPT_TIMEZONE`/`DELTA_RANGE`/`POSITIVE_BACKGROUND`/`NEGATIVE_BACKGROUND` constants, extended `installTriggers()` with the time-driven trigger, extended `onOpen()` to the full three-item menu; fixed `applyFormatting()`'s `toast()` receiver.

## Decisions Made

- `checkFreshness()` discards a `NaN` candidate at parse time, before it can win the newest-timestamp comparison — the guard that stops a single unparseable cell from making the watchdog permanently and silently quiet.
- `applyFormatting()`'s `toast()` bug (Sheet has no `toast` method; only Spreadsheet does) was fixed by hoisting `ss = SpreadsheetApp.getActive()` and calling `ss.toast(...)`, matching `installTriggers()`'s already-correct pattern — see Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `applyFormatting()` calling `toast()` on a `Sheet` instead of a `Spreadsheet`**
- **Found during:** Orchestrator review of Task 2's commit, before the human pasted the code into the live editor (i.e., before Task 3's verification began)
- **Issue:** `getSheetByName()` returns a `Sheet` object, which has no `toast` method — only `Spreadsheet` does. `setConditionalFormatRules(rules)` would execute first (so the rules WOULD apply), and the very next line would throw `TypeError: sheet.toast is not a function`. The Executions panel would show a red failed run even though the formatting had, in fact, succeeded — a confusing false-negative landing in the phase's most time-pressured verification step. It also broke the plan's own Task 3 step 3, which instructs the human to read a toast reporting the rule count; that toast would never have appeared.
- **Fix:** Hoisted `const ss = SpreadsheetApp.getActive();` and changed `sheet.toast(...)` to `ss.toast(...)`, matching the pattern already established in `installTriggers()`. Message text and title (`'CreatorPulse'`) left unchanged since the plan's Task 3 verification refers to them.
- **Files modified:** `apps-script/Code.gs`
- **Verification:** All four gate commands re-run and confirmed green; grepped every `toast(` call site (2 total) and confirmed both are on `ss`. Live verification in Task 3 step 3 then confirmed the fix: the toast `'CreatorPulse — 2 conditional format rule(s) applied to E2:E1000.'` fired without error against the real Sheet.
- **Committed in:** `180dc07` (fix, separate from Task 2's `f974f21`)

---

**Total deviations:** 1 auto-fixed (1 bug, caught in review before live paste)
**Impact on plan:** Necessary correctness fix to Task 2's deliverable, found before it reached the live editor rather than during verification. No scope creep — `applyFormatting()` was the only function touched, and no other function's `toast()` call site needed changing (`installTriggers()` was already correct; `checkFreshness()` and `_diagnoseTimestampType()` hold a `Sheet` in a variable named `sheet` but neither calls `toast()`).

## Issues Encountered

None beyond the deviation above. All grep-based acceptance criteria for both auto tasks passed after two comment wording adjustments (see below) made before commit, not after.

- Two acceptance-criteria greps initially over-counted because explanatory comments restated the exact literal token the grep was counting (`> STALE_THRESHOLD_HOURS` inside a comment describing the guard's purpose, and `setConditionalFormatRules(` inside a docstring describing the whole-array-replace behavior). Reworded both comments to describe the mechanism without repeating the counted literal — the same principle 05-01 applied to non-forbidden-but-grep-counted tokens. No functional change; resolved before each task's commit.

## User Setup Required

None beyond what Task 3's `how-to-verify` already covered and the human completed live: re-pasting `Code.gs` (post-fix) into the Sheet's Apps Script editor, clicking *Install triggers*, running the full forced-stale / cannot-determine / silence-is-fresh proof sequence, and restoring column F afterward. No further action needed to close this plan.

## Live Sheet State After Verification

Recorded here since Task 3's verification necessarily left temporary state on the live Sheet, now cleaned up:

- Column F restored to its pre-verification values (pasted back from the off-Sheet copy taken before the forced-stale steps).
- The stray "Cell is not empty" rule on `E1`, introduced by an accidental interaction with the Sheets rule-creation form during verification, was removed by a `Re-apply formatting` click (a live demonstration of the whole-array-replace semantics, not a separate fix) — `E1` is back to white.
- The temporary `Sheet2` tab from 05-01's wrong-tab negative test has been deleted.
- Cell `G2` (held `Done` from 05-01's Status test) has been cleared.
- The Dashboard is in a clean, demo-ready state: three seeded creators' real `Δ Views` are all currently negative (red), `mkbhd`'s is a genuine `—` (unformatted), and both triggers are live.

## Next Phase Readiness

- 05-03 (COVERAGE.md and UAT) is unblocked. This plan's live evidence — the exact alert texts, the Triggers panel configuration, the Executions log entries, and the idempotency proof — is ready to lift into `05-UAT.md`.
- **Outstanding, non-blocking:** the natural 09:00 Asia/Manila fire of `checkFreshness` had not yet occurred at verification time (~06:00 Manila). D-08's forced proof already satisfies ROADMAP criterion 4 on its own; the natural fire is bonus evidence 05-03 or the human can add to `05-UAT.md` after 09:00 Manila by checking the Executions log for a `Time-driven` trigger source with a `Completed` status.
- No blockers for 05-03. `apps-script/Code.gs` is feature-complete for this phase: menu, both triggers, the watchdog, and the formatter are all live and proven.

---
*Phase: 05-apps-script*
*Completed: 2026-08-06*

## Self-Check: PENDING
