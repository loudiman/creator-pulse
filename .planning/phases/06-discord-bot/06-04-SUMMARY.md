---
phase: 06-discord-bot
plan: "04"
subsystem: phase-artifacts
tags: [coverage-gate, uat, discord-api-surface]

requires:
  - phase: 06-discord-bot
    plan: "01"
    provides: "the digest loop, config resolver, and 06-01's live checkpoint evidence lifted verbatim into 06-UAT.md entry 1"
  - phase: 06-discord-bot
    plan: "02"
    provides: "the two webhook alert call sites and coverage id D5, lifted into 06-UAT.md entry 3"
  - phase: 06-discord-bot
    plan: "03"
    provides: "the ±20% flag boundary tests, lifted into 06-UAT.md entry 2"
  - phase: 06-discord-bot
    plan: "05"
    provides: "/creator and /status, their verbatim rendered output, lifted into 06-UAT.md entry 4"
  - phase: 05-apps-script
    provides: "COVERAGE.md's webhook-surface rows, cited rather than restated for the two Python-side webhook capabilities"
provides:
  - "COVERAGE.md — 17 INTEGRATE / 27 OPT-OUT rows for the Discord gateway and application-command surface, three privileged intents each with their own OPT-OUT row"
  - "06-UAT.md — five entries against the five ROADMAP Phase 6 criteria, one closed with a caveat, four pending with close-later commands"
affects: []

tech-stack:
  added: []
  patterns:
    - "Split-status entries (passed_with_caveat) for criteria with a forced half and a natural/unforced half, matching 03-UAT.md entry 2's and 05-UAT.md's split-claim pattern"

key-files:
  created:
    - .planning/phases/06-discord-bot/COVERAGE.md
    - .planning/phases/06-discord-bot/06-UAT.md
  modified: []

key-decisions:
  - "06-05 was not cut (06-05-PLAN.md and 06-05-SUMMARY.md both exist, status complete) — 06-UAT.md entry 4 was written as a normal live-verification entry rather than a not_applicable/cut entry"
  - "Entry 5 HALF B (the author's intents explanation) left genuinely blank, not pre-filled, mirroring the plan's explicit prohibition and 05-UAT.md entry 7's still-open equivalent"
  - "No systemctl command was run and deploy/ was not touched — verified via git status --porcelain deploy/ (empty) as part of this plan's own verification"

requirements-completed: [BOT-06, BOT-07]

coverage:
  - id: D1
    description: "COVERAGE.md records the Discord bot/application-command surface with every OPT-OUT reasoned and the three privileged intents each getting their own row"
    requirement: "BOT-07"
    verification:
      - kind: other
        ref: "grep -c '^| capability | decision | reason |$' COVERAGE.md == 1; INTEGRATE rows == 17 (>= 8); OPT-OUT rows == 27 (>= 20); 0 rows with an empty reason cell"
        status: pass
    human_judgment: false
  - id: D2
    description: "06-UAT.md holds exactly five entries against the five ROADMAP criteria, each with expected/why_human/not_closed_reason/result/evidence, no entry closed without traceable evidence"
    requirement: "BOT-06"
    verification:
      - kind: other
        ref: "grep -c '^### ' == 5; grep -c '^not_closed_reason:' == 5; grep -c '^result:' == 5; '## Open Items' present; 'systemctl' appears (as human-step prose, never executed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The systemd install and Developer Portal configuration were not performed by this plan"
    requirement: "BOT-06, BOT-07"
    verification:
      - kind: other
        ref: "git status --porcelain deploy/ src/ tests/ — all empty after this plan"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-08-06
status: complete
---

# Phase 6 Plan 4: COVERAGE.md and 06-UAT.md — the Discord bot surface and the five criteria, evidence or an honest gap Summary

**Two documents, no source files: `COVERAGE.md` records 17 INTEGRATE / 27 OPT-OUT rows for the Discord gateway and application-command surface the bot actually uses, and `06-UAT.md` closes ROADMAP criterion 1's forced half on 06-01's live checkpoint evidence while leaving the other four criteria — the natural 08:15 fire, a live ±20% flag, the failure-alert ordering, the live slash-command round trip, and both halves of the systemd/intents criterion — recorded PENDING with named close-later commands rather than fabricated.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-06T09:18Z (first commit of this plan)
- **Completed:** 2026-08-06T09:30Z
- **Tasks:** 2 of 2 committed
- **Files modified:** 2 (2 new, 0 modified)

## Accomplishments

- `COVERAGE.md` — one `| capability | decision | reason |` table, 17 `INTEGRATE` rows (Intents.default(), commands.Bot, setup_hook, wait_until_ready, the get_channel/fetch_channel fallback, AllowedMentions.none(), guild-scoped CommandTree.sync, copy_global_to, app_commands.describe, Interaction.response.send_message, tasks.loop(time=...), before_loop, plain content, and the three Execute-Webhook rows citing 05-apps-script/COVERAGE.md rather than restating it) and 27 `OPT-OUT` rows, every one reasoned and cited to a D-NN, a ROADMAP note, or a 06-RESEARCH finding. The three privileged intents (message_content, members, presence) each get their own row — the table form of criterion 5's "why none of them are privileged" half.
- `06-UAT.md` — five entries, one per ROADMAP Phase 6 success criterion, in order:
  - Entry 1 (BOT-01): `passed_with_caveat` — the forced `--digest-now` proof is CLOSED, lifted verbatim from 06-01-SUMMARY.md's live checkpoint (console log, the exact posted digest text, the config-fails-loudly evidence); the natural, unattended 08:15 Asia/Manila fire is PENDING.
  - Entry 2 (BOT-02): PENDING — the flag is proven by five unit tests, but every real creator moved exactly 0% between 08-05 and 08-06 (YouTube view-count cache had not rolled over), so no flag has fired live; a labelled forced-proof recipe is recorded.
  - Entry 3 (BOT-03): PENDING — both webhook call sites are unit-tested and 06-02-SUMMARY.md's own coverage table already flagged this exact ordering claim as `human_judgment: true`; the cross-process ordering itself has not been observed, and the bogus-handle recipe from `06-VALIDATION.md` is lifted verbatim as the close-later step.
  - Entry 4 (BOT-04/BOT-05): PENDING — 06-05 was checked and confirmed **not cut** (`06-05-PLAN.md`/`06-05-SUMMARY.md` both exist, status complete), so this entry was written as a normal live-verification entry, not a cut/not_applicable one. Both commands' exact rendered output against the live database is already quoted verbatim from 06-05-SUMMARY.md; only the live guild round trip is missing.
  - Entry 5 (BOT-06/BOT-07): PENDING on both halves by design — the systemd install commands are recorded as the author's step and were not run (`git status --porcelain deploy/` empty), and the intents explanation slot is left genuinely blank for the author to write unaided, with an explicit note that Phase 5's equivalent (`05-UAT.md` entry 7) is still open and this one must not silently join it.
  - `## Open Items` lists all six open items (entry 1's HALF B, entries 2-4, entry 5's two halves) each with its own close-later command.

## Task Commits

Each task was committed atomically:

1. **Task 1: COVERAGE.md for the Discord bot and application-command surface** - `27228e5` (docs)
2. **Task 2: 06-UAT.md — five entries against the five ROADMAP criteria, evidence or an honest gap** - `aa2b278` (docs)

**Plan metadata:** this commit lands with the SUMMARY.

## Files Created/Modified

- `.planning/phases/06-discord-bot/COVERAGE.md` - new. 17 INTEGRATE / 27 OPT-OUT rows, one table, format-contract verified (capability ≤80 chars, reason ≤200 chars, no pipes/newlines in cells)
- `.planning/phases/06-discord-bot/06-UAT.md` - new. Five entries, `## Open Items` with six close-later commands, frontmatter `status: partial`

## Decisions Made

- **06-05 confirmed not cut** before writing entry 4 — checked `06-05-PLAN.md` and `06-05-SUMMARY.md` both exist with `status: complete`, so the entry was written as a normal pending live-verification entry rather than `result: not_applicable`.
- **Entry 5 HALF B left genuinely blank**, not pre-filled with the technical explanation — an entry the author could close by reading their own `COVERAGE.md` would prove nothing about whether they can explain the code unaided, exactly the reasoning `05-UAT.md` entry 7 already established for Phase 5.
- **No `systemctl` command was run and `deploy/` was not touched** — verified explicitly via `git status --porcelain deploy/` (empty) as part of this plan's own gate, not assumed.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' automated `<verify>` commands and all listed `<acceptance_criteria>` were checked directly against the written files before committing.

## Issues Encountered

None.

## User Setup Required

None new. This plan writes only two markdown documents in `.planning/`.

## Open UAT Items (for the phase's own verification step, so it does not have to reopen 06-UAT.md)

| # | Entry | Criterion | Close-later command |
|---|-------|-----------|---------------------|
| 1 | 1, HALF B | BOT-01 (unforced half) | Watch the real channel at/after 08:15 Asia/Manila with the bot already running and nobody typing a command; paste the posted message + timestamp into entry 1's evidence block. |
| 2 | 2 | BOT-02 | Wait for a real ±20% delta, or run the labelled forced proof: temporarily edit one 2026-08-05 `views` value in `creatorpulse.db`, run `creatorpulse bot --digest-now`, screenshot the flagged 🚨 row, restore the value. |
| 3 | 3 | BOT-03 | Add a bogus handle to `creators.yaml`, run `creatorpulse collect` by hand, confirm the alert lands immediately, confirm the 08:15 digest separately lists the same failure — one screenshot, both messages in order — then `git checkout creators.yaml`. |
| 4 | 4 | BOT-04, BOT-05 | With `creatorpulse bot` running, type `/creator kaicenat` and `/status` in the guild; paste the live replies into entry 4's evidence block. |
| 5 | 5, HALF A | BOT-06 | `sudo cp deploy/creatorpulse-bot.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now creatorpulse-bot && sudo systemctl status creatorpulse-bot && sudo reboot` then re-check status and `journalctl -u creatorpulse-bot -n 20 --no-pager` after reboot. |
| 6 | 5, HALF B | BOT-07 (explanation half) | Author writes, unaided, with `bot.py` closed: which intents does `CreatorPulseBot` request, and why is none of them privileged? Paste into entry 5's evidence block. |

## Next Phase Readiness

- `COVERAGE.md` satisfies the api-coverage gate for Phase 6.
- `06-UAT.md` gives Phase 6's verification step (`/gsd-verify-work` or equivalent) a complete, honest picture: 1 entry closed with a named caveat, 4 pending with runnable close-later commands, nothing fabricated.
- Phase 6 remains PARTIAL until the six open items above close — all six require the author, on the droplet or in the live guild/channel, none require further agent code work.
- No blockers introduced for Phase 7.

---
*Phase: 06-discord-bot*
*Completed: 2026-08-06*

## Self-Check: PASSED

- FOUND: .planning/phases/06-discord-bot/COVERAGE.md
- FOUND: .planning/phases/06-discord-bot/06-UAT.md
- FOUND: 27228e5 (Task 1 commit)
- FOUND: aa2b278 (Task 2 commit)
