# Phase 5: Apps Script - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-06
**Phase:** 5-Apps Script
**Areas discussed:** Ownership split, Trigger job, Menu + formatting, Webhook wiring

**Framing:** the author opened by reclassifying the phase from `human` to `mixed`, citing under ten
hours to the interview. The agent flagged the conflict with `.claude/CLAUDE.md` Hard Rule 2,
ROADMAP's `Owner: human`, and ROADMAP's "the agent does not generate this code" note; the author
reaffirmed. Discussion proceeded on `mixed`.

---

## Ownership split

### Q1 — What does 'mixed' mean concretely for the ~100 lines of Apps Script?

| Option | Description | Selected |
|--------|-------------|----------|
| Draft + you paste | Agent writes the complete `.gs`; author reads it line by line with a walkthrough, then pastes into the Sheets editor. Fastest; criterion 5 met by review, not typing. | ✓ |
| Skeleton + you fill | Agent writes signatures and step comments; author types the bodies. Strongest proof of understanding, slower. | |
| Draft + you retype | Agent writes complete, author retypes by hand from the draft. Middle ground, ~20–30 min cost. | |

**User's choice:** Draft + you paste
**Notes:** → CONTEXT.md D-01.

### Q2 — Do the written ownership rules get amended to record this change?

| Option | Description | Selected |
|--------|-------------|----------|
| Amend both, dated | Update `.claude/CLAUDE.md` Hard Rule 2 and ROADMAP Phase 5 Owner with a dated note saying what changed and why. | ✓ |
| ROADMAP only | Flip Owner in ROADMAP; leave the Hard Rules block alone so the general principle stands. | |
| Neither — CONTEXT.md only | Record the deviation only in CONTEXT.md. | |

**User's choice:** Amend both, dated
**Notes:** → CONTEXT.md D-02. Executed during this session: `.claude/CLAUDE.md`, `.planning/ROADMAP.md`, and additionally `.planning/REQUIREMENTS.md` (whose §Apps Script heading carried the same "human-built" parenthetical) were all amended in place with dated notes.

### Q3 — Criterion 5: keep it, and how is it proven?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep — you write it up | Author writes the explanation into `05-UAT.md` in their own words, unaided. | ✓ |
| Keep — verbal rehearsal | Proven by a live walkthrough in Phase 7's rehearsal; nothing written. | |
| Keep as-is, no extra proof | Criterion stands but the phase closes on the other four. | |

**User's choice:** Keep — you write it up
**Notes:** → CONTEXT.md D-03. This is the control that keeps the ownership change from hollowing out the phase.

### Q4 — Where does the Apps Script source live?

| Option | Description | Selected |
|--------|-------------|----------|
| `apps-script/` in repo | `Code.gs` + `appsscript.json` committed, synced to the Sheets editor by manual copy-paste. No clasp (Node + new dependency). | ✓ |
| Sheets editor only | Code lives only in the bound script; repo gets nothing. | |
| You decide | Agent picks and records the reasoning. | |

**User's choice:** `apps-script/` in repo
**Notes:** → CONTEXT.md D-04. Accepted cost: copy-paste drift between repo and live Sheet, mitigated procedurally.

---

## Trigger job

**Agent's framing before the questions:** the strongest thing a Sheet-side timer can do that the
Phase 6 bot cannot is watch for the collector being dead — the bot runs on the droplet, so a
droplet outage produces silence rather than an alert, while Apps Script runs on Google's
infrastructure.

### Q1 — What does the time-driven trigger actually do?

| Option | Description | Selected |
|--------|-------------|----------|
| Stale-data watchdog | Reads newest column F; alerts to the webhook when older than a threshold. Survives the droplet being dead. | (agent's pick) |
| Sheet-side daily summary | Posts today's numbers to the webhook. Duplicates Phase 6 BOT-01. | |
| Formatting refresh | Re-applies format rules daily. Catches no real failure. | |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **stale-data watchdog** (CONTEXT.md D-05).

### Q2 — When does it fire, and how stale is too stale?

| Option | Description | Selected |
|--------|-------------|----------|
| 09:00 Manila, >26h stale | One hour after the run should finish; tolerates a slow or slightly late run. | (agent's pick) |
| 09:00 Manila, >12h stale | Tighter; higher false-alarm risk on timezone/slow-run edges. | |
| 12:00 Manila, >26h stale | More slack, but a dead collector goes unreported until midday. | |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **09:00 Manila / 26h** (CONTEXT.md D-06).

### Q3 — Does it post on healthy days too?

| Option | Description | Selected |
|--------|-------------|----------|
| Silent unless broken | Posts only when stale. Quiet channel; watchdog liveness proven via the execution log. | (agent's pick) |
| Daily heartbeat either way | Posts every day; proves the watchdog is alive at the cost of a daily message. | |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **silent unless broken** (CONTEXT.md D-07). Deciding factor: ROADMAP criterion 4 already requires opening the Apps Script execution log, which closes the who-watches-the-watchdog gap without a second daily message.

### Q4 — How is criterion 4 proven before the interview?

| Option | Description | Selected |
|--------|-------------|----------|
| Force a stale alert | Hand-edit a column F cell to an old timestamp, run the function manually, watch the alert land. ~2 min. | |
| Wait for the real 09:00 fire | Honest but one shot, and a healthy fire never exercises the alert branch. | |
| Both | Force the alert now; also capture the scheduled fire if the clock allows. | ✓ |

**User's choice:** "you decide twin" — read as both/you-decide; agent selected **Both** (CONTEXT.md D-08). Either reading lands on the same answer, so no ambiguity needed resolving.

---

## Menu + formatting

### Q1 — What goes in the onOpen menu?

| Option | Description | Selected |
|--------|-------------|----------|
| Two items, both reuse | "Check freshness now" + "Re-apply formatting" — second entry points to existing functions, zero new logic. | |
| Two items + setup | The above plus "Install triggers" — `ScriptApp.newTrigger` for both triggers, with a duplicate guard. ~10 lines. | (agent's pick) |
| One item only | Just "Check freshness now". | |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **two items + setup** (CONTEXT.md D-09). Deciding factor: installing the `onEdit` trigger is the most error-prone step in the phase; in code it is reproducible and reviewable rather than a remembered click-sequence.

### Q2 — How do the conditional-format rules get applied?

| Option | Description | Selected |
|--------|-------------|----------|
| By script | `newConditionalFormatRule`, ~15 lines, in the repo, re-runnable, survives tab rebuild. | (agent's pick) |
| Clicked in the UI | Faster now; nothing reviewable, nothing explainable as code, rules die with the tab. | |

**User's choice:** "you decide king" — read as you-decide; agent selected **by script** (CONTEXT.md D-10).

### Q3 — What do the rules highlight?

| Option | Description | Selected |
|--------|-------------|----------|
| Sign on Δ Views | Green >0, red <0, untouched at 0; `—` cells skipped by construction. Range `E2:E1000`. | (agent's pick) |
| Sign + stale row | The above plus a gray/italic whole-row rule keyed on column F. | |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **sign only** (CONTEXT.md D-11). Deciding factor: the stale-row rule restates the watchdog in a second place, and a ±20% rule matching BOT-02 is not viable because column E is an absolute delta, not a percentage.

### Q4 — Status column: free text or fixed values?

| Option | Description | Selected |
|--------|-------------|----------|
| Data validation dropdown | Known values, one-click demo, no typos; adds `setDataValidation`. | |
| Free text, unchanged | Column G stays exactly as Phase 4 left it; handler posts the raw string. | (agent's pick) |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **free text** (CONTEXT.md D-12). Deciding factor: a dropdown alters a frozen, human-owned column and invalidates the SHEET-06 proof already recorded in `04-UAT.md`; the handler must survive arbitrary pasted text either way.

---

## Webhook wiring

**Agent's framing before the questions:** the webhook is created in Discord **Server Settings →
Integrations → Webhooks**, not the Developer Portal — so it sits outside CLAUDE.md Hard Rule 3,
though it remains a step the author clicks. And `e.user.getEmail()` returns blank in many
configurations even for installable triggers, so nothing may depend on it.

### Q1 — Where does the Discord webhook URL live?

| Option | Description | Selected |
|--------|-------------|----------|
| Script Properties | `PropertiesService.getScriptProperties()`; pasted once into the editor panel, never in `Code.gs`, never in the repo. | (agent's pick) |
| Hardcoded, file gitignored | Simpler code, but reverses the in-repo decision and removes the file from the reviewable artifact. | |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **Script Properties** (CONTEXT.md D-13). Deciding factor: D-04 puts `Code.gs` in the repo, so a hardcoded URL would be a committed secret.

### Q2 — What does the onEdit message say?

| Option | Description | Selected |
|--------|-------------|----------|
| Creator + old → new | Row looked up via `e.range.getRow()`; both `e.oldValue` and `e.value`. | (agent's pick) |
| Creator + new value | Same lookup, new value only. | |
| Cell reference only | "G4 changed to Flagged" — does not say which creator. | |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **creator + old → new** (CONTEXT.md D-14). Deciding factor: it exercises exactly the event-object knowledge criterion 5 tests, so the message shape and the criterion reinforce each other.

### Q3 — Does clearing a Status cell post?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, post the clear | Every human touch of column G is visible in Discord. | (agent's pick) |
| No, skip empty | Quieter, but "someone deleted the flag" becomes invisible. | |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **post the clear** (CONTEXT.md D-15). A rule with no exception is easier to state and defend than the same rule with one carved out.

### Q4 — One webhook or two?

| Option | Description | Selected |
|--------|-------------|----------|
| One webhook, one channel | Watchdog and Status edits to the same place, alongside Phase 6's bot. | (agent's pick) |
| Two webhooks | Ops alerts separated from human signal. | |
| You decide | Agent picks and records the reasoning. | ✓ |

**User's choice:** You decide → agent selected **one webhook** (CONTEXT.md D-16). Two channels is correct at team scale, ceremony at one-operator scale.

---

## Claude's Discretion

The author answered "you decide" to twelve of sixteen questions — every question in the Trigger job,
Menu + formatting, and Webhook wiring areas. All twelve are resolved as recorded decisions (D-05
through D-16) with rationale, not left open. What remains genuinely open to the implementer is
listed in CONTEXT.md §"Claude's Discretion": function names and file organisation, the exact
`UrlFetchApp` payload shape, menu label wording, format colours, constant placement, and
`appsscript.json` fields beyond timezone and runtime.

## Deferred Ideas

- Data-validation dropdown on column G (D-12)
- Stale-row conditional format keyed on column F (D-11)
- Daily heartbeat from the watchdog (D-07)
- Two webhooks / two channels (D-16)
- `clasp` for repo↔Sheet sync (D-04)
- A Discord embed instead of a plain-content message (left to the implementer)
- Editor identity in the `onEdit` message — blocked by `e.user.getEmail()` unreliability, not preference
