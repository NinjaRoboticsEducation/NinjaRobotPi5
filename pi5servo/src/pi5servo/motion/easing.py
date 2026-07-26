"""Easing functions for smooth servo movement.

These functions take a normalized time value t (0.0 to 1.0) and return
a normalized position value (0.0 to 1.0) with the specified easing curve.
"""


def linear(t: float) -> float:
    """Linear interpolation (no easing).

    Args:
        t: Normalized time (0.0 to 1.0)

    Returns:
        Position at time t (same as t, no easing)
    """
    return t


def ease_out(t: float) -> float:
    """Quadratic ease-out (DEFAULT). Start fast, end slow.

    This is the recommended default for servo movements as it creates
    a natural deceleration effect.

    Args:
        t: Normalized time (0.0 to 1.0)

    Returns:
        Eased position at time t
    """
    return t * (2 - t)


def ease_in(t: float) -> float:
    """Quadratic ease-in. Start slow, end fast.

    Args:
        t: Normalized time (0.0 to 1.0)

    Returns:
        Eased position at time t
    """
    return t * t


def ease_in_out(t: float) -> float:
    """Quadratic ease-in-out. Smooth acceleration and deceleration.

    Args:
        t: Normalized time (0.0 to 1.0)

    Returns:
        Eased position at time t
    """
    if t < 0.5:
        return 2 * t * t
    return 1 - pow(-2 * t + 2, 2) / 2


# --- Cubic Easing (Smoother than Quadratic) ---


def ease_in_cubic(t: float) -> float:
    """Cubic ease-in. Very slow start, fast end.

    Args:
        t: Normalized time (0.0 to 1.0)

    Returns:
        Eased position at time t
    """
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out. Fast start, very slow end.

    Args:
        t: Normalized time (0.0 to 1.0)

    Returns:
        Eased position at time t
    """
    return 1 - pow(1 - t, 3)


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease-in-out (DEFAULT). Smoother than quadratic.

    Provides gentler acceleration and deceleration curves
    for more natural, fluid servo motion.

    Args:
        t: Normalized time (0.0 to 1.0)

    Returns:
        Eased position at time t
    """
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


# Dictionary for lookup by name
EASING_FUNCTIONS = {
    "linear": linear,
    "ease_out": ease_out,
    "ease_in": ease_in,
    "ease_in_out": ease_in_out,
    "ease_in_cubic": ease_in_cubic,
    "ease_out_cubic": ease_out_cubic,
    "ease_in_out_cubic": ease_in_out_cubic,
}
