"""Pytest fixtures for mocking pigpio on PC/Mac."""

import sys
from unittest.mock import MagicMock

import pytest

# Mock ninja_utils before any imports that need it
mock_ninja_utils = MagicMock()
mock_ninja_utils.get_module_logger = MagicMock(return_value=MagicMock())
sys.modules["ninja_utils"] = mock_ninja_utils


@pytest.fixture(autouse=True)
def mock_pigpio(monkeypatch):
    """Mock pigpio for all tests - no hardware required.

    This fixture automatically mocks the pigpio module so tests can run
    on development machines without a Raspberry Pi.
    """
    # Create a mock pigpio module
    mock_pigpio_module = MagicMock()

    # Create a mock pi instance
    mock_pi = MagicMock()
    mock_pi.connected = True
    mock_pi.get_servo_pulsewidth.return_value = 1500  # Default center position
    mock_pi.set_servo_pulsewidth.return_value = None

    # Configure pigpio.pi() to return our mock
    mock_pigpio_module.pi.return_value = mock_pi

    # Inject the mock into sys.modules
    monkeypatch.setitem(sys.modules, "pigpio", mock_pigpio_module)

    return mock_pi
