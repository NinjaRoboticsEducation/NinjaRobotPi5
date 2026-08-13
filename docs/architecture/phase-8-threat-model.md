# Phase 8 Threat Model

## Protected assets

- physical safety and exclusive ownership of motors, display, buzzer, camera,
  microphone, I2C, SPI, GPIO, and PWM resources
- user profiles, faces, conversations, preferences, memories, behavior assets,
  configuration, calibration, and safety state
- provider keys, ngrok authtoken, pairing/session credentials, local TLS keys,
  and privileged shutdown authority
- truthful presentation of listening, connected, Greeting, Idle, Error, stop,
  and power-off state

## Trust boundaries and required controls

| Boundary | Threat | Required control |
|---|---|---|
| Physical QR → browser | Photograph, reuse, or share a pairing token | High-entropy short lifetime, single use, secure cookie exchange, rotation and local revocation |
| Internet → ngrok endpoint | Anonymous robot control, scanning, abuse, or malformed traffic | Pairing before assets/API/WebSocket, strict message schemas, origin/size bounds, exclusive controller lease, no inspection API exposure |
| ngrok service → local HTTPS | TLS downgrade or credential leakage | HTTPS upstream, NinjaRobot CA trust, explicit pyngrok config, redacted errors, no authtoken in URL/QR/logs |
| Browser → power-off | Accidental, forged, stale, or replayed shutdown | Paired active lease, visible Power Off/Cancel modal, expiring single-use nonce, ordered safe cleanup, narrow privilege helper |
| Ambient audio → agent | False wake, eavesdropping, retained recordings, duplicate dispatch | Local bounded detector, visible state, silence/15-second cap, no wake retention, temporary deletion, single-flight state machine |
| Voice transcript → motion | Motion without consent or after controller loss | Existing confirmed arm extended to voice, source tracking, fail-closed revoke set, normal policy/IDE path, no uncertain retry |
| Service boot → hardware | Duplicate ownership, restart loop, premature Greeting | Single lock/socket owner, one service, restart throttling, no separate voice/ngrok daemon, paired-WebSocket exactly-once Greeting |
| Dependency/model supply chain | Replaced model/binary or boot-time download | Locked packages, packaged assets, checksums, explicit setup install, license/provenance audit, no unattended downloads |
| Logs/status/database | Secret, raw audio, pairing fragment, or provider response leakage | Central redaction, bounded safe error categories, negative persistence tests, owner-only files |

## Residual risks accepted for `v1.0.0`

- A person with physical access to an unexpired QR can pair a browser.
- ngrok availability, interstitials, quotas, pricing, and account enforcement
  are external service conditions.
- Wake-word accuracy depends on voice, microphone placement, noise, threshold,
  and the approved model; text/manual microphone input remains the fallback.
- The current hardware has documented physical power-path residual risks;
  powered motion validation requires raised wheels and an accessible cutoff.
- Face recognition supports profile selection and is not security
  authentication.

These risks must remain visible in setup and validation documentation. They do
not authorize anonymous remote access, automatic motion arming, or suppression
of errors.
