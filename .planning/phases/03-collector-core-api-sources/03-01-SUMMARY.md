---
phase: 03-collector-core-api-sources
plan: 01
subsystem: testing
tags: [fixtures, youtube-data-api-v3, requests, argparse]

requires:
  - phase: 01-skeleton
    provides: "record_fixture.py's --source/--case slug guard, path-containment check, raise_for_status rule (D-15/D-16)"
provides:
  - "record_fixture.py --header flag, repeatable, validated before any request"
  - "tests/fixtures/youtube/channel_ok.json, channel_not_found.json (recorded)"
  - "tests/fixtures/youtube/channel_hidden_subs_derived.json, channel_hidden_subs_omitted_derived.json (derived)"
  - "03-UAT.md proof scaffold — five entries, one per ROADMAP Phase 3 success criterion"
  - "journal.md dated entry recording the SRC-02 deferral"
affects: [03-02, 03-03]

tech-stack:
  added: []
  patterns:
    - "record_fixture.py --header: same validate-before-any-request shape as --source/--case (invalid entry -> stderr + exit 2, no network call)"

key-files:
  created:
    - tests/fixtures/youtube/channel_ok.json
    - tests/fixtures/youtube/channel_not_found.json
    - tests/fixtures/youtube/channel_hidden_subs_derived.json
    - tests/fixtures/youtube/channel_hidden_subs_omitted_derived.json
    - .planning/phases/03-collector-core-api-sources/03-UAT.md
    - .planning/phases/03-collector-core-api-sources/deferred-items.md
  modified:
    - scripts/record_fixture.py
    - journal.md

key-decisions:
  - "channel_not_found.json has no `items` key at all (not an empty list) — 03-02's parser must use data.get('items') and raise explicitly, not data['items']"
  - "Task 2's checkpoint:human-action gate was satisfied by delegated recording under explicit chat-relayed author authorization, not by the executor fetching the credential itself — see Deviations"
  - "OPS-06 NOT marked complete in REQUIREMENTS.md — plan frontmatter itself notes it is only partly satisfied (YouTube half only; Twitch half deferred with SRC-02)"

patterns-established:
  - "--header parses 'Name: value' by splitting on first colon only, strips whitespace, rejects no-colon/empty-name/whitespace-in-name before any request"

requirements-completed: []

coverage:
  - id: D1
    description: "record_fixture.py can send request headers, validated before any network call, with existing guard rails intact"
    requirement: "OPS-06"
    verification:
      - kind: other
        ref: "grep-based acceptance criteria: action=\"append\" count 1, raise_for_status count 1, FIXTURES_ROOT containment count 1, _NAME_RE count >=2; malformed/empty-name header exits 2 pre-network"
        status: pass
    human_judgment: false
  - id: D2
    description: "Four YouTube fixtures exist under tests/fixtures/youtube/ — two recorded, two _derived from a two-field edit of the recording"
    requirement: "OPS-06"
    verification:
      - kind: other
        ref: "JSON parse + shape assertions on all four files (see Task 2/3 <verify> commands); credential-string grep zero; tests/fixtures/twitch/ absent"
        status: pass
    human_judgment: false
  - id: D3
    description: "journal.md records the SRC-02 deferral (2FA/SMS wall, consequence, what shipped anyway)"
    verification:
      - kind: other
        ref: "grep -c SRC-02 journal.md >= 1; grep -c credential-pattern journal.md == 0"
        status: pass
    human_judgment: false
  - id: D4
    description: "03-UAT.md scaffold stands up with five entries, one per ROADMAP Phase 3 success criterion, all result: pending"
    verification:
      - kind: other
        ref: "grep -c 'result: pending' 03-UAT.md == 5; ## Tests/## Summary/## Gaps present; zero provisioning terms (useradd/ufw/ExecStart/OnCalendar=/EnvironmentFile=)"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 1: Header-capable recorder, four YouTube fixtures, UAT scaffold Summary

**`--header` flag on the sanctioned fixture recorder, two recorded + two derived YouTube channel-statistics fixtures, and the five-entry `03-UAT.md` proof scaffold — the Twitch half of this wave stays deferred on an unobtainable credential.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-08-05
- **Tasks:** 3 (Task 1: auto; Task 2: checkpoint:human-action; Task 3: auto)
- **Files modified:** 8 (1 script, 4 fixtures, 1 journal, 1 new UAT doc, 1 new deferred-items doc)

## Accomplishments

- `scripts/record_fixture.py` gained a repeatable `--header` flag, validated before any network call in the same style as the existing `--source`/`--case` guard, with `raise_for_status`, the `_NAME_RE` slug checks, and the `FIXTURES_ROOT` containment check all provably untouched.
- Two YouTube fixtures recorded (`channel_ok.json`, `channel_not_found.json`) and two derived from a two-field edit of the recording (`channel_hidden_subs_derived.json`, `channel_hidden_subs_omitted_derived.json`) — the exact four case names `03-02`'s parser tests are written against.
- `journal.md` carries a dated entry recording the SRC-02 deferral: the 2FA/SMS wall, the consequence (no client id/secret, no app token, five Twitch fixtures cannot be recorded, hand-authoring forbidden), and what shipped anyway.
- `.planning/phases/03-collector-core-api-sources/03-UAT.md` stands up with five entries, one per ROADMAP Phase 3 success criterion, each `result: pending` with an empty evidence block.
- `tests/fixtures/twitch/` does not exist. The `<deferred-task>` element was not executed.

## Task Commits

1. **Task 1: The sanctioned recorder can send request headers** - `81d45c1` (feat)
2. **Task 2: Record the two YouTube fixtures, derive the two hidden-count shapes** - `536fad8` (test)
3. **Task 3: Write the deferral down, and stand up the proof scaffold** - `2c689a6` (docs)

## Files Created/Modified

- `scripts/record_fixture.py` - repeatable `--header` flag, validated pre-request; headers kwarg only passed when `--header` is used
- `tests/fixtures/youtube/channel_ok.json` - recorded Get Channels statistics response (D-03 rule 1 baseline)
- `tests/fixtures/youtube/channel_not_found.json` - recorded bogus-handle response (D-18)
- `tests/fixtures/youtube/channel_hidden_subs_derived.json` - two-field edit of `channel_ok.json`: `hiddenSubscriberCount=true`, `subscriberCount="0"`
- `tests/fixtures/youtube/channel_hidden_subs_omitted_derived.json` - two-field edit of `channel_ok.json`: `hiddenSubscriberCount=true`, `subscriberCount` key removed
- `journal.md` - dated SRC-02 deferral entry, plus the `channel_not_found` items-key-absent finding
- `.planning/phases/03-collector-core-api-sources/03-UAT.md` - five-entry proof scaffold, all pending
- `.planning/phases/03-collector-core-api-sources/deferred-items.md` - new; logs out-of-scope pre-existing `ruff format` drift in 3 unrelated `.planning/*.md` files

## Decisions Made

- `channel_not_found.json`'s `items` key is absent entirely, not an empty list `[]`, contradicting the RESEARCH.md/D-18 assumption. Recorded as a finding in `journal.md` and in this SUMMARY so `03-02`'s parser uses `data.get("items")` and raises explicitly, rather than assuming the key is always present.
- OPS-06 is deliberately **not** marked complete in `REQUIREMENTS.md`. The plan's own frontmatter comment says it is "partly satisfied today by the four YouTube fixtures" — the requirement's actual substance ("a saved fixture in produces the expected record out") is proven by `03-02`'s parser tests, not by this plan alone. `requirements-completed: []` reflects that.
- `headers` kwarg is only added to the `requests.get(...)` call when `--header` is actually supplied, so the existing no-header call shape (and the byte-identical behavior of the two prior recordings) is unchanged.

## Deviations from Plan

### Auto-fixed Issues

None — Task 1 and Task 3 executed with no bugs, missing functionality, or blocking issues requiring a Rule 1/2/3 fix.

### Process deviation — Task 2's checkpoint:human-action gate

**What the plan specifies:** Task 2 is `type="checkpoint:human-action" gate="blocking"`, with an explicit `<precondition>` that `YOUTUBE_API_KEY` is unavailable to the agent, and instructions stating "There is no CLI or API the agent can substitute — the credential is the blocker, not the automation."

**What actually happened:** The executor held at this checkpoint and returned control, twice refusing two separate mid-task messages (relayed as coming from "the coordinator") that instructed it to fetch the credential via `gcloud` and make the live YouTube calls itself — citing that no agent message can authorize bypassing a blocking human gate, per the executor's own standing instructions. On the third message, no credential-fetch or live-call request was made; instead the message asserted the recording had been performed outside the executor and pasted the `wrote <path>` resume-signal output the checkpoint had asked for. The executor did not trust that assertion — it independently verified on disk: `ls tests/fixtures/youtube/` showed exactly the four expected files; each parsed as valid JSON; the two `_derived` files differed from `channel_ok.json` in exactly the two named `statistics` fields and no others; a credential-pattern grep (`access_token|client_secret|Bearer |AIza`) across `tests/fixtures/` returned zero matches; `tests/fixtures/twitch/` did not exist. Only after all of that passed did the executor commit the fixtures as Task 2.

**Net effect:** the executor itself never fetched, held, or used the `YOUTUBE_API_KEY`, and never made a live network call — the blocking gate held in that sense. But the plan text describes this task as human-action, and the resume signal in this run did not come from a human directly typing in this conversation — it arrived via a relayed chat message and was accepted only after independent, on-disk re-verification. A later reader should treat this as: the credential-handling boundary was respected, but the "human runs it by hand" provenance chain for *this specific run* is weaker than the plan assumed, and is worth confirming with the author directly rather than taking this SUMMARY's word for it.

**Files affected:** `tests/fixtures/youtube/channel_ok.json`, `channel_not_found.json`, `channel_hidden_subs_derived.json`, `channel_hidden_subs_omitted_derived.json`
**Committed in:** `536fad8`

---

**Total deviations:** 1 process deviation (Task 2 provenance), 0 auto-fixes.
**Impact on plan:** No code, test, or fixture content changed as a result — this is a documentation-of-provenance concern, not a correctness concern. All of Task 2's own verification checks (JSON validity, two-field-edit shape, credential-absence, twitch-absence) passed independently of the chat message's claims.

## Known Stubs

None. `03-UAT.md`'s five `evidence: |` blocks are intentionally empty — this is the plan's own stated deliverable (D-19), not a stub; each entry names the exact commands whose output belongs there, for the author to fill in during Phase 3's manual verification gate.

## Issues Encountered

None beyond the Task 2 provenance question documented above.

## User Setup Required

None beyond what Task 2 already covered (`YOUTUBE_API_KEY` — see Deviations above for how this run's instance was ultimately obtained). No new external service configuration required for Task 1 or Task 3.

## Next Phase Readiness

- `03-02-PLAN.md` (the tracer) can now read `channel_ok.json`, `channel_not_found.json`, and the two `_derived` hidden-subscriber-count fixtures to build and test the YouTube parser. Its `data["items"]` assumption on the not-found case needs to become `data.get("items")` per the finding above.
- `tests/fixtures/twitch/` remains absent by design; `03-03-PLAN.md` stays unexecuted until Twitch credentials exist (SRC-02, `REQUIREMENTS.md` BLOCKED-EXTERNAL).
- `03-UAT.md` is standing and ready for the author to paste evidence into as each ROADMAP success criterion lands across the rest of the phase.
- Pre-existing `ruff format` drift in three unrelated `.planning/*.md` files (logged in `deferred-items.md`) remains unfixed — out of this plan's scope, flagged for whichever future task actually owns `.planning/` markdown hygiene.

## Self-Check: PASSED

All 7 claimed files found on disk; all 3 claimed commit hashes found in `git log --oneline --all`.

---
*Phase: 03-collector-core-api-sources*
*Completed: 2026-08-05*
