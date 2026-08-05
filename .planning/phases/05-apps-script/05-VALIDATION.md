---
phase: 5
slug: apps-script
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-06
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

**Read this first — this phase is the exception, and the reason is structural.** Phase 5 adds zero
Python. It adds `apps-script/Code.gs` and `apps-script/appsscript.json`, which run on Google's
infrastructure, not on the droplet and not in `pytest`. Apps Script has no unit-test framework
inside this project's locked stack, and adding one (a Node-based harness) would violate the
no-new-dependencies rule for a ~100-line file. ROADMAP's Definition of Green already anticipates
this: from Phase 3 onward every phase carries a **human-observed** gate, and for Phase 5 that gate
is a real Discord message produced by a real Status edit.

So the automated suite's job here is **regression only** — prove Phase 5 broke nothing — while
correctness is proven by direct observation. Both halves are mandatory. Neither substitutes for
the other.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (existing; unchanged by this phase) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest` |
| **Full suite command** | `ruff format --check . && ruff check . && mypy src/ && pytest` |
| **Estimated runtime** | ~10 seconds |

**The four-command gate is the Definition of Green** (ROADMAP §"Definition of Green", Phase 1
D-04/D-08). It runs in that order. This phase must leave all four green without weakening any of
them — CLAUDE.md's test-weakening guard applies in full.

---

## Sampling Rate

- **After every task commit:** `pytest`
- **After every plan wave:** `ruff format --check . && ruff check . && mypy src/ && pytest`
- **Before `/gsd-verify-work`:** all four commands green, **and** the human-observed proofs below recorded in `05-UAT.md`
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

Task IDs are filled in by the planner. The rows below fix the *shape* of the proof for each
requirement, which is what the planner must honour.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 0 | — | — | New `apps-script/` directory does not trip lint/format/type gates | regression | `ruff format --check . && ruff check . && mypy src/` | ✅ existing | ⬜ pending |
| TBD | TBD | 0 | SCRIPT-02 | — | Column F timestamp type is known, not assumed | empirical | `Logger.log(typeof v)` in the Apps Script editor — see Wave 0 below | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | SCRIPT-01 | — | Menu is present and its items are bound to real functions | manual | none — visual | n/a | ⬜ pending |
| TBD | TBD | 1 | SCRIPT-04 | — | Green/red match the sign of Δ Views; `—` cells untouched; rules do not duplicate on re-apply | manual | none — visual + re-click | n/a | ⬜ pending |
| TBD | TBD | 1 | SCRIPT-03 | T-05-01, T-05-02 | Webhook URL read from Script Properties, never from source; handler ignores edits outside `Dashboard!G2:G` | manual | `grep -r 'discord.com/api/webhooks' apps-script/` returns nothing | n/a | ⬜ pending |
| TBD | TBD | 1 | SCRIPT-02 | T-05-03 | Stale data produces a Discord alert; fresh data produces silence — and silence is proven to mean fresh, not crashed | manual | none — forced stale cell + Executions log | n/a | ⬜ pending |
| TBD | TBD | 2 | all four | — | Author can explain the `onEdit` event object and the webhook call unaided | manual | none — written into `05-UAT.md` (CONTEXT.md D-03) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] **Empirical timestamp-type check — blocks `checkFreshness()` being written.** RESEARCH.md
      Pitfall 4: Python writes column F via gspread with `value_input_option="USER_ENTERED"`, and an
      ISO-8601 string carrying a `+00:00` offset may land in Sheets as **text**, not as a `Date`.
      Read one cell in the Apps Script editor and log `typeof v` plus `v instanceof Date`. The answer
      determines the watchdog's date arithmetic. Do not write the staleness math before this returns.
      **Why it is Wave 0 and not a detail:** if the value is text and the code assumes `Date`, the
      comparison yields `NaN`, `NaN > threshold` is `false`, and the watchdog stays silent — which
      under D-07 ("silent unless broken") is indistinguishable from healthy. A broken watchdog that
      looks exactly like a working one is the worst available failure and the whole point of D-05.
- [ ] **Gate-reach confirmation.** After `apps-script/` exists, run `ruff format --check .` and
      `ruff check .` and confirm they still pass. RESEARCH.md marks "ruff and mypy skip non-`.py`
      files" as ASSUMED/HIGH but not re-verified in this session — prove it rather than assume it.
      If either tool does traverse the directory, add an exclude to `pyproject.toml`; do not
      reformat or delete the `.gs` file to satisfy a Python tool.

No new test files and no framework install. The existing suite covers this phase's regression
surface completely, because this phase's regression surface is "did anything Python change?" and
the answer must be no.

---

## Manual-Only Verifications

Every requirement in this phase is manual-only. That is a property of the phase, not a gap in the
plan. ROADMAP's success criteria for Phase 5 use the words "observed live, not inferred from logs"
— the manual proof *is* the specified proof.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Custom menu appears on open | SCRIPT-01 | Menu rendering has no API to assert against; criterion 1 says "shows a custom menu that was not there before" | Reload the Sheet. Confirm a `CreatorPulse` menu appears with its three items. Click each; confirm none throws. |
| Status edit posts to Discord within seconds | SCRIPT-03 | Criterion 2 explicitly says "observed live, not inferred from logs" | Type a value into `Dashboard!G3`. Watch the Discord channel. Message names the creator and shows old → new. Then clear the same cell and confirm the `(cleared)` message (D-15). |
| Edits outside column G post nothing | SCRIPT-03 | Negative case; no automated harness | Edit `Dashboard!D3` and a cell on any other tab. Confirm Discord stays silent both times. |
| Δ Views movement is visually obvious | SCRIPT-04 | Criterion 3 is explicitly about visual obviousness "without reading the numbers" | Confirm positive deltas green, negative red, `—` cells unformatted. Then click *Re-apply formatting* a second time and confirm the rule count did not double (RESEARCH.md: `setConditionalFormatRules` replaces the whole array — a read-then-append implementation duplicates). |
| Time-driven trigger fires on schedule | SCRIPT-02 | Criterion 4 names the Apps Script Executions log specifically | Open Extensions → Apps Script → Executions. Confirm a run appears for the time-driven trigger. |
| Stale data produces an alert | SCRIPT-02 | The alert branch never runs on a healthy day (D-07/D-08) | Hand-edit a column F cell to an old timestamp. Run *Check freshness now*. Confirm the alert reaches Discord. Let the next `creatorpulse sync` overwrite the cell — the Python write covers column F, so no cleanup is needed. |
| Fresh data produces silence *for the right reason* | SCRIPT-02 | Silence is the failure mode's disguise | After the forced-stale proof, run *Check freshness now* against fresh data and confirm the Executions log shows a **completed** run with no error — silence backed by a successful execution, not by a throw. |
| Author explains the `onEdit` event object and webhook call unaided | ROADMAP criterion 5 | It tests a person, not the code (CONTEXT.md D-03) | After the walkthrough, the author writes the explanation into `05-UAT.md` in their own words without re-reading `Code.gs`. |

---

## Validation Sign-Off

- [ ] Wave 0 timestamp-type check completed and its answer recorded in the plan before `checkFreshness()` is written
- [ ] Wave 0 gate-reach confirmation run; `ruff format --check .` and `ruff check .` pass with `apps-script/` present
- [ ] All four commands green: `ruff format --check .`, `ruff check .`, `mypy src/`, `pytest`
- [ ] No test file modified during this phase (CLAUDE.md test-weakening guard — this phase touches no Python, so any test diff is a red flag)
- [ ] Every manual verification above recorded in `05-UAT.md` with observed evidence, not "should work"
- [ ] Criterion 5 write-up present in `05-UAT.md` in the author's own words
- [ ] No webhook URL present anywhere under `apps-script/` (`grep -r 'discord.com/api/webhooks' apps-script/` returns nothing)
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
