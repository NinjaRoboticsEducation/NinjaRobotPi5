"""Unit tests for the VL53L0X sensor driver."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, call, patch

import pytest

from pi5vl53l0x import registers as R
from pi5vl53l0x.core.sensor import VL53L0X


def _make_mock_bus_device() -> MagicMock:
    """Create a mock bus object with standard I2C behavior."""
    bus = MagicMock()
    bus.read_byte_data.return_value = 0x00
    bus.write_byte_data.return_value = None
    bus.read_word_data.return_value = 0
    bus.write_word_data.return_value = None
    bus.read_i2c_block_data.return_value = [0x00] * 6
    bus.write_i2c_block_data.return_value = None
    return bus


def _setup_init_responses(bus: MagicMock) -> None:
    """Configure the mock bus to pass through full initialization."""

    def smart_read(address: int, register: int) -> int:
        del address

        if register == 0xC0:
            return 0xEE
        if register == 0x01:
            return 0x01
        if register == 0x91:
            return 0x28
        if register == 0x84:
            return 0x10
        if register == 0x89:
            return 0x00
        if register == 0x60:
            return 0x00
        if register == 0x83:
            return 0x01
        if register == 0x92:
            return 12
        if register == 0x13:
            return 0x07
        if register == 0x50:
            return 0x06
        if register == 0x70:
            return 0x04

        return 0x00

    def smart_read_word(address: int, register: int) -> int:
        del address, register
        return 0x0100

    bus.read_byte_data.side_effect = smart_read
    bus.read_word_data.side_effect = smart_read_word


@pytest.fixture
def mock_bus() -> MagicMock:
    """Create a mock bus with full init support."""
    bus = _make_mock_bus_device()
    _setup_init_responses(bus)
    return bus


@pytest.fixture
def sensor(mock_bus: MagicMock) -> VL53L0X:
    """Create a VL53L0X instance with successful initialization."""
    return VL53L0X(
        i2c_bus=1,
        i2c_address=0x29,
        bus_factory=MagicMock(return_value=mock_bus),
    )


class TestInit:
    """Tests for VL53L0X initialization."""

    def test_successful_init(self, sensor: VL53L0X) -> None:
        """Sensor should initialize successfully with valid responses."""
        assert sensor._initialized is True

    def test_init_verifies_model_id(self, mock_bus: MagicMock) -> None:
        """Init should check Model ID is 0xEE."""
        original_side_effect = mock_bus.read_byte_data.side_effect

        def wrong_id(address: int, register: int) -> int:
            if register == 0xC0:
                return 0x00
            return original_side_effect(address, register)

        mock_bus.read_byte_data.side_effect = wrong_id

        with pytest.raises(ConnectionError, match="Invalid Model ID"):
            VL53L0X(bus_factory=MagicMock(return_value=mock_bus))

    def test_init_cleanup_on_failure(self) -> None:
        """I2C bus should be closed if init fails."""
        bus = _make_mock_bus_device()

        def always_wrong(address: int, register: int) -> int:
            del address
            if register == 0xC0:
                return 0x00
            return 0x00

        bus.read_byte_data.side_effect = always_wrong

        with pytest.raises(ConnectionError):
            VL53L0X(bus_factory=MagicMock(return_value=bus))

        bus.close.assert_called()

    def test_firmware_boot_timeout(self) -> None:
        """Should raise TimeoutError if firmware doesn't boot."""
        bus = _make_mock_bus_device()

        def no_boot(address: int, register: int) -> int:
            del address
            if register == 0xC0:
                return 0xEE
            if register == 0x01:
                return 0x00
            return 0x00

        bus.read_byte_data.side_effect = no_boot

        with pytest.raises(TimeoutError, match="firmware did not boot"):
            VL53L0X(bus_factory=MagicMock(return_value=bus), firmware_boot_timeout=0.05)


class TestGetRange:
    """Tests for the get_range() method."""

    def test_returns_distance_mm(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """get_range should return distance in mm."""
        original = mock_bus.read_byte_data.side_effect

        def range_read(address: int, register: int) -> int:
            if register == 0x13:
                return 0x07
            return original(address, register)

        mock_bus.read_byte_data.side_effect = range_read
        mock_bus.read_word_data.side_effect = lambda address, register: 0xFA00

        result = sensor.get_range()
        assert result == 250

    def test_raises_runtime_error_if_not_initialized(self, mock_bus: MagicMock) -> None:
        """get_range should raise RuntimeError if not initialized."""
        test_sensor = VL53L0X(bus_factory=MagicMock(return_value=mock_bus))
        test_sensor._initialized = False

        with pytest.raises(RuntimeError, match="not initialized"):
            test_sensor.get_range()

    def test_raises_timeout_on_no_data(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """get_range should raise TimeoutError if measurement never completes."""

        def never_ready(address: int, register: int) -> int:
            del address
            if register == 0x13:
                return 0x00
            return 0x00

        mock_bus.read_byte_data.side_effect = never_ready
        sensor._measurement_timing_budget_us = 1000

        with pytest.raises(TimeoutError, match="did not complete"):
            sensor.get_range()

    def test_applies_offset(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """get_range should subtract offset from raw measurement."""
        original = mock_bus.read_byte_data.side_effect

        def range_read(address: int, register: int) -> int:
            if register == 0x13:
                return 0x07
            return original(address, register)

        mock_bus.read_byte_data.side_effect = range_read
        mock_bus.read_word_data.side_effect = lambda address, register: 0xFA00

        sensor.set_offset(10)
        result = sensor.get_range()
        assert result == 240


class TestGetData:
    """Tests for get_data() and raw-value correctness."""

    def test_raw_value_is_truly_raw(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """get_data() raw_value should be the actual raw sensor value."""
        original = mock_bus.read_byte_data.side_effect

        def range_read(address: int, register: int) -> int:
            if register == 0x13:
                return 0x07
            return original(address, register)

        mock_bus.read_byte_data.side_effect = range_read
        mock_bus.read_word_data.side_effect = lambda address, register: 0xFA00

        sensor.set_offset(10)
        data = sensor.get_data()

        assert data["raw_value"] == 250
        assert data["distance_mm"] == 240
        assert data["is_valid"] is True

    def test_error_returns_safe_defaults(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """get_data() should return safe defaults on error."""
        mock_bus.read_byte_data.side_effect = Exception("bus error")

        data = sensor.get_data()
        assert data["distance_mm"] == -1
        assert data["is_valid"] is False
        assert data["raw_value"] is None
        assert "timestamp" in data

    def test_invalid_range_detection(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """get_data() should detect out-of-range values."""
        original = mock_bus.read_byte_data.side_effect

        def range_read(address: int, register: int) -> int:
            if register == 0x13:
                return 0x07
            return original(address, register)

        mock_bus.read_byte_data.side_effect = range_read
        mock_bus.read_word_data.side_effect = lambda address, register: 0xFE1F

        data = sensor.get_data()
        assert data["is_valid"] is False


class TestHealthAndRecovery:
    """Tests for health_check() and reinitialize()."""

    def test_health_check_ok(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """health_check should return True if model ID matches."""
        original = mock_bus.read_byte_data.side_effect

        def model_read(address: int, register: int) -> int:
            if register == 0xC0:
                return 0xEE
            return original(address, register)

        mock_bus.read_byte_data.side_effect = model_read
        assert sensor.health_check() is True

    def test_health_check_fail(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """health_check should return False on I2C error."""
        mock_bus.read_byte_data.side_effect = Exception("bus error")
        assert sensor.health_check() is False

    def test_reinitialize(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """reinitialize should re-run full init sequence."""
        _setup_init_responses(mock_bus)
        sensor.reinitialize()
        assert sensor._initialized is True


class TestAsync:
    """Tests for async get_range_async()."""

    def test_get_range_async(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """get_range_async should return same result as get_range."""
        original = mock_bus.read_byte_data.side_effect

        def range_read(address: int, register: int) -> int:
            if register == 0x13:
                return 0x07
            return original(address, register)

        mock_bus.read_byte_data.side_effect = range_read
        mock_bus.read_word_data.side_effect = lambda address, register: 0xFA00

        result = asyncio.run(sensor.get_range_async())
        assert result == 250


class TestContextManager:
    """Tests for context manager protocol."""

    def test_context_manager_closes(self, mock_bus: MagicMock) -> None:
        """__exit__ should close I2C connection."""
        with VL53L0X(bus_factory=MagicMock(return_value=mock_bus)) as _sensor:
            pass
        mock_bus.close.assert_called()


class TestUtilities:
    """Tests for get_ranges() and calibrate()."""

    def test_get_ranges_returns_list(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """get_ranges should return a list of ints."""
        original = mock_bus.read_byte_data.side_effect

        def range_read(address: int, register: int) -> int:
            if register == 0x13:
                return 0x07
            return original(address, register)

        mock_bus.read_byte_data.side_effect = range_read
        mock_bus.read_word_data.side_effect = lambda address, register: 0xFA00

        result = sensor.get_ranges(3)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(range_mm == 250 for range_mm in result)

    def test_calibrate(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """calibrate should return offset between measured and target."""
        original = mock_bus.read_byte_data.side_effect

        def range_read(address: int, register: int) -> int:
            if register == 0x13:
                return 0x07
            return original(address, register)

        mock_bus.read_byte_data.side_effect = range_read
        mock_bus.read_word_data.side_effect = lambda address, register: 0xFA00

        offset = sensor.calibrate(target_distance_mm=200, num_samples=3)
        assert offset == 50

    def test_calibrate_rejects_invalid_samples_and_restores_offset(
        self,
        sensor: VL53L0X,
        mock_bus: MagicMock,
    ) -> None:
        """Calibration must not derive or persist an offset from sentinel data."""
        original = mock_bus.read_byte_data.side_effect

        def range_read(address: int, register: int) -> int:
            if register == 0x13:
                return 0x07
            return original(address, register)

        mock_bus.read_byte_data.side_effect = range_read
        mock_bus.read_word_data.side_effect = lambda address, register: 0xFF1F
        sensor.set_offset(12)

        with pytest.raises(ValueError, match="Calibration aborted"):
            sensor.calibrate(target_distance_mm=100, num_samples=3)

        assert sensor.offset_mm == 12

    @pytest.mark.parametrize("num_samples", [0, -1])
    def test_get_ranges_rejects_non_positive_counts(
        self,
        sensor: VL53L0X,
        num_samples: int,
    ) -> None:
        """Multi-read should reject counts that cannot produce samples."""
        with pytest.raises(ValueError, match="num_samples"):
            sensor.get_ranges(num_samples)


class TestTimingBudget:
    """Regression tests for vendor timing-budget calculations."""

    def test_decodes_vcsel_period_register(self) -> None:
        """Encoded VCSEL register values should be converted to PCLKs."""
        sensor = object.__new__(VL53L0X)

        assert sensor._decode_vcsel_period(0x06) == 14
        assert sensor._decode_vcsel_period(0x04) == 10

    def test_budget_includes_all_enabled_sequence_steps(self) -> None:
        """Timing budget should include TCC, DSS, pre-range, and final-range."""
        sensor = object.__new__(VL53L0X)
        sensor.i2c = MagicMock()
        sensor.i2c.read_byte.side_effect = {
            R.SYSTEM_SEQUENCE_CONFIG: 0xDC,
            R.MSRC_CONFIG_TIMEOUT_MACROP: 0x09,
            R.PRE_RANGE_CONFIG_VCSEL_PERIOD: 0x06,
            R.FINAL_RANGE_CONFIG_VCSEL_PERIOD: 0x04,
        }.get
        sensor.i2c.read_word_big_endian.side_effect = {
            R.PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI: 0x0000,
            R.FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI: 0x0001,
        }.get

        msrc_us = sensor._timeout_mclks_to_microseconds(10, 14)
        pre_range_us = sensor._timeout_mclks_to_microseconds(1, 14)
        final_range_us = sensor._timeout_mclks_to_microseconds(1, 10)
        expected_us = (
            1910
            + 960
            + msrc_us
            + 590
            + 2 * (msrc_us + 690)
            + pre_range_us
            + 660
            + final_range_us
            + 550
        )

        assert sensor._get_measurement_timing_budget() == expected_us

    def test_set_budget_reapplies_final_range_timeout(self) -> None:
        """Setting the current budget should preserve its final-range duration."""
        sensor = object.__new__(VL53L0X)
        sensor.i2c = MagicMock()
        sensor.i2c.read_byte.side_effect = {
            R.SYSTEM_SEQUENCE_CONFIG: 0xE8,
            R.MSRC_CONFIG_TIMEOUT_MACROP: 0x09,
            R.PRE_RANGE_CONFIG_VCSEL_PERIOD: 0x06,
            R.FINAL_RANGE_CONFIG_VCSEL_PERIOD: 0x04,
        }.get
        sensor.i2c.read_word_big_endian.side_effect = {
            R.PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI: 0x0000,
            R.FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI: 0x0001,
        }.get
        budget_us = sensor._get_measurement_timing_budget()

        assert sensor._set_measurement_timing_budget(budget_us) is True
        sensor.i2c.write_word_big_endian.assert_called_once_with(
            R.FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI,
            sensor._encode_timeout(2),
        )

    def test_calibration_timeout_retries_and_cleans_up_each_attempt(self) -> None:
        """A failed calibration should retry once and clean up both attempts."""
        sensor = object.__new__(VL53L0X)
        sensor.i2c = MagicMock()
        sensor.i2c.read_byte.return_value = 0x00

        with (
            patch(
                "pi5vl53l0x.core.sensor.time.monotonic",
                side_effect=[0.0, 3.0, 0.0, 3.0],
            ),
            patch("pi5vl53l0x.core.sensor.time.sleep"),
            pytest.raises(TimeoutError, match="reference calibration"),
        ):
            sensor._perform_single_ref_calibration(0x00)

        assert sensor.i2c.write_byte.call_args_list == [
            call(R.SYSRANGE_START, 0x01),
            call(R.SYSTEM_INTERRUPT_CLEAR, 0x01),
            call(R.SYSRANGE_START, 0x00),
            call(R.SYSRANGE_START, 0x01),
            call(R.SYSTEM_INTERRUPT_CLEAR, 0x01),
            call(R.SYSRANGE_START, 0x00),
        ]


class TestBackwardCompat:
    """Tests for backward compatibility."""

    def test_driver_import(self) -> None:
        """pi5vl53l0x.driver should export VL53L0X."""
        from pi5vl53l0x.core.sensor import VL53L0X as CoreVL53L0X
        from pi5vl53l0x.driver import VL53L0X as DriverVL53L0X

        assert DriverVL53L0X is CoreVL53L0X

    def test_package_import(self) -> None:
        """pi5vl53l0x should export VL53L0X."""
        from pi5vl53l0x import VL53L0X as PkgVL53L0X
        from pi5vl53l0x.core.sensor import VL53L0X as CoreVL53L0X

        assert PkgVL53L0X is CoreVL53L0X

    def test_direct_read_write_methods(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """Sensor should expose read_byte/write_byte for compatibility."""
        original = mock_bus.read_byte_data.side_effect

        def compat_read(address: int, register: int) -> int:
            if register == 0xAA:
                return 0x55
            return original(address, register)

        mock_bus.read_byte_data.side_effect = compat_read

        assert sensor.read_byte(0xAA) == 0x55
        sensor.write_byte(0xBB, 0xCC)

    def test_close_method(self, sensor: VL53L0X, mock_bus: MagicMock) -> None:
        """close() should work on sensor instance."""
        sensor.close()
        mock_bus.close.assert_called()
