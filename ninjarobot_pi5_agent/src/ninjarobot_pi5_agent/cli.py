"""Unified Phase 1 CLI for contract and configuration validation."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from ninjarobot_pi5_ide.testing import FakeIDEClient
from pydantic import ValidationError

from ninjarobot_pi5_ide import (
    ActionRequest,
    ActionResult,
    CapabilityDescriptor,
    RiskLevel,
    load_robot_config,
)

from . import __version__
from .models import ModelRequest, ModelTurn


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser without touching hardware or configuration."""
    parser = argparse.ArgumentParser(
        prog="ninjarobot_pi5_cli",
        description="NinjaRobotPi5V4 Phase 1 contract and configuration tools.",
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
        help="Inspect machine-readable Phase 1 schemas.",
    )
    contracts_subcommands = contracts_parser.add_subparsers(
        dest="contracts_command",
        required=True,
    )
    contracts_subcommands.add_parser(
        "schema",
        help="Print the core IDE and agent JSON schemas.",
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
    return parser


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
        description="Simulated Phase 1 echo capability.",
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
        deadline=datetime.now(tz=UTC),
        idempotency_key="dry-run-0001",
    )
    try:
        return await client.execute(request)
    finally:
        await client.close()


def _parse_json_object(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("--json must contain a JSON object")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    """Run the unified Phase 1 CLI and return a process exit code."""
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
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    parser.error("unsupported command")
    return 2
