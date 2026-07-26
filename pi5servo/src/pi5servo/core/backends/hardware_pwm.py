"""RP1 hardware PWM backend for header-connected servos on Raspberry Pi 5."""

from __future__ import annotations

import os
from importlib import import_module
from time import monotonic, sleep
from typing import Any

from ..backend_errors import BackendConfigurationError, BackendUnavailableError
from ..endpoint import parse_servo_endpoint

DEFAULT_SERVO_FREQUENCY_HZ = 50
DEFAULT_PWM_CHIP = 0
SYSFS_REQUIRED_CONTROLS = ("period", "duty_cycle", "enable")
SYSFS_RELEASE_TIMEOUT_S = 0.5
PI5_HEADER_PWM_CHANNELS = {
    12: 0,
    13: 1,
    18: 0,
    19: 1,
}


class HardwarePWMServoBackend:
    """Long-lived servo backend using `rpi-hardware-pwm`."""

    def __init__(
        self,
        *,
        pins: list[int] | None = None,
        pin_channel_map: dict[int, int] | None = None,
        frequency_hz: int = DEFAULT_SERVO_FREQUENCY_HZ,
        chip: int = DEFAULT_PWM_CHIP,
        pwm_cls: type[Any] | None = None,
    ) -> None:
        if pwm_cls is None:
            try:
                pwm_module = import_module("rpi_hardware_pwm")
                pwm_cls = pwm_module.HardwarePWM
            except ImportError as exc:
                raise BackendUnavailableError(
                    "rpi-hardware-pwm is not installed. Install the `pi` extra on Raspberry Pi 5."
                ) from exc

        self._pwm_cls = pwm_cls
        self._frequency_hz = int(frequency_hz)
        self._chip = int(chip)
        self._pin_channel_map = dict(pin_channel_map or PI5_HEADER_PWM_CHANNELS)
        self._pwms: dict[int, Any] = {}
        self._active: set[int] = set()
        self._current_pulses: dict[int, int] = {}

        if pins:
            self._validate_unique_channels(pins)

    def _normalize_pin(self, identifier: int | str) -> int:
        endpoint = parse_servo_endpoint(identifier)
        if endpoint.kind != "gpio":
            raise BackendConfigurationError("RP1 hardware PWM only supports native GPIO endpoints.")
        return endpoint.legacy_pin

    def _validate_pin(self, pin: int | str) -> int:
        pin = self._normalize_pin(pin)
        try:
            return self._pin_channel_map[pin]
        except KeyError as exc:
            supported = ", ".join(str(candidate) for candidate in sorted(self._pin_channel_map))
            raise BackendConfigurationError(
                f"GPIO{pin} is not supported by the RP1 hardware PWM backend. "
                f"Supported header pins: {supported}."
            ) from exc

    def _validate_unique_channels(self, pins: list[int | str]) -> None:
        """Reject alternate GPIO routes that would claim one PWM channel twice."""
        channel_pins: dict[int, int] = {}
        for identifier in pins:
            pin = self._normalize_pin(identifier)
            channel = self._validate_pin(pin)
            existing_pin = channel_pins.get(channel)
            if existing_pin is not None and existing_pin != pin:
                raise BackendConfigurationError(
                    f"GPIO{existing_pin} and GPIO{pin} are alternate routes for PWM{channel}; "
                    "choose only one."
                )
            channel_pins[channel] = pin

    def _ensure_channel_is_available(self, pin: int, pwm_channel: int) -> None:
        for claimed_pin in self._pwms:
            if claimed_pin != pin and self._validate_pin(claimed_pin) == pwm_channel:
                raise BackendConfigurationError(
                    f"GPIO{claimed_pin} and GPIO{pin} are alternate routes for PWM{pwm_channel}; "
                    "choose only one."
                )

    def _period_us(self) -> float:
        return 1_000_000.0 / float(self._frequency_hz)

    def _pulse_to_duty_cycle(self, pulse_width_us: int) -> float:
        pulse_width_us = max(0, pulse_width_us)
        duty = (pulse_width_us / self._period_us()) * 100.0
        return max(0.0, min(100.0, duty))

    def _channel_paths(self, pwm_channel: int) -> tuple[str, str, str]:
        chippath = f"/sys/class/pwm/pwmchip{self._chip}"
        pwm_dir = os.path.join(chippath, f"pwm{pwm_channel}")
        return chippath, pwm_dir, os.path.join(chippath, "unexport")

    @staticmethod
    def _controls_writable(pwm_dir: str) -> bool:
        return os.path.isdir(pwm_dir) and all(
            os.path.exists(os.path.join(pwm_dir, control))
            and os.access(os.path.join(pwm_dir, control), os.W_OK)
            for control in SYSFS_REQUIRED_CONTROLS
        )

    def _best_effort_unexport_channel(
        self,
        pwm_channel: int,
        *,
        chippath: str | None = None,
        pwm_dir: str | None = None,
        unexport_path: str | None = None,
        echo: Any | None = None,
    ) -> None:
        if chippath is None or pwm_dir is None or unexport_path is None:
            chippath, pwm_dir, unexport_path = self._channel_paths(pwm_channel)
        if not os.path.exists(unexport_path) or not os.access(unexport_path, os.W_OK):
            return

        try:
            if callable(echo):
                echo(pwm_channel, unexport_path)
            else:
                with open(unexport_path, "w", encoding="ascii") as handle:
                    handle.write(f"{pwm_channel}\n")
        except OSError:
            return

        if not pwm_dir:
            return

        deadline = monotonic() + SYSFS_RELEASE_TIMEOUT_S
        while os.path.exists(pwm_dir) and monotonic() < deadline:
            sleep(0.01)

    def _best_effort_unexport(self, pwm: Any) -> None:
        chippath = getattr(pwm, "chippath", None)
        pwm_channel = getattr(pwm, "pwm_channel", None)
        pwm_dir = getattr(pwm, "pwm_dir", None)
        if not isinstance(chippath, str) or not isinstance(pwm_channel, int):
            return

        self._best_effort_unexport_channel(
            pwm_channel,
            chippath=chippath,
            pwm_dir=pwm_dir if isinstance(pwm_dir, str) else None,
            unexport_path=os.path.join(chippath, "unexport"),
            echo=getattr(pwm, "echo", None),
        )

    def _prepare_channel_for_claim(self, pwm_channel: int) -> None:
        chippath, pwm_dir, unexport_path = self._channel_paths(pwm_channel)
        if os.path.isdir(pwm_dir) and not self._controls_writable(pwm_dir):
            self._best_effort_unexport_channel(
                pwm_channel,
                chippath=chippath,
                pwm_dir=pwm_dir,
                unexport_path=unexport_path,
            )

    def claim(self, identifier: int | str) -> None:
        identifier = self._normalize_pin(identifier)
        if identifier in self._pwms:
            return
        pwm_channel = self._validate_pin(identifier)
        self._ensure_channel_is_available(identifier, pwm_channel)
        self._prepare_channel_for_claim(pwm_channel)
        try:
            pwm = self._pwm_cls(
                pwm_channel=pwm_channel,
                hz=self._frequency_hz,
                chip=self._chip,
            )
        except PermissionError:
            self._best_effort_unexport_channel(pwm_channel)
            pwm = self._pwm_cls(
                pwm_channel=pwm_channel,
                hz=self._frequency_hz,
                chip=self._chip,
            )
        self._pwms[identifier] = pwm
        self._current_pulses.setdefault(identifier, 0)

    def set_pulse_us(self, identifier: int | str, pulse_width_us: int) -> None:
        identifier = self._normalize_pin(identifier)
        if pulse_width_us <= 0:
            self.off(identifier)
            return

        self.claim(identifier)
        pwm = self._pwms[identifier]
        duty_cycle = self._pulse_to_duty_cycle(int(pulse_width_us))

        if identifier in self._active:
            pwm.change_frequency(self._frequency_hz)
            pwm.change_duty_cycle(duty_cycle)
        else:
            pwm.start(duty_cycle)
            self._active.add(identifier)

        self._current_pulses[identifier] = int(pulse_width_us)

    def get_pulse_us(self, identifier: int | str) -> int:
        identifier = self._normalize_pin(identifier)
        return int(self._current_pulses.get(identifier, 0))

    def off(self, identifier: int | str) -> None:
        identifier = self._normalize_pin(identifier)
        self.claim(identifier)
        pwm = self._pwms[identifier]
        if identifier in self._active:
            pwm.stop()
            self._active.discard(identifier)
        self._current_pulses[identifier] = 0

    def release(self, identifier: int | str) -> None:
        identifier = self._normalize_pin(identifier)
        if identifier not in self._pwms:
            return
        self.off(identifier)
        self._pwms.pop(identifier, None)
        self._active.discard(identifier)
        self._current_pulses.pop(identifier, None)

    def close(self) -> None:
        for identifier in list(self._pwms):
            self.release(identifier)
