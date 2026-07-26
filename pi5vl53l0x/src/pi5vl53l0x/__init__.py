"""pi5vl53l0x — VL53L0X Time-of-Flight distance sensor driver.

This package preserves the main public contract from the legacy
pi0vl53l0x driver while targeting Raspberry Pi 5 standalone use.
"""

try:
    from .core.sensor import VL53L0X
except ImportError:
    VL53L0X = None  # type: ignore[assignment,misc]

__all__ = ["VL53L0X"]
__version__ = "0.1.0"
