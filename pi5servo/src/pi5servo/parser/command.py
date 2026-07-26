"""Command string parser for movement-tool format.

Parses command strings in the format:
    [SPEED_]PIN:ANGLE[/PIN:ANGLE...]

Examples:
    "20:45"                   -> Medium speed, GPIO 20 to 45°
    "gpio20:45"               -> Explicit GPIO endpoint
    "hat_pwm1:45"             -> DFRobot HAT PWM channel 1
    "F_20:45/21:-30"          -> Fast speed, multiple servos
    "S_gpio20:C/hat_pwm1:M"   -> Slow speed, mixed endpoint syntax
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from ..core.endpoint import ServoEndpoint, parse_servo_endpoint


@dataclass
class ServoTarget:
    """Parsed target for a single servo."""

    pin: int | str | ServoEndpoint
    angle: Optional[float] = None  # Degrees (-90 to 90), None for special
    special: Optional[str] = None  # "C" (center), "M" (min), "X" (max)
    speed: Optional[str] = None  # Per-target speed override: "F", "M", or "S"
    endpoint: ServoEndpoint = field(init=False)

    def __post_init__(self):
        """Validate the target."""
        self.endpoint = parse_servo_endpoint(self.pin)
        self.pin = self.endpoint.legacy_key
        if self.angle is None and self.special is None:
            raise ValueError("Either angle or special must be provided")
        if self.special and self.special not in ("C", "M", "X"):
            raise ValueError(f"Invalid special position: {self.special}")
        if self.speed and self.speed not in ("F", "M", "S"):
            raise ValueError(f"Invalid speed mode: {self.speed}")

    @property
    def endpoint_id(self) -> str:
        """Stable endpoint identifier for mixed-backend routing."""
        return self.endpoint.identifier


@dataclass
class ParsedCommand:
    """Result of parsing a command string."""

    speed_mode: str = "M"  # Default to Medium
    targets: list[ServoTarget] = field(default_factory=list)


# Regex patterns
SPEED_PREFIX_PATTERN = re.compile(r"^([FSM])_")
# Target format: ENDPOINT:ANGLE_OR_SPECIAL[SPEED] where endpoint is a GPIO
# number, explicit gpioNN name, or DFRobot HAT PWM identifier.
TARGET_PATTERN = re.compile(r"^([A-Za-z0-9_]+):(-?\d+(?:\.\d+)?|[CMX])([FSM])?$")


def parse_command(command: str) -> ParsedCommand:
    """Parse a movement-tool format command string.

    Format: [SPEED_]PIN:ANGLE[/PIN:ANGLE...]

    Args:
        command: The command string to parse

    Returns:
        ParsedCommand with speed_mode and list of ServoTarget

    Raises:
        ValueError: If command format is invalid

    Examples:
        >>> result = parse_command("F_gpio20:45/hat_pwm1:-30")
        >>> result.speed_mode
        'F'
        >>> result.targets[0].endpoint_id
        'gpio20'
        >>> result.targets[0].angle
        45.0
    """
    if not command or not command.strip():
        raise ValueError("Empty command string")

    command = command.strip()
    result = ParsedCommand()

    # Check for speed prefix
    speed_match = SPEED_PREFIX_PATTERN.match(command)
    if speed_match:
        result.speed_mode = speed_match.group(1)
        command = command[len(speed_match.group(0)) :]  # Remove prefix

    # Split by "/" and parse each target
    parts = command.split("/")
    for part in parts:
        if not part.strip():
            continue

        target_match = TARGET_PATTERN.match(part.strip())
        if not target_match:
            raise ValueError(f"Invalid target format: {part}")

        pin = target_match.group(1)
        value = target_match.group(2)
        target_speed = target_match.group(3)  # Optional per-target speed

        if value in ("C", "M", "X"):
            target = ServoTarget(pin=pin, special=value, speed=target_speed)
        else:
            angle = float(value)
            if not -90 <= angle <= 90:
                raise ValueError(f"Angle out of range (-90 to 90): {angle}")
            target = ServoTarget(pin=pin, angle=angle, speed=target_speed)

        result.targets.append(target)

    if not result.targets:
        raise ValueError("No valid targets found in command")

    return result


def resolve_special_angle(special: str, calibration: dict | None = None) -> float:
    """Convert special position code to angle.

    Args:
        special: "C" (center), "M" (min), "X" (max)
        calibration: Optional dict with 'angle_min', 'angle_max', 'angle_center'

    Returns:
        Resolved angle in degrees
    """
    defaults = {"C": 0.0, "M": -90.0, "X": 90.0}

    if calibration:
        mapping = {
            "C": calibration.get("angle_center", 0.0),
            "M": calibration.get("angle_min", -90.0),
            "X": calibration.get("angle_max", 90.0),
        }
        return mapping.get(special, defaults[special])

    return defaults[special]
