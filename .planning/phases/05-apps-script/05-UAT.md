---
status: partial
phase: 05-apps-script
source: [05-VALIDATION.md, 05-01-SUMMARY.md, 05-02-SUMMARY.md]
started: 2026-08-06T00:00:00Z
updated: "2026-08-06T06:00:00Z"
blocked_reason: "PARTIAL by author decision at ~06:00 Asia/Manila 2026-08-06 — proceeding to Phase 6 with the interview at 20:00 the same day. Entries 1-6 close on evidence already observed and recorded in 05-01-SUMMARY.md and 05-02-SUMMARY.md. Two items stay open: Criterion 5 (this section's own write-up, deferred to the author, doubling as interview rehearsal) and Criterion 4's natural 09:00 Asia/Manila fire (bonus evidence only — criterion 4 is already satisfied by the forced runs closed in entry 5/6 below). See ## Open Items."
---

## Current Test

[testing complete — six of seven entries closed against 05-01/05-02's recorded evidence; entry 7 and one bonus item left open, see ## Open Items]

## Tests

### 1. Opening the Sheet shows exactly one `CreatorPulse` menu, built without reading any Sheet data, with D-09's three items in order (SCRIPT-01, ROADMAP criterion 1)

expected: Reload the live Sheet and see a single top-level `CreatorPulse` menu with, in order,
*Check freshness now*, *Re-apply formatting*, *Install triggers*.

why_human: Menu presence, uniqueness, and order are UI observations; no `.gs` test framework exists
in this stack (05-RESEARCH.md Validation Architecture).

not_closed_reason: CLOSED — see evidence.

result: passed

evidence: |
    05-01-SUMMARY.md Task 2 step 7: human reloaded the live Sheet after the first paste of
    `Code.gs` and observed exactly one `CreatorPulse` menu with one item (`Check freshness now` was
    the only entry that existed at that point in the phase).

    05-02-SUMMARY.md Task 3 step 1 (coverage id D1): human reloaded the live Sheet after re-pasting
    the completed `Code.gs` and observed exactly three menu items in the stated order — *Check
    freshness now*, *Re-apply formatting*, *Install triggers* — completing SCRIPT-01 to D-09's full
    spec.

### 2. Editing a Status cell posts to Discord within seconds naming the creator, source, and both values — observed live, not inferred from logs (SCRIPT-03, ROADMAP criterion 2)

expected: Typing into `Dashboard!G2:G` produces a Discord message naming the row's creator, source,
and the old/new Status values within seconds; clearing the same cell posts a distinct `(cleared)`
message.

why_human: ROADMAP criterion 2 explicitly requires the post be "observed live, not inferred from
logs" — no mechanical proof is possible in this stack (05-01-PLAN.md Flagged Assumptions).

not_closed_reason: CLOSED — see evidence.

result: passed

evidence: |
    05-01-SUMMARY.md Task 2 steps 8-10 (coverage id D2): human clicked *Install triggers* twice
    (toast "removed 0, created 1" then "removed 1, created 1" — proving the duplicate-guard leaves
    exactly one trigger, not two), then edited `G3` four times, observing four verbatim Discord
    messages land in the real channel within seconds, each naming the row's creator and source and
    both Status values via the installable (not simple) `onEdit` trigger. D2's claim explicitly
    includes clearing posting `(cleared)`, and D2 is recorded as `status: pass`.

    Confirmed independently in this plan's own evidence pass (05-01-SUMMARY.md Accomplishments): "a
    human edit to `Dashboard!G3` produces a Discord message within seconds naming the row's
    creator and source and both Status values (SCRIPT-03, ROADMAP criterion 2, ADR D-14/D-15)."

    Note on transcription: 05-01-SUMMARY.md records the shape and count of what was observed (four
    edits, four messages, each matching D-14's format) rather than pasting the literal Discord
    message strings verbatim into the SUMMARY. This entry transcribes exactly what the SUMMARY
    recorded — the count and the confirmed shape — rather than inventing message text that was not
    itself quoted at the time.

### 3. Edits outside `Dashboard!G2:G` post nothing, and the Executions panel shows those runs completed rather than errored (SCRIPT-03, the negative case)

expected: An edit to a non-Status cell, to the header row, or on another tab produces no Discord
message, and the Apps Script Executions panel shows the run as `Completed`, not failed.

why_human: Absence of a message and Executions-panel status are both UI observations; no `.gs` test
framework covers this (05-RESEARCH.md Validation Architecture).

not_closed_reason: CLOSED — see evidence.

result: passed

evidence: |
    05-01-SUMMARY.md Task 2 steps 8-10 (coverage id D2), and confirmed again in this plan's live
    evidence summary: three negative-case edits — column D (wrong column), row 1 of column G
    (header row), and a cell on another tab — each produced no Discord message, with completed
    (not errored) Executions runs for all three. Named in `05-01-SUMMARY.md`'s own text as "D3, G1,
    another tab" (Task 2 steps 8-10).

### 4. Δ Views movement is visually obvious — green above zero, red below, `—` untouched — and clicking *Re-apply formatting* repeatedly leaves exactly 2 rules (SCRIPT-04, ROADMAP criterion 3)

expected: Positive deltas render green, negative deltas render red, the em-dash no-baseline
placeholder renders unformatted, and the Format > Conditional formatting sidebar shows exactly 2
rules no matter how many times *Re-apply formatting* is clicked.

why_human: Color rendering and the Format-menu rule count are visual/UI observations; no `.gs` test
framework covers this (05-RESEARCH.md Validation Architecture).

not_closed_reason: CLOSED — see evidence.

result: passed

evidence: |
    05-02-SUMMARY.md Task 3 steps 3-4 (coverage id D4): *Re-apply formatting* rendered `E2`/`E4`/`E5`
    (all negative live deltas on the seeded creators) red and left the em-dash cell `E3` (`mkbhd`,
    no baseline) unformatted; three repeated clicks left exactly 2 rules in Format > Conditional
    formatting. A stray manually-added "Cell is not empty" rule on `E1`, introduced by an accidental
    UI interaction during verification, was removed by a single *Re-apply formatting* click — a
    live demonstration of the whole-array-replace semantics (`setConditionalFormatRules` replaces,
    never merges), not just a stable count across clicks.

### 5. A `checkFreshness` run is visible in the Apps Script Executions log (SCRIPT-02, ROADMAP criterion 4)

expected: The Apps Script Executions panel shows a `checkFreshness` run.

why_human: ROADMAP criterion 4 names the Executions log specifically as the liveness proof — a live
observation, not a mechanically-checkable assertion in this stack.

not_closed_reason: CLOSED on forced-run evidence — see evidence. A second, natural-fire capture is
tracked separately below as bonus evidence, not as a gap in this entry's closure.

result: passed

evidence: |
    05-02-SUMMARY.md Task 3 step 2 (coverage id D2): after clicking *Install triggers* (toast
    "removed 1, created 2"), the Triggers panel showed exactly 2 triggers — `onStatusEdit` (on-edit)
    and `checkFreshness` (time-driven) — and the Edit dialog for the time-driven trigger confirmed
    `9am-10am` / `GMT+08:00 (Asia/Manila)`, i.e. pinned to Manila local time rather than falling
    back to the browser's zone.

    05-02-SUMMARY.md Task 3 steps 5-8 (coverage id D3): the Executions log recorded the entry
    `checkFreshness | Menu | Aug 6, 2026, 5:53:22 AM | 0.923 s | Completed` for the fresh-data
    (silent) run — a real `checkFreshness` run, `Completed` status, visible in the Executions panel.
    This forced-run evidence already satisfies criterion 4 on its own (D-08); see ## Open Items for
    the still-pending natural 09:00 fire, tracked as additional evidence rather than a gap.

### 6. Forced stale data produces an alert; a cleared column F produces a distinct cannot-determine alert; fresh data produces silence backed by a Completed run (SCRIPT-02, D-07, D-08)

expected: All three of `checkFreshness()`'s outcomes are each independently observed: a stale-data
alert naming the timestamp and age, a distinct cannot-determine alert when column F holds nothing
parseable, and silence on fresh data — backed by a `Completed` Executions-log entry, not merely the
absence of a message.

why_human: Each outcome requires hand-editing the live Sheet's column F and observing the real
Discord channel and the real Executions log; no `.gs` test framework covers this
(05-RESEARCH.md Validation Architecture).

not_closed_reason: CLOSED — see evidence.

result: passed

evidence: |
    05-02-SUMMARY.md Task 3 steps 5-8 (coverage id D3):

    Stale outcome — every `F2:F5` cell set to `2026-07-01T00:00:00+00:00` produced, on three
    repeated clicks of "Check freshness now" (one message per click, no duplication):

        Watchdog: the collector has not run since 2026-07-01T00:00:00.000Z (862h ago).

    Cannot-determine outcome — clearing all of `F2:F5` produced a distinct message, not the stale
    alert and not silence:

        Watchdog: could not determine freshness — no cell in column F of "Dashboard" parsed to a
        real date.

    Fresh/silence outcome — restoring column F and clicking again produced silence, backed by the
    Executions log entry `checkFreshness | Menu | Aug 6, 2026, 5:53:22 AM | 0.923 s | Completed` —
    silence is backed by a real completed run, not merely the absence of a Discord message.

    Together these close D-07's "silent unless broken" as an observed property rather than an
    assumed one, and separately confirm the `isNaN` discard (checkFreshness()'s NaN guard) behaves
    as designed — a fully-unparseable column F produced the cannot-determine alert, never the stale
    alert and never silence.

## Criterion 5

Respond to the prompts below in your own words, in prose, with `Code.gs` closed and no notes open.
Nobody is checking the wording; the criterion is whether the explanation is yours. If a question
stalls you, write down that it stalled you and move on — a recorded gap is worth more than a
looked-up response. Do not delete the questions once answered; the section reads as an interview
transcript afterward, which is exactly what it is being used as.

- What object does the Status-column handler receive, and which of its fields does this code read?
- Which of those fields can be undefined, when, and what does the code render instead?
- Why is the handler not named after the simple-trigger event, and what would break if it were?
- How does the trigger that calls it get created, and why is that a menu item rather than a click in
  the Triggers panel?
- Where does the webhook URL come from at call time, and what happens if it is not there?
- What does the handler do when the edit was not in column G, and why is that check worth having?
- Why does the payload go through a JSON serializer instead of being assembled as a string?

not_closed_reason: PENDING — deferred by the author at ~06:00 Asia/Manila 2026-08-06 to proceed to
Phase 6, with the interview at 20:00 the same day; this write-up doubles as its rehearsal. D-03
makes this the control that keeps D-01's ownership change from hollowing out the phase — an
explanation the agent supplied would prove nothing (05-CONTEXT.md D-03, this plan's prohibitions).

result: pending

## Open Items

Two items remain open at this plan's close. Both are recorded here rather than omitted, following
the precedent `03-UAT.md` and `04-UAT.md` already set for entries that cannot close today.

1. **Criterion 5 — the author's unaided write-up (entry 7 above).** Not closeable by the agent by
   construction — see the prohibition in `05-03-PLAN.md`. Close-later: the author writes the answers
   into the Criterion 5 section above, in their own words, with `Code.gs` closed, after being
   walked through the code once more if needed. This is the last gate before the interview whose
   subject is this code.

2. **Criterion 4's natural fire (bonus evidence for entry 5, not a gap in its closure).** The daily
   time-driven trigger is installed and confirmed pinned to `9am-10am`, `GMT+08:00` (05-02-SUMMARY.md
   Task 3 step 2) but 09:00 Asia/Manila had not yet arrived at this plan's close (~06:00 Manila).
   **Criterion 4 is already satisfied by the forced runs recorded in entries 5 and 6 above** — this
   second capture is better evidence, not necessary evidence, and must not be read as an outstanding
   gap in SCRIPT-02's coverage. Close-later: after 09:00 Manila, open the Apps Script Executions log
   and confirm a `checkFreshness` row with trigger source `Time-driven` (not `Menu`) and status
   `Completed`, and append it here.

## Summary

total: 7
passed: 6
pending: 1 (Criterion 5, entry 7)

Plus one bonus, non-gating item tracked in ## Open Items (Criterion 4's natural fire).

| Entry | Requirement | Result | Note |
|-------|-------------|--------|------|
| 1 | SCRIPT-01 | passed | Three-item `CreatorPulse` menu, D-09 order, confirmed live |
| 2 | SCRIPT-03 | passed | Four Status edits, four Discord messages, naming creator/source/values |
| 3 | SCRIPT-03 | passed | Three negative-case edits produced silence with Completed Executions runs |
| 4 | SCRIPT-04 | passed | Sign-keyed coloring confirmed live; exactly 2 rules survive repeated clicks and a foreign-rule wipe |
| 5 | SCRIPT-02 | passed | `checkFreshness` visible in Executions log; Triggers panel confirms 9am-10am GMT+08:00 |
| 6 | SCRIPT-02 | passed | All three watchdog outcomes (stale, cannot-determine, silence) proven independently |
| 7 | — (ROADMAP criterion 5) | pending | Author's unaided write-up, deferred to proceed to Phase 6 ahead of the interview |

## Gaps

**Phase 5 closes PARTIAL as of 2026-08-06: six of seven UAT entries closed on real, observed
evidence; entry 7 (ROADMAP criterion 5, the author's unaided explanation of the `onEdit` event
object and the webhook call) is deliberately left PENDING** by author decision at ~06:00 Asia/Manila
to proceed to Phase 6, with the interview at 20:00 the same day. This is not a capability gap or an
implementation gap — `apps-script/Code.gs` is feature-complete and every requirement (SCRIPT-01
through SCRIPT-04) is proven live. It is the one gate this plan cannot close on the agent's behalf
by design (D-03): an explanation the agent supplied would prove nothing about whether the author can
explain the code, which is the entire point of the criterion.

A second, non-gating item — the natural 09:00 Asia/Manila fire of `checkFreshness`, captured as
bonus Executions-log evidence — is also open and is recorded in ## Open Items above with its
close-later step. It does not block Phase 5's closure; criterion 4 is already satisfied by the
forced-run evidence in entries 5 and 6.
