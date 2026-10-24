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
        if self.kind == "hat_pwm" and not 0 <= self.value <= 15:
            raise ValueError(
                f"Invalid HAT PWM channel {self.value}. Supported channels are 0 to 15."
            )

    @property
    def identifier(self) -> str:
        """Stable string identifier used in config and CLI parsing."""
        if self.kind == "gpio":
            return f"gpio{self.value}"
        return f"hat_pwm{self.value}"

    @property
    def label(self) -> str:
        """Human-readable label for CLI display."""
        if self.kind == "gpio":
            return f"GPIO{self.value}"
        return f"HAT_PWM{self.value}"

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

    if text.startswith("pwm") and text[3:].isdigit():
        return ServoEndpoint(kind="hat_pwm", value=int(text[3:]))

    if text.startswith("p") and text[1:].isdigit():
        return ServoEndpoint(kind="hat_pwm", value=int(text[1:]))

    raise ValueError(
        f"Unsupported servo endpoint '{raw}'. Use GPIO numbers, gpioNN, hat_pwmN, pwmN, or pN."
    )
