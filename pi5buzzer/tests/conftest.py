"""Shared test fixtures for the pi5buzzer test suite."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_pi():
    """Create a mocked pigpio-style backend instance."""
    pi = MagicMock()
    pi.connected = True
    pi.OUTPUT = 1
    pi.set_mode = MagicMock()
    pi.set_PWM_dutycycle = MagicMock()
    pi.set_PWM_frequency = MagicMock()
    pi.release_pwm = MagicMock()
    pi.stop = MagicMock()
    return pi


@pytest.fixture
def mock_backend_factory(mock_pi):
    """Patch the default backend factory to return our mock backend."""
    with patch("pi5buzzer.core.driver.create_default_backend", return_value=mock_pi) as factory:
        yield factory


@pytest.fixture
def buzzer(mock_pi):
    """Create an initialized Buzzer with a mocked backend."""
    from pi5buzzer.core.driver import Buzzer

    driver = Buzzer(pin=17, pi=mock_pi)
    driver.initialize()
    yield driver
    if driver.is_initialized:
        driver.off()


@pytest.fixture
def music_buzzer(mock_pi):
    """Create an initialized MusicBuzzer with a mocked backend."""
    from pi5buzzer.core.music import MusicBuzzer

    driver = MusicBuzzer(pin=17, pi=mock_pi)
    driver.initialize()
    yield driver
    if driver.is_initialized:
        driver.off()


@pytest.fixture
def tmp_config(tmp_path):
    """Provide a temporary config file path."""
    return str(tmp_path / "test_buzzer.json")
