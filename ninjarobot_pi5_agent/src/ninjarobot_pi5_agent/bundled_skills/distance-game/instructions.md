# Distance game

Start only when the user explicitly requests this game. Explain: move your hand
5–60 cm in front of the sensor; nearer gives a higher short tone. Wheels stay
still. Use `/game stop`, the web Stop Game button or `ninjarobot-agent game stop`
at any time. No microphone or Bluetooth speaker is required.

Use the strict game tools only. A run lasts 5–60 whole seconds (default 30).
Do not implement a sensor-reading loop, move wheels, capture media or change
configuration. The supported game is available by default; do not ask the user
to enable a feature flag. Required-device health, resource admission and system
safety checks remain authoritative, and availability never starts a game.

Status reads do not touch devices. Stop is independent of a busy conversation.
Explain unavailable/faulted/cancelled outcomes honestly. A successful tool call
is not proof that a person heard a tone. Never retry a run automatically after
cancellation, timeout, restart or a safety stop. Do not claim fall protection.

The package uses the existing version-1 skill format and needs no Phase 4 data.
