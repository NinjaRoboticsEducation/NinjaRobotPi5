"""Unit tests for motion module."""

from pi5servo.motion import (
    EASING_FUNCTIONS,
    FMS_MULTIPLIERS,
    PHYSICAL_MAX_VELOCITY,
    calculate_duration,
    calculate_step_count,
    ease_in,
    ease_in_out,
    ease_out,
    linear,
)


class TestEasingFunctions:
    """Test easing function correctness."""

    def test_linear_midpoint(self):
        """Linear should return same value as input."""
        assert linear(0.5) == 0.5

    def test_ease_out_midpoint(self):
        """Ease-out should be ahead of linear at midpoint."""
        assert ease_out(0.5) == 0.75  # Faster at start

    def test_ease_in_midpoint(self):
        """Ease-in should be behind linear at midpoint."""
        assert ease_in(0.5) == 0.25  # Slower at start

    def test_ease_in_out_midpoint(self):
        """Ease-in-out should be at 0.5 at midpoint."""
        assert ease_in_out(0.5) == 0.5

    def test_boundaries(self):
        """All easing functions should return 0 at t=0 and 1 at t=1."""
        for fn in [linear, ease_out, ease_in, ease_in_out]:
            assert fn(0.0) == 0.0, f"{fn.__name__}(0) should be 0"
            assert fn(1.0) == 1.0, f"{fn.__name__}(1) should be 1"

    def test_easing_functions_dict(self):
        """EASING_FUNCTIONS dictionary should contain all functions."""
        assert "linear" in EASING_FUNCTIONS
        assert "ease_out" in EASING_FUNCTIONS
        assert "ease_in" in EASING_FUNCTIONS
        assert "ease_in_out" in EASING_FUNCTIONS
        assert EASING_FUNCTIONS["ease_out"] is ease_out


class TestCalculateDuration:
    """Test velocity-based duration calculations."""

    def test_fast_mode_full_speed(self):
        """90° at 100% speed limit, Fast mode."""
        # velocity = 600 * 1.0 * 1.0 = 600 °/sec
        # duration = 90 / 600 = 0.15 sec
        assert calculate_duration(90, 100, "F") == 0.15

    def test_medium_mode_80_speed(self):
        """90° at 80% speed limit, Medium mode."""
        # velocity = 600 * 0.8 * 0.75 = 360 °/sec
        # duration = 90 / 360 = 0.25 sec
        assert calculate_duration(90, 80, "M") == 0.25

    def test_slow_mode_full_speed(self):
        """45° at 100% speed limit, Slow mode."""
        # velocity = 600 * 1.0 * 0.5 = 300 °/sec
        # duration = 45 / 300 = 0.15 sec
        assert calculate_duration(45, 100, "S") == 0.15

    def test_zero_speed_returns_zero(self):
        """Zero speed limit should return zero duration."""
        assert calculate_duration(90, 0, "F") == 0.0

    def test_unknown_mode_defaults_to_medium(self):
        """Unknown speed mode should default to Medium (0.75x)."""
        # velocity = 600 * 1.0 * 0.75 = 450 °/sec
        # duration = 90 / 450 = 0.2 sec
        assert calculate_duration(90, 100, "X") == 0.2

    def test_negative_distance_uses_absolute(self):
        """Negative distance should be treated as positive."""
        assert calculate_duration(-90, 100, "F") == 0.15


class TestCalculateStepCount:
    """Test interpolation step count calculations."""

    def test_typical_duration(self):
        """0.5 second movement at 20ms steps should have 25 steps."""
        assert calculate_step_count(0.5, 0.02) == 25

    def test_minimum_one_step(self):
        """Very short or zero duration should return at least 1 step."""
        assert calculate_step_count(0.0) == 1
        assert calculate_step_count(0.01) == 1

    def test_default_interval(self):
        """Default interval should be 20ms."""
        assert calculate_step_count(0.1) == 5


class TestConstants:
    """Test module constants."""

    def test_physical_max_velocity(self):
        """Physical max velocity should be 600 °/sec (SG90 spec)."""
        assert PHYSICAL_MAX_VELOCITY == 600.0

    def test_fms_multipliers(self):
        """FMS multipliers should have correct values."""
        assert FMS_MULTIPLIERS["F"] == 1.0
        assert FMS_MULTIPLIERS["M"] == 0.75
        assert FMS_MULTIPLIERS["S"] == 0.5
