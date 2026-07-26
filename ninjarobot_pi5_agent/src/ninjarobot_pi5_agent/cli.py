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
    BuzzerDevice,
    BuzzerStopAdapter,
    BuzzerToneAdapter,
    CapabilityDescriptor,
    CapabilityRegistry,
    DisplayBrightnessAdapter,
    DisplayClearAdapter,
    DisplayDevice,
    DisplayShowTextAdapter,
    ExecutionEngine,
    HealthReport,
    ResourceHealth,
    ResourceScheduler,
    RiskLevel,
    ServoDevice,
    ServoMoveAdapter,
    ServoRuntime,
    ServoStatusAdapter,
    ServoStopAdapter,
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

    buzzer_parser = subcommands.add_parser(
        "buzzer",
        help="Exercise bounded GPIO27 buzzer capabilities.",
    )
    buzzer_subcommands = buzzer_parser.add_subparsers(
        dest="buzzer_command",
        required=True,
    )
    buzzer_health_parser = buzzer_subcommands.add_parser(
        "health",
        help="Check simulated or real GPIO27 readiness without making sound.",
    )
    _add_backend_options(buzzer_health_parser)
    buzzer_play_parser = buzzer_subcommands.add_parser(
        "play",
        help="Play a simulated tone unless --real is supplied explicitly.",
    )
    _add_backend_options(buzzer_play_parser)
    _add_action_identity_options(buzzer_play_parser)
    buzzer_play_parser.add_argument(
        "--frequency",
        type=int,
        required=True,
        help="Tone frequency in hertz, from 20 through 20000.",
    )
    buzzer_play_parser.add_argument(
        "--duration",
        type=float,
        default=0.2,
        help="Tone duration in seconds, from 0.05 through 2.0.",
    )
    buzzer_play_parser.add_argument(
        "--volume",
        type=int,
        default=32,
        help="Bounded volume from 1 through 128; 32 is the quiet default.",
    )
    buzzer_stop_parser = buzzer_subcommands.add_parser(
        "stop",
        help="Request emergency buzzer silence; simulated unless --real is supplied.",
    )
    _add_backend_options(buzzer_stop_parser)
    _add_action_identity_options(buzzer_stop_parser)

    display_parser = subcommands.add_parser(
        "display",
        help="Exercise serialized ST7789V display capabilities.",
    )
    display_subcommands = display_parser.add_subparsers(
        dest="display_command",
        required=True,
    )
    display_health_parser = display_subcommands.add_parser(
        "health",
        help="Check simulated or real SPI display readiness without writing a test frame.",
    )
    _add_backend_options(display_health_parser)
    display_text_parser = display_subcommands.add_parser(
        "text",
        help="Render simulated text unless --real is supplied explicitly.",
    )
    _add_backend_options(display_text_parser)
    _add_action_identity_options(display_text_parser)
    display_text_parser.add_argument("--text", required=True, help="Text to display.")
    display_text_parser.add_argument(
        "--font-size",
        type=int,
        default=32,
        help="Default-font size in pixels, from 8 through 96.",
    )
    display_text_parser.add_argument(
        "--foreground",
        default="#FFFFFF",
        help="Text color in #RRGGBB notation.",
    )
    display_text_parser.add_argument(
        "--background",
        default="#000000",
        help="Background color in #RRGGBB notation.",
    )
    _add_display_hold_option(display_text_parser)
    display_clear_parser = display_subcommands.add_parser(
        "clear",
        help="Clear the simulated display unless --real is supplied explicitly.",
    )
    _add_backend_options(display_clear_parser)
    _add_action_identity_options(display_clear_parser)
    display_clear_parser.add_argument(
        "--color",
        default="#000000",
        help="Solid clear color in #RRGGBB notation.",
    )
    _add_display_hold_option(display_clear_parser)
    display_brightness_parser = display_subcommands.add_parser(
        "brightness",
        help="Set simulated brightness unless --real is supplied explicitly.",
    )
    _add_backend_options(display_brightness_parser)
    _add_action_identity_options(display_brightness_parser)
    display_brightness_parser.add_argument(
        "--percent",
        type=int,
        required=True,
        help="Backlight brightness from 0 through 100 percent.",
    )
    _add_display_hold_option(display_brightness_parser)

    servo_parser = subcommands.add_parser(
        "servo",
        help="Exercise safety-gated six-servo capabilities.",
    )
    servo_subcommands = servo_parser.add_subparsers(
        dest="servo_command",
        required=True,
    )
    servo_health_parser = servo_subcommands.add_parser(
        "health",
        help="Check simulated or real mixed-backend readiness without sending a pulse.",
    )
    _add_backend_options(servo_health_parser)
    servo_status_parser = servo_subcommands.add_parser(
        "status",
        help="Report topology, calibration readiness, and motion gates.",
    )
    _add_backend_options(servo_status_parser)
    _add_action_identity_options(servo_status_parser)
    servo_move_parser = servo_subcommands.add_parser(
        "move",
        help="Move one simulated endpoint, or one explicitly enabled real endpoint.",
    )
    _add_backend_options(servo_move_parser)
    _add_action_identity_options(servo_move_parser)
    servo_move_parser.add_argument(
        "--endpoint",
        required=True,
        choices=(
            "gpio12",
            "gpio13",
            "hat_pwm1",
            "hat_pwm2",
            "hat_pwm3",
            "hat_pwm4",
        ),
        help="One explicit V4 servo endpoint.",
    )
    servo_move_parser.add_argument(
        "--angle",
        type=float,
        required=True,
        help="Calibrated target from -90 through 90 degrees.",
    )
    servo_move_parser.add_argument(
        "--speed",
        choices=("S", "M", "F"),
        default="S",
        help="S, M, or F for slow, medium, or fast; slow is the safe default.",
    )
    servo_move_parser.add_argument(
        "--confirm-motion",
        action="store_true",
        help="Required with --real to confirm the workspace and power cutoff are ready.",
    )
    _add_servo_hold_option(servo_move_parser)
    servo_stop_parser = servo_subcommands.add_parser(
        "stop",
        help="Request emergency zero pulse on all servo endpoints.",
    )
    _add_backend_options(servo_stop_parser)
    _add_action_identity_options(servo_stop_parser)
    return parser


def _add_backend_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--real",
        action="store_true",
        help="Explicitly open the configured Raspberry Pi hardware.",
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


def _add_action_identity_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--action-id", help="Optional explicit action identifier.")
    parser.add_argument("--idempotency-key", help="Optional duplicate-protection key.")


def _add_display_hold_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--hold",
        type=float,
        default=0.0,
        help="Keep the CLI display session open for 0 through 30 seconds before cleanup.",
    )


def _add_servo_hold_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--hold",
        type=float,
        default=0.0,
        help="Keep the servo session active for 0 through 5 seconds before zero-pulse cleanup.",
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


class _SimulatedBuzzerDriver:
    """Hardware-free buzzer driver used by default CLI commands."""

    def __init__(self) -> None:
        self._initialized = False
        self._volume = 32

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value: int) -> None:
        self._volume = value

    def initialize(self) -> None:
        self._initialized = True

    def play_sound(self, frequency: int, duration: float) -> None:
        del frequency, duration

    def off(self) -> None:
        self._initialized = False


class _SimulatedDisplayDriver:
    """Hardware-free display double used by default CLI commands."""

    def __init__(self, **settings: Any) -> None:
        native_width = int(settings["width"])
        native_height = int(settings["height"])
        rotation = int(settings["rotation"])
        if rotation in (90, 270):
            self.width = native_height
            self.height = native_width
        else:
            self.width = native_width
            self.height = native_height
        self.brightness = 0
        self.closed = False

    def display(self, image: Any) -> None:
        if image.size != (self.width, self.height):
            raise ValueError("simulated frame dimensions do not match the display")

    def clear(self, color: tuple[int, int, int]) -> None:
        del color

    def set_brightness(self, percent: int) -> None:
        self.brightness = percent

    def health_check(self) -> bool:
        return not self.closed

    def close(self) -> None:
        self.closed = True


class _SimulatedServoCalibration:
    """Explicit safe calibration used only by the hardware-free CLI backend."""

    pulse_min = 1000
    pulse_max = 2000
    pulse_center = 1500
    angle_min = -90.0
    angle_max = 90.0
    angle_center = 0.0
    speed = 80


class _SimulatedServo:
    def __init__(self) -> None:
        self.calibration = _SimulatedServoCalibration()

    def move_to_center(self) -> None:
        return None


class _SimulatedServoGroup:
    """Hardware-free six-servo group used by default CLI commands."""

    def __init__(self, endpoints: tuple[str, ...]) -> None:
        self._servos = {endpoint: _SimulatedServo() for endpoint in endpoints}
        self._aborted = False

    def get_servo(self, pin: int | str) -> _SimulatedServo | None:
        return self._servos.get(str(pin))

    async def move_all_async(
        self,
        targets: list[float | None],
        speed_mode: str = "M",
    ) -> bool:
        del targets, speed_mode
        self._aborted = False
        await asyncio.sleep(0)
        return not self._aborted

    def abort(self) -> None:
        self._aborted = True

    def off(self) -> None:
        return None

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
    buzzer = BuzzerDevice()
    display = DisplayDevice()
    servo = ServoDevice()
    engine = ExecutionEngine(
        CapabilityRegistry(
            [
                BuzzerToneAdapter(buzzer),
                BuzzerStopAdapter(buzzer),
                DisplayBrightnessAdapter(display),
                DisplayClearAdapter(display),
                DisplayShowTextAdapter(display),
                ServoMoveAdapter(servo),
                ServoStatusAdapter(servo),
                ServoStopAdapter(servo),
                VL53L0XDistanceAdapter(),
            ]
        ),
        ActionLedger(":memory:"),
    )
    try:
        return await engine.capabilities()
    finally:
        await engine.close()


def _build_buzzer_engine(
    *,
    real: bool,
    config_path: str,
    ledger_path: str,
) -> ExecutionEngine:
    if real:
        config = load_robot_config(config_path)
        device = BuzzerDevice(pin=config.hardware.buzzer.gpio)
    else:
        simulated_driver = _SimulatedBuzzerDriver()
        device = BuzzerDevice(
            pin=27,
            driver_factory=lambda _pin, _volume: simulated_driver,
            simulated=True,
        )
    return ExecutionEngine(
        CapabilityRegistry(
            [
                BuzzerToneAdapter(device),
                BuzzerStopAdapter(device),
            ]
        ),
        ActionLedger(Path(ledger_path)),
        scheduler=ResourceScheduler(max_concurrency=2, max_queue_size=4),
    )


def _build_display_engine(
    *,
    real: bool,
    config_path: str,
    ledger_path: str,
) -> ExecutionEngine:
    if real:
        config = load_robot_config(config_path)
        display_config = config.hardware.display
        device = DisplayDevice(
            spi_bus=display_config.spi_bus,
            spi_device=display_config.spi_device,
            dc_gpio=display_config.dc_gpio,
            reset_gpio=display_config.reset_gpio,
            backlight_gpio=display_config.backlight_gpio,
            frequency_hz=display_config.frequency_hz,
            width=display_config.width,
            height=display_config.height,
            rotation=display_config.rotation,
            initial_brightness=display_config.brightness,
        )
    else:
        device = DisplayDevice(
            driver_factory=lambda **settings: _SimulatedDisplayDriver(**settings),
            simulated=True,
        )
    return ExecutionEngine(
        CapabilityRegistry(
            [
                DisplayBrightnessAdapter(device),
                DisplayClearAdapter(device),
                DisplayShowTextAdapter(device),
            ]
        ),
        ActionLedger(Path(ledger_path)),
        scheduler=ResourceScheduler(max_concurrency=3, max_queue_size=6),
    )


def _build_servo_engine(
    *,
    real: bool,
    config_path: str,
    ledger_path: str,
) -> ExecutionEngine:
    if real:
        config = load_robot_config(config_path)
        servo_config = config.hardware.servos
        device = ServoDevice(
            endpoints=servo_config.endpoints,
            calibration_file=servo_config.calibration_file,
            i2c_bus=config.hardware.i2c.bus,
            dfr0566_address=config.hardware.i2c.dfr0566_address,
            motion_enabled=servo_config.motion_enabled,
        )
    else:
        endpoints = (
            "gpio12",
            "gpio13",
            "hat_pwm1",
            "hat_pwm2",
            "hat_pwm3",
            "hat_pwm4",
        )
        simulated_group = _SimulatedServoGroup(endpoints)
        device = ServoDevice(
            endpoints=endpoints,
            calibration_file="simulated-servo.json",
            motion_enabled=True,
            runtime_factory=lambda current_endpoints, _path, _bus, _address: ServoRuntime(
                group=simulated_group,
                calibrated_endpoints=frozenset(current_endpoints),
            ),
            simulated=True,
        )
    return ExecutionEngine(
        CapabilityRegistry(
            [
                ServoMoveAdapter(device),
                ServoStatusAdapter(device),
                ServoStopAdapter(device),
            ]
        ),
        ActionLedger(Path(ledger_path)),
        scheduler=ResourceScheduler(max_concurrency=2, max_queue_size=4),
    )


async def _run_buzzer_health(
    *,
    real: bool,
    config_path: str,
    ledger_path: str,
) -> HealthReport:
    engine = _build_buzzer_engine(
        real=real,
        config_path=config_path,
        ledger_path=ledger_path,
    )
    try:
        return await engine.health()
    finally:
        await engine.close()


async def _run_buzzer_action(
    *,
    capability: str,
    arguments: dict[str, Any],
    real: bool,
    config_path: str,
    ledger_path: str,
    action_id: str | None,
    idempotency_key: str | None,
) -> ActionResult:
    generated = uuid.uuid4().hex
    current_action_id = action_id or f"buzzer-{generated}"
    current_key = idempotency_key or f"buzzer-key-{generated}"
    engine = _build_buzzer_engine(
        real=real,
        config_path=config_path,
        ledger_path=ledger_path,
    )
    try:
        return await engine.execute(
            ActionRequest(
                action_id=current_action_id,
                capability=capability,
                arguments=arguments,
                requested_by="manual-cli",
                session_id="manual-buzzer-test",
                idempotency_key=current_key,
            )
        )
    finally:
        await engine.close()


async def _run_display_health(
    *,
    real: bool,
    config_path: str,
    ledger_path: str,
) -> HealthReport:
    engine = _build_display_engine(
        real=real,
        config_path=config_path,
        ledger_path=ledger_path,
    )
    try:
        return await engine.health()
    finally:
        await engine.close()


async def _run_display_action(
    *,
    capability: str,
    arguments: dict[str, Any],
    real: bool,
    config_path: str,
    ledger_path: str,
    action_id: str | None,
    idempotency_key: str | None,
    hold_seconds: float,
) -> ActionResult:
    if not 0 <= hold_seconds <= 30:
        raise ValueError("--hold must be between 0 and 30 seconds")
    generated = uuid.uuid4().hex
    current_action_id = action_id or f"display-{generated}"
    current_key = idempotency_key or f"display-key-{generated}"
    engine = _build_display_engine(
        real=real,
        config_path=config_path,
        ledger_path=ledger_path,
    )
    try:
        result = await engine.execute(
            ActionRequest(
                action_id=current_action_id,
                capability=capability,
                arguments=arguments,
                requested_by="manual-cli",
                session_id="manual-display-test",
                idempotency_key=current_key,
            )
        )
        if result.status is ActionStatus.SUCCEEDED and hold_seconds:
            await asyncio.sleep(hold_seconds)
        return result
    finally:
        await engine.close()


async def _run_servo_health(
    *,
    real: bool,
    config_path: str,
    ledger_path: str,
) -> HealthReport:
    engine = _build_servo_engine(
        real=real,
        config_path=config_path,
        ledger_path=ledger_path,
    )
    try:
        return await engine.health()
    finally:
        await engine.close()


async def _run_servo_action(
    *,
    capability: str,
    arguments: dict[str, Any],
    real: bool,
    config_path: str,
    ledger_path: str,
    action_id: str | None,
    idempotency_key: str | None,
    hold_seconds: float = 0.0,
    motion_confirmed: bool = False,
) -> ActionResult:
    if not 0 <= hold_seconds <= 5:
        raise ValueError("--hold must be between 0 and 5 seconds")
    if real and capability == "servo.move" and not motion_confirmed:
        raise ValueError("real servo movement requires --confirm-motion")
    generated = uuid.uuid4().hex
    current_action_id = action_id or f"servo-{generated}"
    current_key = idempotency_key or f"servo-key-{generated}"
    engine = _build_servo_engine(
        real=real,
        config_path=config_path,
        ledger_path=ledger_path,
    )
    try:
        result = await engine.execute(
            ActionRequest(
                action_id=current_action_id,
                capability=capability,
                arguments=arguments,
                requested_by="manual-cli",
                session_id="manual-servo-test",
                idempotency_key=current_key,
            )
        )
        if result.status is ActionStatus.SUCCEEDED and hold_seconds:
            await asyncio.sleep(hold_seconds)
        return result
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
        if args.command == "buzzer" and args.buzzer_command == "health":
            health = asyncio.run(
                _run_buzzer_health(
                    real=args.real,
                    config_path=args.config,
                    ledger_path=args.ledger,
                )
            )
            print(health.model_dump_json(indent=2))
            return 0 if health.status is ResourceHealth.READY else 1
        if args.command == "buzzer" and args.buzzer_command in {"play", "stop"}:
            capability = "buzzer.play_tone" if args.buzzer_command == "play" else "buzzer.stop"
            arguments = (
                {
                    "frequency_hz": args.frequency,
                    "duration_seconds": args.duration,
                    "volume": args.volume,
                }
                if args.buzzer_command == "play"
                else {}
            )
            result = asyncio.run(
                _run_buzzer_action(
                    capability=capability,
                    arguments=arguments,
                    real=args.real,
                    config_path=args.config,
                    ledger_path=args.ledger,
                    action_id=args.action_id,
                    idempotency_key=args.idempotency_key,
                )
            )
            print(result.model_dump_json(indent=2))
            return 0 if result.status is ActionStatus.SUCCEEDED else 1
        if args.command == "display" and args.display_command == "health":
            health = asyncio.run(
                _run_display_health(
                    real=args.real,
                    config_path=args.config,
                    ledger_path=args.ledger,
                )
            )
            print(health.model_dump_json(indent=2))
            return 0 if health.status is ResourceHealth.READY else 1
        if args.command == "display" and args.display_command in {
            "text",
            "clear",
            "brightness",
        }:
            if args.display_command == "text":
                capability = "display.show_text"
                arguments = {
                    "text": args.text,
                    "font_size": args.font_size,
                    "foreground": args.foreground,
                    "background": args.background,
                }
            elif args.display_command == "clear":
                capability = "display.clear"
                arguments = {"color": args.color}
            else:
                capability = "display.set_brightness"
                arguments = {"percent": args.percent}
            result = asyncio.run(
                _run_display_action(
                    capability=capability,
                    arguments=arguments,
                    real=args.real,
                    config_path=args.config,
                    ledger_path=args.ledger,
                    action_id=args.action_id,
                    idempotency_key=args.idempotency_key,
                    hold_seconds=args.hold,
                )
            )
            print(result.model_dump_json(indent=2))
            return 0 if result.status is ActionStatus.SUCCEEDED else 1
        if args.command == "servo" and args.servo_command == "health":
            health = asyncio.run(
                _run_servo_health(
                    real=args.real,
                    config_path=args.config,
                    ledger_path=args.ledger,
                )
            )
            print(health.model_dump_json(indent=2))
            return 0 if health.status is ResourceHealth.READY else 1
        if args.command == "servo" and args.servo_command in {
            "status",
            "move",
            "stop",
        }:
            if args.servo_command == "move":
                capability = "servo.move"
                arguments = {
                    "endpoint": args.endpoint,
                    "target_angle": args.angle,
                    "speed_mode": args.speed,
                }
                hold_seconds = args.hold
                motion_confirmed = args.confirm_motion
            elif args.servo_command == "status":
                capability = "servo.status"
                arguments = {}
                hold_seconds = 0.0
                motion_confirmed = False
            else:
                capability = "servo.stop"
                arguments = {}
                hold_seconds = 0.0
                motion_confirmed = False
            result = asyncio.run(
                _run_servo_action(
                    capability=capability,
                    arguments=arguments,
                    real=args.real,
                    config_path=args.config,
                    ledger_path=args.ledger,
                    action_id=args.action_id,
                    idempotency_key=args.idempotency_key,
                    hold_seconds=hold_seconds,
                    motion_confirmed=motion_confirmed,
                )
            )
            print(result.model_dump_json(indent=2))
            return 0 if result.status is ActionStatus.SUCCEEDED else 1
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
