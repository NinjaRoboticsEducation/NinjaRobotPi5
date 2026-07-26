"""Thread-safe I2C bus wrapper with retry and recovery for Raspberry Pi 5.

This module replaces the legacy pigpio transport with kernel I2C access
through smbus2 while preserving the public method contract used by the old
pi0vl53l0x driver.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from smbus2 import SMBus

logger = logging.getLogger(__name__)

BusFactory = Callable[[int | str], Any]


class I2CError(Exception):
    """Raised when I2C communication fails after all retries."""


class I2CBus:
    """Resilient, thread-safe I2C bus wrapper with automatic retry.

    Args:
        bus: I2C bus number or bus path. Defaults to `1`, which maps to
            `/dev/i2c-1` on Raspberry Pi 5.
        address: 7-bit I2C device address (default: 0x29 for VL53L0X).
        max_retries: Maximum number of retry attempts per operation.
        bus_factory: Optional factory used to construct the bus object.
            Defaults to `smbus2.SMBus`. This exists primarily for tests.
    """

    _BACKOFF_DELAYS = (0.010, 0.020, 0.050, 0.100, 0.200)

    def __init__(
        self,
        bus: int | str = 1,
        address: int = 0x29,
        max_retries: int = 3,
        bus_factory: BusFactory | None = None,
    ) -> None:
        self._bus_number = bus
        self._address = address
        self._max_retries = max_retries
        self._bus_factory = bus_factory or SMBus
        self._lock = threading.Lock()
        self._bus_device: Any | None = None
        self._closed = False

        self._bus_device = self._open_bus()
        logger.debug(
            "I2CBus opened: bus=%s, address=0x%02X",
            self._bus_number,
            self._address,
        )

    def _open_bus(self) -> Any:
        """Open a new SMBus object."""
        try:
            return self._bus_factory(self._bus_number)
        except Exception as exc:
            raise I2CError(
                f"Failed to open I2C bus={self._bus_number}, address=0x{self._address:02X}: {exc}"
            ) from exc

    def _close_bus_device(self) -> None:
        """Best-effort close of the current bus object."""
        if self._bus_device is None:
            return
        try:
            self._bus_device.close()
        except Exception as exc:
            logger.warning("Error closing I2C bus device: %s", exc)
        finally:
            self._bus_device = None

    def _recover_bus(self) -> None:
        """Attempt bus recovery by closing and reopening the SMBus object."""
        logger.warning("Attempting I2C bus recovery (close + reopen)...")
        self._close_bus_device()

        try:
            self._bus_device = self._open_bus()
            logger.info("I2C bus recovery successful")
        except I2CError:
            logger.error("I2C bus recovery FAILED")
            raise

    def _ensure_open(self) -> Any:
        """Return the active bus object or raise if already closed."""
        if self._closed or self._bus_device is None:
            raise I2CError("I2C bus is closed")
        return self._bus_device

    def _retry_operation(self, operation_name: str, func: Callable[[], Any]) -> Any:
        """Execute an I2C operation with retry and exponential backoff."""
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                return func()
            except I2CError:
                raise
            except Exception as exc:
                last_error = exc
                delay = self._BACKOFF_DELAYS[min(attempt, len(self._BACKOFF_DELAYS) - 1)]
                logger.debug(
                    "%s failed (attempt %d/%d): %s — retrying in %.0fms",
                    operation_name,
                    attempt + 1,
                    self._max_retries,
                    exc,
                    delay * 1000,
                )
                time.sleep(delay)

        logger.error(
            "%s failed after %d retries, attempting bus recovery",
            operation_name,
            self._max_retries,
        )
        try:
            self._recover_bus()
            return func()
        except Exception as exc:
            raise I2CError(
                f"{operation_name} failed after {self._max_retries} retries "
                f"and bus recovery: {last_error}"
            ) from exc

    def read_byte(self, register: int) -> int:
        """Read a single byte from a register."""
        with self._lock:
            result = self._retry_operation(
                f"read_byte(0x{register:02X})",
                lambda: self._ensure_open().read_byte_data(self._address, register),
            )
            return int(result)

    def write_byte(self, register: int, value: int) -> None:
        """Write a single byte to a register."""
        with self._lock:
            self._retry_operation(
                f"write_byte(0x{register:02X}, 0x{value:02X})",
                lambda: self._ensure_open().write_byte_data(
                    self._address,
                    register,
                    value,
                ),
            )

    def read_word_big_endian(self, register: int) -> int:
        """Read a 16-bit word from a register in big-endian format."""
        with self._lock:
            raw = self._retry_operation(
                f"read_word(0x{register:02X})",
                lambda: self._ensure_open().read_word_data(self._address, register),
            )
            return ((raw & 0xFF) << 8) | (raw >> 8)

    def write_word_big_endian(self, register: int, value: int) -> None:
        """Write a 16-bit word to a register in big-endian format."""
        swapped = ((value & 0xFF) << 8) | (value >> 8)
        with self._lock:
            self._retry_operation(
                f"write_word(0x{register:02X}, 0x{value:04X})",
                lambda: self._ensure_open().write_word_data(
                    self._address,
                    register,
                    swapped,
                ),
            )

    def read_block(self, register: int, count: int) -> list[int]:
        """Read a block of bytes from a register."""
        with self._lock:
            result = self._retry_operation(
                f"read_block(0x{register:02X}, {count})",
                lambda: self._ensure_open().read_i2c_block_data(
                    self._address,
                    register,
                    count,
                ),
            )
            if isinstance(result, (bytes, bytearray, list, tuple)):
                return [int(value) for value in result]
            return []

    def write_block(self, register: int, data: list[int]) -> None:
        """Write a block of bytes to a register."""
        with self._lock:
            self._retry_operation(
                f"write_block(0x{register:02X}, {len(data)} bytes)",
                lambda: self._ensure_open().write_i2c_block_data(
                    self._address,
                    register,
                    data,
                ),
            )

    def close(self) -> None:
        """Close the I2C bus object. Safe to call multiple times."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._close_bus_device()

    @property
    def is_closed(self) -> bool:
        """Whether the I2C bus has been closed."""
        return self._closed
