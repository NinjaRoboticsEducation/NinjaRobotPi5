# Phase 2 walkthrough and manual tests — 9 September 2026

This guide explains the implemented local task assistant and helps you test it
without confusing a saved request with a completed real-world action. Development
pauses here before Phase 3. These instructions have been checked against code;
the live robot and browser tests below have **not** been performed by the coding agent.

## Contents

- [What is available](#what-is-available)
- [Before testing](#before-testing)
- [Safe smoke tests](#safe-smoke-tests)
- [Face-recognition cleanup tests](#face-recognition-cleanup-tests)
- [Local reminders](#local-reminders)
- [Task progress and cancellation](#task-progress-and-cancellation)
- [Memory review and correction](#memory-review-and-correction)
- [Device communication and optional notifications](#device-communication-and-optional-notifications)
- [Actuator-moving checks](#actuator-moving-checks)
- [Power-risk checks](#power-risk-checks)
- [Results and rollback](#results-and-rollback)

## What is available

| Area | What changed | Important limit |
| --- | --- | --- |
| Reminders | Exact time, daily/weekly repeats, review before scheduling, snooze, cancel, restart recovery. | The Pi and Agent service must be running. No phone call, off-Pi alarm, or wake-from-power-off promise. |
| Local task records | Chat requests and reminder states are saved in the existing private database. Tool steps include outcome evidence. | General requests do not automatically resume after restart. Refresh the task panel to see progress; it does not push live updates. |
| Cancellation | Task controls remain available while a model request is busy. | Cancellation cannot undo an action already performed. An in-progress reminder notification may finish. Use the existing emergency stop for immediate robot safety. |
| Recovery limits | Model calls, actual tool attempts including safe retries, time, model input size and requested output tokens are bounded. | This is a usage limit, not a currency-denominated spending cap or billing guarantee. Unknown external effects are not automatically repeated. |
| Memory | See the source, confidence, reason and confirmation; correct, confirm or forget a preference. | Existing profile boundaries remain. Conflicting structured preferences become suggestions; arbitrary natural-language contradictions are not comprehensively resolved. |
| Guidance and accessibility | Optional guided checks, browser zoom/focus, keyboard movement release; privacy-conscious lifecycle logs. | No new persistent on-screen lifecycle display. Actual browser, assistive technology and robot checks remain manual. |

The hardware path is unchanged: Agent (conversation and decisions) → IDE
(device coordination and safety) → existing Pi5 drivers → devices.
Calendar writes, briefings, reusable learned recipes and later interaction changes
are not part of this handoff.

## Before testing

1. Keep a note of your current code revision and preserve your private configuration
   and database using your existing backup procedure. Do not share these files.
2. Run shell commands below from the NinjaRobotPi5 repository root. `uv` runs the
   project's installed tools; `--no-sync` prevents changing installed packages.
3. Do not start another hardware owner alongside the Agent. Close standalone driver
   tools before a real Agent session.
4. For an already running Agent, use the existing controller or CLI (terminal
   interface). Restart it under operator control to load changed Python code;
   refresh the browser to load changed JavaScript. Startup may greet, move devices
   or activate configured voice input. Raise wheels, have power removal ready,
   and obtain consent before camera/microphone use. Do not restart casually as
   part of the read-only checks.
5. Use your existing local profile. Tasks follow the active profile. Where memory
   is disabled, tasks belong to that chat session; reconnecting with another
   session may show a different inbox. A profile boundary is not proof of who is
   physically holding the keyboard.
6. Use only synthetic messages such as “Phase 2 practice”. Record test task IDs
   (unique identifiers) so cleanup never removes unrelated reminders or memories.

The owner approved the face-recognition cleanup on 9 September 2026; it is now
implemented. See the focused tests below and the
[repair validation record](refinement_f08_face_cleanup_260909.md).
The [Traditional Chinese font proposal](refinement_h06_font_proposal_260908.md)
remains pending. Do not regenerate the driver baseline or erase safety state to
make a test pass.

## Safe smoke tests

These commands inspect software without starting the Agent or opening hardware:

```bash
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py
uv run --frozen --no-sync ninjarobot_pi5_cli doctor --profile hardware --root .
```

Expected: both verifiers pass. Doctor names missing environment requirements and
repair guidance if any. Doctor checks package discovery, not physical device
communication. If it reports a missing driver, follow the installation guide for
the existing environment; do not bypass the safety health check.

For software-only development, the doctor can instead use `--profile development`.
This profile is not a statement that physical hardware is ready.

Run deterministic local assistant tests without model or hardware access:

```bash
uv run --frozen --no-sync pytest -q \
  ninjarobot_pi5_agent/tests/test_tasks.py \
  ninjarobot_pi5_agent/tests/test_task_tools.py \
  ninjarobot_pi5_agent/tests/test_memory_review.py \
  ninjarobot_pi5_agent/tests/test_ipc.py \
  tests/test_keyboard_controls.py
```

Expected: all tests pass. The keyboard test uses a fake browser environment and
requires Node.js; an explicit skip when Node.js is absent is not browser validation.
No `--run-hardware` or `--run-provider-live` flags are needed.

## Face-recognition cleanup tests

This repair releases the recognition backend (the component that detects and
compares faces) when a recognition call finishes or fails. It does not change face
matching, enrollment, saved-face formats, camera capture policy or robot movement.
A successful backend construction is required before there is an object to close.
The existing backend's close method specifically releases its MediaPipe detector
when one is present; this is not a promise that process memory immediately falls
or that all native libraries return memory to the operating system.

### Test F1 — deterministic cleanup, no camera or personal image

From the repository root, run each suite in its own process:

```bash
uv run --frozen --no-sync pytest -q pi5camera/tests
uv run --frozen --no-sync pytest -q ninjarobot_pi5_ide/tests/test_face_backend_cleanup.py
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
```

Expected: **27 camera tests**, **8 cleanup tests**, and driver verification pass.
The verifier now reports 56 authorized repairs; its 222-file import baseline is
unchanged. The cleanup tests replace the detector and capture/storage functions
with controlled substitutes, so they use no camera, real faces, model download,
provider, or live user database.

The eight cases cover success, missing image, capture failure, generic detection
failure, a recognition-specific error, face-index failure, pending-record storage
failure and five consecutive calls in one process. A successfully constructed
backend must close exactly once on each call. The existing camera suite also
checks known/unknown results and compatibility with older test backends without a
close method. Stop here if any check fails; do not change baseline hashes yourself.

### Test F2 — optional installed recognition software, still no capture

This checks the installed real detector against a generated blank image. It does
not test recognition accuracy or the physical camera. It may use CPU and memory;
run it while the robot is idle. No service start or stop is needed. If prerequisites
are missing, record the error and repair them through the installation guide.

From the repository root, run:

```bash
uv run --frozen --no-sync python - <<'PYTEST'
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from PIL import Image
from pi5camera.core import recognition
from pi5camera.errors import RecognitionError

build_backend = recognition.build_recognition_backend
backends = []


def tracked_backend(config):
    backend = build_backend(config)
    backend.close = Mock(wraps=backend.close)
    backends.append(backend)
    return backend


with TemporaryDirectory(prefix="ninja-face-cleanup-") as directory:
    temporary = Path(directory)
    image = temporary / "blank.png"
    Image.new("RGB", (320, 240), "white").save(image)
    config = {"paths": {"data_dir": str(temporary / "faces")}}
    with patch.object(recognition, "build_recognition_backend", tracked_backend):
        for attempt in range(3):
            if attempt == 1:
                try:
                    recognition.recognize_faces(config, image_path=temporary / "missing.png")
                except RecognitionError as error:
                    assert "Image file does not exist" in str(error)
                else:
                    raise AssertionError("Missing image should fail")
            else:
                result = recognition.recognize_faces(config, image_path=image)
                assert result["face_count"] == 0
            assert len(backends) == attempt + 1
            assert all(backend.close.call_count == 1 for backend in backends)
    print("PASS: success, missing-image failure, then success; each backend closed once.")
PYTEST
```

Expected: the final PASS line. Detector startup messages may also appear. All
images and face-index files are temporary and removed when the command exits.
Existing profiles/configuration are not read or changed. MediaPipe may be absent
on the Pi, where the existing OpenCV fallback can be selected; a pass there does
not prove the MediaPipe native detector was exercised. Do not interpret this as
a measured memory-leak benchmark or a guarantee about backend-constructor failures.

### Device, movement, power and rollback boundaries

No physical device communication, camera capture, actuator movement or power test
is required for this narrowly scoped cleanup. If you separately test live face
recognition, use the existing operator-controlled camera procedure, obtain capture
consent and follow its media-retention rules; that is outside these two checks.
Do not run a standalone live camera tool alongside the Agent's hardware owner.

On failure, record only the failing test name and non-sensitive error. Test F2's
temporary directory cleans itself up. Do not delete existing face profiles or
reset the robot. A code rollback must restore both this driver repair and its
matching authorization entry to their prior state, preserve the immutable import
baseline and unrelated edits, and rerun verification. Use an operator-controlled
stop before replacing code used by a running hardware service.

## Local reminders

Open chat in your already running Agent controller. Alternatively, connect from
the terminal without starting another hardware owner:

```bash
uv run --frozen --no-sync ninjarobot-agent chat --session phase2-manual
```

Expected: a chat prompt connected to the current service. Select/create a profile
through your existing controls if requested. Commands below are typed **in chat**,
not in the shell. The local slash commands do not need a working model provider.
Normal natural-language chat still does.

### Test 1 — preview does not schedule

1. Type `/remind 120 Phase 2 practice`.
2. Read the returned task ID, due time and effect. It must say `draft` and
   “Not scheduled yet”. The default effect is a silent notice in the local inbox.
3. Open the menu's **Local tasks** panel and press **Refresh**, or type `/tasks`.
4. Confirm this exact test ID before its due time:
   `/tasks confirm TASK_ID` (replace `TASK_ID` with the returned `task-...` value).
5. Confirm the same ID again. It should remain one `queued` task, not two reminders.
6. After about two minutes, refresh or type `/tasks`. It should be `completed`,
   with “Reading by the user is not confirmed”. No display or buzzer is expected.

Fail if a draft notifies, confirmation creates duplicates, or a silent reminder
claims a physical notification. Drafts expire after ten minutes and cannot be
confirmed after the due time; make a new test draft if needed.

### Test 2 — snooze requires fresh review

1. Create another reminder with `/remind 120 Phase 2 snooze`.
2. Confirm it, then type `/tasks snooze TASK_ID 5`.
3. It must return to `draft` with a new due time and no new delivery approval.
4. Confirm the new preview to schedule it, or cancel it with `/tasks cancel TASK_ID`.
5. Refresh. Cancelled reminders must not notify later. Cancel only your test IDs.

The browser offers the same confirm/cancel controls and a five-minute snooze.
Snoozing a daily/weekly reminder changes that occurrence; its usual local clock
time remains the recurrence anchor (the time used for future repeats).

### Test 3 — exact dates and repeats

Use `/remind-json` followed by a JSON object (a structured list of named values).
The example below deliberately uses placeholders: choose an actual future date
and time, within the next 366 days, before sending it.

```text
/remind-json {"title":"Phase 2 daily practice","due_at":"YYYY-MM-DDTHH:MM:SS+09:00","timezone":"Asia/Tokyo","repeat":"daily","notification":"text"}
```

1. Replace the date/time with a time about two minutes ahead in Tokyo. Elsewhere,
   use your IANA zone name (a location-based clock rule, such as `Europe/London`)
   and the matching UTC offset (difference from the global reference clock).
2. Review the exact time, daily repeat and silent effect, then confirm.
3. After delivery, refresh. The record should be `queued` for the next day and
   retain the last result. Cancel the test ID to stop future repeats.
4. Submit a draft with a missing offset or a past time. It must be rejected, not
   silently moved to tomorrow. `weekly` and `none` are the other repeat choices.

For daylight saving (seasonal clock changes), nonexistent local times are refused.
A later recurring occurrence that falls in a missing hour pauses for review.
A repeated fall-back hour defaults to its first occurrence for recurrence; the
initial exact-time request can select either occurrence by its offset.
The task record retains the current occurrence and last result, not a full archive
of every historical repeat.

### Test 4 — restart and missed reminders

This is an operator-controlled service test, not a read-only check. Service start
may activate configured devices or voice input; use the precautions above.

1. Schedule a silent test reminder far enough ahead to restart your service safely.
2. Stop and start the Agent using the existing service menu while the reminder is
   still in the future. Reconnect with the same profile/session and list tasks.
3. Expect one queued record and one eventual delivery, without asking the model
   to reconstruct the reminder.
4. For a second silent reminder, keep the service stopped until more than 60
   seconds after its due time. Restart and inspect it. Expect `missed`; the robot
   must not unexpectedly catch up with the old notification.
5. Review or snooze that test record if needed, then cancel the test repeat.

Do not deliberately cut power during delivery. Automated tests cover interrupted
claims: a record that was running becomes `uncertain` on recovery, without
automatic replay. The Pi being powered off cannot deliver an alarm.

## Task progress and cancellation

1. Ask a harmless text question, such as “Explain how rain forms”. This may call
   your selected paid provider; use your normal provider budget settings.
2. In the Local tasks panel, refresh while the request runs. Its record should show
   `request` and `running`. Short requests may finish before you can inspect them.
3. On a sufficiently long text-only request, press **Cancel**. The control must
   respond without waiting behind the model request. Do not use motion to make
   the request longer.
4. Inspect the final task result. Tool evidence can show `failed` or `uncertain`
   even if a model generated a friendly reply. `completed` for a request means
   response processing ended; it is not verification of an external goal.
5. Review a normal completed question. There should be no claim that an email,
   calendar change or other external effect occurred without tool evidence.

Request progress is not a model's private reasoning. Saved step descriptions and
safe result identifiers explain observable actions. General requests are not
replayed after restart. Active tasks are limited to 100 per profile/session, the
list returns the latest 100 records, and long chat listings are shortened; use
the browser panel to inspect more of the returned records.

Default ceilings are six model calls, eight actual tool attempts including safe
retries, 600 seconds per request, 128,000 serialized input characters per model
call, and 1,024 requested output tokens per call. A token is a model's unit of
text. Tool and provider internal behavior can have its own limits; these numbers
are not a monetary accounting system. Oversized input is refused before the
provider call. A new chat may help with long conversation history, but will not
fix an oversized enabled tool catalog.

## Memory review and correction

Use only a test preference that you are comfortable storing locally.

1. Type `I like phase two practice tea.` Normal chat can contact the selected model.
2. Type `/memory review`. Locate the test preference and note its ID. If automatic
   capture did not select that phrasing, do not assume it saved anything; use the
   existing memory list to inspect the result rather than inventing an ID.
3. Check its source references, confidence (how strongly it was inferred), saved
   reason and last confirmation. A historical item may honestly say its original
   reason or confirmation time was not recorded.
4. Type `/memory confirm MEMORY_ID`, replacing the ID. The preference should become
   confirmed, rather than silently changing a technical action's result.
5. Type `/memory edit MEMORY_ID I prefer phase two practice coffee.`
6. Review again and confirm the text changed. A lower-confidence inferred
   structured preference must not silently overwrite a confirmed one; conflicting
   structured values are presented separately for review.
7. Type `/memory forget MEMORY_ID`. Review again. The test preference should be
   absent from both the memory listing and effective structured preferences.
8. Switch to another existing authorized local profile if available. Its review
   must not reveal the first profile's items. Do not delete real profiles for this test.

Technical success/failure memories can be reviewed or removed, but these commands
cannot rewrite them into successes. Profile deletion and reset retain the existing
boundaries and remove associated task rows. Do not reset your database to clean up
these tests. Finished tasks use the conversation-retention setting (default seven
days); queued repeating reminders remain active until cancelled.

## Device communication and optional notifications

1. Open **Guided checks** from the browser menu, or option **15** in the interactive
   Agent menu. Navigate forward, back and return later. These guide steps only
   explain and inspect software; they must not start a device action automatically.
2. Inspect existing status/health. Capability details distinguish disabled or
   missing devices from an execution block. A health result is a short-lived
   observation, not permission to move or proof of a physical connection.
3. For the optional physical reminder test, raise wheels and have an operator ready
   to remove power. No camera/microphone capture is required. Obtain agreement for
   a short audible tone. Keep the existing safety system active.
4. Create an exact-time JSON reminder as above, using `"notification":"display_buzzer"`
   and a short ASCII message, with `"repeat":"none"`. Confirm only after reviewing
   the physical effect and future time.
5. Expect the message on the display for roughly two seconds followed by a short
   buzzer tone. No wheel motion should be requested. Inspect the saved IDE action
   identifier and result, rather than accepting a model's “done”.
6. If the display or buzzer is unavailable or the system is stopped, expect a failed
   or uncertain outcome and no automatic retry. Correct the reported health issue
   using the existing procedure before making a new reviewed test.

Use the existing emergency stop if anything unexpected happens. Do not erase
safety files. A Traditional Chinese font test is separate and remains pending the
font repair; an ASCII notification does not validate that font.

## Actuator-moving checks

These checks cover earlier Phase 0/1 changes, not a prerequisite for silent
reminder tests. They must be supervised on the physical robot with raised wheels.

1. Verify the existing emergency stop before a short permitted movement.
2. Use a short existing movement and Stop. Confirm physical output stops and queued
   work does not restart. Software tests do not establish a physical stop deadline.
3. In the browser, focus a direction button. Hold Space or Enter briefly, release,
   then test losing focus while held. Expect movement permission revoked and Stop
   sent. Test browser zoom and visible keyboard focus as separate usability checks.
4. With movement stopped, verify conflicting real-device ownership is rejected
   before another tool initializes hardware. Do not deliberately run two owners.
5. If a servo continues moving, remove power; keep the robot stopped until the
   failure is investigated. A blocking driver call is not forcibly terminated by
   Python cancellation.

## Power-risk checks

No live shutdown, battery removal, boot-file change or forced power-failure test
is required for Phase 2. Backup/restore tests use temporary data. Do not restore an
archive over your live data just to validate this feature. Earlier installer
changes were checked using previews and fake boot text; they still need the normal
operator-approved deployment acceptance if you choose to deploy them.

## Results and rollback

Record the following without including private conversation text or configuration:

| Check | Expected result | Your result |
| --- | --- | --- |
| Environment and driver verifiers | Pass; missing prerequisites clearly explained | Not run |
| Automated local tests | Pass without hardware or provider opt-in | Not run |
| Face cleanup F1 | 27 camera tests and 8 cleanup tests pass | Not run |
| Optional face cleanup F2 | Success/error/success closes each real backend once | Not run |
| Silent preview/confirm/delivery | One reviewed inbox entry, no sound | Not run |
| Cancel and snooze | Cancel stops future delivery; snooze needs confirmation | Not run |
| Repeat and exact time | Correct next clock time; invalid times refused | Not run |
| Restart/downtime | Future tasks survive; overdue/uncertain work is not replayed | Not run |
| Request progress/cancel | Controls responsive; evidence and uncertainty visible | Not run |
| Preference review/edit/forget | Correct active-profile data and no stale effective value | Not run |
| Optional display/buzzer | Reviewed notification only; no motion | Not run |
| Optional moving/browser checks | Supervised stop/release works physically | Not run |
| Power-risk tests | Not required; no live power action taken | Not run |

On failure, stop the failing test and preserve only non-sensitive error details.
Cancel only synthetic test tasks and forget only synthetic test preferences. For
code rollback, stop the Agent under operator control and revert only the reviewed
refinement patch; keep unrelated edits and private data. Do not run a blanket Git
reset. The database additions are additive, but an older Agent does not deliver
new reminders. Preserve a backup before changing versions, and do not downgrade
by manually deleting database tables.

See the [progress record](refinement_progress_260907.md),
[approved plan](../../DevelopmentPlanDoc/NinjarobotPi5_RefinementPlan_260907.md), and
[wiki maintenance workflow](../../ninjarobot_pi5_wiki/docs/PROJECT_WORKFLOW.md).
