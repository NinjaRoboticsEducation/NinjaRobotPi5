"""pi0servo.motion - Motion interpolation and timing calculations.

This module provides easing functions and velocity-based duration calculations
for smooth servo movements.

Exports:
    - linear, ease_out, ease_in, ease_in_out: Quadratic easing functions
    - ease_in_cubic, ease_out_cubic, ease_in_out_cubic: Cubic easing functions
    - EASING_FUNCTIONS: Dictionary lookup for easing by name
    - calculate_duration: Physics-based duration calculation
    - calculate_step_count: Interpolation step count calculation
    - PHYSICAL_MAX_VELOCITY: SG90 max velocity (600°/sec)
    - FMS_MULTIPLIERS: Speed mode multipliers (F, M, S)
"""

from .calculator import (
    FMS_MULTIPLIERS,
    PHYSICAL_MAX_VELOCITY,
    calculate_duration,
    calculate_step_count,
)
from .easing import (
    EASING_FUNCTIONS,
    ease_in,
    ease_in_cubic,
    ease_in_out,
    ease_in_out_cubic,
    ease_out,
    ease_out_cubic,
    linear,
)

__all__ = [
    # Easing functions (quadratic)
    "linear",
    "ease_out",
    "ease_in",
    "ease_in_out",
    # Easing functions (cubic - smoother)
    "ease_in_cubic",
    "ease_out_cubic",
    "ease_in_out_cubic",
    "EASING_FUNCTIONS",
    # Calculator functions
    "calculate_duration",
    "calculate_step_count",
    "PHYSICAL_MAX_VELOCITY",
    "FMS_MULTIPLIERS",
]
