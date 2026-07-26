# Phase 1 validation report

Date: 2026-07-26

Phase: V4 contracts and package skeletons

Hardware accessed: No

## 1. Scope of validation

This report covers the new IDE and agent packages, strict contracts,
configuration, deterministic fakes, unified CLI, package boundaries, and root
workspace. It does not certify a real driver adapter or robot action.

Automated result: **PASS**

- Root/V4 tests: 30 passed.
- Managed-library tests: 447 passed.
- Strict mypy: passed for 12 new source files.
- Compilation, Ruff lint, Ruff formatting, lock check, and `git diff --check`:
  passed.
- Driver provenance: 222 tracked files and 23 authorized repairs, unchanged.

## 2. Safety notes

All Phase 1 commands are non-moving. They do not import a `pi5*` package or open
GPIO, PWM (pulse-width modulation), I2C, SPI, camera, or audio devices.
`dry-run` must always identify its result as simulated.

## 3. Safe smoke tests

```bash
uv sync --frozen
uv run --frozen ninjarobot_pi5_cli --version
uv run --frozen ninjarobot_pi5_cli --help
uv run --frozen ninjarobot_pi5_cli config validate \
  --config config/ninjarobot_pi5.toml.example
```

Expected: version `0.1.0`, help lists `config`, `contracts`, and `dry-run`, and
configuration reports GPIO27, GPIO12/GPIO13, DC4/RST5/BL6, rotation 90°, and
brightness 75%.

## 4. Communication/interface tests

```bash
uv run --frozen ninjarobot_pi5_cli contracts schema
uv run --frozen ninjarobot_pi5_cli dry-run \
  --capability system.echo \
  --json '{"message":"hello"}'
```

Expected: schema output contains `action_request`, `action_result`,
`capability_descriptor`, `model_request`, and `model_turn`. Dry-run status is
`succeeded`, data contains `"simulated": true`, and retry safety is `safe`.

## 5. Actuator-moving tests

None. Phase 1 has no real actuator path. Do not substitute a `pi5servo`,
`pi5buzzer`, or `pi5disp` hardware command for this checklist.

## 6. Expected outcomes

- Unknown configuration fields fail validation.
- Conflicting GPIO assignments fail validation.
- Agent source contains no `pi5*`, OpenClaw, or historical-runtime import.
- Strict typing, serialization, and schema tests pass.
- All managed-driver hashes remain unchanged from their approved states.

## 7. Pass/fail checklist

- [ ] CLI version and help pass.
- [ ] Example configuration passes and prints the confirmed wiring.
- [ ] Contract schema command returns valid JSON.
- [ ] Dry-run clearly reports simulated success.
- [ ] Complete root pytest passes.
- [ ] Strict mypy passes.
- [ ] Immutable-driver verifier passes.
- [ ] No physical movement, sound, display change, capture, or recording occurs.

## 8. Rollback steps

1. Stop; no hardware cleanup is needed because Phase 1 opens no hardware.
2. Return to the Phase 0 commit:
   `git switch --detach 9812bdf`
3. Run:
   `uv run --frozen python scripts/verify_immutable_drivers.py`
4. Return to the normal branch with:
   `git switch main`

Do not use `git reset --hard`; it could discard unrelated local work.
