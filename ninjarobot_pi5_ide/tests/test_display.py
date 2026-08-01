from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from ninjarobot_pi5_ide import (
    ActionLedger,
    ActionRequest,
    ActionStatus,
    CapabilityRegistry,
    DisplayBrightnessAdapter,
    DisplayClearAdapter,
    DisplayDevice,
    DisplayShowTextAdapter,
    ExecutionEngine,
    ResourceHealth,
    ResourceScheduler,
    RetrySafety,
)


class FakeDisplayDriver:
    def __init__(
        self,
        *,
        width: int = 320,
        height: int = 240,
        healthy: bool = True,
        fail_write: bool = False,
        fail_brightness: bool = False,
    ) -> None:
        self.width = width
        self.height = height
        self.healthy = healthy
        self.fail_write = fail_write
        self.fail_brightness = fail_brightness
        self.frames: list[tuple[str, tuple[int, int]]] = []
        self.clear_calls: list[tuple[int, int, int]] = []
        self.brightness_calls: list[int] = []
        self.close_calls = 0

    def display(self, image: Any) -> None:
        if self.fail_write:
            raise OSError("SPI transfer failed")
        self.frames.append((image.mode, image.size))

    def clear(self, color: tuple[int, int, int]) -> None:
        self.clear_calls.append(color)

    def set_brightness(self, percent: int) -> None:
        if self.fail_brightness:
            raise OSError("backlight PWM failed")
        self.brightness_calls.append(percent)

    def health_check(self) -> bool:
        return self.healthy

    def close(self) -> None:
        self.close_calls += 1


class ConcurrencyDisplayDriver(FakeDisplayDriver):
    def __init__(self) -> None:
        super().__init__()
        self.active_calls = 0
        self.max_active_calls = 0
        self._call_lock = threading.Lock()

    def clear(self, color: tuple[int, int, int]) -> None:
        self._slow_call()
        super().clear(color)

    def set_brightness(self, percent: int) -> None:
        self._slow_call()
        super().set_brightness(percent)

    def _slow_call(self) -> None:
        with self._call_lock:
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        time.sleep(0.01)
        with self._call_lock:
            self.active_calls -= 1


class BlockingDisplayDriver(FakeDisplayDriver):
    def __init__(self) -> None:
        super().__init__()
        self.call_started = threading.Event()
        self.release_call = threading.Event()
        self.active_calls = 0
        self.max_active_calls = 0
        self._call_lock = threading.Lock()

    def clear(self, color: tuple[int, int, int]) -> None:
        with self._call_lock:
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        self.call_started.set()
        assert self.release_call.wait(timeout=1.0)
        super().clear(color)
        with self._call_lock:
            self.active_calls -= 1

    def set_brightness(self, percent: int) -> None:
        if self.brightness_calls:
            with self._call_lock:
                self.active_calls += 1
                self.max_active_calls = max(self.max_active_calls, self.active_calls)
            with self._call_lock:
                self.active_calls -= 1
        super().set_brightness(percent)


def request(
    action_id: str,
    capability: str,
    arguments: dict[str, Any],
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        capability=capability,
        arguments=arguments,
        requested_by="test",
        session_id="display-test",
        idempotency_key=f"key-{action_id}",
    )


def engine_for(
    tmp_path: Path,
    device: DisplayDevice,
) -> ExecutionEngine:
    return ExecutionEngine(
        CapabilityRegistry(
            [
                DisplayBrightnessAdapter(device),
                DisplayClearAdapter(device),
                DisplayShowTextAdapter(device),
            ]
        ),
        ActionLedger(tmp_path / "display.sqlite3"),
        scheduler=ResourceScheduler(max_concurrency=3, max_queue_size=6),
    )


def test_exact_configuration_text_render_health_and_cleanup(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = FakeDisplayDriver()
        settings_seen: dict[str, Any] = {}

        def factory(**settings: Any) -> FakeDisplayDriver:
            settings_seen.update(settings)
            return driver

        device = DisplayDevice(driver_factory=factory, simulated=True)
        engine = engine_for(tmp_path, device)
        result = await engine.execute(
            request(
                "display-text-1",
                "display.show_text",
                {
                    "text": "NinjaRobot\nPhase 3.2",
                    "font_size": 24,
                    "foreground": "#00ff00",
                    "background": "#000020",
                },
            )
        )

        assert result.status is ActionStatus.SUCCEEDED
        assert result.retry_safety is RetrySafety.SAFE
        assert result.data == {
            "text": "NinjaRobot\nPhase 3.2",
            "font_size": 24,
            "foreground": "#00FF00",
            "background": "#000020",
            "width": 320,
            "height": 240,
            "rotation": 90,
            "brightness": 75,
            "simulated": True,
        }
        assert settings_seen == {
            "channel": 0,
            "dc_pin": 4,
            "rst_pin": 5,
            "backlight_pin": 6,
            "speed_hz": 32_000_000,
            "width": 240,
            "height": 320,
            "rotation": 90,
        }
        assert driver.brightness_calls == [75]
        assert driver.frames == [("RGB", (320, 240))]
        health = await engine.health()
        assert health.status is ResourceHealth.READY

        await engine.close()
        assert driver.close_calls == 1

    asyncio.run(exercise())


def test_clear_and_brightness_share_one_driver(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = FakeDisplayDriver()
        device = DisplayDevice(
            driver_factory=lambda **_settings: driver,
            simulated=True,
        )
        engine = engine_for(tmp_path, device)

        cleared = await engine.execute(
            request("display-clear-1", "display.clear", {"color": "#123456"})
        )
        brightness = await engine.execute(
            request(
                "display-brightness-1",
                "display.set_brightness",
                {"percent": 25},
            )
        )

        assert cleared.status is ActionStatus.SUCCEEDED
        assert cleared.data == {
            "cleared": True,
            "color": "#123456",
            "simulated": True,
        }
        assert brightness.status is ActionStatus.SUCCEEDED
        assert brightness.data == {"brightness": 25, "simulated": True}
        assert driver.clear_calls == [(18, 52, 86)]
        assert driver.brightness_calls == [75, 25]
        await engine.close()

    asyncio.run(exercise())


def test_invalid_display_arguments_never_reach_driver(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = FakeDisplayDriver()
        device = DisplayDevice(
            driver_factory=lambda **_settings: driver,
            simulated=True,
        )
        engine = engine_for(tmp_path, device)

        invalid_color = await engine.execute(
            request(
                "bad-color",
                "display.show_text",
                {"text": "hello", "foreground": "white"},
            )
        )
        invalid_brightness = await engine.execute(
            request(
                "bad-brightness",
                "display.set_brightness",
                {"percent": 101},
            )
        )

        assert invalid_color.status is ActionStatus.FAILED
        assert invalid_color.error is not None
        assert invalid_color.error.code == "INVALID_CAPABILITY_ARGUMENTS"
        assert invalid_color.error.definitely_not_executed is True
        assert invalid_brightness.status is ActionStatus.FAILED
        assert invalid_brightness.error is not None
        assert invalid_brightness.error.code == "INVALID_CAPABILITY_ARGUMENTS"
        assert driver.frames == []
        assert driver.brightness_calls == [75]
        await engine.close()

    asyncio.run(exercise())


def test_unavailable_display_becomes_structured_failure(tmp_path: Path) -> None:
    async def exercise() -> None:
        def unavailable(**_settings: Any) -> FakeDisplayDriver:
            raise ConnectionError("SPI0 unavailable")

        device = DisplayDevice(driver_factory=unavailable)
        engine = engine_for(tmp_path, device)
        result = await engine.execute(request("display-unavailable", "display.clear", {}))

        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "DISPLAY_UNAVAILABLE"
        assert result.error.definitely_not_executed is True
        assert result.error.technical_detail == "ConnectionError: SPI0 unavailable"
        health = await engine.health()
        assert health.status is ResourceHealth.UNAVAILABLE
        await engine.close()

    asyncio.run(exercise())


def test_partial_startup_failure_closes_constructed_driver(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = FakeDisplayDriver(fail_brightness=True)
        device = DisplayDevice(driver_factory=lambda **_settings: driver)
        engine = engine_for(tmp_path, device)
        result = await engine.execute(request("display-start-failure", "display.clear", {}))

        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "DISPLAY_UNAVAILABLE"
        assert result.error.technical_detail == "OSError: backlight PWM failed"
        assert driver.close_calls == 1
        await engine.close()

    asyncio.run(exercise())


def test_explicit_recovery_retries_one_shot_startup_and_probes_a_write() -> None:
    async def exercise() -> None:
        driver = FakeDisplayDriver()
        factory_calls = 0

        def factory(**_settings: Any) -> FakeDisplayDriver:
            nonlocal factory_calls
            factory_calls += 1
            if factory_calls == 1:
                raise ConnectionError("SPI0 unavailable")
            return driver

        device = DisplayDevice(driver_factory=factory)
        await device.start()
        await device.start()
        assert factory_calls == 1
        assert await device.health() is ResourceHealth.UNAVAILABLE

        await device.recover()

        assert factory_calls == 2
        assert driver.brightness_calls == [75]
        assert driver.clear_calls == [(0, 0, 0)]
        assert await device.health() is ResourceHealth.READY
        await device.close()

    asyncio.run(exercise())


def test_repeated_recovery_closes_every_replaced_display_driver() -> None:
    async def exercise() -> None:
        drivers: list[FakeDisplayDriver] = []

        def factory(**_settings: Any) -> FakeDisplayDriver:
            driver = FakeDisplayDriver()
            drivers.append(driver)
            return driver

        device = DisplayDevice(driver_factory=factory)
        await device.start()
        for _ in range(20):
            await device.recover()

        assert len(drivers) == 21
        assert all(driver.close_calls == 1 for driver in drivers[:-1])
        assert all(driver.clear_calls == [(0, 0, 0)] for driver in drivers[1:])
        assert await device.health() is ResourceHealth.READY
        await device.close()
        assert drivers[-1].close_calls == 1

    asyncio.run(exercise())


def test_failed_spi_write_is_retry_safe_and_structured(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = FakeDisplayDriver(fail_write=True)
        device = DisplayDevice(driver_factory=lambda **_settings: driver)
        engine = engine_for(tmp_path, device)
        result = await engine.execute(
            request(
                "display-write-failure",
                "display.show_text",
                {"text": "test"},
            )
        )

        assert result.status is ActionStatus.FAILED
        assert result.error is not None
        assert result.error.code == "DISPLAY_WRITE_FAILED"
        assert result.error.retry_safety is RetrySafety.SAFE
        assert result.error.definitely_not_executed is False
        await engine.close()

    asyncio.run(exercise())


def test_all_display_adapters_declare_the_same_serial_resources() -> None:
    expected = ("display", "spi0", "gpio4", "gpio5", "gpio6")
    assert DisplayShowTextAdapter.descriptor.resources == expected
    assert DisplayClearAdapter.descriptor.resources == expected
    assert DisplayBrightnessAdapter.descriptor.resources == expected


def test_concurrent_display_actions_are_serialized(tmp_path: Path) -> None:
    async def exercise() -> None:
        driver = ConcurrencyDisplayDriver()
        device = DisplayDevice(driver_factory=lambda **_settings: driver)
        engine = engine_for(tmp_path, device)
        await engine.start()

        clear_result, brightness_result = await asyncio.gather(
            engine.execute(request("concurrent-clear", "display.clear", {})),
            engine.execute(
                request(
                    "concurrent-brightness",
                    "display.set_brightness",
                    {"percent": 50},
                )
            ),
        )

        assert clear_result.status is ActionStatus.SUCCEEDED
        assert brightness_result.status is ActionStatus.SUCCEEDED
        assert driver.max_active_calls == 1
        await engine.close()

    asyncio.run(exercise())


def test_cancelled_display_call_keeps_lock_until_spi_thread_finishes() -> None:
    async def exercise() -> None:
        driver = BlockingDisplayDriver()
        device = DisplayDevice(driver_factory=lambda **_settings: driver)
        await device.start()

        first = asyncio.create_task(device.clear(color="#000000"))
        assert await asyncio.to_thread(driver.call_started.wait, 0.5)
        first.cancel()
        second = asyncio.create_task(device.set_brightness(percent=50))
        await asyncio.sleep(0.02)

        assert not first.done()
        assert not second.done()
        assert driver.max_active_calls == 1

        driver.release_call.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert (await second)["brightness"] == 50
        assert driver.max_active_calls == 1
        await device.close()

    asyncio.run(exercise())
