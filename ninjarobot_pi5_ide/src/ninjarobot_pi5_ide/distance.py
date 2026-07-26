"""Read-only VL53L0X adapter with lazy managed-driver loading."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
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

    @property
    def descriptor(self) -> CapabilityDescriptor:
        """Return the stable read-only capability description."""
        return self._descriptor

    @property
    def startup_error(self) -> str | None:
        """Return sanitized initialization detail for diagnostics."""
        return self._startup_error

    async def start(self) -> None:
        """Initialize the sensor once while preserving unavailable health state."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("distance adapter is closed")
            if self._sensor is not None:
                return
            try:
                self._sensor = await asyncio.to_thread(
                    self._sensor_factory,
                    self._i2c_bus,
                    self._i2c_address,
                )
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
                reading = await asyncio.to_thread(sensor.get_data)
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
            if self._sensor is None:
                return ResourceHealth.UNAVAILABLE
            try:
                healthy = await asyncio.to_thread(self._sensor.health_check)
            except Exception:
                return ResourceHealth.UNAVAILABLE
        return ResourceHealth.READY if healthy else ResourceHealth.DEGRADED

    async def close(self) -> None:
        """Close the managed sensor safely and idempotently."""
        async with self._lock:
            if self._closed:
                return
            sensor, self._sensor = self._sensor, None
            self._closed = True
            if sensor is not None:
                await asyncio.to_thread(sensor.close)

    def _require_sensor(self) -> DistanceSensor:
        if self._sensor is None:
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
        ):
            raise self._invalid_reading(distance, raw_value, valid)
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
