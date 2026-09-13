"""Read-only VL53L0X adapter with lazy managed-driver loading."""

from __future__ import annotations

import asyncio
import importlib
import math
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

from .errors import IDEError
from .models import (
    CapabilityDescriptor,
    ErrorDetails,
    ResourceHealth,
    RetrySafety,
    RiskLevel,
)


class DistanceSensor(Protocol):
    """Narrow surface consumed from the standalone sensor driver."""

    def get_data(self) -> dict[str, Any]:
        """Return one driver-normalized reading."""

    def health_check(self) -> bool:
        """Check sensor identity without starting a range measurement."""

    def close(self) -> None:
        """Close the I2C handle."""


SensorFactory = Callable[[int, int], DistanceSensor]


def _load_vl53l0x(i2c_bus: int, i2c_address: int) -> DistanceSensor:
    """Import and initialize the managed driver only for explicit real use."""
    module = importlib.import_module("pi5vl53l0x")
    sensor_type = getattr(module, "VL53L0X", None)
    if sensor_type is None:
        raise ImportError("pi5vl53l0x.VL53L0X is unavailable")
    sensor = sensor_type(i2c_bus=i2c_bus, i2c_address=i2c_address)
    return cast(DistanceSensor, sensor)


class VL53L0XDistanceAdapter:
    """Expose one safe distance-reading capability through IDE contracts."""

    _descriptor = CapabilityDescriptor(
        name="distance.read",
        version="1.0.0",
        description="Read one validated distance from the VL53L0X sensor.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "distance_mm": {"type": "integer", "minimum": 1, "maximum": 8189},
                "raw_value": {"type": "integer", "minimum": 1, "maximum": 8189},
                "sensor_timestamp": {"type": "number"},
            },
            "required": ["distance_mm", "raw_value", "sensor_timestamp"],
            "additionalProperties": False,
        },
        risk=RiskLevel.READ_ONLY,
        resources=("i2c1", "vl53l0x-0x29"),
        default_timeout_seconds=2.0,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
    )

    def __init__(
        self,
        *,
        i2c_bus: int = 1,
        i2c_address: int = 0x29,
        sensor_factory: SensorFactory | None = None,
    ) -> None:
        if i2c_bus < 0:
            raise ValueError("i2c_bus must not be negative")
        if not 0x08 <= i2c_address <= 0x77:
            raise ValueError("i2c_address must be a usable 7-bit I2C address")
        self._i2c_bus = i2c_bus
        self._i2c_address = i2c_address
        self._sensor_factory = sensor_factory or _load_vl53l0x
        self._sensor: DistanceSensor | None = None
        self._startup_error: str | None = None
        self._lock = asyncio.Lock()
        self._closed = False
        self._pending: asyncio.Task[Any] | None = None
        self._recovery_required = False

    @property
    def descriptor(self) -> CapabilityDescriptor:
        """Return the stable read-only capability description."""
        return self._descriptor

    @property
    def startup_error(self) -> str | None:
        """Return sanitized initialization detail for diagnostics."""
        return self._startup_error

    async def start(self, *, recover: bool = False) -> None:
        """Initialize the sensor once while preserving unavailable health state."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("distance adapter is closed")
            self._require_drained()
            if self._sensor is not None:
                if self._recovery_required:
                    if not recover:
                        raise RuntimeError("distance recovery must be explicitly requested")
                    healthy = await self._owned_call(self._sensor.health_check)
                    if not healthy:
                        raise RuntimeError("distance sensor recovery health check failed")
                    self._recovery_required = False
                return
            try:

                async def initialize() -> None:
                    self._sensor = await asyncio.to_thread(
                        self._sensor_factory, self._i2c_bus, self._i2c_address
                    )

                await self._owned_operation(initialize())
                self._recovery_required = False
                self._startup_error = None
            except Exception as exc:
                self._startup_error = f"{type(exc).__name__}: {exc}"

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Read one sample and reject driver sentinel values such as 8191 mm."""
        if arguments:
            raise self._error(
                code="INVALID_CAPABILITY_ARGUMENTS",
                message="distance.read does not accept arguments.",
                technical_detail=f"Unexpected argument keys: {sorted(arguments)}",
                definitely_not_executed=True,
            )
        async with self._lock:
            sensor = self._require_sensor()
            try:
                reading = await self._owned_call(sensor.get_data)
            except Exception as exc:
                raise self._error(
                    code="DEVICE_READ_FAILED",
                    message="The VL53L0X distance read failed.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    definitely_not_executed=False,
                ) from exc
        return self._validate_reading(reading)

    async def health(self) -> ResourceHealth:
        """Check sensor identity without taking a distance measurement."""
        async with self._lock:
            if self._sensor is None or self._recovery_required or self._busy:
                return ResourceHealth.UNAVAILABLE
            try:
                healthy = await self._owned_call(self._sensor.health_check)
            except Exception:
                return ResourceHealth.UNAVAILABLE
        return ResourceHealth.READY if healthy else ResourceHealth.DEGRADED

    async def suspend(self) -> None:
        """Release I2C resources while allowing a later start."""
        async with self._lock:
            if self._closed:
                return
            self._require_drained()
            sensor = self._sensor
            self._startup_error = None
            if sensor is not None:

                async def release() -> None:
                    await asyncio.to_thread(sensor.close)
                    self._sensor = None

                await self._owned_operation(release())

    async def close(self) -> None:
        """Close the managed sensor safely and idempotently."""
        async with self._lock:
            if self._closed:
                return
            self._require_drained()
            sensor = self._sensor
            if sensor is not None:

                async def release() -> None:
                    await asyncio.to_thread(sensor.close)
                    self._sensor = None

                await self._owned_operation(release())

            self._closed = True

    @property
    def _busy(self) -> bool:
        return self._pending is not None and not self._pending.done()

    def _require_drained(self) -> None:
        if self._busy:
            raise self._error(
                code="DEVICE_READ_PENDING",
                message="Distance sensor work is still pending; device reuse is blocked.",
                technical_detail=(
                    "Wait for the worker to drain, then explicitly resume. "
                    "A stuck worker requires service recovery."
                ),
                definitely_not_executed=True,
            )

    async def _owned_call(self, operation: Callable[[], Any]) -> Any:
        self._require_drained()
        return await self._owned_operation(asyncio.to_thread(operation))

    async def _owned_operation(self, operation: Awaitable[Any]) -> Any:
        # Shield ownership, not the caller: cancelled/timed-out work stays owned
        # until the actual thread returns. Its late value never becomes a sample.
        task = asyncio.ensure_future(operation)
        self._pending = task
        task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except (asyncio.CancelledError, TimeoutError):
            self._recovery_required = True
            raise

    def _require_sensor(self) -> DistanceSensor:
        self._require_drained()
        if self._sensor is None or self._recovery_required or self._closed:
            raise self._error(
                code="DEVICE_UNAVAILABLE",
                message="The VL53L0X sensor is unavailable.",
                technical_detail=self._startup_error,
                definitely_not_executed=True,
            )
        return self._sensor

    def _validate_reading(self, reading: dict[str, Any]) -> dict[str, Any]:
        distance = reading.get("distance_mm")
        raw_value = reading.get("raw_value")
        timestamp = reading.get("timestamp")
        valid = reading.get("is_valid")
        if (
            not isinstance(distance, int)
            or isinstance(distance, bool)
            or not isinstance(raw_value, int)
            or isinstance(raw_value, bool)
            or not isinstance(timestamp, (int, float))
            or isinstance(timestamp, bool)
            or not math.isfinite(timestamp)
        ):
            raise self._invalid_reading(distance, raw_value, valid)
        if raw_value == 8191:
            raise self._error(
                code="DEVICE_OUT_OF_RANGE",
                message="The VL53L0X did not detect a target within measurable range.",
                technical_detail=(
                    f"distance_mm={distance!r}, raw_value=8191, "
                    f"is_valid={valid!r}; this is the sensor's clear-space sentinel."
                ),
                definitely_not_executed=False,
            )
        if valid is not True or not 0 < distance < 8190 or not 0 < raw_value < 8190:
            raise self._invalid_reading(distance, raw_value, valid)
        return {
            "distance_mm": distance,
            "raw_value": raw_value,
            "sensor_timestamp": float(timestamp),
        }

    def _invalid_reading(
        self,
        distance: object,
        raw_value: object,
        valid: object,
    ) -> IDEError:
        return self._error(
            code="DEVICE_INVALID_READING",
            message="The VL53L0X returned an invalid distance sample.",
            technical_detail=(
                f"distance_mm={distance!r}, raw_value={raw_value!r}, "
                f"is_valid={valid!r}; 8191 mm is a sensor sentinel, not a distance."
            ),
            definitely_not_executed=False,
        )

    @staticmethod
    def _error(
        *,
        code: str,
        message: str,
        technical_detail: str | None,
        definitely_not_executed: bool,
    ) -> IDEError:
        return IDEError(
            ErrorDetails(
                code=code,
                message=message,
                technical_detail=technical_detail,
                definitely_not_executed=definitely_not_executed,
                retry_safety=RetrySafety.SAFE,
                capability="distance.read",
            )
        )
