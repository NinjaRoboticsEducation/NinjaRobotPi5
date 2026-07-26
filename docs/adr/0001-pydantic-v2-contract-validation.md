# ADR 0001: Pydantic v2 for boundary validation

- Status: Accepted
- Date: 2026-07-26
- Owners: NinjaRobotPi5V4 maintainers

## Context

IDE actions, model requests, configuration, memory candidates, and provider
results cross trust boundaries. Python type hints alone do not validate runtime
data, while handwritten validation would duplicate schema and serialization
logic.

## Decision

Use Pydantic v2 for Phase 1 boundary models. Contract models use strict mode,
reject unknown fields, and are frozen against attribute reassignment. They
provide JSON serialization, JSON parsing, and JSON Schema generation from the
same definitions.

TOML arrays that intentionally become tuples are normalized by an explicit
validator. This is a documented conversion, not permissive global coercion.
Nested JSON dictionaries remain normal mutable containers, so callers must not
mutate a model's nested data after validation.

## Consequences

- Invalid and unexpected input fails before reaching hardware-facing code.
- Provider tool schemas and CLI inspection use generated JSON Schema.
- Pydantic becomes a small runtime dependency of both V4 packages.
- Frozen Pydantic models provide shallow rather than recursively deep
  immutability.

## Validation

- Reject unknown fields and unsafe scalar coercion.
- Round-trip core contracts through JSON.
- Generate schemas with `additionalProperties` disabled.
- Keep Pydantic out of all managed `pi5*` projects.
