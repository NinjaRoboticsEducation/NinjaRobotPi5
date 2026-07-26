# Immutable driver containment matrix

The copied drivers cannot be edited. V4-owned adapters must contain known
legacy risks as follows.

| Driver or boundary | Audit finding | V4 containment rule | Phase |
| --- | --- | --- | --- |
| OpenClaw runner | A timeout may trigger a one-shot retry and duplicate a physical action | Do not copy the runner; IDE results distinguish failed, cancelled, and unknown outcomes; never automatically retry an unknown physical outcome | 2 |
| `pi5camera` pending records | Recognition IDs are used in paths without a containment check | IDE validates opaque identifiers against a strict schema and keeps all V4 paths under a configured root | 3 |
| `pi5camera` recognition | Recognition backends are not consistently closed | Camera adapter owns the backend lifecycle and closes it in a guarded teardown path | 3 |
| `pi5buzzer` worker | Shutdown may race a playback worker | Buzzer adapter serializes play/stop/close and waits for a known idle state before teardown | 3 |
| `pi5buzzer` GPIO backend | Backend cleanup is process-global | Scheduler gives the buzzer exclusive ownership of the global GPIO cleanup resource; it is closed last among GPIO adapters | 3 |
| `pi5vl53l0x` calibration | Offset restoration is not protected by `finally` | Distance calibration is disabled in V4 until an adapter-owned recovery transaction and Pi checklist exist | 2 |
| `pi5disp` configuration | Copied JSON rotation differs from the required 90-degree orientation | V4 configuration passes rotation 90 explicitly; copied configuration remains untouched | 3 |
| All drivers | Argument schemas and health semantics differ | Adapters expose strict capability schemas, reject unknown fields, normalize errors, and report health per capability | 1–3 |
| `pi5mic` | Public exports include OpenClaw and Gemini-specific components | V4 imports only approved device-facing modules; no OpenClaw transport or presence controller is registered | 3 and 8 |
| `pi5servo` | Package and module versions differ | Record both values for diagnostics; do not rewrite either version | 3 |
