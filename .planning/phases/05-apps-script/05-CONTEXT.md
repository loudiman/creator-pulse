# Phase 5: Apps Script - Context

**Gathered:** 2026-08-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 delivers the Apps Script layer bound to the Google Sheet's frozen `Dashboard` tab — the
one part of the system that runs on Google's infrastructure rather than on the droplet. Four
requirements, all of them: **SCRIPT-01** (`onOpen` custom menu), **SCRIPT-02** (time-driven
trigger), **SCRIPT-03** (`onEdit` on the Status column posting to a Discord webhook), **SCRIPT-04**
(conditional formatting on the day-over-day delta).

**The ownership rule changed on 2026-08-06, and this is the phase's single most important
context.** ROADMAP.md and `.claude/CLAUDE.md` both declared this phase `human` — "entirely
human-built, roughly 100 lines typed by hand, the agent does not generate this code." With the
interview under ten hours away and Phases 5, 6, and 7 all outstanding, the author reclassified the
phase as **`mixed`** (D-01). The agent now writes the Apps Script; the author reads it, is walked
through it, pastes it, and must still be able to explain it cold. The three prohibitions this rule
change does **not** touch: VPS provisioning and systemd units stay human-built (Phase 2 D-12
remains binding), and Discord Developer Portal registration stays human-built (Phase 6).

**Not in this phase:** any Python (the collector and `sheets.py` are finished and are not reopened
— Phase 5 does not add a column, rename the tab, or change the write range); the Discord *bot*
(Phase 6 — a webhook is not a bot, and BOT-01's daily digest is explicitly not duplicated here);
the README and journal (Phase 7).

**What Phase 5 depends on and must not disturb** — from Phase 4 D-03, frozen for v1:

| Col | Header | Owner |
|-----|--------|-------|
| A | `Creator` (`creator_id` slug) | DB |
| B | `Source` | DB |
| C | `Followers (coarse)` | DB |
| D | `Views` | DB |
| E | `Δ Views` — numeric, `—` when no baseline | DB |
| F | `Last updated (UTC)` | DB |
| G | `Status` | **human** |

Tab name `Dashboard`. Sheet id `1hP7rZqq9Z-QnYGCkt8uhNK1yiwF3dsM9e-T2sYQOqQI`. The Python write
covers `A1:F{n+1}` only and never touches G. Every trigger and format rule in this phase binds to
that layout; the layout does not move to accommodate them.

</domain>

<decisions>
## Implementation Decisions

### Ownership and Artifact Location

- **D-01:** **Phase 5 ownership changes from `human` to `mixed`.** The agent writes the complete
  Apps Script; the author reads it line by line with a walkthrough, then pastes it into the Sheets
  editor. Chosen over a fill-in-the-blanks skeleton and over retyping-from-draft, both of which the
  author considered and rejected on time. The stated reason is the clock, and it is recorded as the
  reason rather than dressed up as a design improvement: at the moment of the change roughly ten
  hours remained before the interview with Phases 5, 6, and 7 all outstanding.
  **What this does not license:** the other two human-built areas are untouched. Phase 2 D-12
  (`deploy/creatorpulse.service`, `deploy/creatorpulse.timer` never written or edited by the agent)
  stays binding, and Discord Developer Portal setup in Phase 6 stays human-built. This is one
  scoped exception, dated, not a general relaxation.
  — **Reversibility:** one-way in the honest sense — the author cannot un-know that the code was
  drafted for them. D-03's write-up requirement exists precisely to make the resulting
  understanding real rather than assumed.

- **D-02:** **Both rule files are amended, with the date and the reason.** `.claude/CLAUDE.md` Hard
  Rule 2 and ROADMAP.md's Phase 5 `Owner:` line and Notes block are updated in place, each carrying
  a dated amendment naming the deadline as the cause. Rejected: amending ROADMAP only, and
  recording the change in this file alone — either would leave `.claude/CLAUDE.md` stating a rule
  that the repo's own contents contradict, which is the exact failure the merge rule ("nothing
  enters the repo the author cannot explain out loud") exists to prevent. A rule that was changed
  deliberately and documented is defensible; a rule silently violated is not.
  — **Reversibility:** reversible — the amendments are additive notes, not deletions. The original
  rule text stays visible above its amendment.

- **D-03:** **ROADMAP criterion 5 stands unchanged, and is proven in writing.** "The author can
  walk someone through the `onEdit` trigger's event object and the webhook call from memory"
  remains a hard criterion. It closes when the author writes that explanation into `05-UAT.md` in
  their own words, unaided, after the walkthrough. Rejected: a verbal-only rehearsal (leaves no
  artifact and no way to tell it happened) and closing on the other four criteria alone. This is
  the control that keeps D-01 from hollowing out the phase — the interview tests whether the author
  can explain it, and this criterion tests the same thing a few hours earlier, when there is still
  time to fix a gap.
  — **Reversibility:** reversible.

- **D-04:** **The source lives at `apps-script/Code.gs` plus `apps-script/appsscript.json`, in the
  repo, synced to the Sheets editor by manual copy-paste.** No `clasp`: it needs Node and a new
  toolchain, which the no-new-dependencies rule forbids, and the sync it automates happens perhaps
  three times in this project's life. Rejected: leaving the code only in the bound Sheets editor —
  the repo *is* the portfolio artifact, and code no reviewer can read is code that did not ship.
  **Known cost, accepted:** copy-paste sync means the repo and the live Sheet can drift. The
  mitigation is procedural, not technical — the Sheet is only ever edited by pasting the repo file
  whole, never by hand-editing in the browser.
  — **Reversibility:** reversible.

### The Time-Driven Trigger (SCRIPT-02)

- **D-05:** **The trigger is a stale-data watchdog, not a second digest.** It reads the newest
  timestamp in column F and, if it is older than the threshold, posts a "the collector has not run
  since X" alert to the Discord webhook. Rejected: a Sheet-side daily summary (duplicates Phase 6
  BOT-01 and reads as redundant once both exist) and a daily formatting refresh (conditional-format
  rules do not decay, so it catches no real failure).
  **The rationale is the interview answer, and it is structural rather than aesthetic:** Phase 6's
  bot runs on the droplet. If the droplet is down, the collector is down *and so is the bot* — the
  outage produces silence, not an alert. Apps Script runs on Google's infrastructure. This is the
  one alert in the system that survives the failure it is watching for, which is the whole reason
  it belongs in the Sheet layer and not in the bot. A watchdog hosted on the thing it watches is
  not a watchdog.
  — **Reversibility:** reversible.

- **D-06:** **Fires 09:00 Asia/Manila; alerts when the newest column F timestamp is older than 26
  hours.** The collector runs 08:00 Manila = 00:00 UTC (Phase 2 D-09), so 09:00 is one hour after
  the run should have finished. The 26-hour threshold alerts on a genuinely missed run while
  tolerating a run that is merely slow, retried, or a little late — a 12-hour threshold was
  rejected as a false-alarm generator around timezone and slow-run edges, and a noon fire time was
  rejected because a dead collector should not go unreported until midday.
  — **Reversibility:** reversible — both numbers are constants at the top of the file.

- **D-07:** **Silent unless broken.** The watchdog posts only when data is stale; a healthy day
  produces no Discord message. Rejected: a daily heartbeat either way. The "who watches the
  watchdog" gap that a heartbeat would close is already closed by ROADMAP criterion 4, which
  requires the author to open the Apps Script execution log and see the trigger's runs — that log
  is the canonical liveness proof and it is already a gate on this phase. A second daily message
  into the same channel Phase 6's digest posts to would add no information and dull the signal.
  — **Reversibility:** reversible.

- **D-08:** **Criterion 4 is proven twice: forced, then natural.** The forced proof is the one that
  must happen — hand-edit a column F cell to an old timestamp, run the watchdog function manually
  from the editor, watch the alert land in Discord, and let the next `creatorpulse sync` overwrite
  the cell (the Python write covers column F, so no cleanup is needed). That exercises the alert
  branch, which a healthy scheduled fire never would. The natural 09:00 fire is captured
  opportunistically if the clock allows, for the execution-log screenshot.
  — **Reversibility:** reversible.

### The Menu and Formatting (SCRIPT-01, SCRIPT-04)

- **D-09:** **Three menu items, and two of them are free.** `onOpen` builds a `CreatorPulse` menu
  with:
  1. *Check freshness now* → calls the same function the time-driven trigger calls (D-05).
  2. *Re-apply formatting* → calls the same function that installs the format rules (D-10).
  3. *Install triggers* → `ScriptApp.newTrigger` creating both the installable `onEdit` and the
     daily time-driven trigger, guarded against creating duplicates by first deleting this
     project's existing triggers via `ScriptApp.getProjectTriggers()`.

  Items 1 and 2 add no logic at all — they are second entry points to functions that exist for
  other reasons, which is why the menu costs almost nothing. Item 3 is the deliberate addition, and
  it earns its ~10 lines: installing the `onEdit` trigger is the single most error-prone setup step
  in this phase (see D-12), and putting it in code makes it reproducible and reviewable instead of
  a click-sequence in the Triggers panel that must be remembered and re-done if the Sheet is ever
  rebuilt.
  — **Reversibility:** reversible.

- **D-10:** **Conditional formatting is applied by script, never clicked in the UI.**
  `SpreadsheetApp.newConditionalFormatRule`, roughly 15 lines, in `Code.gs`. Rejected: setting the
  rules by hand in the Sheets Format menu — that produces nothing reviewable, nothing in the repo,
  nothing explainable as code, and rules that die with the tab. This is the same judgment D-04
  makes about where code lives, applied to formatting.
  — **Reversibility:** reversible.

- **D-11:** **The rules key on the sign of column E, and nothing else.** Green when `Δ Views > 0`,
  red when `< 0`, untouched at exactly 0. The `—` no-baseline cells are non-numeric, so a
  number-comparison rule skips them by construction rather than by a special case — which is the
  correct rendering of "no comparison available" (Phase 4 D-05). Applied to `E2:E1000` rather than
  to the current row count, so creators added later inherit the formatting with no edit. Rejected:
  an additional stale-row rule keyed on column F — it restates the watchdog's job in a second
  place, adds a date-formula rule to explain, and the watchdog already reports staleness to Discord
  where the author will actually see it. A ±20% rule matching BOT-02 was not viable: column E is an
  absolute delta, not a percentage.
  — **Reversibility:** reversible.

- **D-12:** **Column G stays free text.** No data-validation dropdown. Rejected despite a cleaner
  demo (one click, no typos): a dropdown alters a column Phase 4 froze and handed to the human,
  and it would invalidate the SHEET-06 "Status survives a sync" proof already run and recorded in
  `04-UAT.md`. The `onEdit` handler must survive arbitrary text regardless — anyone can paste into
  a validated cell — so the validation would buy presentation, not safety.
  — **Reversibility:** reversible — a dropdown can be added later without touching the handler.

### The Webhook Path (SCRIPT-03)

- **D-13:** **The webhook URL lives in Script Properties, never in `Code.gs`.**
  `PropertiesService.getScriptProperties().getProperty('DISCORD_WEBHOOK_URL')`, with the value
  pasted once by hand into the Apps Script editor's Script Properties panel. This follows directly
  from D-04: the moment `Code.gs` enters the repo, a hardcoded webhook URL is a committed secret,
  and this project has been disciplined about secrets since Phase 1 (`chmod 600` env file, key
  material outside the repo, `.gitignore` written before the first commit). Rejected:
  hardcoding the URL and gitignoring `apps-script/` — that reverses D-04 and removes the file from
  the reviewable artifact.
  **Failure behaviour:** if the property is unset, the function throws a named error saying which
  property to set. Silent no-op is the wrong failure — it looks identical to "nobody edited
  anything" (the same reasoning as Phase 4 D-07 and PITFALLS.md §18(d)).
  — **Reversibility:** reversible.

- **D-14:** **The message names the creator and both values:**
  `xqc / youtube — Status: (blank) → Flagged`. The creator and source come from reading columns A
  and B of the edited row via `e.range.getRow()`; the values come from `e.oldValue` and `e.value`.
  Rejected: new-value-only (drops the most informative half of an edit) and a bare cell reference
  like "G4 changed" (does not say which creator, which is the entire point of the notification).
  **This choice is deliberately aimed at criterion 5** — reading the row off `e.range` and using
  both `e.oldValue` and `e.value` is exactly the event-object knowledge the author must be able to
  explain from memory, so the message shape and the criterion reinforce each other.
  — **Reversibility:** reversible.

- **D-15:** **Clearing a Status cell posts too.** Deleting the text sends
  `xqc / youtube — Status: Flagged → (cleared)`. Rejected: skipping empty new values. "Every human
  touch of column G is visible in Discord" is a simpler rule to state and defend than the same rule
  with an exception carved out of it — and "someone removed the flag" is arguably the edit most
  worth knowing about.
  **Note:** `e.oldValue` is `undefined` for a multi-cell edit, so the handler renders a missing old
  value as `(blank)` rather than assuming it.
  — **Reversibility:** reversible.

- **D-16:** **One webhook, one channel** — the watchdog (D-05) and the `onEdit` handler post to the
  same Discord webhook, in the channel Phase 6's bot will also use. One Script Property to set, one
  channel to watch, one thing to open during the demo. Rejected: splitting ops alerts from human
  signal into two channels — correct at team scale, ceremony at one-operator scale.
  — **Reversibility:** reversible.

### Claude's Discretion

The author answered "you decide" to twelve of the sixteen questions asked — every question in the
Trigger job, Menu + formatting, and Webhook wiring areas. All twelve are resolved above as recorded
decisions with their rationale, not left open. What genuinely remains at the planner's and
implementer's discretion:

- Function names and file organisation inside `Code.gs` — whether the watchdog, the formatter, the
  trigger installer, and the webhook poster are four functions or five, and their ordering.
- The exact `UrlFetchApp.fetch` payload shape: a plain `{content: "..."}` JSON body is sufficient;
  a Discord embed is permitted but not required, and `muteHttpExceptions` handling is the
  implementer's call so long as a non-2xx response is logged rather than swallowed.
- Menu label wording and the top-level menu name (`CreatorPulse` is the assumed default).
- The precise green and red colours for D-11's rules.
- Whether the stale threshold and fire time are `const` declarations at the top of the file or
  inline — top-of-file constants are preferred for the walkthrough, not mandated.
- `appsscript.json` contents beyond what is required: timezone (`Asia/Manila`) and runtime V8
  are load-bearing; everything else is default.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Binding project rules

- `.claude/CLAUDE.md` — the hand-written "Hard Rules" block above the GSD markers, authoritative
  over the generated sections below it in the same file. **Hard Rule 2 is amended by D-02 as part
  of this phase** — read the amended text, not a remembered version of it. Rules 1 (VPS/systemd)
  and 3 (Discord Developer Portal) are untouched and still bind. The merge rule — "nothing enters
  the repo that the author cannot explain out loud" — is the reason D-03 exists and is the single
  rule this phase is most at risk of violating.
- `.planning/PROJECT.md` — constraints and the Key Decisions table. "The database is the source of
  truth; the Sheet is a disposable view. Only the Status column is human-owned" is the rule every
  decision here obeys: Phase 5 reads the Sheet and writes formatting, and writes no data.

### Scope

- `.planning/ROADMAP.md` §"Phase 5: Apps Script" — the goal, the five success criteria, and the
  Notes. **The `Owner:` line and the "entirely human-built" note are amended by D-02.** All five
  criteria stand unchanged; criterion 5 is reinforced by D-03 rather than relaxed.
- `.planning/ROADMAP.md` §"Cut Order" — items 2 and 3 are spent (Phase 4). **Phase 5 is marked
  never-cut.** Nothing in this phase may be dropped to save time; the ownership change (D-01) is
  the concession that was made instead, and it is the only one available.
- `.planning/ROADMAP.md` §"Definition of Green" — `ruff format --check .`, `ruff check .`,
  `mypy src/`, `pytest`, **plus** the manual gate from Phase 3 onward. Note the shape of the gate
  here: the four commands cover Python, and this phase adds no Python — so they must still pass
  (nothing regresses) but they prove nothing about the Apps Script. **This phase is closed almost
  entirely by the human-observed gate**, which for Phase 5 means a real Discord message produced by
  a real Status edit.
- `.planning/REQUIREMENTS.md` §"Apps Script" — SCRIPT-01 through SCRIPT-04. The heading carries
  *"(entire category human-built — the agent does not generate these)"*; **that parenthetical is
  superseded by D-01 and needs updating alongside the other two files.**
- `.planning/REQUIREMENTS.md` §"Out of Scope" — "Sheet cells as a second source of truth" is the
  row that makes column G the single human-owned exception, and D-12 is what keeps it that way.

### Prior phase context — the frozen contract this phase binds to

- `.planning/phases/04-playwright-sheets/04-CONTEXT.md` — **read D-02, D-03, D-04, and D-05 before
  writing a line.** D-03 freezes the seven columns *and the tab name* `Dashboard`, and states the
  ceiling explicitly: inserting a column shifts Status out from under this phase's
  `e.range.getColumn()` check. D-02 explains why Twitch arriving later means more rows, not more
  columns — which is why `E2:E1000` in D-11 is safe. D-04 confirms the Python write is
  `A1:F{n+1}` with `USER_ENTERED`, so column E holds real numbers that a numeric format rule can
  key on, and column G is never touched. D-05 explains the `—` placeholder that D-11 relies on
  being non-numeric.
- `.planning/phases/02-vps-systemd/02-CONTEXT.md` — **D-09** (08:00 Asia/Manila = 00:00 UTC, the
  arithmetic behind D-06's fire time) and **D-12, still binding despite D-01:** the systemd unit
  and timer files may be read and must never be written or edited by the agent.
- `.planning/phases/01-skeleton/01-CONTEXT.md` — the four-command gate and the fixtures-only rule.
  Relevant here mainly as a constraint on what Phase 5 must not break.

### Technical grounding

- `.planning/research/PITFALLS.md` §6 — the warning against reordering Dashboard columns. This
  phase is the reason that warning exists.
- `.planning/research/PITFALLS.md` §18(d) — the silently stale Sheet. D-05's watchdog is the direct
  answer to it, and D-13's throw-on-missing-property follows the same logic.
- `.planning/research/ARCHITECTURE.md` §"Internal Boundaries" — the Apps Script row, which states
  the Python side's only obligation to this phase: the Status column's location and format stay
  stable. Phase 4 delivered that; this phase consumes it.
- `.planning/STATE.md` §"Blockers/Concerns" — the outstanding Phase 3 droplet UAT. Relevant
  because D-08's forced watchdog proof does *not* depend on it: the watchdog reads the Sheet, and
  the Sheet already holds rows.

### External APIs used by this phase

No Google or Discord documentation has been fetched for this phase yet. The research step should
verify, against `developers.google.com/apps-script` and Discord's webhook documentation:
simple-vs-installable trigger authorization limits (see Specific Ideas below), `ScriptApp.newTrigger`
builder syntax for both `onEdit` and time-driven triggers, `newConditionalFormatRule` syntax,
`PropertiesService` access, and the Discord webhook JSON payload shape and rate limit.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

This phase writes JavaScript, not Python, so it reuses no Python code. What it consumes is the
Sheet's *shape*, produced by:

- **`src/creatorpulse/sheets.py`** — the module that owns the `A1:F{n+1}` write. Read it to confirm
  the exact header strings and the column order before binding to them; do not modify it. The
  `DELTA_PLACEHOLDER` constant is the `—` that D-11 relies on being non-numeric.
- **The live Sheet itself** — id `1hP7rZqq9Z-QnYGCkt8uhNK1yiwF3dsM9e-T2sYQOqQI`, tab `Dashboard`.
  It currently holds three synthetic seed rows plus a `G2` test marker, deliberately left in place
  as SHEET-06 evidence (STATE.md). Those rows are enough to develop and demo against — the
  watchdog and the `onEdit` handler need rows, not *real* rows.

### Established Patterns

- **No new dependencies.** Applies to `clasp` (D-04) as much as to pip packages.
- **Secrets never enter the repo** (Phase 1, Phase 2 D-09). D-13 is this rule applied to the
  webhook URL.
- **Fail loudly, never silently** (Phase 3 D-16, Phase 4 D-07, PITFALLS.md §18(d)). D-13's
  throw-on-missing-property and the non-2xx logging in Claude's Discretion both follow it.
- **The four-command gate must still pass** even though this phase adds no Python — `ruff format
  --check .` will see the new `apps-script/` directory. Confirm `.gs` and `.json` files there are
  outside ruff's and mypy's reach, or excluded, before closing the phase.

### Integration Points

- **`apps-script/Code.gs` → the `Dashboard` tab** — reads columns A, B, E, F; writes formatting to
  E and nothing else. Never writes a data cell.
- **`apps-script/Code.gs` → Discord webhook** — `UrlFetchApp.fetch`, two callers (watchdog, onEdit),
  one URL from Script Properties.
- **Phase 6 consumes D-16** — the bot posts to the same channel. It does *not* share the webhook;
  a bot token and a webhook are different credentials. Phase 6 must not assume this phase created
  anything it can reuse beyond the channel itself.
- **Nothing in Phase 5 is imported by Python.** The two layers meet only at the Sheet.

</code_context>

<specifics>
## Specific Ideas

- **The simple-vs-installable `onEdit` trap — verify this first, it dictates the design.** A
  *simple* trigger (a function literally named `onEdit`) runs without authorization to make
  external requests, so it **cannot call `UrlFetchApp`**. SCRIPT-03 therefore requires an
  **installable** `onEdit` trigger bound to a differently-named function (e.g. `onStatusEdit`),
  created via `ScriptApp.newTrigger(...).forSpreadsheet(...).onEdit().create()` or the Triggers
  panel. This is the most common way this exact feature fails, and it fails *silently* — the
  handler runs, the fetch throws, and nothing reaches Discord. **The research step must confirm
  this against current Apps Script documentation rather than trusting this note.** D-09's
  *Install triggers* menu item exists largely to make this correct-by-construction.
- **`e.user.getEmail()` is not reliable** — it returns blank in many configurations even for
  installable triggers. D-14 deliberately does not put the editor's identity in the message. Do not
  add it back on the assumption it will populate.
- **Prove SCRIPT-03 the way criterion 2 words it** — "the author edits a Status cell and a Discord
  message appears within seconds — observed live, not inferred from logs." Type into `G3`, watch
  Discord. That is the requirement's entire content and it is a ten-second proof. It is also the
  best demo moment in the project; ROADMAP's Notes say to rehearse it, and that advice survives the
  ownership change intact — arguably it matters more now.
- **`05-UAT.md` follows the `04-UAT.md` pattern**, with one addition unique to this phase: D-03's
  written explanation of the `onEdit` event object and the webhook call, in the author's own words,
  as the evidence for criterion 5. Screenshots are appropriate here in a way they were not for
  earlier phases — criterion 4 explicitly names the Apps Script execution log, which has no CLI
  output to paste.
- **Three files need amending before or during planning, and the planner should not silently absorb
  it** (D-02): `.claude/CLAUDE.md` Hard Rule 2, ROADMAP.md's Phase 5 `Owner:` line and Notes, and
  REQUIREMENTS.md's "*(entire category human-built)*" parenthetical under §Apps Script. All three
  currently assert the agent does not write this code.
- **Check ruff's and mypy's reach over the new `apps-script/` directory** before closing. The gate
  is four commands and it must stay green; a new top-level directory of `.gs` and `.json` files is
  exactly the kind of thing that trips `ruff format --check .` on an unexpected file.

</specifics>

<deferred>
## Deferred Ideas

- **A data-validation dropdown on column G.** Declined by D-12 — it would alter a frozen,
  human-owned column and invalidate the SHEET-06 proof already recorded. Cheap to add later if the
  Status vocabulary ever stabilises into a fixed set.
- **A stale-row conditional format keyed on column F.** Declined by D-11 — the watchdog already
  reports staleness where it will be seen. Revisit only if the Sheet is ever watched without
  Discord alongside it.
- **A daily heartbeat message from the watchdog.** Declined by D-07 — the execution log is the
  liveness proof criterion 4 already demands. Revisit if the watchdog ever silently stops and the
  execution log turns out not to be checked in practice.
- **Two webhooks / two channels**, separating ops alerts from human signal. Declined by D-16 as
  ceremony at one-operator scale. Correct at team scale.
- **`clasp` for repo↔Sheet sync.** Declined by D-04 — Node plus a new toolchain, against the
  no-new-dependencies rule, to automate a sync that happens perhaps three times. Revisit only if
  the Apps Script layer ever grows past one file.
- **A Discord embed instead of a plain-content message.** Left to the implementer (Claude's
  Discretion) rather than deferred, but noted here: if the plain message ships, an embed is a
  cosmetic upgrade with no design consequences.
- **Putting the editor's identity in the `onEdit` message.** Blocked by `e.user.getEmail()`'s
  unreliability, not by preference. If a future setup makes it reliable, it is a one-line addition.

</deferred>

---

*Phase: 5-Apps Script*
*Context gathered: 2026-08-06*
