"""Fusion HAT+ kernel transport; never bypass the kernel with raw I2C writes."""

from __future__ import annotations

import fcntl
import math
import os
from pathlib import Path
from typing import TextIO

from ..backend_errors import BackendConfigurationError, BackendUnavailableError
from ..endpoint import ServoEndpoint, parse_servo_endpoint

DRIVER_VERSION = "1.1.0-ninja1"


class FusionHatPlusBackend:
    """One exclusive controller session shared by standalone and integrated users."""

    name = "fusion_hat_plus"

    def __init__(
        self,
        *,
        frequency_hz: int = 50,
        sysfs_root: str | Path = "/sys/class/fusion_hat/fusion_hat",
        battery_path: str | Path = "/sys/class/power_supply/fusion-hat/voltage_now",
        lock_path: str | Path = "/run/lock/ninjarobot-fusion.lock",
    ) -> None:
        if isinstance(frequency_hz, bool) or frequency_hz != 50:
            raise BackendConfigurationError(
                "Fusion servo sessions require a shared 50 Hz frequency"
            )
        self.frequency_hz = frequency_hz
        self.address = 0x17
        self._root = Path(sysfs_root)
        self._battery = Path(battery_path)
        self._lock: TextIO | None = None
        self._claimed: set[int] = set()
        self._pulses: dict[int, int] = {}
        self._closed = False
        try:
            if (self._root / "version").read_text().strip() != DRIVER_VERSION:
                raise BackendUnavailableError(
                    "Fusion driver requires reviewed version " + DRIVER_VERSION
                )
            for channel in range(12):
                for attribute in ("period", "duty_cycle", "enable"):
                    if not self._path(channel, attribute).is_file():
                        raise BackendUnavailableError(
                            f"Fusion PWM{channel} interface is incomplete"
                        )
            # Installation creates this group-writable lock. Never create a per-user
            # replacement: that would allow two users to claim the same hardware.
            fd = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
            handle = os.fdopen(fd, "r+")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                raise BackendUnavailableError("Fusion controller is owned by another servo session")
            self._lock = handle
            # Clear abandoned outputs before configuring shared timers. No pulse is
            # produced by construction or claim; explicit set_pulse_us starts output.
            for channel in range(12):
                self._write(channel, "enable", 0)
            for channel in (0, 4, 8):
                self._write(channel, "period", 20_000)
        except FileNotFoundError as exc:
            self._unlock()
            raise BackendUnavailableError(
                "Fusion kernel interface or shared lock is missing. Run "
                "scripts/fusion_hat_setup.py check; follow the reviewed installation guide "
                "and reboot manually. Selecting Fusion does not install its driver."
            ) from exc
        except PermissionError as exc:
            self._unlock()
            raise BackendUnavailableError(
                "Fusion permission denied. Check gpio group membership, udev and tmpfiles "
                "rules; log in again after group changes. Do not run the tool as root."
            ) from exc
        except Exception as exc:
            self._unlock()
            if isinstance(exc, BackendUnavailableError):
                raise
            raise BackendUnavailableError(
                "Fusion prerequisite/permission failure; run reviewed Fusion setup and reboot"
            ) from exc

    def _path(self, channel: int, attribute: str) -> Path:
        return self._root / "pwm" / f"pwm{channel}" / attribute

    def _write(self, channel: int, attribute: str, value: int) -> None:
        try:
            self._path(channel, attribute).write_text(f"{value}\n")
        except OSError as exc:
            raise BackendUnavailableError(
                f"Fusion PWM{channel} {attribute} failed; physical output state is uncertain"
            ) from exc

    def _channel(self, identifier: int | str | ServoEndpoint) -> int:
        if self._closed:
            raise BackendUnavailableError("Fusion servo session is closed")
        endpoint = parse_servo_endpoint(identifier)
        if endpoint.kind != "hat_pwm" or not 0 <= endpoint.value < 12:
            raise BackendConfigurationError("Fusion accepts explicit hat_pwm0 through hat_pwm11")
        return endpoint.value

    def claim(self, identifier: int | str | ServoEndpoint) -> None:
        channel = self._channel(identifier)
        if channel not in self._claimed:
            self._write(channel, "enable", 1)
            self._claimed.add(channel)
            self._pulses[channel] = 0

    def set_pulse_us(self, identifier: int | str | ServoEndpoint, pulse_width_us: int) -> None:
        channel = self._channel(identifier)
        if isinstance(pulse_width_us, bool) or not 500 <= pulse_width_us <= 2500:
            raise BackendConfigurationError("Servo pulse must be between 500 and 2500 microseconds")
        self.claim(identifier)
        self._write(channel, "duty_cycle", int(pulse_width_us))
        self._pulses[channel] = int(pulse_width_us)

    def get_pulse_us(self, identifier: int | str | ServoEndpoint) -> int:
        return self._pulses.get(self._channel(identifier), 0)

    def off(self, identifier: int | str | ServoEndpoint) -> None:
        channel = self._channel(identifier)
        self._write(channel, "enable", 0)
        self._pulses[channel] = 0
        self._claimed.discard(channel)

    def release(self, identifier: int | str | ServoEndpoint) -> None:
        self.off(identifier)

    def read_battery_voltage(self) -> float:
        # Patched kernel rejects invalid/expired samples; a fresh file-read time
        # alone would NOT demonstrate that the underlying sample is current.
        voltage = int(self._battery.read_text().strip()) / 1_000_000
        if not math.isfinite(voltage) or not 0.5 < voltage <= 15:
            raise BackendUnavailableError("Fusion battery telemetry is invalid")
        return voltage

    def _unlock(self) -> None:
        if self._lock is not None:
            self._lock.close()
            self._lock = None

    def close(self) -> None:
        if self._closed:
            return
        failures = []
        try:
            for channel in tuple(self._claimed):
                try:
                    self.off(f"hat_pwm{channel}")
                except BackendUnavailableError as exc:
                    failures.append(exc)
        finally:
            self._closed = True
            self._unlock()
        if failures:
            raise BackendUnavailableError(
                "Fusion cleanup failed; remove actuator power"
            ) from failures[0]
