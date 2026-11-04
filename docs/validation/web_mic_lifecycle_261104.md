# Web microphone lifecycle repair

Source review confirms premature session clearing and handler removal in
`app-agent.js`. It also confirms duplicate stop calls on final results. The new
IDLE/STARTING/RECORDING/STOPPING lifecycle retains identity and `onend`, queues an
explicit repeat click and discards stale callbacks. Send clears queued restarts
and ignores late results; hidden pages abort capture. Final results await natural
completion. Synchronous start failures return to idle with feedback. Unexpected
abort errors are visible, without automatic microphone retries or device switching.

## Investigation fact check

The two input paths in the report are present: browser SpeechRecognition and
robot push-to-talk. Zero ledger entries alone do not prove browser support or
exclude failed/unlogged backend attempts. The quoted private runtime observations
and 15.55-second benchmark are historical report evidence, not independently
reproduced measurements in this repair. No private conversations were reread.

The 200–600 ms timing, exact browser rejection code and causal explanation for
manual typing restoring recognition are plausible hypotheses, not guaranteed
browser behavior. The code-level race exists independently of those hypotheses.
`onend` signals recognition service disconnection; it is not a physical hardware
release measurement. No fixed-delay automatic retry is introduced.

The audio runner already caught BrokenPipeError around drain and joined its work
tasks. Thus merely adding that catch, as proposed, would not fix a demonstrated
gap. Write errors and the stdin transport close future are now handled, including
cleanup after timeout/cancellation. The reported log cannot alone establish the
specific unretrieved future's origin. Tests cover early process exit and timeout
with large stdin input and an event-loop exception collector.

## Scope and validation

Changes affect browser recognition and IDE subprocess cleanup only; managed
libraries and public robot tools are unchanged. Node VM tests execute actual
client code with delayed recognition events, repeated dictation, queued restart,
submission cancellation and stale callbacks. Python subprocess tests use harmless
local children, never audio devices. Physical browser/microphone validation remains
pending. No live capture, playback, motion or power command was executed.

Safe smoke: run the new Node/Python tests. Device test with consent: ten rapid
harmless dictation/Send/restart cycles; confirm prefix preservation, denied
permission feedback and cancellation on page hiding. No actuator or power-risk
test is required. Rollback: stop dictation and restore the prior client/runtime
revision, then reload browser assets. A browser that never emits onend requires a
page reload; no timer is allowed to overlap a possibly active capture session.

New raw manual successors are in 2026-11-04-02. MCP contracts and dependencies
are unchanged, so their manuals/notices require no changes. No ingestion or
semantic review was performed; registered sources are preserved.

## Automated results — 4 November 2026

- `uv run --frozen pytest -q`: **1,141 passed**, one dependency warning.
- Separate managed-driver suites: servo **159**, buzzer **68**, camera **27**,
  microphone **92**, display **65**, distance sensor **71** tests passed.
- Ruff lint and format checks passed (477 files); mypy passed (122 source files).
- Compilation, immutable-driver verification, workspace-driver verification and
  `git diff --check` passed. No managed-driver files or authorization records changed.
- Wiki `check` and `lint` could not run: the wiki environment is missing.
  No setup, ingestion or semantic review was performed.
- The first full run exposed an outdated source-text assertion expecting an
  explicit stop on final recognition. It now verifies that manual stop remains
  available while final results await natural completion; the full rerun passed.

## Manual acceptance checklist

1. Restart the agent using your existing service workflow, then hard-refresh the
   web page so it loads the updated JavaScript.
2. With microphone consent, type a short prefix, click Web Mic and dictate a
   harmless question. Confirm the transcript follows the prefix.
3. Send the question and immediately click Web Mic again. Repeat ten times.
   Each explicit request should start after the preceding session ends, and old
   transcripts must not overwrite the new input.
4. Click twice while a session is stopping to queue and then cancel a restart.
   Confirm no new capture starts after cancellation. Hide the page during
   recording and confirm capture stops without automatically restarting.
5. Deny browser microphone permission and confirm visible feedback with no
   automatic switch to the robot microphone. Restore permission before retesting.

| Validation category | Expected result | Status |
| --- | --- | --- |
| Safe smoke | Automated lifecycle and harmless subprocess tests pass | Automated |
| Device communication | Ten browser cycles, cancellation and permission checks pass | Pending owner test |
| Actuator movement | No actuator commands needed or executed | Not applicable |
| Power risk | No shutdown or power configuration changes needed | Not applicable |

If a session remains stuck, reload the page. For a regression, stop dictation,
restore the previous application revision, restart the existing service and
hard-refresh the browser. No driver or boot configuration rollback is needed.
