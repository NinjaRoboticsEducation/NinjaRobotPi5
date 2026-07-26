"""Unit tests for the I2CBus thread-safe wrapper."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from pi5vl53l0x.core.i2c import I2CBus, I2CError


@pytest.fixture
def mock_bus_device() -> MagicMock:
    """Create a mock smbus2 bus object with standard I2C methods."""
    bus = MagicMock()
    bus.read_byte_data.return_value = 0xAB
    bus.write_byte_data.return_value = None
    bus.read_word_data.return_value = 0x1234
    bus.write_word_data.return_value = None
    bus.read_i2c_block_data.return_value = [1, 2, 3, 4, 5, 6]
    bus.write_i2c_block_data.return_value = None
    return bus


@pytest.fixture
def mock_bus_factory(mock_bus_device: MagicMock) -> MagicMock:
    """Create a bus factory that returns the mocked bus."""
    return MagicMock(return_value=mock_bus_device)


@pytest.fixture
def bus(mock_bus_factory: MagicMock) -> I2CBus:
    """Create an I2CBus instance with the mocked SMBus factory."""
    return I2CBus(bus=1, address=0x29, max_retries=3, bus_factory=mock_bus_factory)


class TestI2CBusInit:
    """Tests for I2CBus initialization."""

    def test_opens_bus_on_init(self, mock_bus_factory: MagicMock, bus: I2CBus) -> None:
        """SMBus should be opened during construction."""
        del bus
        mock_bus_factory.assert_called_once_with(1)

    def test_raises_on_failed_open(self) -> None:
        """Should raise I2CError if the bus cannot be opened."""
        factory = MagicMock(side_effect=OSError("device missing"))
        with pytest.raises(I2CError, match="Failed to open I2C"):
            I2CBus(bus_factory=factory)


class TestReadWrite:
    """Tests for basic I2C read and write operations."""

    def test_read_byte(self, bus: I2CBus, mock_bus_device: MagicMock) -> None:
        """read_byte should return the value from smbus2."""
        result = bus.read_byte(0xC0)
        assert result == 0xAB
        mock_bus_device.read_byte_data.assert_called_once_with(0x29, 0xC0)

    def test_write_byte(self, bus: I2CBus, mock_bus_device: MagicMock) -> None:
        """write_byte should pass register and value to smbus2."""
        bus.write_byte(0x00, 0x01)
        mock_bus_device.write_byte_data.assert_called_once_with(0x29, 0x00, 0x01)

    def test_read_block(self, bus: I2CBus, mock_bus_device: MagicMock) -> None:
        """read_block should return a list of byte values."""
        result = bus.read_block(0xB0, 6)
        assert result == [1, 2, 3, 4, 5, 6]
        mock_bus_device.read_i2c_block_data.assert_called_once_with(0x29, 0xB0, 6)

    def test_write_block(self, bus: I2CBus, mock_bus_device: MagicMock) -> None:
        """write_block should pass data list to smbus2."""
        data = [0x01, 0x02, 0x03]
        bus.write_block(0xB0, data)
        mock_bus_device.write_i2c_block_data.assert_called_once_with(
            0x29,
            0xB0,
            [0x01, 0x02, 0x03],
        )


class TestBigEndianSwap:
    """Tests for big-endian word read/write with byte swap."""

    def test_read_word_swaps_bytes(self, bus: I2CBus, mock_bus_device: MagicMock) -> None:
        """read_word_big_endian should swap bytes from LE to BE."""
        mock_bus_device.read_word_data.return_value = 0x1234
        result = bus.read_word_big_endian(0x14)
        assert result == 0x3412

    def test_read_word_identity_on_symmetric(
        self,
        bus: I2CBus,
        mock_bus_device: MagicMock,
    ) -> None:
        """Symmetric values should be unchanged."""
        mock_bus_device.read_word_data.return_value = 0xAAAA
        result = bus.read_word_big_endian(0x14)
        assert result == 0xAAAA

    def test_write_word_swaps_bytes(
        self,
        bus: I2CBus,
        mock_bus_device: MagicMock,
    ) -> None:
        """write_word_big_endian should swap BE value to LE for smbus2."""
        bus.write_word_big_endian(0x44, 0xABCD)
        mock_bus_device.write_word_data.assert_called_once_with(0x29, 0x44, 0xCDAB)

    def test_roundtrip_word(self, bus: I2CBus, mock_bus_device: MagicMock) -> None:
        """Writing then reading the same value should produce identity."""
        bus.write_word_big_endian(0x50, 0x1234)
        written_le = mock_bus_device.write_word_data.call_args[0][2]
        mock_bus_device.read_word_data.return_value = written_le
        result = bus.read_word_big_endian(0x50)
        assert result == 0x1234


class TestRetry:
    """Tests for retry with exponential backoff."""

    def test_retries_on_transient_failure(
        self,
        bus: I2CBus,
        mock_bus_device: MagicMock,
    ) -> None:
        """Should retry and succeed if a later attempt works."""
        mock_bus_device.read_byte_data.side_effect = [
            OSError("glitch"),
            OSError("glitch"),
            0x42,
        ]
        result = bus.read_byte(0xC0)
        assert result == 0x42
        assert mock_bus_device.read_byte_data.call_count == 3

    def test_backoff_timing(self, bus: I2CBus, mock_bus_device: MagicMock) -> None:
        """Verify that retry delays follow the backoff schedule."""
        mock_bus_device.read_byte_data.side_effect = [
            OSError("fail1"),
            OSError("fail2"),
            0xFF,
        ]
        with patch("pi5vl53l0x.core.i2c.time.sleep") as mock_sleep:
            bus.read_byte(0xC0)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(0.010)
            mock_sleep.assert_any_call(0.020)


class TestBusRecovery:
    """Tests for bus recovery after persistent failure."""

    def test_recovery_on_all_retries_exhausted(self) -> None:
        """Should attempt bus recovery after all retries fail."""
        failing_bus = MagicMock()
        recovered_bus = MagicMock()
        failing_bus.read_byte_data.side_effect = [
            OSError("fail"),
            OSError("fail"),
            OSError("fail"),
        ]
        recovered_bus.read_byte_data.return_value = 0x77

        bus_factory = MagicMock(side_effect=[failing_bus, recovered_bus])
        bus = I2CBus(bus=1, address=0x29, max_retries=3, bus_factory=bus_factory)

        result = bus.read_byte(0xC0)
        assert result == 0x77
        failing_bus.close.assert_called_once()
        assert bus_factory.call_count == 2

    def test_raises_if_recovery_also_fails(self) -> None:
        """Should raise I2CError if both retries and recovery fail."""
        failing_bus = MagicMock()
        failing_bus.read_byte_data.side_effect = OSError("permanent failure")
        bus_factory = MagicMock(side_effect=[failing_bus, OSError("adapter dead")])
        bus = I2CBus(bus=1, address=0x29, max_retries=3, bus_factory=bus_factory)

        with pytest.raises(I2CError, match="failed after 3 retries"):
            bus.read_byte(0xC0)


class TestClose:
    """Tests for close behavior."""

    def test_close_releases_bus(self, bus: I2CBus, mock_bus_device: MagicMock) -> None:
        """close() should call the bus close method."""
        bus.close()
        mock_bus_device.close.assert_called_once()
        assert bus.is_closed is True

    def test_double_close_is_safe(self, bus: I2CBus, mock_bus_device: MagicMock) -> None:
        """Calling close() twice should not raise."""
        bus.close()
        bus.close()
        mock_bus_device.close.assert_called_once()

    def test_is_closed_property(self, bus: I2CBus) -> None:
        """is_closed should reflect the close state."""
        assert bus.is_closed is False
        bus.close()
        assert bus.is_closed is True

    def test_read_after_close_raises(self, bus: I2CBus) -> None:
        """Reads after close should raise a clear I2CError."""
        bus.close()
        with pytest.raises(I2CError, match="closed"):
            bus.read_byte(0xC0)


class TestThreadSafety:
    """Tests for concurrent thread safety."""

    def test_concurrent_reads_are_serialized(
        self,
        bus: I2CBus,
        mock_bus_device: MagicMock,
    ) -> None:
        """Multiple threads reading simultaneously should not corrupt data."""
        call_count = 0
        lock = threading.Lock()

        def slow_read(address: int, register: int) -> int:
            nonlocal call_count
            assert address == 0x29
            with lock:
                call_count += 1
            time.sleep(0.001)
            return register

        mock_bus_device.read_byte_data.side_effect = slow_read

        results: dict[int, int] = {}
        errors: list[Exception] = []

        def reader(thread_id: int, register: int) -> None:
            try:
                results[thread_id] = bus.read_byte(register)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=reader, args=(index, index + 0x10)) for index in range(10)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 10
        assert call_count == 10
        for thread_id, value in results.items():
            assert value == thread_id + 0x10

    def test_concurrent_read_write_no_crash(
        self,
        bus: I2CBus,
        mock_bus_device: MagicMock,
    ) -> None:
        """Mix of reads and writes from multiple threads should not crash."""
        del mock_bus_device
        errors: list[Exception] = []

        def writer(value: int) -> None:
            try:
                for _ in range(20):
                    bus.write_byte(0x00, value)
            except Exception as exc:
                errors.append(exc)

        def reader() -> None:
            try:
                for _ in range(20):
                    bus.read_byte(0xC0)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=(1,)),
            threading.Thread(target=writer, args=(2,)),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)

        assert len(errors) == 0, f"Thread errors: {errors}"


class TestEdgeCases:
    """Tests for unusual inputs and edge conditions."""

    def test_read_block_empty_result(
        self,
        bus: I2CBus,
        mock_bus_device: MagicMock,
    ) -> None:
        """Should return empty list if the backend returns no byte sequence."""
        mock_bus_device.read_i2c_block_data.return_value = None
        result = bus.read_block(0xB0, 0)
        assert result == []

    def test_custom_max_retries(self, mock_bus_factory: MagicMock) -> None:
        """Should respect custom max_retries value."""
        bus = I2CBus(
            bus=1,
            address=0x29,
            max_retries=5,
            bus_factory=mock_bus_factory,
        )
        mock_bus_factory.return_value.read_byte_data.side_effect = [
            OSError("e1"),
            OSError("e2"),
            OSError("e3"),
            OSError("e4"),
            0xDD,
        ]
        result = bus.read_byte(0xC0)
        assert result == 0xDD
        assert mock_bus_factory.return_value.read_byte_data.call_count == 5
