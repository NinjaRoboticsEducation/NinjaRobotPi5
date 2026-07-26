"""Pytest fixtures for pi5disp hardware mocks."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_pigpio() -> MagicMock:
    """Create a pigpio-like mock backend for the driver tests."""
    mock_pi = MagicMock()
    mock_pi.connected = True
    mock_pi.OUTPUT = 1
    mock_pi.spi_open.return_value = 0
    mock_pi.spi_write.return_value = (0, b"")
    mock_pi.spi_close.return_value = 0
    mock_pi.write.return_value = 0
    mock_pi.set_mode.return_value = 0
    mock_pi.set_PWM_dutycycle.return_value = 0
    return mock_pi
