"""pi5servo.config - Configuration and calibration management.

Exports:
    - ConfigManager: JSON-based calibration storage
    - get_default_config_path: Default config file location
"""

from .config_manager import (
    BACKEND_CONFIG_KEY,
    DEFAULT_CONFIG_FILE,
    ConfigManager,
    get_default_config_path,
)

__all__ = [
    "BACKEND_CONFIG_KEY",
    "ConfigManager",
    "get_default_config_path",
    "DEFAULT_CONFIG_FILE",
]
