"""Velocity and duration calculations for servo movement.

This module provides physics-based calculations for servo movement timing
using the SG90 servo motor specification (0.10s per 60°, i.e., 600°/sec).
"""

# SG90 servo motor physical maximum velocity (degrees per second)
PHYSICAL_MAX_VELOCITY = 600.0  # °/sec (SG90 spec: 0.10s/60°)

# Speed mode multipliers relative to the per-servo speed limit
FMS_MULTIPLIERS = {
    "F": 1.0,  # Fast = 100% of speed limit
    "M": 0.75,  # Medium = 75% of speed limit
    "S": 0.5,  # Slow = 50% of speed limit
}


def calculate_duration(distance: float, speed_limit: int, speed_mode: str) -> float:
    """Calculate movement duration from distance and velocity.

    Uses physics-based calculation:
        velocity = PHYSICAL_MAX_VELOCITY * (speed_limit / 100) * fms_multiplier
        duration = distance / velocity

    Args:
        distance: Angle difference in degrees (always positive)
        speed_limit: Per-servo speed limit (0-100)
        speed_mode: "F" (Fast), "M" (Medium), or "S" (Slow)

    Returns:
        Duration in seconds. Returns 0 if velocity is 0.

    Examples:
        >>> calculate_duration(90, 100, "F")  # 90° at full speed
        0.15
        >>> calculate_duration(90, 80, "M")   # 90° at 80% limit, Medium mode
        0.25
    """
    fms_mult = FMS_MULTIPLIERS.get(speed_mode, 0.75)  # Default to Medium
    velocity = PHYSICAL_MAX_VELOCITY * (speed_limit / 100) * fms_mult

    if velocity <= 0:
        return 0.0

    return abs(distance) / velocity


def calculate_step_count(duration: float, step_interval: float = 0.02) -> int:
    """Calculate the number of interpolation steps for a movement.

    Args:
        duration: Total movement duration in seconds
        step_interval: Time between each step (default 20ms for ~50Hz)

    Returns:
        Number of steps (minimum 1)
    """
    if duration <= 0:
        return 1
    return max(1, int(duration / step_interval))
