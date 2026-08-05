# Phase 5: Apps Script - Research

**Researched:** 2026-08-06
**Domain:** Google Apps Script (container-bound, V8 runtime) bound to a Google Sheet; Discord incoming webhooks
**Confidence:** HIGH on the load-bearing trigger-authorization question; MEDIUM on timestamp-parsing specifics (flagged for a one-line empirical check during implementation)

## Summary

The single claim CONTEXT.md flagged as unverified is **confirmed true against primary Google
documentation**: a *simple* trigger — a function literally named `onEdit(e)` — cannot call
`UrlFetchApp.fetch`, because simple triggers run without authorization to reach any service that
requires it (Gmail, Drive, UrlFetchApp, etc.). SCRIPT-03 must use an **installable** `onEdit`
trigger, created via `ScriptApp.newTrigger(functionName).forSpreadsheet(ss).onEdit().create()`,
bound to a differently-named function (e.g. `onStatusEdit`). D-09's *Install triggers* menu item is
exactly the right shape of fix — it makes the correct trigger type the only one that ever gets
created, removing the failure mode by construction rather than by documentation.

The rest of the phase is standard, well-documented Apps Script: `ScriptApp.newTrigger()` builders
for both trigger kinds, `SpreadsheetApp.newConditionalFormatRule()` for the delta-column
highlighting, `PropertiesService.getScriptProperties()` for the webhook URL, and a one-field JSON
POST to Discord's webhook endpoint. One genuine unknown remains and could not be resolved from
documentation alone: whether the exact ISO-8601 string Python writes into column F round-trips
through Google Sheets as a `Date` object or lands as plain text under `USER_ENTERED`. Evidence
points toward **plain text** — Sheets does not reliably parse the `+00:00` timezone-offset suffix
Python's `datetime.isoformat()` produces — which changes how the watchdog must read column F. This
is flagged MEDIUM confidence and the plan should include a two-minute empirical check (write one
real row, read the cell in the Apps Script editor, `Logger.log(typeof value, value)`) before
committing to a parsing strategy.

**Primary recommendation:** Build the installable `onEdit` trigger and the daily time-driven
trigger exactly as D-09 describes, via `ScriptApp.newTrigger`, guarded by a delete-then-recreate
pass over `ScriptApp.getProjectTriggers()`. Treat column F as a string on the Apps Script side
unless the empirical check proves otherwise, and parse it with `new Date(rawString)` — V8's `Date`
constructor is lenient enough to handle Python's ISO-8601 output in the common case, but confirm
before trusting it for the 26-hour threshold math.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Custom menu (`onOpen`) | Google Apps Script (bound to Sheet) | — | Runs entirely inside the Sheets UI; no server-side counterpart exists in this project |
| Stale-data watchdog (time-driven trigger) | Google Apps Script (Google's infrastructure) | — | Deliberately placed outside the droplet (D-05) — it must survive the failure it watches for |
| `onEdit` → Discord webhook | Google Apps Script (installable trigger) | Discord (webhook receiver) | Apps Script owns the event read and the HTTP call; Discord is a passive HTTP endpoint, not a peer service in this project |
| Conditional formatting | Google Apps Script | Google Sheets rendering engine | Script writes rules once; Sheets' own rendering evaluates them on every subsequent cell change with no further script involvement |
| Dashboard data (columns A-F) | Python collector / `sheets.py` (already built, Phase 4) | — | Phase 5 reads this tier's output; it never writes data cells |
| Status column (G) | Human (Sheets UI) | Apps Script (reader only) | Column G is the one human-owned exception in the whole system; Apps Script reads it, never writes it |

## User Constraints

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

All sixteen decisions D-01 through D-16 in `05-CONTEXT.md` are locked. Summarized by area (full text
in CONTEXT.md — read it in full before planning):

**Ownership (D-01, D-02, D-03, D-04):** Phase 5 ownership is `mixed` as of 2026-08-06 — the agent
writes `apps-script/Code.gs` and `apps-script/appsscript.json`; the author reads, is walked through
it, pastes it into the Sheets editor by hand (no `clasp`), and must write an unaided explanation of
the `onEdit` event object and webhook call into `05-UAT.md` (criterion 5, unchanged). VPS/systemd
(Phase 2 D-12) and Discord Developer Portal setup (Phase 6) remain human-built — untouched by this
amendment.

**Time-driven trigger / watchdog (D-05 through D-08):** A stale-data watchdog, not a digest. Reads
the newest column F timestamp; if older than 26 hours, posts a "collector has not run since X"
alert. Fires 09:00 Asia/Manila. Silent when healthy (no heartbeat). Proven twice: forced (hand-edit
a stale F cell, run manually, watch Discord, let next sync overwrite it) and, opportunistically, the
natural 09:00 fire captured via the execution log.

**Menu and formatting (D-09 through D-12):** Three `onOpen` menu items — *Check freshness now*,
*Re-apply formatting*, *Install triggers* (delete-then-recreate guard against duplicates).
Conditional formatting applied only by script (`newConditionalFormatRule`, ~15 lines), keyed purely
on the sign of column E (green `> 0`, red `< 0`, untouched at `0`), applied to `E2:E1000`. No
stale-row format rule. Column G stays free text — no data-validation dropdown.

**Webhook path (D-13 through D-16):** Webhook URL lives in Script Properties
(`DISCORD_WEBHOOK_URL`), never in `Code.gs`. Missing property throws a named error. Message names
creator, source, and both values: `xqc / youtube — Status: (blank) → Flagged`, read via
`e.range.getRow()` for columns A/B and `e.oldValue`/`e.value` for the change. Clearing a cell posts
too (`(cleared)`). Missing `e.oldValue` on a multi-cell edit renders as `(blank)`, never assumed.
One webhook, one channel, shared later with Phase 6's bot (different credential, same channel).

### Claude's Discretion

- Function names and file organisation inside `Code.gs` (four vs. five functions, ordering).
- Exact `UrlFetchApp.fetch` payload shape: plain `{content: "..."}` is sufficient; an embed is
  permitted but not required; `muteHttpExceptions` handling is the implementer's call so long as a
  non-2xx response is logged, not swallowed.
- Menu label wording and top-level menu name (`CreatorPulse` assumed default).
- Exact green/red colours for the D-11 formatting rules.
- Whether the 26-hour threshold and 09:00 fire time are top-of-file `const` declarations
  (preferred, not mandated) or inline.
- `appsscript.json` contents beyond timezone (`Asia/Manila`, load-bearing) and V8 runtime
  (load-bearing) — everything else defaults.

### Deferred Ideas (OUT OF SCOPE)

- A data-validation dropdown on column G (D-12).
- A stale-row conditional format keyed on column F (D-11) — the watchdog already covers it.
- A daily heartbeat message from the watchdog (D-07).
- Two webhooks / two channels (D-16).
- `clasp` for repo↔Sheet sync (D-04).
- Putting the editor's identity in the `onEdit` message — blocked by `e.user.getEmail()`
  unreliability, not preference.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCRIPT-01 | Sheet has an `onOpen` custom menu | `onOpen(e)` simple trigger is sufficient — building a `Ui.Menu` and calling `.addToUi()` requires no authorization, so this stays a simple trigger unlike SCRIPT-03. See Pattern 1. |
| SCRIPT-02 | A time-driven trigger runs on schedule | `ScriptApp.newTrigger(fn).timeBased().atHour(9).everyDays(1).inTimezone('Asia/Manila').create()`, installed via the *Install triggers* menu item (D-09), guarded against duplicates via `getProjectTriggers()`/`deleteTrigger()`. See Pattern 2 and Code Examples. |
| SCRIPT-03 | Editing a Status cell posts to a Discord webhook via `onEdit` | **The load-bearing finding of this research**: requires an *installable* `onEdit` trigger, not a simple one, because `UrlFetchApp` needs authorization a simple trigger cannot obtain. See Pattern 1 (Anti-Pattern) and Common Pitfalls §1. |
| SCRIPT-04 | Conditional formatting highlights day-over-day movement on the Dashboard | `SpreadsheetApp.newConditionalFormatRule()` with `whenNumberGreaterThan(0)` / `whenNumberLessThan(0)`, applied via `setConditionalFormatRules()` with a freshly-built array each run (never `.push()` onto the existing array) to avoid duplicate accumulation. See Pattern 3. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Google Apps Script (V8 runtime) | V8 (current default; declare explicitly in manifest) | Runs `Code.gs`, bound to the Sheet | The only scripting layer Google Sheets natively hosts; no alternative exists for this requirement set |
| `appsscript.json` manifest | schema version 1 (implicit — no version field) | Declares timezone, runtime, OAuth scopes, exception logging | Required file for any Apps Script project; container-bound scripts get a default one that must be made visible via Project Settings to edit manually |

No package manager, no `npm install`, no `pip install` — Apps Script has no dependency system for
this project's scope. **Package Legitimacy Audit is not applicable to this phase** (see below).

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Discord Webhook HTTP API | current (no versioning scheme) | Receives the alert/notification POST | `POST /webhooks/{id}/{token}` — see Code Examples |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual copy-paste sync (D-04) | `clasp` (Node CLI) | Automates repo↔editor sync but needs a Node toolchain — explicitly rejected by D-04 as a new dependency for a sync that happens ~3 times total |
| Plain `{content: "..."}` webhook payload | Discord embed object | Embeds look nicer (color bar, fields) but add a payload shape to explain for zero functional gain — left to implementer discretion, not required |
| Script Properties for the webhook URL | Hardcoding the URL in `Code.gs` | Hardcoding would commit a secret the moment the file enters the repo (D-04's whole premise) — never acceptable here |

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages, npm modules, or pip packages. Apps
Script projects in this shape (container-bound, no `npm`/`clasp` toolchain per D-04) have no
package manifest and no dependency tree to audit. The only "install" step is a human pasting
`Code.gs` into the Sheets-bound Apps Script editor — a copy-paste, not a package installation.

## Architecture Patterns

### System Architecture Diagram

```
Python collector (Phase 3/4, already built)
        │
        │  worksheet.update(A1:F{n+1}, USER_ENTERED)   [daily, ~08:00 Manila]
        ▼
┌─────────────────────────────────────────────┐
│  Google Sheet — "Dashboard" tab              │
│  A:Creator B:Source C:Followers D:Views      │
│  E:Δ Views F:Last updated  G:Status (human)  │
└───────────────┬───────────────┬─────────────┘
                │                │
   onOpen (simple trigger)   onEdit on column G
   builds CreatorPulse menu  (installable trigger,
        │                     bound function e.g.
        │                     onStatusEdit)
        ▼                          │
  ┌──────────────┐                 ▼
  │ Menu items:  │        reads e.range, e.oldValue,
  │ 1. Check     │        e.value; reads row's A/B via
  │    freshness │        e.range.getRow()
  │ 2. Re-apply  │                 │
  │    formatting│                 ▼
  │ 3. Install   │        UrlFetchApp.fetch(webhook,
  │    triggers  │          {content: "xqc / youtube —
  └──────┬───────┘           Status: (blank) → Flagged"})
         │                          │
         ▼                          │
  ScriptApp.newTrigger(...)         │
  .timeBased().atHour(9)            │
  .everyDays(1)                     │
  .inTimezone('Asia/Manila')        │
  .create()   ──────┐               │
                     │               │
                     ▼               ▼
         ┌───────────────────────────────────┐
         │  Time-driven trigger (installable) │
         │  fires 09:00 Manila daily          │
         │  reads newest column F timestamp   │
         │  if stale > 26h: UrlFetchApp.fetch │
         │  (webhook, "collector has not run  │
         │  since X")                         │
         └───────────────┬─────────────────────┘
                          │
                          ▼
              PropertiesService.getScriptProperties()
              .getProperty('DISCORD_WEBHOOK_URL')
                          │
                          ▼
              ┌───────────────────────┐
              │  Discord channel      │
              │  (webhook receiver;   │
              │  Phase 6 bot posts    │
              │  to same channel via  │
              │  a different token)   │
              └───────────────────────┘
```

### Recommended Project Structure

```
apps-script/
├── Code.gs           # onOpen, watchdog, formatter, trigger installer, webhook poster
└── appsscript.json    # timeZone: Asia/Manila, runtimeVersion: V8, oauthScopes if narrowed
```

One file is enough for ~100 lines (D-09's own estimate); the "four or five functions" split is
Claude's Discretion, not an architectural decision. A reasonable split, in file order:

```javascript
// 1. onOpen(e)                — simple trigger, builds the menu (SCRIPT-01)
// 2. checkFreshness()         — the watchdog body (SCRIPT-02), called by both the menu
//                                item and the time-driven trigger
// 3. applyFormatting()        — SCRIPT-04, called by both the menu item and (optionally)
//                                at the end of checkFreshness() or a separate installer step
// 4. installTriggers()        — SCRIPT-02's ScriptApp.newTrigger calls, delete-then-recreate
// 5. onStatusEdit(e)          — installable trigger target for SCRIPT-03, NOT named onEdit
// 6. postToDiscord(message)   — shared UrlFetchApp.fetch wrapper, used by checkFreshness()
//                                and onStatusEdit()
```

### Pattern 1: Simple trigger vs. installable trigger

**What:** Apps Script recognizes two kinds of event handlers. A *simple* trigger is any function
literally named `onOpen`, `onEdit`, `onInstall`, etc. Google runs it automatically with no setup —
but simple triggers execute with restricted authorization and **cannot call any service that
requires authorization**, including `UrlFetchApp`, `GmailApp`, and `DriveApp`. An *installable*
trigger is a handler explicitly registered via `ScriptApp.newTrigger(...)`, bound to a function of
any name, and runs with the full authorization the script's owner granted at setup time.

**When to use:**
- Simple trigger (`onOpen`): the menu build (SCRIPT-01) — no external call, no authorization needed.
- Installable trigger: the `onEdit`-driven webhook (SCRIPT-03, needs `UrlFetchApp`) and the
  time-driven watchdog (SCRIPT-02, needs `UrlFetchApp` and runs on a schedule simple triggers
  cannot express at all — there is no "simple" time-based trigger).

**Example:**
```javascript
// Source: developers.google.com/apps-script/guides/triggers (simple trigger restriction),
// developers.google.com/apps-script/guides/triggers/installable (installable syntax)

// SCRIPT-01 — simple trigger, no authorization needed, runs automatically
function onOpen(e) {
  SpreadsheetApp.getUi()
    .createMenu('CreatorPulse')
    .addItem('Check freshness now', 'checkFreshness')
    .addItem('Re-apply formatting', 'applyFormatting')
    .addItem('Install triggers', 'installTriggers')
    .addToUi();
}

// SCRIPT-02 + SCRIPT-03 — installable triggers, created once via installTriggers()
function installTriggers() {
  const ss = SpreadsheetApp.getActive();

  // Duplicate-guard (D-09): delete every trigger this project owns before recreating
  ScriptApp.getProjectTriggers().forEach(function (t) {
    ScriptApp.deleteTrigger(t);
  });

  ScriptApp.newTrigger('onStatusEdit').forSpreadsheet(ss).onEdit().create();

  ScriptApp.newTrigger('checkFreshness')
    .timeBased()
    .atHour(9)
    .everyDays(1)
    .inTimezone('Asia/Manila')
    .create();
}

// NOT named onEdit — this is the point. A function named exactly onEdit(e) here would
// silently lose the ability to call UrlFetchApp the moment someone also left a bare
// onEdit(e) simple trigger in the file; keeping the name different removes the ambiguity.
function onStatusEdit(e) {
  // handler body — see Pattern 4 for the event object details
}
```

### Anti-Patterns to Avoid

- **A function literally named `onEdit(e)` that calls `UrlFetchApp.fetch`:** this is exactly the
  trap CONTEXT.md flagged. It **is confirmed to fail** — simple triggers cannot reach authorized
  services. The failure mode is not a clean error dialog; see Common Pitfalls §1 for where it
  actually surfaces.
- **Accumulating conditional format rules by reading-then-appending on every "Re-apply formatting"
  click:** calling `sheet.getConditionalFormatRules()`, pushing a new rule, then
  `setConditionalFormatRules()` on that grown array will duplicate the green/red rules every time
  the menu item runs. Build a fresh two-rule array each time and pass it whole to
  `setConditionalFormatRules()` — that call *replaces* the sheet's rule set, it does not merge.
- **Creating triggers without the duplicate-guard:** clicking *Install triggers* twice without
  first deleting existing triggers creates two `onEdit` triggers and two daily triggers — the
  webhook then posts twice per edit and the watchdog checks twice per day. D-09's design
  (`getProjectTriggers()` + `deleteTrigger()` loop before `newTrigger()`) exists specifically to
  prevent this.

### Pattern 2: `ScriptApp.newTrigger` builder syntax

**What:** A fluent builder. `.forSpreadsheet(ss)` (or `.forSpreadsheet(spreadsheetId)`) plus
`.onEdit()`/`.onOpen()`/`.onChange()` builds an event-driven trigger; `.timeBased()` plus
`.atHour()`, `.everyDays()`, `.inTimezone()` (etc.) builds a clock trigger. `.create()` finalizes
and registers it.

**When to use:** Any time a trigger must be created or recreated programmatically (D-09's *Install
triggers* menu item is the only place this fires in this phase).

**Example:**
```javascript
// Source: developers.google.com/apps-script/guides/triggers/installable,
// developers.google.com/apps-script/reference/script/clock-trigger-builder

// Installable onEdit, bound to the active/container spreadsheet
ScriptApp.newTrigger('onStatusEdit')
  .forSpreadsheet(SpreadsheetApp.getActive())
  .onEdit()
  .create();

// Daily time-driven trigger. atHour(9) means "runs sometime in the 09:00-10:00 window",
// not exactly on the hour — Google's docs are explicit that time-driven triggers fire
// within an hour-wide window, not at a precise minute.
ScriptApp.newTrigger('checkFreshness')
  .timeBased()
  .atHour(9)
  .everyDays(1)
  .inTimezone('Asia/Manila')
  .create();

// Enumerate and delete — the duplicate-guard
ScriptApp.getProjectTriggers().forEach(function (trigger) {
  ScriptApp.deleteTrigger(trigger);
});
```

**Authorization:** The first time a script creates an installable trigger (or is run at all, if it
calls `UrlFetchApp`), the editor shows a standard OAuth consent screen listing the scopes the
script needs. There is no separate "permission to create triggers" scope — trigger creation itself
uses whatever scopes the script's code already requires (`spreadsheets.currentonly` for reading the
Sheet, `script.external_request` for `UrlFetchApp`, `script.scriptapp` implicitly for
`ScriptApp.newTrigger`). Installable triggers, once created, **run under the identity of whoever
created them** — for a single-operator project this is a non-issue, but it is the reason a trigger
created by one Google account cannot be silently "taken over" by another.
`[CITED: developers.google.com/apps-script/guides/triggers/installable]`

### Pattern 3: `SpreadsheetApp.newConditionalFormatRule()` for the delta column

**What:** A builder for a single conditional-format rule: a boolean condition
(`whenNumberGreaterThan`, `whenNumberLessThan`, etc.), a format action (`setBackground`), and a
range (`setRanges`). Rules are applied to a sheet as a **whole replacement array** via
`sheet.setConditionalFormatRules(rules)` — not incrementally.

**When to use:** SCRIPT-04, keyed on column E's sign per D-11.

**Example:**
```javascript
// Source: developers.google.com/apps-script/reference/spreadsheet/conditional-format-rule-builder

function applyFormatting() {
  const sheet = SpreadsheetApp.getActive().getSheetByName('Dashboard');
  const deltaRange = sheet.getRange('E2:E1000');

  const positiveRule = SpreadsheetApp.newConditionalFormatRule()
    .whenNumberGreaterThan(0)
    .setBackground('#d9ead3') // light green
    .setRanges([deltaRange])
    .build();

  const negativeRule = SpreadsheetApp.newConditionalFormatRule()
    .whenNumberLessThan(0)
    .setBackground('#f4cccc') // light red
    .setRanges([deltaRange])
    .build();

  // Whole-array replacement — safe to call on every menu click or trigger fire without
  // ever accumulating duplicate rules. Do NOT read getConditionalFormatRules() and push().
  sheet.setConditionalFormatRules([positiveRule, negativeRule]);
}
```

**Non-numeric cells (the `—` placeholder):** `whenNumberGreaterThan`/`whenNumberLessThan` rules
only evaluate cells Sheets recognizes as numbers. A text cell — which is what the em-dash
`DELTA_PLACEHOLDER` produces — does not satisfy either comparison and the rule is skipped for that
cell by construction, exactly as D-11 assumes. This is standard conditional-format behavior
(number-comparison rules silently no-op on non-numeric content; they do not error and do not treat
text as zero). `[CITED: developers.google.com/apps-script/reference/spreadsheet/conditional-format-rule-builder]`
— the specific "non-numeric skip" behavior is well-established Sheets UI behavior applied
identically via the API; no source explicitly states the em-dash case, so treat that one inference
as `[ASSUMED]` at HIGH practical confidence (it is the same rule the Sheets UI's own conditional
formatting exhibits).

### Pattern 4: The installable `onEdit` event object

**What:** The object passed to any `onEdit(e)`-shaped handler (simple or installable — the shape is
identical either way; only the authorization differs).

| Field | Type | Notes |
|-------|------|-------|
| `e.range` | `Range` | The edited range. `e.range.getRow()`, `.getColumn()`, `.getSheet()` all work. |
| `e.value` | `string \| number \| undefined` | New value. **Undefined when the edited range spans more than one cell, or when the cell was cleared.** |
| `e.oldValue` | `string \| number \| undefined` | Old value. **Undefined when the edited range spans more than one cell** (confirmed — official guide: "only available if the edited range is a single cell"), and also reported undefined in some single-cell-clear cases per community bug reports (`issuetracker.google.com/issues/304676293`). |
| `e.source` | `Spreadsheet` | The bound spreadsheet. |
| `e.user` | `User` | The editing user, **unreliably populated** — D-14 already declines to use it. |
| `e.authMode` | `ScriptApp.AuthMode` | `LIMITED` for a simple trigger, full for installable. Not needed by this phase's logic. |
| `e.triggerUid` | `string` | Installable triggers only — not needed by this phase's logic. |

**Confirmed from primary docs:** `[CITED: developers.google.com/apps-script/guides/triggers/events]`
— both `oldValue` and `value` are documented as "only available if the edited range is a single
cell." A paste of multiple cells, a fill-down, or any multi-cell edit leaves both undefined.

**Practical handler shape for SCRIPT-03 (D-14, D-15):**
```javascript
// Source: pattern synthesized from developers.google.com/apps-script/guides/triggers/events
// plus D-14/D-15's message-shape requirements
function onStatusEdit(e) {
  const range = e.range;
  const sheet = range.getSheet();

  // Only react to edits on the Dashboard tab's Status column (G = column 7)
  if (sheet.getName() !== 'Dashboard' || range.getColumn() !== 7) {
    return;
  }

  const row = range.getRow();
  const creator = sheet.getRange(row, 1).getValue(); // column A
  const source = sheet.getRange(row, 2).getValue();  // column B

  const oldVal = e.oldValue !== undefined ? e.oldValue : '(blank)';
  const newVal = e.value !== undefined ? e.value : '(cleared)';

  postToDiscord(creator + ' / ' + source + ' — Status: ' + oldVal + ' → ' + newVal);
}
```

Note the guard on `range.getColumn() !== 7`: without it, *any* edit anywhere on the tab (including
the daily Python sync itself, though that writes via the API not the UI, so it does not fire
`onEdit` at all — API writes via `Sheets.Spreadsheets.Values.update` / gspread do **not** trigger
`onEdit`, only human edits through the Sheets UI do) would be evaluated. The column check is cheap
insurance and directly explains "why does editing column A not post to Discord" if asked in the
walkthrough.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Scheduling a daily job | A time-check inside every script execution, or an external cron-like poller | `ScriptApp.newTrigger().timeBased()...create()` | Apps Script's own trigger service already does this reliably on Google's infrastructure — reinventing it adds nothing and loses the execution-log visibility criterion 4 depends on |
| Retry/backoff for the webhook POST | A custom retry loop with `Utilities.sleep()` | Not needed at this scale — one POST, `muteHttpExceptions: true`, log on non-2xx | A daily watchdog and an occasional Status edit are low-volume enough that a failed POST logging a warning is sufficient; a retry loop adds complexity with no proportionate benefit, and is explicitly left to implementer discretion in CONTEXT.md, not mandated |
| Parsing/validating the Discord webhook URL format | A regex validator | None — just attempt the POST and check the status code | Over-engineering for a value pasted once by hand into Script Properties; a malformed URL will simply fail the fetch and get logged |

**Key insight:** the whole phase is small (~100 lines) precisely because Apps Script's built-in
services (`ScriptApp`, `SpreadsheetApp`, `PropertiesService`, `UrlFetchApp`) already cover every
capability this phase needs. The only "custom" logic is the staleness comparison and the message
string formatting — everything else is direct calls into Google's own trigger, formatting, and
properties APIs.

## Common Pitfalls

### Pitfall 1: The simple-trigger authorization trap (SCRIPT-03's central risk)

**What goes wrong:** A function named exactly `onEdit(e)` is auto-recognized by Apps Script as a
simple trigger. If it calls `UrlFetchApp.fetch(...)`, the call throws.

**Why it happens:** Simple triggers run with `ScriptApp.AuthMode.LIMITED` — no consent-gated
service access, by design (Google's security model prevents a script from silently exfiltrating
data the moment someone opens/edits a file they were merely given view access to, since simple
triggers can run for *any* user who edits the file, not just the script's owner).

**How to avoid:** Never name the Status-column handler `onEdit`. Register it as an installable
trigger under any other name (`onStatusEdit` in this research's examples) via
`ScriptApp.newTrigger(...).forSpreadsheet(ss).onEdit().create()`. D-09's *Install triggers* menu
item is the mechanism that guarantees this — as long as the trigger is always created through that
function and never hand-added in the Triggers panel under the wrong function name.

**Warning signs / failure mode when misconfigured:** This is the pitfall's sharpest edge. Evidence
from multiple sources agrees the failure is at minimum **not obviously loud**:
- The Executions panel (clock icon, left sidebar of the Apps Script editor) will show the run with
  a red error — this is the authoritative place to look. `[CITED: developers.google.com/apps-script/guides/support/troubleshooting synthesis]`
- Whether the *editing user in the Sheets UI* additionally sees any visible toast/alert at the
  moment of the failed edit could not be confirmed from documentation in this session — sources
  disagree/are silent on this specific UI-surfacing question. **`[ASSUMED — LOW confidence]`: treat
  it as effectively silent from the editor's point of view** (no popup dialog), and rely on the
  Executions log as the diagnostic tool. This matters for planning: a task verifying SCRIPT-03
  should explicitly check the Executions log after the first test edit, not just watch Discord and
  assume success/failure from that alone.
- **This entire failure mode is avoided by construction** if the handler is only ever installed via
  D-09's menu item, since that always creates the installable form. The pitfall matters for
  understanding *why* the design looks the way it does (criterion 5's walkthrough), not as a
  residual risk once built correctly.

### Pitfall 2: Conditional format rules accumulating on repeated "Re-apply formatting" clicks

**What goes wrong:** If `applyFormatting()` reads the existing rules, appends new ones, and writes
the grown array back, every click doubles the rule count. Behavior may look identical at first
(the first-matching rule wins visually) but the sheet accumulates dead weight and `sheet.getConditionalFormatRules().length` grows unbounded.

**Why it happens:** `setConditionalFormatRules()` is a full replace, not a merge — but
`getConditionalFormatRules()` + `push()` + `setConditionalFormatRules()` is a very natural (wrong)
pattern to reach for if you think of it as "adding" a rule.

**How to avoid:** Always construct the complete two-rule array fresh inside `applyFormatting()` and
pass that literal array to `setConditionalFormatRules()`. Never read the existing rules first.

**Warning signs:** Re-running the menu item and then checking Format > Conditional formatting in
the Sheets UI shows more than 2 rules in the sidebar list.

### Pitfall 3: Trusting `Session.getScriptTimeZone()` / manifest `timeZone` for the wrong thing

**What goes wrong:** Assuming the manifest's `timeZone` field controls anything about how a
JavaScript `Date` object is displayed when logged or compared, when it actually governs
`Utilities.formatDate()` defaults and the timezone `ClockTriggerBuilder.atHour()` schedules
against. `inTimezone('Asia/Manila')` on the trigger builder is what actually pins the 09:00 fire
time to Manila local time — it does not implicitly inherit from the manifest's `timeZone` unless
you omit `.inTimezone()` entirely (in which case it falls back to the script's timezone, which is
the manifest value). D-06 already calls for setting both explicitly and 09:00 is unambiguous either
way, but this is worth stating plainly for the walkthrough: **two settings, not one**, both need to
agree.

**How to avoid:** Set `timeZone: "Asia/Manila"` in `appsscript.json` **and** call
`.inTimezone('Asia/Manila')` on the trigger builder. Redundant but correct — the second is the one
that actually matters for `atHour()`.

### Pitfall 4: Assuming column F arrives as a `Date` object

**What goes wrong:** Writing `checkFreshness()` logic assuming `sheet.getRange('F2:F100').getValues()`
returns JavaScript `Date` objects (as it would for a cell Sheets recognizes as a date/time), then
doing `Date.now() - cellDate.getTime()` directly.

**Why it happens:** `USER_ENTERED` *does* cause Sheets to auto-convert recognizable date/time
strings into real Date-typed cells — but Python's `datetime.now(UTC).isoformat()` produces a string
like `2026-08-06T00:12:34.567891+00:00`: a `T` separator plus a `+00:00` timezone-offset suffix.
Evidence gathered in this research session (web search synthesis, not a live test) indicates Google
Sheets' date-recognition parser **does not reliably accept the `+00:00` offset suffix** and is
likely to leave the cell as plain text under `USER_ENTERED`, the same way it would leave any
unrecognized string as text. `[ASSUMED — MEDIUM confidence, not verified live this session]`

**How to avoid:** Do not assume either outcome. Add a one-line empirical check to the plan before
writing `checkFreshness()`'s date-math: after the next real `creatorpulse sync`, open the Apps
Script editor and run `Logger.log(typeof sheet.getRange('F2').getValue())` (or read it via the
`onOpen`/menu flow). If it logs `"object"` (a `Date`), arithmetic is direct
(`Date.now() - cell.getTime()`). If it logs `"string"`, parse with `new Date(rawString)` — V8's
`Date` constructor is generally lenient about extra fractional-second digits and the `+00:00`
suffix (unlike Sheets' own cell-type parser), but this too should be confirmed by logging
`new Date(rawString).getTime()` and checking it is not `NaN` before trusting the 26-hour comparison
against it. If `NaN`, the fallback is a manual split (`rawString.split('.')[0].replace('T', ' ')`
type truncation, or a stricter regex) — a ~3-line addition, not a redesign.

**Warning signs:** The watchdog reports "stale" every single day regardless of the real collector
run time (a `NaN` comparison is always `false` in a `>` check, meaning `NaN > threshold` is
`false`, which would make the watchdog **never** fire — the more dangerous silent-failure direction,
since D-07 requires silence-unless-broken and a broken date parse would produce exactly that silence
even during a real outage). This is the single most important thing to verify empirically before
trusting D-08's forced-proof test.

## Code Examples

### `appsscript.json` — minimal correct manifest

```json
// Source: developers.google.com/apps-script/manifest, synthesized with D-06/D-13's requirements.
// timeZone and runtimeVersion are load-bearing per CONTEXT.md's Claude's Discretion section;
// oauthScopes is left implicit (Apps Script's default scope-detection covers
// SpreadsheetApp/ScriptApp/PropertiesService/UrlFetchApp usage without an explicit array in the
// common case — explicit oauthScopes are only required if you want to NARROW below what the
// code would otherwise request). Omit oauthScopes unless a narrower scope set becomes desirable.
{
  "timeZone": "Asia/Manila",
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8"
}
```

To edit this file directly in the Sheets-bound Apps Script editor: **Project Settings** (gear icon,
left sidebar) → check **"Show `appsscript.json` manifest file in editor"**. Container-bound scripts
hide the manifest by default. `[CITED: developers.google.com/apps-script/manifest]`

### PropertiesService — reading the webhook URL, D-13's throw-on-missing

```javascript
// Source: developers.google.com/apps-script/guides/properties, pattern per D-13
function getWebhookUrl() {
  const url = PropertiesService.getScriptProperties().getProperty('DISCORD_WEBHOOK_URL');
  if (!url) {
    // getProperty() returns null for an unset key (not an empty string, not a throw) —
    // this session's tool-fetch of the properties guide did not state this explicitly, so
    // treat the null-vs-empty-string distinction as [ASSUMED — MEDIUM confidence] and verify
    // it once by leaving the property unset and logging typeof getProperty(...) directly.
    throw new Error(
      'DISCORD_WEBHOOK_URL is not set. Project Settings > Script Properties > add ' +
        'DISCORD_WEBHOOK_URL with the Discord webhook URL.'
    );
  }
  return url;
}
```

Setting it by hand: **Project Settings** (gear icon) → **Script Properties** → **Add script
property** → key `DISCORD_WEBHOOK_URL`, value the webhook URL → **Save script properties**. The old
`File > Project properties` menu path from the Rhino-era editor no longer exists.
`[CITED: developers.google.com/apps-script/guides/properties]`

### Posting to Discord

```javascript
// Source: docs.discord.com/developers/resources/webhook, UrlFetchApp usage per
// developers.google.com/apps-script/reference/url-fetch/url-fetch-app
function postToDiscord(message) {
  const url = getWebhookUrl();
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({ content: message }),
    muteHttpExceptions: true, // so a non-2xx response is inspectable, not a thrown exception
  });
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    // Fail loudly per D-13's own reasoning (PITFALLS.md §18(d)) — log, don't swallow.
    console.error('Discord webhook returned ' + code + ': ' + response.getContentText());
  }
}
```

Discord's Execute Webhook endpoint: `POST /webhooks/{webhook.id}/{webhook.token}`. Success is `204
No Content` by default (empty body) — `200 OK` with the created message body only if `?wait=true`
is appended to the URL, which this phase does not need. Content is capped at 2000 characters — well
beyond anything this phase's one-line messages produce. `[CITED: docs.discord.com/developers/resources/webhook]`

Creating the webhook itself (human step, D-13): Discord desktop/web client → target server →
**Server Settings** → **Integrations** → **Webhooks** → **New Webhook** → pick the channel → copy
the **Webhook URL**. `[ASSUMED — this exact click path is standard Discord UI knowledge, not
re-verified against a live Discord client in this research session; confirm on the day, it is a
stable and long-unchanged path]`

### The watchdog's staleness check (illustrative, pending the Pitfall 4 empirical check)

```javascript
// Source: synthesized — no single primary doc covers this composite; follows D-05/D-06/D-08.
const STALE_THRESHOLD_HOURS = 26;

function checkFreshness() {
  const sheet = SpreadsheetApp.getActive().getSheetByName('Dashboard');
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return; // header only, nothing to check

  const timestamps = sheet.getRange(2, 6, lastRow - 1, 1).getValues(); // column F, all data rows
  let newest = null;
  timestamps.forEach(function (row) {
    const raw = row[0];
    const asDate = raw instanceof Date ? raw : new Date(raw); // handles both outcomes of Pitfall 4
    if (!isNaN(asDate.getTime()) && (newest === null || asDate > newest)) {
      newest = asDate;
    }
  });

  if (newest === null) return; // nothing parseable — do not alert on a parse failure as if
                                 // it were staleness; that would misreport the actual problem

  const ageHours = (Date.now() - newest.getTime()) / 3600000;
  if (ageHours > STALE_THRESHOLD_HOURS) {
    postToDiscord(
      'The collector has not run since ' + newest.toISOString() + ' (' +
        Math.round(ageHours) + 'h ago).'
    );
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Rhino runtime, `File > Project properties` for script properties | V8 runtime (default for new projects since ~2020), `Project Settings > Script Properties` | Google migrated Apps Script's default runtime to V8 years ago; the old Rhino-era editor UI paths (including the old properties menu) no longer exist | Any tutorial or blog post referencing `File > Project properties` or non-V8 syntax (`var` instead of modern JS features, no arrow functions) is dated — this research relied on current `developers.google.com` pages, not those older references |

**Deprecated/outdated:** None specific to this phase's scope beyond the runtime/UI note above.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | Column F's ISO-8601 string with `+00:00` offset lands as plain text (not a `Date`) under `USER_ENTERED` | Common Pitfalls §4 | If wrong direction assumed, the watchdog's date math either throws or silently never fires (worse: never fires = D-07's "silent unless broken" masks a real broken state). Mitigated by the empirical check and the `instanceof Date` branch in the Code Example. |
| A2 | `PropertiesService.getScriptProperties().getProperty()` returns `null` (not `undefined`, not throw, not empty string) for an unset key | Code Examples — PropertiesService | Low risk — the `if (!url)` guard in the example catches `null`, `undefined`, and `''` identically; only matters if the code were written to check `=== null` specifically |
| A3 | Whether a failed simple-trigger `UrlFetchApp` call surfaces any visible toast/alert to the editing user in the Sheets UI, versus only in the Executions log | Common Pitfalls §1 | Low practical risk since D-09's design avoids this failure mode entirely by always installing the correct trigger type — relevant only to the walkthrough narrative (criterion 5), not to correctness |
| A4 | The Discord webhook-creation click path (Server Settings → Integrations → Webhooks → New Webhook) is current | Code Examples — Discord section | Low risk, stable UI path; confirm on the day since this is a human-performed step outside the agent's control anyway |
| A5 | Number-comparison conditional format rules skip the em-dash placeholder cell rather than erroring | Pattern 3 | Low risk — this is standard, long-standing Sheets behavior; if wrong, it would be immediately visually obvious (the `—` cell would show a color) and a one-line fix (exclude the row via a custom formula rule) is available |

**Confirmed, not assumed:** The load-bearing claim (simple-trigger `onEdit` cannot call
`UrlFetchApp`) is **not** on this list — it was independently confirmed via both `WebSearch`
synthesis and a direct `WebFetch` of `developers.google.com/apps-script/guides/triggers`, which
states plainly that simple triggers "can't access services that require authorization." This is
`[VERIFIED]` at the ceiling of what a documentation fetch (rather than a live test) can establish.

## Open Questions

1. **Does Python's `datetime.isoformat()` string actually get accepted by V8's lenient `Date`
   constructor once it lands as Sheets text?**
   - What we know: JS `Date.parse` officially supports 3-digit millisecond ISO-8601 with a `Z` or
     `±HH:mm` offset; V8's implementation-defined fallback parser is documented as "very lenient"
     but its exact tolerance for 6-digit microsecond fractions was not confirmed from a primary
     spec source in this session.
   - What's unclear: whether `new Date("2026-08-06T00:12:34.567891+00:00")` parses cleanly in the
     Apps Script V8 sandbox specifically (not just generic browser V8), and whether it silently
     truncates the extra fraction digits or returns `Invalid Date`.
   - Recommendation: the Code Example's `isNaN(asDate.getTime())` guard already defends against
     this; the plan should still include the one-line empirical check from Pitfall 4 as a Wave 0
     task before writing the rest of `checkFreshness()`, since a silent `NaN` here inverts D-07's
     intended failure direction.

2. **Exact rate limit for Discord webhook execution.**
   - What we know: Discord returns `429` with a `retry_after` field when rate-limited; the
     documentation fetched in this session did not state the specific requests-per-second ceiling
     for the webhook execution endpoint.
   - What's unclear: the numeric threshold.
   - Recommendation: irrelevant at this phase's volume (at most a handful of manual Status edits
     plus one daily watchdog check) — no retry/backoff logic is needed, consistent with the
     Don't-Hand-Roll table above. Not worth spending further research budget on.

## Environment Availability

Not applicable in the tool-probe sense — this phase's runtime is Google's hosted Apps Script
environment, not anything installed on the local machine or the droplet. There is nothing to probe
with `command -v` or version checks; access is entirely via a Google account with edit rights on
the Sheet and the Apps Script editor reached through it (**Extensions > Apps Script** in the Sheets
UI).

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Google account with Editor access to the Sheet | All of Phase 5 | Confirmed via Phase 4's live write proof (STATE.md) | — | none needed |
| Discord server + channel for the webhook | SCRIPT-03, SCRIPT-02's alert | Assumed available (Phase 6 will also need it) — creating the webhook itself is a human step this phase depends on but does not perform | — | none — blocking if the author has not yet created a Discord server/channel; confirm before planning tasks that assume a live webhook URL exists |

**Missing dependencies with no fallback:** none identified that block starting the code-writing
work; the Discord webhook URL itself must exist before SCRIPT-03/SCRIPT-02's live-post proof can
close, but the code can be written and reviewed before that URL is pasted into Script Properties.

## Validation Architecture

**Section explicitly not applicable in the usual pytest sense.** `workflow.nyquist_validation` is
enabled in `.planning/config.json`, but this phase adds zero Python and the existing four-command
gate (`ruff format --check .`, `ruff check .`, `mypy src/`, `pytest`) covers no `.gs` file by
design — Apps Script has no unit-test framework this project's stack includes, and adding one
(e.g. a Node-based Apps Script test harness) would violate the no-new-dependencies rule for a
~100-line file whose correctness is proven by direct observation (ROADMAP's Definition of Green:
"a real Discord post" from Phase 5 onward).

### What proves correctness instead

| Req ID | Behavior | Proof method | Automatable? |
|--------|----------|---------------|---------------|
| SCRIPT-01 | Menu appears on open | Visual — open the Sheet, see `CreatorPulse` menu | No — human-observed, per criterion 1 |
| SCRIPT-02 | Time-driven trigger fires on schedule | Apps Script Executions log shows a run at ~09:00 Manila; forced proof via manual "Check freshness now" click with a hand-edited stale F cell | No — human-observed, per criterion 4 and D-08 |
| SCRIPT-03 | `onEdit` posts to Discord | Live edit of a Status cell, Discord message observed within seconds | No — human-observed, per criterion 2 (explicitly "not inferred from logs") |
| SCRIPT-04 | Conditional formatting on column E | Visual — green/red cells match sign of Δ Views, `—` cells untouched | No — human-observed, per criterion 3 |

### Wave 0 Gaps

None — there is no automated test infrastructure gap to fill for this phase's `.gs`/`.json`
artifacts; the four-command Python gate stays green because ruff and mypy do not traverse
non-`.py` files by default and this phase adds none.
`[ASSUMED — HIGH confidence: standard, well-known behavior of both tools' default file
discovery, not separately re-verified against this specific ruff/mypy version in this session]`.
The plan should still include a one-line confirmation task: run `ruff format --check .` and
`ruff check .` after `apps-script/` exists, to prove rather than assume the new directory does not
trip the gate.

## Security Domain

`security_enforcement` is enabled in `.planning/config.json` (absent-defaults-to-enabled rule; here
it is explicitly `true`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | No | Apps Script's own Google-account auth model governs editor access; this phase adds no auth logic |
| V3 Session Management | No | N/A — no sessions in this phase's scope |
| V4 Access Control | Partial | The `onStatusEdit` handler's column-and-sheet-name guard (`range.getColumn() !== 7`, `sheet.getName() !== 'Dashboard'`) is the only access-control-shaped logic — it is a correctness guard, not a security boundary (any Editor on the Sheet can already write any cell) |
| V5 Input Validation | Partial | The Status cell's content is untrusted-by-humans free text (D-12 deliberately leaves it unvalidated); the webhook message construction must not let arbitrary Status text break the Discord payload — `JSON.stringify()` handles escaping automatically, so no manual string-concatenation into a JSON body should ever appear in the implementation |
| V6 Cryptography | No | No cryptographic operations in this phase; the webhook URL functions as a bearer secret, handled per V-Secrets below, not as a crypto primitive |
| V-Secrets (not a numbered ASVS section but directly applicable) | Yes | `DISCORD_WEBHOOK_URL` is a bearer-token-equivalent secret. Standard control: never commit it, store it in Script Properties (D-13) — analogous to an environment variable, scoped to the script project, not readable by anyone without Editor access to the underlying Apps Script project itself |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Discord message-content injection via crafted Status text (e.g. `@everyone`, Discord markdown abuse, or an attempt to break the JSON payload with unescaped quotes) | Tampering / Information Disclosure | `JSON.stringify({content: message})` escapes the string correctly by construction — do not hand-build the JSON string. A malicious `@everyone` in a Status cell would still ping the channel if webhook messages are not configured to suppress mentions; Discord's webhook API supports an `allowed_mentions` field to suppress this, which is worth a one-line addition (`allowed_mentions: {parse: []}`) if the demo channel has notification-sensitive members — left to implementer discretion since D-14/D-15 do not mandate it, but flagged here as a cheap, real mitigation `[ASSUMED — reasonable security hygiene addition beyond what CONTEXT.md required; not a locked decision]` |
| Webhook URL leakage (committed to the repo, logged, or echoed in an error message) | Information Disclosure | D-13's Script-Properties-only rule already prevents this; the implementation must also avoid ever `console.log`-ing the full webhook URL (log the response status code and body on failure, not the request URL) |
| Trigger-owner account compromise leading to unauthorized `UrlFetchApp` calls under the script's identity | Elevation of Privilege | Out of scope for this phase's threat model — this is the standard Google-account security boundary every Apps Script project relies on; no additional mitigation is specific to this project |

## Sources

### Primary (HIGH confidence)

- `developers.google.com/apps-script/guides/triggers` — direct `WebFetch`; confirmed simple
  triggers cannot access authorization-requiring services, confirmed `e.range`/`e.source`/`e.user`
  presence, confirmed `e.user` reliability caveat
- `developers.google.com/apps-script/guides/triggers/installable` — direct `WebFetch`; confirmed
  `ScriptApp.newTrigger` builder syntax for `onEdit`, `timeBased`/`atHour`/`everyDays`/`inTimezone`,
  `getProjectTriggers`/`deleteTrigger`, and the "runs under creator's identity" fact
- `developers.google.com/apps-script/guides/triggers/events` — direct `WebFetch`; confirmed
  `oldValue`/`value` are undefined for multi-cell edits and cell clears, confirmed `authMode`,
  `triggerUid` fields
- `docs.discord.com/developers/resources/webhook` — direct `WebFetch`; confirmed endpoint shape,
  `content` field, `204` default success, 2000-char limit
- `developers.google.com/apps-script/guides/properties` — direct `WebFetch`; confirmed
  `Project Settings > Script Properties` UI path

### Secondary (MEDIUM confidence)

- `developers.google.com/apps-script/manifest` — direct `WebFetch`; confirmed manifest fields and
  the "Show appsscript.json" toggle, but did not resolve whether `oauthScopes` is auto-inferred vs.
  strictly required when omitted (documentation was silent on this specific point)
- `developers.google.com/apps-script/reference/spreadsheet/conditional-format-rule-builder` — via
  `WebSearch` synthesis (not directly fetched) — confirmed builder method names and the
  whole-array-replacement behavior of `setConditionalFormatRules`
- Google Sheets ISO-8601-with-timezone-offset parsing behavior — `WebSearch` synthesis across
  several community/blog sources, no single canonical Google doc fetched verbatim; this is the
  basis for Pitfall 4 and Assumption A1
- V8 `Date` constructor leniency toward extra fractional-second digits — `WebSearch` synthesis;
  ECMA-262 spec supports 3-digit milliseconds explicitly, tolerance beyond that is
  implementation-defined and not confirmed against the specific Apps Script V8 sandbox

### Tertiary (LOW confidence)

- Whether a failed simple-trigger `UrlFetchApp.fetch` call shows any visible UI notification to
  the editing user (vs. only the Executions log) — search results were inconclusive; flagged in
  Common Pitfalls §1 and Assumption A3
- Discord webhook creation click path (Server Settings → Integrations → Webhooks) — general
  knowledge / `WebSearch`, not independently re-verified against a live Discord client this session

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no package selection ambiguity exists; Apps Script's built-in services
  are the only option
- Architecture: HIGH — the trigger/menu/formatting/webhook shape is directly confirmed against
  primary Google and Discord documentation
- Pitfalls: MEDIUM — the load-bearing trigger-authorization pitfall is HIGH confidence
  (`[VERIFIED]`-grade via direct doc fetch); the timestamp-parsing pitfall is MEDIUM and explicitly
  flagged for a cheap empirical check before implementation proceeds

**Research date:** 2026-08-06
**Valid until:** Apps Script's trigger and properties APIs are extremely stable (years without
breaking change) — this research is valid well beyond this project's timeline. The one
time-sensitive element is Discord's webhook API shape, also stable; no near-term deprecation is
known. Treat as valid indefinitely for this project's purposes.
