"""Unified CLI for V4 contracts, simulation, and explicit hardware checks."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ninjarobot_pi5_ide.testing import FakeIDEClient
from pydantic import ValidationError

from ninjarobot_pi5_ide import (
    ActionLedger,
    ActionRequest,
    ActionResult,
    ActionStatus,
    CapabilityDescriptor,
    CapabilityRegistry,
    ExecutionEngine,
    HealthReport,
    ResourceHealth,
    RiskLevel,
    VL53L0XDistanceAdapter,
    load_robot_config,
)

from . import __version__
from .models import ModelRequest, ModelTurn


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser without touching hardware or configuration."""
    parser = argparse.ArgumentParser(
        prog="ninjarobot_pi5_cli",
        description="NinjaRobotPi5V4 deterministic IDE and validation tools.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    config_parser = subcommands.add_parser(
        "config",
        help="Validate V4-owned configuration.",
    )
    config_subcommands = config_parser.add_subparsers(dest="config_command", required=True)
    validate_parser = config_subcommands.add_parser(
        "validate",
        help="Validate one TOML configuration without opening hardware.",
    )
    validate_parser.add_argument("--config", required=True, help="Path to the TOML file.")

    contracts_parser = subcommands.add_parser(
        "contracts",
        help="Inspect machine-readable contract schemas.",
    )
    contracts_subcommands = contracts_parser.add_subparsers(
        dest="contracts_command",
        required=True,
    )
    contracts_subcommands.add_parser(
        "schema",
        help="Print core JSON schemas (machine-readable data-shape definitions).",
    )

    dry_run_parser = subcommands.add_parser(
        "dry-run",
        help="Execute one clearly simulated action through the fake IDE.",
    )
    dry_run_parser.add_argument(
        "--capability",
        default="system.echo",
        help="Namespaced fake capability name.",
    )
    dry_run_parser.add_argument(
        "--json",
        default="{}",
        help="JSON object passed to the fake capability.",
    )

    subcommands.add_parser(
        "capabilities",
        help="List Phase 2 capabilities without opening hardware.",
    )

    health_parser = subcommands.add_parser(
        "health",
        help="Check the simulated or real distance adapter without taking a measurement.",
    )
    _add_backend_options(health_parser)

    actions_parser = subcommands.add_parser(
        "actions",
        help="Inspect durable action records.",
    )
    actions_subcommands = actions_parser.add_subparsers(dest="actions_command", required=True)
    show_parser = actions_subcommands.add_parser(
        "show",
        help="Show the latest state of one action.",
    )
    show_parser.add_argument("--ledger", required=True, help="Path to the SQLite action ledger.")
    show_parser.add_argument("--action-id", required=True, help="Action identifier to inspect.")

    distance_parser = subcommands.add_parser(
        "distance",
        help="Exercise the Phase 2 VL53L0X distance capability.",
    )
    distance_subcommands = distance_parser.add_subparsers(
        dest="distance_command",
        required=True,
    )
    read_parser = distance_subcommands.add_parser(
        "read",
        help="Read simulated data unless --real is supplied explicitly.",
    )
    _add_backend_options(read_parser)
    read_parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of separate actions to execute (1 to 100).",
    )
    read_parser.add_argument(
        "--interval",
        type=float,
        default=0.2,
        help="Seconds between repeated reads.",
    )
    read_parser.add_argument(
        "--action-id",
        help="Explicit action ID for a single read; useful for idempotency testing.",
    )
    read_parser.add_argument(
        "--idempotency-key",
        help="Explicit idempotency key for a single read.",
    )
    return parser


def _add_backend_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--real",
        action="store_true",
        help="Explicitly open the configured VL53L0X on Raspberry Pi I2C.",
    )
    parser.add_argument(
        "--config",
        default="config/ninjarobot_pi5.toml.example",
        help="V4 TOML configuration used by --real.",
    )
    parser.add_argument(
        "--ledger",
        default="data/phase2-actions.sqlite3",
        help="SQLite action-ledger path (a local database file).",
    )


def _schema_bundle() -> dict[str, dict[str, Any]]:
    return {
        "capability_descriptor": CapabilityDescriptor.model_json_schema(),
        "action_request": ActionRequest.model_json_schema(),
        "action_result": ActionResult.model_json_schema(),
        "model_request": ModelRequest.model_json_schema(),
        "model_turn": ModelTurn.model_json_schema(),
    }


async def _run_fake_action(capability: str, arguments: dict[str, Any]) -> ActionResult:
    descriptor = CapabilityDescriptor(
        name=capability,
        version="1.0.0",
        description="Simulated echo capability.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk=RiskLevel.READ_ONLY,
        resources=("fake_ide",),
        default_timeout_seconds=5.0,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
    )
    client = FakeIDEClient((descriptor,))
    request = ActionRequest(
        action_id="dry-run-0001",
        capability=capability,
        arguments=arguments,
        requested_by="manual-cli",
        session_id="manual-session",
        idempotency_key="dry-run-0001",
    )
    try:
        return await client.execute(request)
    finally:
        await client.close()


class _SimulatedDistanceSensor:
    """Hardware-free sensor double whose data shape matches the managed driver."""

    def get_data(self) -> dict[str, Any]:
        return {
            "distance_mm": 250,
            "raw_value": 250,
            "is_valid": True,
            "timestamp": 0.0,
        }

    def health_check(self) -> bool:
        return True

    def close(self) -> None:
        return None


def _build_distance_engine(
    *,
    real: bool,
    config_path: str,
    ledger_path: str,
) -> ExecutionEngine:
    if real:
        config = load_robot_config(config_path)
        adapter = VL53L0XDistanceAdapter(
            i2c_bus=config.hardware.i2c.bus,
            i2c_address=config.hardware.i2c.vl53l0x_address,
        )
    else:
        adapter = VL53L0XDistanceAdapter(
            sensor_factory=lambda _bus, _address: _SimulatedDistanceSensor(),
        )
    return ExecutionEngine(
        CapabilityRegistry([adapter]),
        ActionLedger(Path(ledger_path)),
    )


async def _list_capabilities() -> tuple[CapabilityDescriptor, ...]:
    engine = ExecutionEngine(
        CapabilityRegistry([VL53L0XDistanceAdapter()]),
        ActionLedger(":memory:"),
    )
    try:
        return await engine.capabilities()
    finally:
        await engine.close()


async def _run_health(*, real: bool, config_path: str, ledger_path: str) -> HealthReport:
    engine = _build_distance_engine(
        real=real,
        config_path=config_path,
        ledger_path=ledger_path,
    )
    try:
        return await engine.health()
    finally:
        await engine.close()


async def _run_distance_reads(
    *,
    real: bool,
    config_path: str,
    ledger_path: str,
    count: int,
    interval: float,
    action_id: str | None,
    idempotency_key: str | None,
) -> tuple[ActionResult, ...]:
    if not 1 <= count <= 100:
        raise ValueError("--count must be between 1 and 100")
    if not 0 <= interval <= 60:
        raise ValueError("--interval must be between 0 and 60 seconds")
    if count != 1 and (action_id is not None or idempotency_key is not None):
        raise ValueError("explicit action IDs and idempotency keys require --count 1")
    engine = _build_distance_engine(
        real=real,
        config_path=config_path,
        ledger_path=ledger_path,
    )
    results: list[ActionResult] = []
    try:
        for index in range(count):
            generated = uuid.uuid4().hex
            current_action_id = action_id or f"distance-{generated}"
            current_key = idempotency_key or f"distance-key-{generated}"
            result = await engine.execute(
                ActionRequest(
                    action_id=current_action_id,
                    capability="distance.read",
                    arguments={},
                    requested_by="manual-cli",
                    session_id="manual-distance-test",
                    idempotency_key=current_key,
                )
            )
            results.append(result)
            if index + 1 < count and interval:
                await asyncio.sleep(interval)
        return tuple(results)
    finally:
        await engine.close()


def _show_action(ledger_path: str, action_id: str) -> str:
    ledger = ActionLedger(Path(ledger_path))
    try:
        record = ledger.get(action_id)
    finally:
        ledger.close()
    if record is None:
        raise KeyError(f"unknown action: {action_id}")
    return record.model_dump_json(indent=2)


def _parse_json_object(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("--json must contain a JSON object")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    """Run the unified V4 CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "config" and args.config_command == "validate":
            config = load_robot_config(args.config)
            print(
                "Configuration valid: "
                f"buzzer=GPIO{config.hardware.buzzer.gpio}, "
                f"servos={','.join(config.hardware.servos.endpoints)}, "
                f"display=DC{config.hardware.display.dc_gpio}/"
                f"RST{config.hardware.display.reset_gpio}/"
                f"BL{config.hardware.display.backlight_gpio}, "
                f"rotation={config.hardware.display.rotation}, "
                f"brightness={config.hardware.display.brightness}%"
            )
            return 0
        if args.command == "contracts" and args.contracts_command == "schema":
            print(json.dumps(_schema_bundle(), indent=2, sort_keys=True))
            return 0
        if args.command == "dry-run":
            arguments = _parse_json_object(args.json)
            result = asyncio.run(_run_fake_action(args.capability, arguments))
            print(result.model_dump_json(indent=2))
            return 0
        if args.command == "capabilities":
            descriptors = asyncio.run(_list_capabilities())
            print(
                json.dumps(
                    [item.model_dump(mode="json") for item in descriptors],
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "health":
            health = asyncio.run(
                _run_health(
                    real=args.real,
                    config_path=args.config,
                    ledger_path=args.ledger,
                )
            )
            print(health.model_dump_json(indent=2))
            return 0 if health.status is ResourceHealth.READY else 1
        if args.command == "actions" and args.actions_command == "show":
            print(_show_action(args.ledger, args.action_id))
            return 0
        if args.command == "distance" and args.distance_command == "read":
            results = asyncio.run(
                _run_distance_reads(
                    real=args.real,
                    config_path=args.config,
                    ledger_path=args.ledger,
                    count=args.count,
                    interval=args.interval,
                    action_id=args.action_id,
                    idempotency_key=args.idempotency_key,
                )
            )
            if len(results) == 1:
                print(results[0].model_dump_json(indent=2))
            else:
                print(
                    json.dumps(
                        [item.model_dump(mode="json") for item in results],
                        indent=2,
                    )
                )
            return 0 if all(result.status is ActionStatus.SUCCEEDED for result in results) else 1
    except (
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
        ValidationError,
        json.JSONDecodeError,
        sqlite3.Error,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    parser.error("unsupported command")
    return 2
