"""Safety-gated mixed-backend servo capabilities for configured endpoints."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from .config import SUPPORTED_SERVO_ENDPOINTS
from .errors import IDEError
from .models import (
    CapabilityDescriptor,
    ErrorDetails,
    ResourceHealth,
    RetrySafety,
    RiskLevel,
)

SERVO_RESOURCES = ("servo_bus", "pwm0", "pwm1", "i2c1", "dfr0566")
MIN_TARGET_ANGLE = -90.0
MAX_TARGET_ANGLE = 90.0
MOVE_STOP_TIMEOUT_SECONDS = 1.0


class ServoCalibrationDriver(Protocol):
    """Calibration fields consumed by the V4 safety gate."""

    pulse_min: int
    pulse_max: int
    pulse_center: int
    angle_min: float
    angle_max: float
    angle_center: float
    speed: int


class ServoDriver(Protocol):
    """Narrow single-servo surface consumed from the managed library."""

    @property
    def calibration(self) -> ServoCalibrationDriver:
        """Return the endpoint calibration."""
        ...

    def move_to_center(self) -> None:
        """Write the calibrated center pulse."""


class ServoGroupDriver(Protocol):
    """Narrow mixed-backend group surface consumed from the managed library."""

    def get_servo(self, pin: int | str) -> ServoDriver | None:
        """Return one configured endpoint."""
        ...

    async def move_all_async(
        self,
        targets: list[float | None],
        speed_mode: str = "M",
    ) -> bool:
        """Move selected endpoints and return false when aborted."""
        ...

    def abort(self) -> None:
        """Signal a running movement to stop."""

    def off(self) -> None:
        """Set every servo pulse output to zero."""

    def close(self) -> None:
        """Release all PWM and I2C resources."""


@dataclass(frozen=True)
class ServoRuntime:
    """Loaded mixed backend and its explicitly valid calibrations."""

    group: ServoGroupDriver
    calibrated_endpoints: frozenset[str]


ServoFactory = Callable[[tuple[str, ...], str, int, int], ServoRuntime]


def _load_servo_runtime(
    endpoints: tuple[str, ...],
    calibration_file: str,
    i2c_bus: int,
    dfr0566_address: int,
) -> ServoRuntime:
    """Import and build the managed mixed backend only for explicit real use."""
    module = importlib.import_module("pi5servo")
    config_type = getattr(module, "ConfigManager", None)
    group_type = getattr(module, "ServoGroup", None)
    if config_type is None or group_type is None:
        raise ImportError("pi5servo ConfigManager and ServoGroup are required")

    calibration_path = Path(calibration_file).expanduser()
    manager = config_type(calibration_path)
    manager.load()
    calibrations = manager.get_all_endpoint_calibrations()
    calibrated = frozenset(
        endpoint
        for endpoint, calibration in calibrations.items()
        if endpoint in endpoints and _is_calibrated(calibration)
    )
    group = group_type(
        None,
        pins=list(endpoints),
        calibrations=calibrations,
        backend="auto",
        backend_kwargs={
            "bus_id": i2c_bus,
            "address": dfr0566_address,
        },
    )
    return ServoRuntime(
        group=cast(ServoGroupDriver, group),
        calibrated_endpoints=calibrated,
    )


class ServoDevice:
    """Own one mixed servo group with calibration and emergency-stop gates."""

    def __init__(
        self,
        *,
        endpoints: tuple[str, ...] = SUPPORTED_SERVO_ENDPOINTS,
        calibration_file: str = "~/.config/pi5servo/servo.json",
        i2c_bus: int = 1,
        dfr0566_address: int = 0x10,
        motion_enabled: bool = False,
        group_motion_enabled: bool = False,
        runtime_factory: ServoFactory | None = None,
        simulated: bool = False,
    ) -> None:
        if not endpoints:
            raise ValueError("servo device requires at least one endpoint")
        if len(endpoints) != len(set(endpoints)):
            raise ValueError("servo endpoints must not contain duplicates")
        unsupported = sorted(set(endpoints) - set(SUPPORTED_SERVO_ENDPOINTS))
        if unsupported:
            raise ValueError(f"unsupported servo endpoints: {', '.join(unsupported)}")
        if not calibration_file:
            raise ValueError("calibration_file must not be empty")
        if i2c_bus != 1:
            raise ValueError("DFR0566 servo integration requires I2C bus 1")
        if not 0x08 <= dfr0566_address <= 0x77:
            raise ValueError("DFR0566 address must be a valid I2C device address")

        self._endpoints = endpoints
        self._calibration_file = calibration_file
        self._i2c_bus = i2c_bus
        self._dfr0566_address = dfr0566_address
        self._motion_enabled = motion_enabled
        self._group_motion_enabled = group_motion_enabled
        self._runtime_factory = runtime_factory or _load_servo_runtime
        self._simulated = simulated
        self._runtime: ServoRuntime | None = None
        self._startup_error: str | None = None
        self._start_attempted = False
        self._movement_task: asyncio.Task[bool] | None = None
        self._state_lock = asyncio.Lock()
        self._closed = False

    @property
    def simulated(self) -> bool:
        """Return whether this device is explicitly hardware-free."""
        return self._simulated

    async def start(self) -> None:
        """Claim both backends once at zero pulse while retaining diagnostics."""
        async with self._state_lock:
            if self._closed:
                raise RuntimeError("servo device is closed")
            if self._start_attempted:
                return
            self._start_attempted = True
            await self._initialize_locked()

    async def status(self) -> dict[str, Any]:
        """Return topology, calibration readiness, and safety-gate state."""
        async with self._state_lock:
            runtime = self._runtime
            calibrated = runtime.calibrated_endpoints if runtime is not None else frozenset()
            return {
                "endpoints": list(self._endpoints),
                "calibrated": {endpoint: endpoint in calibrated for endpoint in self._endpoints},
                "motion_enabled": self._motion_enabled,
                "group_motion_enabled": self._group_motion_enabled,
                "driver_available": runtime is not None,
                "simulated": self._simulated,
            }

    async def move(
        self,
        *,
        endpoint: str,
        target_angle: float,
        speed_mode: str,
    ) -> dict[str, Any]:
        """Center and move one explicitly calibrated endpoint."""
        async with self._state_lock:
            runtime = self._require_runtime_locked("servo.move")
            if not self._motion_enabled:
                raise _servo_error(
                    code="SERVO_MOTION_DISABLED",
                    message="Real servo motion is disabled by V4 configuration.",
                    technical_detail=(
                        "Complete the electrical record and calibration checklist, "
                        "then use a private config with motion_enabled = true."
                    ),
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move",
                )
            if endpoint not in runtime.calibrated_endpoints:
                raise _servo_error(
                    code="SERVO_NOT_CALIBRATED",
                    message=f"Servo endpoint {endpoint} has no valid explicit calibration.",
                    technical_detail=(
                        f"Calibrate {endpoint} in {Path(self._calibration_file).expanduser()} "
                        "before enabling movement."
                    ),
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move",
                )
            if self._movement_task is not None and not self._movement_task.done():
                raise _servo_error(
                    code="SERVO_BUSY",
                    message="Another servo movement is already running.",
                    technical_detail=None,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move",
                )
            servo = runtime.group.get_servo(endpoint)
            if servo is None:
                raise _servo_error(
                    code="SERVO_ENDPOINT_UNAVAILABLE",
                    message=f"Servo endpoint {endpoint} is not available in the mixed backend.",
                    technical_detail=None,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move",
                )
            calibration = servo.calibration
            if not calibration.angle_min <= target_angle <= calibration.angle_max:
                raise _servo_error(
                    code="SERVO_TARGET_OUTSIDE_CALIBRATION",
                    message=f"Servo target is outside the calibration for {endpoint}.",
                    technical_detail=(
                        f"Allowed range is {calibration.angle_min} through "
                        f"{calibration.angle_max} degrees."
                    ),
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move",
                )

            try:
                await asyncio.to_thread(servo.move_to_center)
            except Exception as exc:
                raise _servo_error(
                    code="SERVO_CENTER_FAILED",
                    message=f"Servo endpoint {endpoint} could not reach its calibrated center.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.UNKNOWN,
                    capability="servo.move",
                ) from exc

            targets: list[float | None] = [
                target_angle if item == endpoint else None for item in self._endpoints
            ]
            movement_task = asyncio.create_task(
                runtime.group.move_all_async(targets, speed_mode=speed_mode)
            )
            self._movement_task = movement_task

        interrupted = False
        try:
            completed = await movement_task
            interrupted = not completed
        except asyncio.CancelledError:
            await self.stop()
            raise
        except Exception as exc:
            raise _servo_error(
                code="SERVO_MOVE_FAILED",
                message=f"Servo endpoint {endpoint} could not complete its movement.",
                technical_detail=f"{type(exc).__name__}: {exc}",
                definitely_not_executed=False,
                retry_safety=RetrySafety.UNKNOWN,
                capability="servo.move",
            ) from exc
        finally:
            async with self._state_lock:
                if self._movement_task is movement_task:
                    self._movement_task = None

        return {
            "endpoint": endpoint,
            "target_angle": target_angle,
            "speed_mode": speed_mode,
            "interrupted": interrupted,
            "simulated": self._simulated,
        }

    async def move_group(
        self,
        *,
        targets: dict[str, float],
        speed_mode: str,
    ) -> dict[str, Any]:
        """Center and command multiple calibrated endpoints as one drive action."""
        async with self._state_lock:
            runtime = self._require_runtime_locked("servo.move_group")
            if not self._motion_enabled:
                raise _servo_error(
                    code="SERVO_MOTION_DISABLED",
                    message="Real servo motion is disabled by V4 configuration.",
                    technical_detail="Set motion_enabled = true only after calibration.",
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move_group",
                )
            if not self._group_motion_enabled:
                raise _servo_error(
                    code="SERVO_GROUP_MOTION_DISABLED",
                    message="Coordinated servo motion is disabled by V4 configuration.",
                    technical_detail=(
                        "Set group_motion_enabled = true after both motors are calibrated."
                    ),
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move_group",
                )
            if not targets:
                raise _servo_error(
                    code="INVALID_CAPABILITY_ARGUMENTS",
                    message="A group movement requires at least one servo target.",
                    technical_detail=None,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move_group",
                )
            unsupported = sorted(set(targets) - set(self._endpoints))
            if unsupported:
                raise _servo_error(
                    code="INVALID_CAPABILITY_ARGUMENTS",
                    message="A group target references an unconfigured servo endpoint.",
                    technical_detail=", ".join(unsupported),
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move_group",
                )
            uncalibrated = sorted(set(targets) - set(runtime.calibrated_endpoints))
            if uncalibrated:
                raise _servo_error(
                    code="SERVO_NOT_CALIBRATED",
                    message="Every group endpoint requires an explicit calibration.",
                    technical_detail=", ".join(uncalibrated),
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move_group",
                )
            if self._movement_task is not None and not self._movement_task.done():
                raise _servo_error(
                    code="SERVO_BUSY",
                    message="Another servo movement is already running.",
                    technical_detail=None,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.move_group",
                )
            servos: list[tuple[str, ServoDriver]] = []
            for endpoint, target in targets.items():
                servo = runtime.group.get_servo(endpoint)
                if servo is None:
                    raise _servo_error(
                        code="SERVO_ENDPOINT_UNAVAILABLE",
                        message=f"Servo endpoint {endpoint} is unavailable.",
                        technical_detail=None,
                        definitely_not_executed=True,
                        retry_safety=RetrySafety.SAFE,
                        capability="servo.move_group",
                    )
                if not servo.calibration.angle_min <= target <= servo.calibration.angle_max:
                    raise _servo_error(
                        code="SERVO_TARGET_OUTSIDE_CALIBRATION",
                        message=f"Servo target is outside the calibration for {endpoint}.",
                        technical_detail=(
                            f"Allowed range is {servo.calibration.angle_min} through "
                            f"{servo.calibration.angle_max} degrees."
                        ),
                        definitely_not_executed=True,
                        retry_safety=RetrySafety.SAFE,
                        capability="servo.move_group",
                    )
                servos.append((endpoint, servo))
            try:
                await asyncio.gather(
                    *(asyncio.to_thread(servo.move_to_center) for _endpoint, servo in servos)
                )
            except Exception as exc:
                await asyncio.to_thread(runtime.group.off)
                raise _servo_error(
                    code="SERVO_CENTER_FAILED",
                    message="The drive servos could not reach their calibrated stop values.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.UNKNOWN,
                    capability="servo.move_group",
                ) from exc
            ordered_targets = [targets.get(endpoint) for endpoint in self._endpoints]
            movement_task = asyncio.create_task(
                runtime.group.move_all_async(ordered_targets, speed_mode=speed_mode)
            )
            self._movement_task = movement_task

        try:
            completed = await movement_task
        except asyncio.CancelledError:
            await self.stop()
            raise
        except Exception as exc:
            await self.stop()
            raise _servo_error(
                code="SERVO_MOVE_FAILED",
                message="The coordinated servo movement failed.",
                technical_detail=f"{type(exc).__name__}: {exc}",
                definitely_not_executed=False,
                retry_safety=RetrySafety.UNKNOWN,
                capability="servo.move_group",
            ) from exc
        finally:
            async with self._state_lock:
                if self._movement_task is movement_task:
                    self._movement_task = None
        if not completed:
            await self.stop()
        return {
            "targets": targets,
            "speed_mode": speed_mode,
            "interrupted": not completed,
            "simulated": self._simulated,
        }

    def emergency_stop_sync(self) -> bool:
        """Best-effort direct zero pulse for a watchdog thread."""
        runtime = self._runtime
        if runtime is None:
            return False
        runtime.group.abort()
        runtime.group.off()
        return True

    async def stop(self) -> dict[str, Any]:
        """Abort movement and set every configured servo output to zero."""
        async with self._state_lock:
            runtime = self._runtime
            movement_task = self._movement_task
            if runtime is not None:
                runtime.group.abort()

        if (
            movement_task is not None
            and movement_task is not asyncio.current_task()
            and not movement_task.done()
        ):
            try:
                await asyncio.wait_for(
                    asyncio.shield(movement_task),
                    timeout=MOVE_STOP_TIMEOUT_SECONDS,
                )
            except Exception:
                pass

        if runtime is not None:
            try:
                await asyncio.to_thread(runtime.group.off)
            except Exception as exc:
                raise _servo_error(
                    code="SERVO_STOP_FAILED",
                    message="The servo backends could not confirm zero pulse on every endpoint.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.SAFE,
                    capability="servo.stop",
                ) from exc
        return {
            "stopped": True,
            "driver_available": runtime is not None,
            "simulated": self._simulated,
        }

    async def health(self) -> ResourceHealth:
        """Report whether both mixed backends were constructed successfully."""
        async with self._state_lock:
            return ResourceHealth.READY if self._runtime is not None else ResourceHealth.UNAVAILABLE

    async def close(self) -> None:
        """Stop all outputs and release PWM/I2C resources idempotently."""
        async with self._state_lock:
            if self._closed:
                return
        try:
            await self.stop()
        finally:
            async with self._state_lock:
                runtime = self._runtime
                self._runtime = None
                self._closed = True
            if runtime is not None:
                await asyncio.to_thread(runtime.group.close)

    async def _initialize_locked(self) -> None:
        try:
            self._runtime = await asyncio.to_thread(
                self._runtime_factory,
                self._endpoints,
                self._calibration_file,
                self._i2c_bus,
                self._dfr0566_address,
            )
            self._startup_error = None
        except Exception as exc:
            self._runtime = None
            self._startup_error = f"{type(exc).__name__}: {exc}"

    def _require_runtime_locked(self, capability: str) -> ServoRuntime:
        if self._runtime is None:
            raise _servo_error(
                code="SERVO_UNAVAILABLE",
                message="The configured mixed servo backend is unavailable.",
                technical_detail=self._startup_error,
                definitely_not_executed=True,
                retry_safety=RetrySafety.SAFE,
                capability=capability,
            )
        return self._runtime


class ServoStatusAdapter:
    """Expose topology and calibration readiness without sending a pulse."""

    descriptor = CapabilityDescriptor(
        name="servo.status",
        version="1.0.0",
        description="Report six-servo topology, calibration readiness, and motion gates.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "endpoints": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "calibrated": {
                    "type": "object",
                    "additionalProperties": {"type": "boolean"},
                },
                "motion_enabled": {"type": "boolean"},
                "group_motion_enabled": {"type": "boolean"},
                "driver_available": {"type": "boolean"},
                "simulated": {"type": "boolean"},
            },
            "required": [
                "endpoints",
                "calibrated",
                "motion_enabled",
                "group_motion_enabled",
                "driver_available",
                "simulated",
            ],
            "additionalProperties": False,
        },
        risk=RiskLevel.READ_ONLY,
        resources=SERVO_RESOURCES,
        default_timeout_seconds=5.0,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, device: ServoDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise _invalid_arguments(
                f"servo.status does not accept arguments: {sorted(arguments)}",
                capability="servo.status",
            )
        return await self._device.status()

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


class ServoMoveAdapter:
    """Expose one calibrated endpoint movement at a time."""

    descriptor = CapabilityDescriptor(
        name="servo.move",
        version="1.0.0",
        description="Move one explicitly calibrated servo endpoint within its limits.",
        input_schema={
            "type": "object",
            "properties": {
                "endpoint": {
                    "type": "string",
                    "enum": list(SUPPORTED_SERVO_ENDPOINTS),
                },
                "target_angle": {
                    "type": "number",
                    "minimum": MIN_TARGET_ANGLE,
                    "maximum": MAX_TARGET_ANGLE,
                },
                "speed_mode": {
                    "type": "string",
                    "enum": ["S", "M", "F"],
                    "default": "S",
                },
            },
            "required": ["endpoint", "target_angle"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "endpoint": {"type": "string"},
                "target_angle": {"type": "number"},
                "speed_mode": {"type": "string"},
                "interrupted": {"type": "boolean"},
                "simulated": {"type": "boolean"},
            },
            "required": [
                "endpoint",
                "target_angle",
                "speed_mode",
                "interrupted",
                "simulated",
            ],
            "additionalProperties": False,
        },
        risk=RiskLevel.MOTION,
        resources=SERVO_RESOURCES,
        default_timeout_seconds=10.0,
        idempotent=False,
        cancellable=True,
        confirmation_required=True,
    )

    def __init__(self, device: ServoDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        unexpected = sorted(set(arguments) - {"endpoint", "target_angle", "speed_mode"})
        if unexpected:
            raise _invalid_arguments(
                f"Unexpected argument keys: {unexpected}",
                capability="servo.move",
            )
        endpoint = arguments.get("endpoint")
        target_angle = arguments.get("target_angle")
        speed_mode = arguments.get("speed_mode", "S")
        if not isinstance(endpoint, str) or endpoint not in SUPPORTED_SERVO_ENDPOINTS:
            raise _invalid_arguments(
                f"endpoint must be one of {list(SUPPORTED_SERVO_ENDPOINTS)}",
                capability="servo.move",
            )
        if (
            not isinstance(target_angle, (int, float))
            or isinstance(target_angle, bool)
            or not MIN_TARGET_ANGLE <= target_angle <= MAX_TARGET_ANGLE
        ):
            raise _invalid_arguments(
                f"target_angle must be from {MIN_TARGET_ANGLE} through {MAX_TARGET_ANGLE}",
                capability="servo.move",
            )
        if not isinstance(speed_mode, str) or speed_mode not in {"S", "M", "F"}:
            raise _invalid_arguments(
                "speed_mode must be S, M, or F",
                capability="servo.move",
            )
        return await self._device.move(
            endpoint=endpoint,
            target_angle=float(target_angle),
            speed_mode=speed_mode,
        )

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


class ServoStopAdapter:
    """Expose confirmation-free emergency zero-pulse shutdown."""

    descriptor = CapabilityDescriptor(
        name="servo.stop",
        version="1.0.0",
        description="Abort movement and set all six servo pulse outputs to zero.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "stopped": {"type": "boolean"},
                "driver_available": {"type": "boolean"},
                "simulated": {"type": "boolean"},
            },
            "required": ["stopped", "driver_available", "simulated"],
            "additionalProperties": False,
        },
        risk=RiskLevel.EMERGENCY,
        resources=(),
        default_timeout_seconds=2.0,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, device: ServoDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise _invalid_arguments(
                f"servo.stop does not accept arguments: {sorted(arguments)}",
                capability="servo.stop",
            )
        return await self._device.stop()

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


def _is_calibrated(calibration: Any) -> bool:
    try:
        return (
            int(calibration.pulse_min) < int(calibration.pulse_center) < int(calibration.pulse_max)
            and float(calibration.angle_min)
            < float(calibration.angle_center)
            < float(calibration.angle_max)
            and int(calibration.speed) > 0
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _invalid_arguments(detail: str, *, capability: str) -> IDEError:
    return _servo_error(
        code="INVALID_CAPABILITY_ARGUMENTS",
        message=f"{capability} received invalid arguments.",
        technical_detail=detail,
        definitely_not_executed=True,
        retry_safety=RetrySafety.SAFE,
        capability=capability,
    )


def _servo_error(
    *,
    code: str,
    message: str,
    technical_detail: str | None,
    definitely_not_executed: bool,
    retry_safety: RetrySafety,
    capability: str,
) -> IDEError:
    return IDEError(
        ErrorDetails(
            code=code,
            message=message,
            technical_detail=technical_detail,
            definitely_not_executed=definitely_not_executed,
            retry_safety=retry_safety,
            capability=capability,
        )
    )
