"""Bounded GPIO27 buzzer capabilities with cancellation-safe silence."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
from typing import Any, Protocol, TypeVar, cast

from .errors import IDEError
from .models import (
    CapabilityDescriptor,
    ErrorDetails,
    ResourceHealth,
    RetrySafety,
    RiskLevel,
)

MIN_FREQUENCY_HZ = 20
MAX_FREQUENCY_HZ = 20_000
MIN_DURATION_SECONDS = 0.05
MAX_DURATION_SECONDS = 2.0
MIN_VOLUME = 1
MAX_SAFE_VOLUME = 128
DEFAULT_DURATION_SECONDS = 0.2
DEFAULT_VOLUME = 32


class BuzzerDriver(Protocol):
    """Narrow surface consumed from the standalone buzzer library."""

    @property
    def is_initialized(self) -> bool:
        """Return whether the GPIO backend and worker are ready."""
        ...

    @property
    def volume(self) -> int:
        """Return the current 0-to-255 driver volume."""
        ...

    @volume.setter
    def volume(self, value: int) -> None:
        """Set the driver volume."""

    def initialize(self) -> None:
        """Initialize GPIO and the playback worker."""

    def play_sound(self, frequency: int, duration: float) -> None:
        """Queue one tone."""

    def off(self) -> None:
        """Silence output and release GPIO."""


BuzzerFactory = Callable[[int, int], BuzzerDriver]
ThreadResult = TypeVar("ThreadResult")


def _load_buzzer(pin: int, volume: int) -> BuzzerDriver:
    """Import the managed buzzer driver only for explicit real use."""
    module = importlib.import_module("pi5buzzer")
    buzzer_type = getattr(module, "Buzzer", None)
    if buzzer_type is None:
        raise ImportError("pi5buzzer.Buzzer is unavailable")
    return cast(BuzzerDriver, buzzer_type(pin=pin, volume=volume))


class BuzzerDevice:
    """Share one safely bounded buzzer instance across play and stop adapters."""

    def __init__(
        self,
        *,
        pin: int = 27,
        default_volume: int = DEFAULT_VOLUME,
        driver_factory: BuzzerFactory | None = None,
        simulated: bool = False,
    ) -> None:
        if not 0 <= pin <= 27:
            raise ValueError("buzzer pin must be a valid Raspberry Pi BCM GPIO number")
        if not MIN_VOLUME <= default_volume <= MAX_SAFE_VOLUME:
            raise ValueError(f"default_volume must be between {MIN_VOLUME} and {MAX_SAFE_VOLUME}")
        self._pin = pin
        self._default_volume = default_volume
        self._driver_factory = driver_factory or _load_buzzer
        self._simulated = simulated
        self._driver: BuzzerDriver | None = None
        self._startup_error: str | None = None
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._closed = False

    @property
    def simulated(self) -> bool:
        """Return whether this device is explicitly hardware-free."""
        return self._simulated

    async def start(self) -> None:
        """Initialize once while retaining an unavailable diagnostic state."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("buzzer device is closed")
            await self._initialize_locked()

    async def recover(self) -> None:
        """Silence and reconstruct the backend for an explicit Level 2 resume."""
        self._stop_event.set()
        async with self._lock:
            if self._closed:
                raise RuntimeError("buzzer device is closed")
            previous = self._driver
            self._driver = None
            close_error: str | None = None
            if previous is not None:
                try:
                    await _run_thread_to_completion(previous.off)
                except Exception as exc:
                    close_error = f"previous stop failed: {type(exc).__name__}: {exc}"

            self._startup_error = None
            await self._initialize_locked()
            if self._driver is None or not self._driver.is_initialized:
                detail = self._startup_error or "buzzer reconstruction did not initialize"
                if close_error is not None:
                    detail = f"{close_error}; {detail}"
                raise _buzzer_error(
                    code="BUZZER_RECOVERY_FAILED",
                    message="The GPIO27 buzzer backend could not be reconstructed.",
                    technical_detail=detail,
                    definitely_not_executed=True,
                    retry_safety=RetrySafety.SAFE,
                    capability="system.resume",
                )

    async def play(
        self,
        *,
        frequency_hz: int,
        duration_seconds: float,
        volume: int,
    ) -> dict[str, Any]:
        """Play one bounded tone and remain interruptible by emergency stop."""
        async with self._lock:
            driver = await self._require_driver_locked()
            driver.volume = volume
            self._stop_event.clear()
            try:
                await _run_thread_to_completion(
                    driver.play_sound,
                    frequency_hz,
                    duration_seconds,
                )
            except Exception as exc:
                raise _buzzer_error(
                    code="BUZZER_PLAY_FAILED",
                    message="The buzzer could not queue the requested tone.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.UNKNOWN,
                    capability="buzzer.play_tone",
                ) from exc

        interrupted = False
        try:
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=duration_seconds + 0.05,
                )
                interrupted = True
            except TimeoutError:
                pass
        except asyncio.CancelledError:
            await self.stop()
            raise

        return {
            "frequency_hz": frequency_hz,
            "duration_seconds": duration_seconds,
            "volume": volume,
            "interrupted": interrupted,
            "simulated": self._simulated,
        }

    async def stop(self) -> dict[str, Any]:
        """Immediately request silence without waiting for the play resource."""
        self._stop_event.set()
        async with self._lock:
            driver = self._driver
            if driver is not None:
                try:
                    await _run_thread_to_completion(driver.off)
                except Exception as exc:
                    raise _buzzer_error(
                        code="BUZZER_STOP_FAILED",
                        message="The buzzer could not confirm GPIO silence.",
                        technical_detail=f"{type(exc).__name__}: {exc}",
                        definitely_not_executed=False,
                        retry_safety=RetrySafety.SAFE,
                        capability="buzzer.stop",
                    ) from exc
        return {"stopped": True, "simulated": self._simulated}

    async def health(self) -> ResourceHealth:
        """Report readiness without playing a tone."""
        async with self._lock:
            if self._driver is None:
                return ResourceHealth.UNAVAILABLE
            return ResourceHealth.READY if self._driver.is_initialized else ResourceHealth.DEGRADED

    async def close(self) -> None:
        """Silence and release GPIO safely and idempotently."""
        if self._closed:
            return
        try:
            await self.stop()
        finally:
            async with self._lock:
                self._driver = None
                self._closed = True

    async def _initialize_locked(self) -> None:
        if self._driver is not None and self._driver.is_initialized:
            return
        driver = self._driver
        try:
            if driver is None:
                driver = await _run_thread_to_completion(
                    self._driver_factory,
                    self._pin,
                    self._default_volume,
                )
            await _run_thread_to_completion(driver.initialize)
            self._driver = driver
            self._startup_error = None
        except Exception as exc:
            if driver is not None:
                try:
                    await _run_thread_to_completion(driver.off)
                except Exception:
                    pass
            self._driver = None
            self._startup_error = f"{type(exc).__name__}: {exc}"

    async def _require_driver_locked(self) -> BuzzerDriver:
        await self._initialize_locked()
        if self._driver is None or not self._driver.is_initialized:
            raise _buzzer_error(
                code="BUZZER_UNAVAILABLE",
                message="The GPIO27 buzzer is unavailable.",
                technical_detail=self._startup_error,
                definitely_not_executed=True,
                retry_safety=RetrySafety.SAFE,
                capability="buzzer.play_tone",
            )
        return self._driver


async def _run_thread_to_completion(
    call: Callable[..., ThreadResult],
    /,
    *args: Any,
) -> ThreadResult:
    """Keep the device lock held until a cancelled GPIO call really exits."""
    worker = asyncio.create_task(asyncio.to_thread(call, *args))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancellation:
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
        try:
            worker.result()
        except Exception:
            pass
        raise cancellation


class BuzzerToneAdapter:
    """Expose bounded passive-buzzer tone playback."""

    descriptor = CapabilityDescriptor(
        name="buzzer.play_tone",
        version="1.0.0",
        description="Play one short, bounded passive-buzzer tone on GPIO27.",
        input_schema={
            "type": "object",
            "properties": {
                "frequency_hz": {
                    "type": "integer",
                    "minimum": MIN_FREQUENCY_HZ,
                    "maximum": MAX_FREQUENCY_HZ,
                },
                "duration_seconds": {
                    "type": "number",
                    "minimum": MIN_DURATION_SECONDS,
                    "maximum": MAX_DURATION_SECONDS,
                    "default": DEFAULT_DURATION_SECONDS,
                },
                "volume": {
                    "type": "integer",
                    "minimum": MIN_VOLUME,
                    "maximum": MAX_SAFE_VOLUME,
                    "default": DEFAULT_VOLUME,
                },
            },
            "required": ["frequency_hz"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "frequency_hz": {"type": "integer"},
                "duration_seconds": {"type": "number"},
                "volume": {"type": "integer"},
                "interrupted": {"type": "boolean"},
                "simulated": {"type": "boolean"},
            },
            "required": [
                "frequency_hz",
                "duration_seconds",
                "volume",
                "interrupted",
                "simulated",
            ],
            "additionalProperties": False,
        },
        risk=RiskLevel.LOW,
        resources=("buzzer", "gpio27"),
        default_timeout_seconds=3.0,
        idempotent=False,
        cancellable=True,
        confirmation_required=False,
    )

    def __init__(self, device: BuzzerDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        frequency = arguments.get("frequency_hz")
        duration = arguments.get("duration_seconds", DEFAULT_DURATION_SECONDS)
        volume = arguments.get("volume", DEFAULT_VOLUME)
        unexpected = sorted(set(arguments) - {"frequency_hz", "duration_seconds", "volume"})
        if unexpected:
            raise _invalid_arguments(
                f"Unexpected argument keys: {unexpected}",
                capability="buzzer.play_tone",
            )
        if (
            not isinstance(frequency, int)
            or isinstance(frequency, bool)
            or not MIN_FREQUENCY_HZ <= frequency <= MAX_FREQUENCY_HZ
        ):
            raise _invalid_arguments(
                f"frequency_hz must be an integer from {MIN_FREQUENCY_HZ} "
                f"through {MAX_FREQUENCY_HZ}",
                capability="buzzer.play_tone",
            )
        if (
            not isinstance(duration, (int, float))
            or isinstance(duration, bool)
            or not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS
        ):
            raise _invalid_arguments(
                f"duration_seconds must be from {MIN_DURATION_SECONDS} "
                f"through {MAX_DURATION_SECONDS}",
                capability="buzzer.play_tone",
            )
        if (
            not isinstance(volume, int)
            or isinstance(volume, bool)
            or not MIN_VOLUME <= volume <= MAX_SAFE_VOLUME
        ):
            raise _invalid_arguments(
                f"volume must be an integer from {MIN_VOLUME} through {MAX_SAFE_VOLUME}",
                capability="buzzer.play_tone",
            )
        return await self._device.play(
            frequency_hz=frequency,
            duration_seconds=float(duration),
            volume=volume,
        )

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


class BuzzerStopAdapter:
    """Expose an idempotent emergency silence capability."""

    descriptor = CapabilityDescriptor(
        name="buzzer.stop",
        version="1.0.0",
        description="Immediately silence the passive buzzer and release GPIO27.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "stopped": {"type": "boolean"},
                "simulated": {"type": "boolean"},
            },
            "required": ["stopped", "simulated"],
            "additionalProperties": False,
        },
        risk=RiskLevel.EMERGENCY,
        resources=(),
        default_timeout_seconds=2.5,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, device: BuzzerDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise _invalid_arguments(
                f"buzzer.stop does not accept arguments: {sorted(arguments)}",
                capability="buzzer.stop",
            )
        return await self._device.stop()

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


def _invalid_arguments(detail: str, *, capability: str) -> IDEError:
    return _buzzer_error(
        code="INVALID_CAPABILITY_ARGUMENTS",
        message=f"{capability} received invalid arguments.",
        technical_detail=detail,
        definitely_not_executed=True,
        retry_safety=RetrySafety.SAFE,
        capability=capability,
    )


def _buzzer_error(
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
