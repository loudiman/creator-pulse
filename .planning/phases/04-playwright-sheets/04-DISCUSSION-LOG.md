# Phase 4: Playwright & Sheets - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-05
**Phase:** 4-Playwright & Sheets
**Areas discussed:** Dashboard grain & columns, Sync trigger & blast radius, History tab
idempotency, TikTok parse seam & fixtures (withdrawn — source cut)

---

## Area selection

Four gray areas were offered. The author selected all four, then supplied a scope change in the
same reply that removed one of them:

> "tiktok is now cut ... Lead with cutting TikTok, and go in willing to cut the History tab too if
> the discussion starts sprawling. Phase 5 needs your evening more than Phase 4 needs completeness."

The author also relayed a Phase 3 agent exchange about an orphan database row (`mkbhd`, left behind
by the entry-1a bogus-handle test after `creators.yaml` was reverted) and stated:

> "which i agree, i will lean on the agent decision to keep it"

Both were treated as decisions, not questions. **TikTok parse seam & fixtures was withdrawn without
questions** — SRC-03 is cut, so the area has no content.

---

## Dashboard grain & columns

### Question 1 — Where does the Dashboard's row list come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Database (orphans visible) | `SELECT DISTINCT creator_id FROM metrics`. MKBHD renders with a `—` delta. Sheet is a view of the DB. Live DATA-04 proof. | |
| creators.yaml (config mirrors) | Iterate configured creators. Orphan history stays in the DB but never renders. Sheet is a view of the config. | |
| You decide | Claude picks and records the reasoning. | ✓ |

**User's choice:** You decide → resolved as **D-01, database-sourced**.
**Notes:** The author had already endorsed keeping the orphan row, which is the stronger signal —
keeping it only means something if the Dashboard renders it.

### Question 2 — What is one Dashboard row?

| Option | Description | Selected |
|--------|-------------|----------|
| One row per creator-source | Matches `UNIQUE (creator_id, source, metric_date)`. Twitch later adds rows, not columns. 4 rows today. | |
| One row per creator, wide | Source-grouped columns. Literal read of criterion 1, but every non-YouTube column is empty today and un-blocking Twitch widens the sheet. | |
| You decide | Claude picks and records the reasoning. | ✓ |

**User's choice:** You decide → resolved as **D-02, one row per (creator, source)**.
**Notes:** Decided against the wide layout because widening on un-blocking is the
column-reorder-in-the-daily-path move PITFALLS.md §6 forbids, and Phase 5's triggers attach to the
layout.

### Question 3 — Which columns, and how are coarse counts labelled?

| Option | Description | Selected |
|--------|-------------|----------|
| Lean (7 cols) | Creator, Source, Followers (coarse), Views, Δ Views, Last updated, Status. Only what the criteria grade. | |
| Full mirror (9 cols) | Adds Videos and Live, mirroring the DB shape. Both render blank or single-source today. | |
| You decide | Claude picks and records the reasoning. | ✓ |

**User's choice:** You decide → resolved as **D-03, lean seven columns, frozen for v1**.
**Notes:** `video_count` is YouTube-only and `is_live` is Twitch-only (Phase 3 D-06), so the full
mirror would ship a permanently blank column while Twitch is walled off. The frozen-column ceiling
was recorded explicitly because inserting a column later shifts Status out from under Phase 5's
`e.range.getColumn()` check.

---

## Sync trigger & blast radius

### Question 4 — Where does the Sheet write run from?

| Option | Description | Selected |
|--------|-------------|----------|
| Both: end of collect + standalone | `collect` calls sync; `creatorpulse sync` also exists. Unit unchanged. Iterate layout with zero quota spend. | |
| Inside collect only | One entrypoint, smallest surface. Every layout iteration costs a real API run. | |
| You decide | Claude picks and records the reasoning. | ✓ |

**User's choice:** You decide → resolved as **D-06, both**.
**Notes:** The standalone command was justified primarily by the 23-hour clock — it is what lets the
layout be iterated tonight against already-committed rows.

### Question 5 — Sheets call fails after rows are committed. What happens?

| Option | Description | Selected |
|--------|-------------|----------|
| Log, then re-raise — exit non-zero | `runs` row already written by D-16's finally. Failed unit + journal line. Answers PITFALLS §18(d). | |
| Count it in failure_count | Phase 6 `/status` sees it without reading the journal, but conflates "a source broke" with "the view didn't update" in one integer. | |
| You decide | Claude picks and records the reasoning. | ✓ |

**User's choice:** You decide → resolved as **D-07, log and re-raise, not counted in
`failure_count`**.
**Notes:** Phase 3 D-10 had already refused to add a `runs` column to disambiguate failure kinds, so
overloading `failure_count` would undo that decision by the back door.

### Question 6 — Where does the SHEET-07 `client_email` check live?

| Option | Description | Selected |
|--------|-------------|----------|
| Wrap `open_by_key`, every run | Catch the APIError on the real path, name the `client_email` in the re-raise. Costs nothing. | |
| Separate `sheets-check` command | Cleaner separation, but leaves the daily 08:00 path unguarded if a permission is revoked later. | |
| You decide | Claude picks and records the reasoning. | ✓ |

**User's choice:** You decide → resolved as **D-08, wrap `open_by_key` on the real path**.

---

## History tab idempotency

### Question 7 — Does the History tab survive tonight?

| Option | Description | Selected |
|--------|-------------|----------|
| Cut it | SHEET-04 deferred. Phase 4 becomes Dashboard-only. Cut-order item 3, already sanctioned. Buys the evening back for Phase 5. | |
| Keep — read-then-append | One read of the key column, diff, one batched `append_rows`. Idempotent across same-day re-runs. ~30–40 lines plus a fixture test. | |
| You decide | Claude picks and records the reasoning. | ✓ |

**User's choice:** You decide → resolved as **cut**.
**Notes:** The author had pre-authorised this in their opening reply ("willing to cut the History tab
too if the discussion starts sprawling... Phase 5 needs your evening more than Phase 4 needs
completeness"). Cut-order item 3 is the standing authority. The design was recorded in CONTEXT.md's
Deferred Ideas so re-adding it later is a lookup, not a re-decision.

---

## Claude's Discretion

The author answered **"you decide" to all seven questions asked**. Every one was resolved as a
recorded decision (D-01 through D-09) rather than left open. What remains genuinely open is listed
in CONTEXT.md §"Claude's Discretion": function decomposition inside `sheets.py`, the exact fixture
seam, two-query versus self-join for the delta, log wording, exception class names, and test/fixture
naming.

Two decisions were made without being asked, both flowing from the cuts:

- **D-04** — the single `A1:F{n+1}` write including the header row, and `USER_ENTERED`.
- **D-05** — strict `metric_date - 1 day` as the delta baseline, `—` when that exact row is absent.
- **D-09** — the two new `CREATORPULSE_`-prefixed environment variables and the `.env.example`-only
  ownership boundary.

## Deferred Ideas

- **SRC-03, the TikTok source** — cut (cut-order item 2). No later phase in this milestone can take
  it; it becomes a v2 candidate. `creators.yaml` keeps its `tiktok` entries harmlessly via Phase 3
  D-09's skip path.
- **SHEET-04, the History tab** — cut (cut-order item 3). Design settled and recorded should it
  return.
- **Videos and Live columns** — dropped by D-03; revisit only alongside the Phase 5 Apps Script.
- **Display names on the Dashboard** — would need a second input or a `creators` table; the slug is
  legible at four rows.
- **Reaching back more than one day for a delta baseline** — declined by D-05; a gap must read as a
  gap.
- **Removing Playwright from `pyproject.toml`** — not tonight; gate-touching change, no benefit, and
  keeping it keeps the source's return cheap.
- **`skipped_count` on `runs`** — still declined (Phase 3 D-10), now with permanent `tiktok` skip
  lines making it marginally more tempting and no more justified.

### Scope-hygiene item raised during discussion

ROADMAP.md and REQUIREMENTS.md both still map SRC-03 and SHEET-04 to Phase 4. Recorded in
CONTEXT.md §"Specific Ideas" as work to do **before** planning, so the phase is graded against six
requirements rather than eight.
