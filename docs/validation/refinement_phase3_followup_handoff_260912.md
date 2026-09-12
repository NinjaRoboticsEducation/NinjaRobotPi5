# Phase 3 follow-up implementation handoff

The software refinements are implemented. Start with the
[walkthrough and step-by-step manual tests](refinement_phase3_followup_walkthrough_260912.md).
Physical speaker and mobile-device acceptance remains pending. Do not begin
Phase 4 as part of this handoff.

## What changed and why

| Area | Cause found | Implemented change |
| --- | --- | --- |
| Task queries | Full internal records could exceed the unchanged 20,000-character model-message limit. | Owned, filtered, compact pages with IDs and contents; default 10, maximum 20, additionally bounded by serialized size. Existing direct task controls and stored records remain. |
| Oversized/interrupted results | Raw result serialization could fail after a tool had already executed, leaving an unmatched historical call. | Central bounded JSON output preserves execution status. Interrupted model context is repaired with explicit uncertainty; history is not rewritten and actions are not replayed. |
| Command help | CLI help and explicitly selected skills did not make ordinary how-to questions discoverable. | Shared command reference, read-only lookup provider and bundled `robot-command-help` skill; narrow natural-language routing, `/help TOPIC` and `/guide 1`–`5`. |
| Web controls | Five control sections occupied four grid rows; keyboard resizing and hidden overflow could squeeze panels. | Remove the dropdown, replace A/B with speech controls, preserve minimum layout dimensions with scrolling, keep long messages inside the transcript, and distinguish physical touch-device orientation from keyboard geometry. |
| Bluetooth setup | Pairing, audio readiness and persistence required separate terminal procedures. | IDE menu 8 and `bluetooth connect` perform bounded discovery, numbered selection, selected-device pairing/trust/connect and audio-output verification before saving. |
| Reconnection | Agent-independent reconnection was absent. | Optional user service retries only the saved paired/trusted device, including while the Agent is stopped. Explicit disconnect disables the helper across boots. No Agent boot startup is added. |
| Configuration | The existing serializer omitted speech-output fields. | Round-trip all speech fields and the optional speaker section; preserve existing voice/volume/microphone values and detect configuration changes during setup. |
| Opening words | The full generated audio reaches a newly opened playback stream. The physical loss location is not proven. | Bounded same-stream Bluetooth startup silence preserves every original sample. The selected speaker can resolve a changed profile suffix without falling back to another device. Cold/warm audibility still needs operator confirmation. |

The hardware path remains Agent → IDE → managed driver → device. No managed
`pi5*` source, existing robot behavior definition or hardware API was changed.
The optional D-Bus client (communication with the OS Bluetooth service) is
`dbus-fast==5.0.22`; the workspace lock pins its artifacts. Pairing callbacks are
restricted to the BlueZ service and the selected device. Background reconnect
cannot pair, trust, scan, capture media or start a robot assembly.

## Validation actually completed

| Check | Result |
| --- | --- |
| Main `uv run --frozen --no-sync pytest -q` | **790 passed**, 34.61 seconds |
| Isolated `pi5buzzer/tests` | **68 passed** |
| Isolated `pi5camera/tests` | **27 passed** |
| Isolated `pi5disp/tests` | **65 passed** |
| Isolated `pi5mic/tests` | **92 passed** |
| Isolated `pi5servo/tests` | **134 passed** |
| Isolated `pi5vl53l0x/tests` | **71 passed** |
| `ruff check .` and `ruff format --check .` | Passed; 417 Python files formatted |
| `mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src` | Passed; 96 source files |
| `compileall` for IDE, Agent, scripts and tests | Passed |
| Immutable-driver verifier | Passed; 222 tracked files, six drivers, existing 56 authorized repairs |
| Workspace-driver source verifier | Passed; all six execute from this checkout |
| `node --check` on web `app.js` | Passed |
| Chromium 140 simulated browser tests | Passed in all four UI languages at 390×844, 360×640, 600×900 and 1280×800 (16 cases); typing, long replies, buttons, panels and simulated keyboard resize; no script errors |
| Current documentation links | 178 local links across 11 documents checked; zero missing targets or anchors |
| `git diff --check` | Passed |
| Agent and IDE source/wheel builds | Passed; new skill files, web assets and Bluetooth helper present in wheels |

The existing main-suite warning concerns Starlette's HTTPX test client. The
unchanged microphone suite warns about Python's deprecated `audioop` module.
Neither warning is a failed test or a new driver change.

Browser checks use `scripts/validate_phase3_web_layout.py` with fake transport;
they never connect to a live robot. Playwright 1.55.0 and its browser were installed
in a temporary validation environment, not as robot runtime dependencies. A real
Android keyboard and iPhone Safari have not been tested by this automation.
The optional direct D-Bus binding test requires the Bluetooth extra; it ran in
this validation environment and is skipped when that optional dependency is absent.

## Documentation and wiki impact

README and the wiki README link to new complete Installation, Development,
MCP/Skill and Development Log sources under `raw/.../2026-09-12/`. Registered
originals are preserved. The earlier Phase 3 handoff and walkthrough link to the
new follow-up guide, and obsolete dropdown instructions have been corrected.
The example configuration and third-party notices describe the new options.

Wiki ingestion, semantic review, publication and fingerprint updates were
**not run**, as requested. The published document map and curated pages may
therefore describe the older checkpoint; the READMEs identify the current full
sources explicitly. No human wiki review or physical verification is claimed.

## Remaining acceptance and practical limits

- **Safe smoke:** command help, task IDs/contents and optional service preview.
  Expected: useful instructions and no device effects from help or preview.
- **Device communication:** pair/connect and power-cycle the selected speaker
  with Agent stopped and running. Expected: reconnect within the documented retry
  interval, without an Agent start or replayed speech. Boot/logout operation
  requires user lingering and working OS audio services.
- **Audible output:** compare first words on cold, warm, idle and reconnected
  playback; test stop/off. Expected: complete words and prompt cancellation.
  The startup buffer is a mitigation, not proof that a particular speaker's
  internal audio gating has been corrected.
- **Browser:** run the guide on the owner's actual phone/browser. Expected:
  reachable controls and stable transcript geometry while typing and receiving.
- **Actuator-moving:** none required for these new features. Keep any additional
  motor regression opt-in, with raised wheels and an operator ready to stop it.
- **Power risk:** no shutdown, reboot, live service deployment, capture or hardware
  movement was performed by automated validation. A planned boot test is optional
  operator work, separate from the software gate.

Rollback instructions are in the walkthrough. Preserve user data, pairing records
and voice models. No commit, push, release or live reconnect-service installation
was performed during this implementation.
