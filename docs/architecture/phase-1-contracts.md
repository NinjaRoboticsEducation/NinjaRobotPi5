# Phase 1 contract reference

Phase 1 creates stable data boundaries without opening hardware. The agent may
import `ninjarobot_pi5_ide`, but it cannot import a `pi5*` package. Real
execution engines, schedulers, providers, and device adapters begin in later
phases.

## IDE contracts

`CapabilityDescriptor` describes a callable operation, its JSON input/output
schemas, risk, required resources, timeout, idempotency, cancellation, and
confirmation rules.

`ActionRequest` carries a unique action ID and idempotency key. An idempotency
key is a unique label used later to prevent accidental duplicate execution.
Deadlines and result timestamps must include a timezone.

`ActionResult` always states its lifecycle status and retry safety. A failed,
cancelled, or rejected result must include structured `ErrorDetails`. A
successful result cannot include an error.

Example:

```python
from datetime import UTC, datetime

from ninjarobot_pi5_ide import ActionRequest

request = ActionRequest(
    action_id="manual-0001",
    capability="distance.read",
    arguments={},
    requested_by="operator",
    session_id="manual-session",
    deadline=datetime.now(tz=UTC),
    idempotency_key="manual-0001",
)
```

## Error semantics

An error has a stable uppercase code, a beginner-readable message, optional
technical detail, the affected capability/action, whether execution definitely
did not happen, and one retry classification:

- `safe`: deterministic evidence says repeating is safe.
- `unsafe`: repeating could duplicate a physical action.
- `unknown`: the outcome is not known; automatic retry is forbidden.

## Agent contracts

`ModelRequest`, `ModelTurn`, `ToolDefinition`, and `ToolCall` normalize provider
differences. `SessionRecord` and `MemoryCandidate` establish provider-neutral
session and memory shapes. A memory candidate is only a suggestion; later
deterministic policy decides whether it is stored.

## Configuration

`config/ninjarobot_pi5.toml.example` is V4-owned. It records GPIO12/GPIO13
servos, GPIO27 buzzer, and the ST7789V display using DC4/RST5/BL6, rotation 90°,
and brightness 75%. It never rewrites a driver-local JSON file.

Provider credentials are represented only by environment-variable names such
as `OPENAI_API_KEY`; secret values must never be placed in the TOML file.

## Fakes

`FakeIDEClient`, `FakeProvider`, `FakeClock`, and
`DeterministicIDGenerator` provide repeatable tests. Fake results contain
`"simulated": true` and never import or access hardware.
