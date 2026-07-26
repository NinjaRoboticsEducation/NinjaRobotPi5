from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ninjarobot_pi5_ide import (
    ActionLedger,
    ActionRequest,
    ActionStatus,
    CapabilityRegistry,
    ExecutionEngine,
    ResourceHealth,
    RetrySafety,
    VL53L0XDistanceAdapter,
)


class FakeSensor:
    def __init__(self, reading: dict[str, Any], *, healthy: bool = True) -> None:
        self.reading = reading
        self.healthy = healthy
        self.reads = 0
        self.closed = 0

    def get_data(self) -> dict[str, Any]:
        self.reads += 1
        return dict(self.reading)

    def health_check(self) -> bool:
        return self.healthy

    def close(self) -> None:
        self.closed += 1


def request(action_id: str = "distance-1") -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        capability="distance.read",
        arguments={},
        requested_by="test",
        session_id="session-1",
        idempotency_key=f"key-{action_id}",
    )


def test_valid_distance_lifecycle_and_health(tmp_path: Path) -> None:
    async def exercise() -> None:
        sensor = FakeSensor(
            {
                "distance_mm": 250,
                "raw_value": 250,
                "is_valid": True,
                "timestamp": 123.5,
            }
        )
        factory_calls: list[tuple[int, int]] = []

        def factory(bus: int, address: int) -> FakeSensor:
            factory_calls.append((bus, address))
            return sensor

        adapter = VL53L0XDistanceAdapter(sensor_factory=factory)
        engine = ExecutionEngine(
            CapabilityRegistry([adapter]),
            ActionLedger(tmp_path / "valid.sqlite3"),
        )
        descriptors = await engine.capabilities()
        assert descriptors[0].name == "distance.read"
        assert factory_calls == []

        result = await engine.execute(request())
        assert result.status is ActionStatus.SUCCEEDED
        assert result.data == {
            "distance_mm": 250,
            "raw_value": 250,
            "sensor_timestamp": 123.5,
        }
        assert factory_calls == [(1, 0x29)]
        assert (await engine.health()).status is ResourceHealth.READY
        await engine.close()
        assert sensor.closed == 1

    asyncio.run(exercise())


def test_8191_sentinel_is_a_structured_out_of_range_result(tmp_path: Path) -> None:
    async def exercise() -> None:
        sensor = FakeSensor(
            {
                "distance_mm": 8191,
                "raw_value": 8191,
                "is_valid": False,
                "timestamp": 123.5,
            }
        )
        adapter = VL53L0XDistanceAdapter(
            sensor_factory=lambda _bus, _address: sensor,
        )
        engine = ExecutionEngine(
            CapabilityRegistry([adapter]),
            ActionLedger(tmp_path / "invalid.sqlite3"),
        )
        result = await engine.execute(request())
        assert result.status is ActionStatus.FAILED
        assert result.retry_safety is RetrySafety.SAFE
        assert result.error is not None
        assert result.error.code == "DEVICE_OUT_OF_RANGE"
        assert result.error.definitely_not_executed is False
        assert "clear-space sentinel" in (result.error.technical_detail or "")
        await engine.close()

    asyncio.run(exercise())


def test_raw_8191_is_out_of_range_even_when_offset_changes_distance(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        sensor = FakeSensor(
            {
                "distance_mm": 8181,
                "raw_value": 8191,
                "is_valid": True,
                "timestamp": 123.5,
            }
        )
        adapter = VL53L0XDistanceAdapter(
            sensor_factory=lambda _bus, _address: sensor,
        )
        engine = ExecutionEngine(
            CapabilityRegistry([adapter]),
            ActionLedger(tmp_path / "offset-sentinel.sqlite3"),
        )

        result = await engine.execute(request())

        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "DEVICE_OUT_OF_RANGE"
        await engine.close()

    asyncio.run(exercise())


def test_unavailable_device_reports_health_and_action_failure(tmp_path: Path) -> None:
    async def exercise() -> None:
        def unavailable(_bus: int, _address: int) -> FakeSensor:
            raise OSError("I2C bus unavailable")

        adapter = VL53L0XDistanceAdapter(sensor_factory=unavailable)
        engine = ExecutionEngine(
            CapabilityRegistry([adapter]),
            ActionLedger(tmp_path / "unavailable.sqlite3"),
        )
        await engine.start()
        health = await engine.health()
        result = await engine.execute(request())
        assert health.status is ResourceHealth.UNAVAILABLE
        assert result.status is ActionStatus.FAILED
        assert result.error is not None and result.error.code == "DEVICE_UNAVAILABLE"
        assert result.error.definitely_not_executed is True
        await engine.close()

    asyncio.run(exercise())


def test_unexpected_arguments_are_rejected_without_reading(tmp_path: Path) -> None:
    async def exercise() -> None:
        sensor = FakeSensor(
            {
                "distance_mm": 100,
                "raw_value": 100,
                "is_valid": True,
                "timestamp": 1.0,
            }
        )
        adapter = VL53L0XDistanceAdapter(
            sensor_factory=lambda _bus, _address: sensor,
        )
        engine = ExecutionEngine(
            CapabilityRegistry([adapter]),
            ActionLedger(tmp_path / "arguments.sqlite3"),
        )
        bad_request = request().model_copy(update={"arguments": {"samples": 2}})
        result = await engine.execute(bad_request)
        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "INVALID_CAPABILITY_ARGUMENTS"
        assert result.error.definitely_not_executed is True
        assert sensor.reads == 0
        await engine.close()

    asyncio.run(exercise())
