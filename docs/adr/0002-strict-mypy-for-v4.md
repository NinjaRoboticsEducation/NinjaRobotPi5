# ADR 0002: Strict mypy for new V4 packages

- Status: Accepted
- Date: 2026-07-26
- Owners: NinjaRobotPi5V4 maintainers

## Context

Phase 1 introduces long-lived contracts that will be implemented by real and
fake adapters. Interface drift is cheaper to catch before runtime, especially
for cancellation, error, and retry-safety paths.

## Decision

Run mypy in strict mode over `ninjarobot_pi5_ide/src` and
`ninjarobot_pi5_agent/src`. Strict typing does not apply retroactively to the
independent managed `pi5*` libraries.

Public functions and protocol methods require complete annotations. Suppression
comments must be narrow and justified; unused suppressions fail the gate.

## Consequences

- New V4 code has a stronger interface gate from its first phase.
- Managed drivers remain untouched and retain their independent validation.
- Third-party missing-type exceptions may be added only for a specific module,
  never as a global ignore.

## Validation

Run:

```bash
uv run --frozen mypy \
  ninjarobot_pi5_ide/src \
  ninjarobot_pi5_agent/src
```

The command must pass before Phase 1 closes.
