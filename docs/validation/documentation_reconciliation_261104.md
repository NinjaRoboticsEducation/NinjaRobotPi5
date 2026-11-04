# Documentation reconciliation — 4 November 2026

This documentation-only update reconciles the README and latest full raw manuals
with the current Fusion HAT+ implementation and follow-up repairs. Historical
plans, registered sources and compiled wiki pages are preserved. It is not a
claim that every historical document describes today's runtime.

## Evidence and coverage

| Feature | Implementation evidence | Documentation outcome |
| --- | --- | --- |
| Fusion installation | `scripts/fusion_hat_setup.py`, `vendor/fusion-hat/manifest.json` | Full normal-user prepare/preview, privileged apply, manual reboot and readiness sequence; persistent source and per-kernel limits |
| Twelve servo ports and calibration | Fusion backend, calibration repair report and existing raw manual | PWM0–11, shared 50 Hz, staged points, F save/Q discard, explicit movement warning |
| Embedded audio | Fusion installation/readiness and onboarding implementation | Embedded defaults, independent USB/Bluetooth options; tone, synthesis and recognition distinguished |
| Ollama routes | `setup_wizard.py` provider flow | Downloaded local models require no cloud key; cloud credentials extend choices |
| Safety recovery | Serena inspection of `AgentRuntime.resume_system` | Motion-only versus system recovery dispatch, health checks, separate re-arming |
| Speech and shutdown provisioning | `prepare_speech_voice.py`, deployment CLI and audit | Preview/apply speech assets; separate helper installation and supervised shutdown test |
| Browser microphone | Current `app-agent.js` and lifecycle validation report | Retain identity until onend; queue explicit restart, cancel on Send/hide, distinguish robot voice input |
| Facial expressions, 48 kHz input and memory filtering | Current post-integration audit and prior source manuals | Retained feature descriptions and manual acceptance; no new physical qualification claims |

The compiled wiki's document map still registers `2026-11-03-04`; current raw
successors are `2026-11-04-03`. Wiki search, check and lint were attempted but
reported the missing separate wiki environment. Direct local sources were used.
No environment setup, ingestion, semantic review, source registration or
fingerprint refresh was performed.

## Corrections

The README previously required readers to assemble Fusion installation from
several incident reports and retained cloud-only steps beneath its broader
local/cloud support claim. Hardware summaries disagreed with wiring tables,
USB input was presented as universal, PCA9685 listed only twelve ports in one
table, and its VCC instruction did not distinguish logic from servo power.
These are corrected; board-specific electrical verification remains necessary.
The latest raw sources also carried a superseded claim that a final browser
transcript immediately terminated the session. Natural completion now governs
release and restart. Old native GPIO/X1208 examples are explicitly baseline-only.

## Validation and remaining work

- Repository documentation/governance tests: **10 passed**.
- Immutable-driver and workspace-source verifiers: **passed**; no driver changes.
- Relative links in both READMEs and three new raw manuals: checked locally.
- `git diff --check`: passed.
- Wiki check/lint: blocked by missing wiki environment, not run successfully.
- No runtime code changed, so no new full runtime regression run was required.
- No recording, playback, movement, driver installation, reboot or shutdown ran.

The README provides separate safe smoke, consented device communication,
actuator-moving and power-risk acceptance steps with expected outcomes and
rollback guidance. The owner should follow those tests before ingesting the new
manuals. Third-party notices and MCP manual have no semantic changes because
this update changes neither dependencies nor external tool contracts.
