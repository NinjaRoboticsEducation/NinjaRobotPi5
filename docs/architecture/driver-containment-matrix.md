# Managed driver containment matrix

The copied drivers retain standalone responsibilities and may change only
through the authorized managed-driver repair workflow. V4-owned adapters
contain integration risks as follows.

| Driver or boundary | Audit finding | V4 containment rule | Phase |
| --- | --- | --- | --- |
| OpenClaw runner | A timeout may trigger a one-shot retry and duplicate a physical action | Do not copy the runner; IDE results distinguish failed, cancelled, and unknown outcomes; never automatically retry an unknown physical outcome | 2 |
| `pi5camera` capture output | The standalone capture API saves a file for every photograph | Phase 3.4 uses a private staging directory, deletes media by default, confines explicit retention to one configured root, rejects path components, and never overwrites | 3.4 |
| `pi5camera` pending records | Recognition IDs are used in paths without a containment check | Recognition is not exposed in Phase 3.4; Phase 8 must validate opaque identifiers and keep every generated path under a configured root | 8 |
| `pi5camera` recognition | Recognition backends are not consistently closed | Recognition is not exposed in Phase 3.4; a later adapter must own and close the recognition backend in a guarded teardown path | 8 |
| `pi5buzzer` worker | Shutdown may race a playback worker | Buzzer adapter serializes play/stop/close and waits for a known idle state before teardown | 3 |
| `pi5buzzer` GPIO backend | Backend cleanup is process-global | Scheduler gives the buzzer exclusive ownership of the global GPIO cleanup resource; it is closed last among GPIO adapters | 3 |
| `pi5vl53l0x` calibration | Offset restoration is not protected by `finally` | Distance calibration is disabled in V4 until an adapter-owned recovery transaction and Pi checklist exist | 2 |
| `pi5disp` configuration | Copied JSON rotation differs from the required 90-degree orientation | V4 configuration passes rotation 90 explicitly; copied configuration remains untouched | 3 |
| All drivers | Argument schemas and health semantics differ | Adapters expose strict capability schemas, reject unknown fields, normalize errors, and report health per capability | 1–3 |
| `pi5mic` | Package-root and core exports eagerly import historical OpenClaw, Gemini, wake-word, and listener components | Phase 3.5 bypasses those exports and loads only errors, models, audio backend, device discovery, and recorder modules into contained namespace packages; runtime tests reject every other `pi5mic` module | 3.5 and 8 |
| `pi5mic` recording output | The standalone recorder always writes a WAV file | Phase 3.5 records into a private staging directory, deletes audio by default, confines explicit retention, uses permission `600`, and never overwrites | 3.5 |
| `pi5servo` | Package and module versions differ | Record both values for diagnostics; do not rewrite either version | 3 |
