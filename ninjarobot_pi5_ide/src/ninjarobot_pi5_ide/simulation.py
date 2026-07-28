"""Hardware-free drivers used only by the IDE tool simulation path."""

from __future__ import annotations

import asyncio
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .servo import ServoRuntime


class SimulatedDisplayDriver:
    """In-memory display with the managed driver's narrow surface."""

    def __init__(self, **settings: Any) -> None:
        width = int(settings["width"])
        height = int(settings["height"])
        rotation = int(settings["rotation"])
        self.width, self.height = (height, width) if rotation in {90, 270} else (width, height)
        self.last_frame: Any | None = None
        self.brightness = 0
        self.closed = False

    def display(self, image: Any) -> None:
        self.last_frame = image.copy()

    def clear(self, color: tuple[int, int, int]) -> None:
        self.last_frame = ("clear", color)

    def set_brightness(self, percent: int) -> None:
        self.brightness = percent

    def health_check(self) -> bool:
        return not self.closed

    def close(self) -> None:
        self.closed = True


class SimulatedBuzzerDriver:
    """In-memory buzzer that records no physical GPIO."""

    def __init__(self, _pin: int, volume: int) -> None:
        self._initialized = False
        self._volume = volume

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

    def play_sound(self, _frequency: int, _duration: float) -> None:
        return

    def off(self) -> None:
        self._initialized = False


@dataclass
class SimulatedCalibration:
    """Wide logical calibration for deterministic simulation."""

    pulse_min: int = 1_000
    pulse_max: int = 2_000
    pulse_center: int = 1_500
    angle_min: float = -90.0
    angle_max: float = 90.0
    angle_center: float = 0.0
    speed: int = 80


class SimulatedServo:
    """One in-memory calibrated endpoint."""

    def __init__(self) -> None:
        self.calibration = SimulatedCalibration()

    def move_to_center(self) -> None:
        return


class SimulatedServoGroup:
    """In-memory mixed group with the managed async movement contract."""

    def __init__(self, endpoints: tuple[str, ...]) -> None:
        self._servos = {endpoint: SimulatedServo() for endpoint in endpoints}
        self._aborted = False

    def get_servo(self, pin: int | str) -> SimulatedServo | None:
        return self._servos.get(str(pin))

    async def move_all_async(
        self,
        _targets: list[float | None],
        speed_mode: str = "M",
    ) -> bool:
        del speed_mode
        self._aborted = False
        await asyncio.sleep(0.01)
        return not self._aborted

    def abort(self) -> None:
        self._aborted = True

    def off(self) -> None:
        self._aborted = True

    def close(self) -> None:
        self._aborted = True


def simulated_servo_runtime(
    endpoints: tuple[str, ...],
    _calibration_file: str,
    _i2c_bus: int,
    _address: int,
) -> ServoRuntime:
    """Build a fully calibrated in-memory servo runtime."""
    return ServoRuntime(
        group=SimulatedServoGroup(endpoints),
        calibrated_endpoints=frozenset(endpoints),
    )


class SimulatedDistanceSensor:
    """Always-clear, healthy front distance sensor."""

    def __init__(self, _bus: int, _address: int) -> None:
        self.closed = False

    def get_data(self) -> dict[str, Any]:
        return {
            "distance_mm": 500,
            "raw_value": 500,
            "is_valid": True,
            "timestamp": time.time(),
        }

    def health_check(self) -> bool:
        return not self.closed

    def close(self) -> None:
        self.closed = True


class SimulatedMicrophoneDeviceInfo:
    """Managed-driver-compatible simulated mono input device."""

    index = 0
    name = "Simulated USB Microphone"
    max_input_channels = 1
    default_samplerate = 16_000.0
    hostapi = 0


class SimulatedMicrophoneClip:
    """Managed-driver-compatible simulated WAV result."""

    def __init__(self, path: Path, duration_seconds: float, sample_rate: int) -> None:
        self.path = path
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate
        self.channels = 1
        self.frames = max(1, round(duration_seconds * sample_rate))
        self.bytes_written = path.stat().st_size
        self.overflowed = False


class SimulatedMicrophoneBackend:
    """Generate bounded silence without opening audio hardware."""

    def __init__(self) -> None:
        self._device = SimulatedMicrophoneDeviceInfo()

    def list_input_devices(self) -> list[SimulatedMicrophoneDeviceInfo]:
        return [self._device]

    def resolve_input_settings(
        self,
        *,
        selector: str,
        sample_rate: int,
        channels: int,
    ) -> tuple[int, int, SimulatedMicrophoneDeviceInfo, None]:
        del selector
        if channels != 1:
            raise ValueError("simulated microphone supports mono audio only")
        return self._device.index, sample_rate, self._device, None

    def record_wav(
        self,
        output_path: Path,
        *,
        selector: str,
        sample_rate: int,
        channels: int,
        duration_seconds: float,
    ) -> SimulatedMicrophoneClip:
        del selector
        frame_count = max(1, round(duration_seconds * sample_rate))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * frame_count * channels)
        return SimulatedMicrophoneClip(output_path, duration_seconds, sample_rate)
