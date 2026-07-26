from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ninjarobot_pi5_ide import (
    ActionLedger,
    ActionRequest,
    ActionStatus,
    BuzzerDevice,
    BuzzerStopAdapter,
    BuzzerToneAdapter,
    CapabilityRegistry,
    ExecutionEngine,
    ResourceHealth,
    ResourceScheduler,
    RetrySafety,
)


class FakeBuzzerDriver:
    def __init__(self, *, fail_initialize: bool = False) -> None:
        self._initialized = False
        self._volume = 0
        self.fail_initialize = fail_initialize
        self.initialize_calls = 0
        self.play_calls: list[tuple[int, float, int]] = []
        self.off_calls = 0

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
        self.initialize_calls += 1
        if self.fail_initialize:
            raise ConnectionError("GPIO unavailable")
        self._initialized = True

    def play_sound(self, frequency: int, duration: float) -> None:
        self.play_calls.append((frequency, duration, self._volume))

    def off(self) -> None:
        self.off_calls += 1
        self._initialized = False


def request(
    action_id: str,
    capability: str = "buzzer.play_tone",
    arguments: dict[str, Any] | None = None,
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        capability=capability,
        arguments=arguments or {},
        requested_by="test",
        session_id="buzzer-test",
        idempotency_key=f"key-{action_id}",
    )


def engine_for(
    tmp_path: Path,
    driver: FakeBuzzerDriver,
) -> tuple[ExecutionEngine, BuzzerDevice]:
    device = BuzzerDevice(
        pin=27,
        driver_factory=lambda _pin, _volume: driver,
        simulated=True,
    )
    engine = ExecutionEngine(
        CapabilityRegistry(
            [
                BuzzerToneAdapter(device),
                BuzzerStopAdapter(device),
            ]
        ),
        ActionLedger(tmp_path / "buzzer.sqlite3"),
        scheduler=ResourceScheduler(max_concurrency=2, max_queue_size=4),
    )
    return engine, device


async def wait_for_play(driver: FakeBuzzerDriver) -> None:
    for _ in range(100):
        if driver.play_calls:
            return
        await asyncio.sleep(0.001)
    raise AssertionError("buzzer play call did not begin")


def test_bounded_tone_success_and_health(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = FakeBuzzerDriver()
        engine, _device = engine_for(tmp_path, driver)
        result = await engine.execute(
            request(
                "tone-1",
                arguments={
                    "frequency_hz": 440,
                    "duration_seconds": 0.05,
                    "volume": 32,
                },
            )
        )
        assert result.status is ActionStatus.SUCCEEDED
        assert result.retry_safety is RetrySafety.UNSAFE
        assert result.data == {
            "frequency_hz": 440,
            "duration_seconds": 0.05,
            "volume": 32,
            "interrupted": False,
            "simulated": True,
        }
        assert driver.play_calls == [(440, 0.05, 32)]
        health = await engine.health()
        assert health.status is ResourceHealth.READY
        await engine.close()
        assert driver.off_calls == 1

    asyncio.run(exercise())


def test_emergency_stop_interrupts_tone_without_waiting_for_play_lock(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        driver = FakeBuzzerDriver()
        engine, _device = engine_for(tmp_path, driver)
        playing = asyncio.create_task(
            engine.execute(
                request(
                    "tone-long",
                    arguments={
                        "frequency_hz": 440,
                        "duration_seconds": 1.0,
                        "volume": 16,
                    },
                )
            )
        )
        await wait_for_play(driver)
        stopped = await engine.execute(request("stop-1", "buzzer.stop"))
        played = await playing
        assert stopped.status is ActionStatus.SUCCEEDED
        assert stopped.data == {"stopped": True, "simulated": True}
        assert stopped.retry_safety is RetrySafety.SAFE
        assert played.status is ActionStatus.SUCCEEDED
        assert played.data is not None and played.data["interrupted"] is True
        assert driver.off_calls >= 1
        await engine.close()

    asyncio.run(exercise())


def test_cancellation_silences_running_tone(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = FakeBuzzerDriver()
        engine, _device = engine_for(tmp_path, driver)
        playing = asyncio.create_task(
            engine.execute(
                request(
                    "cancel-tone",
                    arguments={
                        "frequency_hz": 880,
                        "duration_seconds": 1.0,
                        "volume": 20,
                    },
                )
            )
        )
        await wait_for_play(driver)
        cancelled = await engine.cancel("cancel-tone")
        returned = await playing
        assert cancelled.status is ActionStatus.CANCELLED
        assert returned == cancelled
        assert driver.off_calls >= 1
        await engine.close()

    asyncio.run(exercise())


def test_invalid_arguments_never_reach_driver(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = FakeBuzzerDriver()
        engine, _device = engine_for(tmp_path, driver)
        invalid = await engine.execute(
            request(
                "invalid-tone",
                arguments={
                    "frequency_hz": 440,
                    "duration_seconds": 10.0,
                },
            )
        )
        assert invalid.status is ActionStatus.FAILED
        assert invalid.error is not None
        assert invalid.error.code == "INVALID_CAPABILITY_ARGUMENTS"
        assert invalid.error.definitely_not_executed is True
        assert driver.play_calls == []
        await engine.close()

    asyncio.run(exercise())


def test_unavailable_gpio_becomes_structured_failure(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = FakeBuzzerDriver(fail_initialize=True)
        engine, _device = engine_for(tmp_path, driver)
        await engine.start()
        health = await engine.health()
        result = await engine.execute(request("unavailable", arguments={"frequency_hz": 440}))
        assert health.status is ResourceHealth.UNAVAILABLE
        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "BUZZER_UNAVAILABLE"
        assert result.error.definitely_not_executed is True
        await engine.close()

    asyncio.run(exercise())
