"""Endpoint helpers for native GPIO and external servo transports."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServoEndpoint:
    """Normalized servo endpoint identifier."""

    kind: str
    value: int

    def __post_init__(self) -> None:
        """Validate endpoint data."""
        if self.kind not in {"gpio", "hat_pwm"}:
            raise ValueError(f"Unsupported servo endpoint kind: {self.kind}")
        if self.value < 0:
            raise ValueError("Servo endpoint value must be non-negative")
        if self.kind == "hat_pwm" and not 1 <= self.value <= 4:
            raise ValueError("DFRobot HAT PWM channels must be in the range 1..4")

    @property
    def identifier(self) -> str:
        """Stable string identifier used in config and CLI parsing."""
        if self.kind == "gpio":
            return f"gpio{self.value}"
        return f"hat_pwm{self.value}"

    @property
    def legacy_pin(self) -> int:
        """Legacy integer GPIO pin for native endpoints."""
        if self.kind != "gpio":
            raise ValueError(
                f"{self.identifier} is not a native GPIO endpoint and has no legacy pin"
            )
        return self.value

    @property
    def legacy_key(self) -> int | str:
        """Backward-compatible key for existing GPIO-only call sites."""
        if self.kind == "gpio":
            return self.value
        return self.identifier


def parse_servo_endpoint(raw: int | str | ServoEndpoint) -> ServoEndpoint:
    """Parse a servo endpoint from legacy or explicit formats."""
    if isinstance(raw, ServoEndpoint):
        return raw

    if isinstance(raw, int):
        return ServoEndpoint(kind="gpio", value=raw)

    text = str(raw).strip().lower()
    if not text:
        raise ValueError("Empty servo endpoint")

    if text.isdigit():
        return ServoEndpoint(kind="gpio", value=int(text))

    if text.startswith("gpio") and text[4:].isdigit():
        return ServoEndpoint(kind="gpio", value=int(text[4:]))

    if text.startswith("hat_pwm") and text[7:].isdigit():
        return ServoEndpoint(kind="hat_pwm", value=int(text[7:]))

    raise ValueError(f"Unsupported servo endpoint '{raw}'. Use GPIO numbers, gpioNN, or hat_pwmN.")
