# Phase 2 handoff status — 9 September 2026

**Later update — face cleanup approved and implemented:** the owner's 9 September
instruction authorized the F08 driver repair. It now passes the independent camera
suite and focused cleanup tests. See the [repair record](refinement_f08_face_cleanup_260909.md)
and [updated walkthrough](refinement_phase2_walkthrough_260909.md#face-recognition-cleanup-tests).
Earlier entries below describe the pre-repair checkpoint. The existing consolidated
wiki proposal still calls face cleanup pending and must be refreshed before approval
or publication; its earlier isolated-preview result is historical. The font repair,
monetary-cap decision and physical acceptance remain separate.

The local task assistant core is implemented and software-tested. Implementation
is paused at the Phase 2 checkpoint for owner testing. Phases 3–5 have not started.
This is not a claim that every approved Phase 2 requirement or earlier managed
driver proposal is complete.

## Delivered and validated

Use the [walkthrough and manual tests](refinement_phase2_walkthrough_260909.md).
It covers silent reminders, exact times, repeats, snooze, cancellation, restart,
request progress, memory correction, optional device communication, separately
supervised movement and rollback. No power-off test is required.

The final root gate used `uv run --frozen --no-sync` in the existing environment:

| Gate | Result |
| --- | --- |
| `python scripts/verify_immutable_drivers.py` | Pass: 222 files, six drivers, 55 existing authorized repairs |
| `python scripts/verify_workspace_driver_sources.py` | Pass: all six managed libraries load from this checkout |
| `python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests` | Pass |
| `ruff check .` | Pass; final test-import ordering corrected |
| `ruff format --check .` | Pass: 401 files |
| `mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src` | Pass: 88 source files |
| `pytest -q` | 734 passed, one existing Starlette test-client deprecation warning |
| `node --check ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js` | Pass |
| `git diff --check` | Pass |

No dependencies were synchronized, no real hardware/provider opt-in flags were
used, and no service, capture, deployment or live power operation was performed.
Individual managed driver suites were not rerun at this final checkpoint because
no managed-driver files changed; their integrity was verified before and after.

The final added tests verify recurrence after snooze and a daylight-saving gap,
joined delivery cleanup, no provider call after input-budget rejection, cleanup
of remaining resources after one close failure, and compilation of the actual
reminder command into text/tone operations without motion. The corrected
clock-change result length is covered by a readable-record regression.

## Consolidated documentation and wiki status

Four complete new manual sources are registered and normalized under the wiki's
`2026-09-09` folders. Registered originals remain unchanged. Source identifiers
use the tool's UTC date (`src-20260908-*`); the source folder and this report use
the local date in Tokyo. This date difference is intentional.

The proposed update refreshes all 11 existing searchable pages, their source
citations and honest AI review records. It does not claim human verification.
Review these exact artifacts:

- [Semantic page diff](refinement_phase2_wiki_260909.diff)
- [Version-2 page plan](refinement_phase2_wiki_260909.yaml)
- [README and document-map patch](refinement_phase2_pointers_260909.patch)
- [Page-by-page review notes](refinement_phase2_wiki_review_260909.md)

Validation passed for the plan and `git apply --check` on the pointer patch.
An isolated preview passed strict wiki lint, all eleven semantic review hashes,
and the full project knowledge checker, including proposed manual pointers,
implementation fingerprints, adapters and local links. Live pages/pointers were
not changed by that preview. The current live wiki still passes its own strict
lint, links and indexes against its older evidence, while the live project
knowledge check correctly flags the code changes whose consolidated map is pending.
Do not mistake that expected drift for a passing current-code knowledge check.

Publication awaits approval of this exact diff and pointer patch. The maintenance
workflow says, “Do not apply an unapproved diff.” After approval, revalidate the
plan and pointer patch, apply the semantic plan with the canonical wiki tool,
apply its matching normal Git patch, then run prepare, check, lint/strict lint,
links, indexes and search. Revalidate if any proposed content changes; do not use
the stale F02-only artifacts.

## Explicit remaining scope

- T07 bounds model calls, actual tool attempts/retries, elapsed time, serialized
  input and requested output. A strict currency-denominated spending cap is not
  implemented. The plan does not specify its amount, currency, accounting period
  or treatment of providers without trustworthy cost data. Resolve that policy
  before claiming complete monetary enforcement. Do not silently invent prices
  or label usage bounds as a billing guarantee.
- [Face backend cleanup](refinement_f08_face_cleanup.patch) and
  [Traditional Chinese font replacement](refinement_h06_font_proposal_260908.md)
  remain unapplied pending their specific managed-file authorization. Preserve the
  immutable baseline and record approved hashes only after real authorization.
- Real Raspberry Pi notification, browser/accessibility and supervised movement
  acceptance are for the owner. The software gate does not prove physical behavior.
- The wiki's exact-diff publication approval is pending. Source preparation is
  complete; searchable publication and active manual-link replacement are not.

## Next safe action

Start with the walkthrough's environment checks and silent practice reminder.
Use synthetic data and your existing profile; do not reset personal data or erase
safety latches. Record expected/actual results. Keep the robot stopped if device
health is unavailable. Resolve the spending-cap policy and pending approvals
before calling the entire Phase 2/earlier-repair scope complete or starting Phase 3.
