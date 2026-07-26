"""pi0servo.core - Core servo control classes.

Exports:
    - ServoEndpoint: Normalized endpoint model for GPIO and HAT PWM targets
    - Servo: Single servo controller with calibration
    - ServoCalibration: Dataclass for calibration data
    - ServoGroup: Multi-servo controller with abort support
"""

from .endpoint import ServoEndpoint, parse_servo_endpoint
from .multi_servos import ServoGroup
from .servo import (
    ANGLE_CENTER,
    ANGLE_MAX,
    ANGLE_MIN,
    DEFAULT_SPEED_LIMIT,
    PULSE_CENTER,
    PULSE_MAX,
    PULSE_MIN,
    Servo,
    ServoCalibration,
)

__all__ = [
    # Endpoint helpers
    "ServoEndpoint",
    "parse_servo_endpoint",
    # Servo
    "Servo",
    "ServoCalibration",
    # Constants
    "PULSE_MIN",
    "PULSE_MAX",
    "PULSE_CENTER",
    "ANGLE_MIN",
    "ANGLE_MAX",
    "ANGLE_CENTER",
    "DEFAULT_SPEED_LIMIT",
    # ServoGroup
    "ServoGroup",
]
