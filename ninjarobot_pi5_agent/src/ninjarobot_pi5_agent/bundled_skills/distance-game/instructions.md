# Distance game

Start only when the user explicitly requests this game. Explain: move your hand
5–60 cm in front of the sensor; nearer gives a higher short tone. Wheels stay
still. Use `/game stop`, the web Stop Game button or `ninjarobot-agent game stop`
at any time. No microphone or Bluetooth speaker is required.

Tell the user to place their hand before starting, not after the final chat
reply: the run tool returns only after the game ends. A starting notice appears
in web chat. No target in the playing area means silent waiting for the rest of
the requested duration, not a broken or unavailable sensor. If the result says
`no_target_detected`, explain hand placement instead of claiming a sensor fault.
For `readings_unavailable`, use the returned explanation and diagnostic counts;
do not confuse rejected/stale readings with a missing device.

Use the strict game tools only. A run lasts 5–60 whole seconds (default 30).
Do not implement a sensor-reading loop, move wheels, capture media or change
configuration. The supported game is available by default; do not ask the user
to enable a feature flag. Required-device health, resource admission and system
safety checks remain authoritative, and availability never starts a game.

On a new explicit request, use the run tool once and report its current result.
An older unavailable result in conversation or game status is historical, not
proof of a current device fault. Normal game cleanup releases the buzzer, and
the next run silently initializes it and safely recovers completed sensor work
before checking health. Do not refuse a new request solely because the previous
game reported an unavailable device. Do not bypass a current safety refusal,
perform system Resume yourself, or automatically retry the same failed request.

Status reads do not touch devices. Stop is independent of a busy conversation.
Explain unavailable/faulted/cancelled outcomes honestly. A successful tool call
is not proof that a person heard a tone. Never retry a run automatically after
cancellation, timeout, restart or a safety stop. Do not claim fall protection.

The package uses the existing version-1 skill format and needs no Phase 4 data.
