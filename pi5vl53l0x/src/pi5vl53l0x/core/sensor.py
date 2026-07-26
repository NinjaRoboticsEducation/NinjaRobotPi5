"""VL53L0X Time-of-Flight distance sensor driver."""

from __future__ import annotations

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass
from typing import Any

from pi5vl53l0x import registers as R
from pi5vl53l0x.core.i2c import I2CBus, I2CError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SequenceStepTimeouts:
    """Decoded sequence-step timeouts used for timing-budget calculations."""

    msrc_dss_tcc_us: int
    pre_range_mclks: int
    pre_range_us: int
    final_range_vcsel_period_pclks: int
    final_range_us: int


class VL53L0X:
    """VL53L0X distance sensor driver.

    This driver preserves the legacy public behavior from `pi0vl53l0x` while
    using a Raspberry Pi 5 compatible kernel-I2C backend.
    """

    _MODEL_ID = 0xEE
    _START_OVERHEAD_US = 1910
    _END_OVERHEAD_US = 960
    _MSRC_OVERHEAD_US = 660
    _TCC_OVERHEAD_US = 590
    _DSS_OVERHEAD_US = 690
    _PRE_RANGE_OVERHEAD_US = 660
    _FINAL_RANGE_OVERHEAD_US = 550
    _CALIBRATION_ATTEMPTS = 2
    _CALIBRATION_RETRY_DELAY_S = 0.05

    def __init__(
        self,
        i2c_bus: int | str = 1,
        i2c_address: int = 0x29,
        debug: bool = False,
        config_file_path: Any = None,
        firmware_boot_timeout: float = 1.0,
        bus_factory: Any = None,
    ) -> None:
        if debug:
            logger.setLevel(logging.DEBUG)

        self._i2c_bus_num = i2c_bus
        self._i2c_address = i2c_address
        self._firmware_boot_timeout = firmware_boot_timeout
        self._initialized = False
        self.offset_mm = 0
        self._stop_variable = 0
        self._measurement_timing_budget_us = 0

        logger.debug(
            "VL53L0X init: bus=%s, address=0x%02X",
            self._i2c_bus_num,
            self._i2c_address,
        )

        try:
            self.i2c = I2CBus(
                bus=i2c_bus,
                address=i2c_address,
                max_retries=3,
                bus_factory=bus_factory,
            )
        except I2CError:
            logger.error("Failed to open I2C bus — sensor unavailable")
            raise

        if config_file_path:
            try:
                from pi5vl53l0x.config.config_manager import load_config

                config = load_config(config_file_path)
                if "offset_mm" in config:
                    self.set_offset(config["offset_mm"])
                    logger.debug(
                        "Loaded offset_mm=%d from %s",
                        self.offset_mm,
                        config_file_path,
                    )
            except Exception as exc:
                logger.warning("Could not load config: %s", exc)

        try:
            self.initialize()
        except Exception:
            logger.error("Initialization failed — closing I2C handle")
            self.i2c.close()
            raise

    def __enter__(self) -> VL53L0X:
        """Context manager entry point."""
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit — closes I2C connection."""
        del exc_type, exc_val, exc_tb
        self.close()

    def initialize(self) -> None:
        """Run the full sensor initialization sequence."""
        self._check_connection()
        self._reset()
        self._wait_for_firmware_boot(self._firmware_boot_timeout)
        self._set_i2c_registers_initial_values()
        self._configure_signal_rate_limit()
        self._setup_spad_info()
        self._configure_interrupt_gpio()
        self._set_timing_budget_and_calibrations()
        self._initialized = True
        logger.info("VL53L0X initialized successfully")

    def _check_connection(self) -> None:
        """Verify sensor is connected by reading Model ID."""
        try:
            model_id = self.i2c.read_byte(R.IDENTIFICATION_MODEL_ID)
        except I2CError as exc:
            raise ConnectionError(f"Failed to connect to VL53L0X: {exc}") from exc

        if model_id != self._MODEL_ID:
            raise ConnectionError(f"Invalid Model ID: 0x{model_id:02X}. Expected 0xEE.")
        logger.debug("Model ID verified: 0xEE")

    def _reset(self) -> None:
        """Perform a software reset of the sensor."""
        logger.debug("Resetting VL53L0X...")
        self.i2c.write_byte(R.SOFT_RESET_GO2_SOFT_RESET_N, 0x00)
        time.sleep(0.01)
        self.i2c.write_byte(R.SOFT_RESET_GO2_SOFT_RESET_N, 0x01)
        time.sleep(0.01)
        logger.debug("VL53L0X reset complete")

    def _wait_for_firmware_boot(self, timeout_s: float = 1.0) -> None:
        """Poll the boot-status register until firmware boot is confirmed."""
        start = time.time()
        while True:
            try:
                status = self.i2c.read_byte(R.FIRMWARE_BOOT_STATUS)
                if status & 0x01:
                    logger.debug("Firmware boot confirmed")
                    return
            except I2CError:
                pass

            if time.time() - start > timeout_s:
                raise TimeoutError(f"VL53L0X firmware did not boot within {timeout_s}s")
            time.sleep(0.005)

    def _set_i2c_registers_initial_values(self) -> None:
        """Set initial I2C register values and read stop_variable."""
        self.i2c.write_byte(R.I2C_STANDARD_MODE, 0x00)

        self.i2c.write_byte(0x80, 0x01)
        self.i2c.write_byte(0xFF, 0x01)
        self.i2c.write_byte(0x00, 0x00)

        self._stop_variable = self.i2c.read_byte(0x91)

        self.i2c.write_byte(0x00, 0x01)
        self.i2c.write_byte(0xFF, 0x00)
        self.i2c.write_byte(0x80, 0x00)

        try:
            current = self.i2c.read_byte(R.VHV_CFG_PAD_SCL_SDA_EXTSUP_HV)
            self.i2c.write_byte(R.VHV_CFG_PAD_SCL_SDA_EXTSUP_HV, current | 0x01)
        except Exception:
            pass

    def _configure_signal_rate_limit(self) -> None:
        """Configure signal rate limits and enable all sequence steps."""
        current = self.i2c.read_byte(R.MSRC_CONFIG_CONTROL)
        self.i2c.write_byte(R.MSRC_CONFIG_CONTROL, current | 0x12)
        self.i2c.write_word_big_endian(
            R.FINAL_RANGE_CFG_MIN_COUNT_RATE_RTN_LIMIT,
            R.SIGNAL_RATE_LIMIT_FIXED,
        )
        self.i2c.write_byte(R.SYSTEM_SEQUENCE_CONFIG, 0xFF)

    def _get_spad_info(self) -> tuple[int, bool]:
        """Get SPAD count and aperture information."""
        max_retries = 5

        for attempt in range(max_retries):
            try:
                self.i2c.write_byte(0x80, 0x01)
                self.i2c.write_byte(0xFF, 0x01)
                self.i2c.write_byte(0x00, 0x00)

                self.i2c.write_byte(0xFF, 0x06)
                current_83 = self.i2c.read_byte(0x83)
                self.i2c.write_byte(0x83, current_83 | 0x04)
                self.i2c.write_byte(0xFF, 0x07)
                self.i2c.write_byte(0x81, 0x01)

                self.i2c.write_byte(0x80, 0x01)
                self.i2c.write_byte(0x94, 0x6B)
                self.i2c.write_byte(0x83, 0x00)

                start = time.time()
                while self.i2c.read_byte(0x83) == 0x00:
                    if time.time() - start > R.TIMEOUT_LIMIT:
                        raise TimeoutError("Timeout waiting for SPAD info")

                self.i2c.write_byte(0x83, 0x01)

                tmp = self.i2c.read_byte(0x92)
                count = tmp & R.SPAD_COUNT_MASK
                is_aperture = (tmp & R.SPAD_APERTURE_BIT) != 0

                self.i2c.write_byte(0x81, 0x00)
                self.i2c.write_byte(0xFF, 0x06)
                current_83 = self.i2c.read_byte(0x83)
                self.i2c.write_byte(0x83, current_83 & ~0x04)
                self.i2c.write_byte(0xFF, 0x01)
                self.i2c.write_byte(0x00, 0x01)

                self.i2c.write_byte(0xFF, 0x00)
                self.i2c.write_byte(0x80, 0x00)

                return count, is_aperture
            except Exception as exc:
                logger.warning(
                    "SPAD info retrieval failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    exc,
                )
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.1)

        raise RuntimeError("SPAD info retrieval failed")  # pragma: no cover

    def _setup_spad_info(self) -> None:
        """Configure SPAD map and default register tuning."""
        spad_count, spad_is_aperture = self._get_spad_info()
        ref_spad_map = self.i2c.read_block(R.GLOBAL_CFG_SPAD_ENABLES_REF_0, 6)

        self.i2c.write_byte(0xFF, 0x01)
        self.i2c.write_byte(R.DYN_SPAD_REF_EN_START_OFFSET, 0x00)
        self.i2c.write_byte(R.DYN_SPAD_NUM_REQUESTED_REF_SPAD, R.SPAD_NUM_REQUESTED_REF)
        self.i2c.write_byte(0xFF, 0x00)
        self.i2c.write_byte(R.GLOBAL_CFG_REF_EN_START_SELECT, 0xB4)

        first_spad = R.SPAD_START_INDEX_APERTURE if spad_is_aperture else 0
        spads_enabled = 0

        for index in range(R.SPAD_TOTAL_COUNT):
            byte_idx = index // R.SPAD_MAP_BITS_PER_BYTE
            bit_idx = index % R.SPAD_MAP_BITS_PER_BYTE
            if index < first_spad or spads_enabled == spad_count:
                ref_spad_map[byte_idx] &= ~(1 << bit_idx)
            elif (ref_spad_map[byte_idx] >> bit_idx) & 0x1:
                spads_enabled += 1

        self.i2c.write_block(R.GLOBAL_CFG_SPAD_ENABLES_REF_0, ref_spad_map)
        self._write_default_tuning()

    def _write_default_tuning(self) -> None:
        """Write the default ST reference-driver tuning sequence."""
        write = self.i2c.write_byte

        write(0xFF, 0x01)
        write(0x00, 0x00)
        write(0xFF, 0x00)
        write(0x09, 0x00)
        write(0x10, 0x00)
        write(0x11, 0x00)
        write(0x24, 0x01)
        write(0x25, 0xFF)
        write(0x75, 0x00)

        write(0xFF, 0x01)
        write(0x4E, R.SPAD_NUM_REQUESTED_REF)
        write(0x48, 0x00)
        write(0x30, 0x20)

        write(0xFF, 0x00)
        write(0x30, 0x09)
        write(0x54, 0x00)
        write(0x31, 0x04)
        write(0x32, 0x03)
        write(0x40, 0x83)
        write(0x46, 0x25)
        write(0x60, 0x00)
        write(0x27, 0x00)
        write(0x50, 0x06)
        write(0x51, 0x00)
        write(0x52, 0x96)
        write(0x56, 0x08)
        write(0x57, 0x30)
        write(0x61, 0x00)
        write(0x62, 0x00)
        write(0x64, 0x00)
        write(0x65, 0x00)
        write(0x66, 0xA0)

        write(0xFF, 0x01)
        write(0x22, 0x32)
        write(0x47, 0x14)
        write(0x49, 0xFF)
        write(0x4A, 0x00)

        write(0xFF, 0x00)
        write(0x7A, 0x0A)
        write(0x7B, 0x00)
        write(0x78, 0x21)

        write(0xFF, 0x01)
        write(0x23, 0x34)
        write(0x42, 0x00)
        write(0x44, 0xFF)
        write(0x45, 0x26)
        write(0x46, 0x05)
        write(0x40, 0x40)
        write(0x0E, 0x06)
        write(0x20, 0x1A)
        write(0x43, 0x40)

        write(0xFF, 0x00)
        write(0x34, 0x03)
        write(0x35, 0x44)

        write(0xFF, 0x01)
        write(0x31, 0x04)
        write(0x4B, 0x09)
        write(0x4C, 0x05)
        write(0x4D, 0x04)

        write(0xFF, 0x00)
        write(0x44, 0x00)
        write(0x45, 0x20)
        write(0x47, 0x08)
        write(0x48, 0x28)
        write(0x67, 0x00)
        write(0x70, 0x04)
        write(0x71, 0x01)
        write(0x72, 0xFE)
        write(0x76, 0x00)
        write(0x77, 0x00)

        write(0xFF, 0x01)
        write(0x0D, 0x01)

        write(0xFF, 0x00)
        write(0x80, 0x01)
        write(0x01, 0xF8)

        write(0xFF, 0x01)
        write(0x8E, 0x01)
        write(0x00, 0x01)
        write(0xFF, 0x00)
        write(0x80, 0x00)

    def _configure_interrupt_gpio(self) -> None:
        """Configure GPIO for measurement-ready interrupts."""
        self.i2c.write_byte(R.SYSTEM_INTERRUPT_CONFIG_GPIO, R.GPIO_INTERRUPT_CONFIG)
        current = self.i2c.read_byte(R.GPIO_HV_MUX_ACTIVE_HIGH)
        self.i2c.write_byte(R.GPIO_HV_MUX_ACTIVE_HIGH, current & ~0x10)
        self.i2c.write_byte(R.SYSTEM_INTERRUPT_CLEAR, 0x01)

    def _set_timing_budget_and_calibrations(self) -> None:
        """Set measurement timing budget and run reference calibrations."""
        self._measurement_timing_budget_us = self._get_measurement_timing_budget()
        logger.debug("Timing budget: %d µs", self._measurement_timing_budget_us)

        self.i2c.write_byte(R.SYSTEM_SEQUENCE_CONFIG, 0xE8)
        self._set_measurement_timing_budget(self._measurement_timing_budget_us)

        try:
            self.i2c.write_byte(R.SYSTEM_SEQUENCE_CONFIG, 0x01)
            self._perform_single_ref_calibration(R.CALIBRATION_VHV_INIT)

            self.i2c.write_byte(R.SYSTEM_SEQUENCE_CONFIG, 0x02)
            self._perform_single_ref_calibration(0x00)
        finally:
            self.i2c.write_byte(R.SYSTEM_SEQUENCE_CONFIG, 0xE8)

    def _calc_macro_period(self, vcsel_period_pclks: int) -> int:
        """Calculate macro period in nanoseconds."""
        return ((2304 * vcsel_period_pclks * 1655) + 500) // 1000

    def _timeout_microseconds_to_mclks(
        self,
        timeout_us: int,
        vcsel_period_pclks: int,
    ) -> int:
        """Convert timeout from microseconds to macro clocks."""
        macro_period_ns = self._calc_macro_period(vcsel_period_pclks)
        return (timeout_us * 1000 + (macro_period_ns // 2)) // macro_period_ns

    def _timeout_mclks_to_microseconds(
        self,
        timeout_mclks: int,
        vcsel_period_pclks: int,
    ) -> int:
        """Convert timeout from macro clocks to microseconds."""
        macro_period_ns = self._calc_macro_period(vcsel_period_pclks)
        return ((timeout_mclks * macro_period_ns) + 500) // 1000

    def _decode_timeout(self, reg_val: int) -> int:
        """Decode timeout register value to macro clocks."""
        ls_byte = reg_val & 0xFF
        ms_byte = (reg_val >> 8) & 0xFF
        return (ls_byte << ms_byte) + 1

    def _decode_vcsel_period(self, reg_val: int) -> int:
        """Decode a VCSEL period register value to PCLKs."""
        return (reg_val + 1) << 1

    def _encode_timeout(self, timeout_mclks: int) -> int:
        """Encode macro clocks to timeout register value."""
        if timeout_mclks <= 0:
            return 0

        ms_byte = 0
        timeout_mclks -= 1
        while (timeout_mclks & 0xFFFFFF00) > 0:
            timeout_mclks >>= 1
            ms_byte += 1
        ls_byte = timeout_mclks & 0xFF
        return (ms_byte << 8) | ls_byte

    def _get_sequence_step_timeouts(self, enables: int) -> _SequenceStepTimeouts:
        """Read and decode all sequence-step timeout registers."""
        pre_range_vcsel_period_pclks = self._decode_vcsel_period(
            self.i2c.read_byte(R.PRE_RANGE_CONFIG_VCSEL_PERIOD)
        )
        msrc_dss_tcc_mclks = self.i2c.read_byte(R.MSRC_CONFIG_TIMEOUT_MACROP) + 1
        msrc_dss_tcc_us = self._timeout_mclks_to_microseconds(
            msrc_dss_tcc_mclks,
            pre_range_vcsel_period_pclks,
        )

        pre_range_mclks = self._decode_timeout(
            self.i2c.read_word_big_endian(R.PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI)
        )
        pre_range_us = self._timeout_mclks_to_microseconds(
            pre_range_mclks,
            pre_range_vcsel_period_pclks,
        )

        final_range_vcsel_period_pclks = self._decode_vcsel_period(
            self.i2c.read_byte(R.FINAL_RANGE_CONFIG_VCSEL_PERIOD)
        )
        final_range_mclks = self._decode_timeout(
            self.i2c.read_word_big_endian(R.FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI)
        )
        if (enables >> 6) & 0x01:
            final_range_mclks -= pre_range_mclks
        final_range_us = self._timeout_mclks_to_microseconds(
            final_range_mclks,
            final_range_vcsel_period_pclks,
        )

        return _SequenceStepTimeouts(
            msrc_dss_tcc_us=msrc_dss_tcc_us,
            pre_range_mclks=pre_range_mclks,
            pre_range_us=pre_range_us,
            final_range_vcsel_period_pclks=final_range_vcsel_period_pclks,
            final_range_us=final_range_us,
        )

    def _get_measurement_timing_budget(self) -> int:
        """Get current measurement timing budget in microseconds."""
        budget_us = self._START_OVERHEAD_US + self._END_OVERHEAD_US
        enables = self.i2c.read_byte(R.SYSTEM_SEQUENCE_CONFIG)
        timeouts = self._get_sequence_step_timeouts(enables)

        if (enables >> 4) & 0x01:
            budget_us += timeouts.msrc_dss_tcc_us + self._TCC_OVERHEAD_US

        if (enables >> 3) & 0x01:
            budget_us += 2 * (timeouts.msrc_dss_tcc_us + self._DSS_OVERHEAD_US)
        elif (enables >> 2) & 0x01:
            budget_us += timeouts.msrc_dss_tcc_us + self._MSRC_OVERHEAD_US

        if (enables >> 6) & 0x01:
            budget_us += timeouts.pre_range_us + self._PRE_RANGE_OVERHEAD_US

        if (enables >> 7) & 0x01:
            budget_us += timeouts.final_range_us + self._FINAL_RANGE_OVERHEAD_US

        return budget_us

    def _set_measurement_timing_budget(self, budget_us: int) -> bool:
        """Set measurement timing budget in microseconds."""
        used_budget_us = self._START_OVERHEAD_US + self._END_OVERHEAD_US
        enables = self.i2c.read_byte(R.SYSTEM_SEQUENCE_CONFIG)
        timeouts = self._get_sequence_step_timeouts(enables)

        if (enables >> 4) & 0x01:
            used_budget_us += timeouts.msrc_dss_tcc_us + self._TCC_OVERHEAD_US

        if (enables >> 3) & 0x01:
            used_budget_us += 2 * (timeouts.msrc_dss_tcc_us + self._DSS_OVERHEAD_US)
        elif (enables >> 2) & 0x01:
            used_budget_us += timeouts.msrc_dss_tcc_us + self._MSRC_OVERHEAD_US

        if (enables >> 6) & 0x01:
            used_budget_us += timeouts.pre_range_us + self._PRE_RANGE_OVERHEAD_US

        if (enables >> 7) & 0x01:
            used_budget_us += self._FINAL_RANGE_OVERHEAD_US
            if used_budget_us > budget_us:
                raise ValueError("Requested timing budget too small")

            final_range_us = budget_us - used_budget_us
            final_range_mclks = self._timeout_microseconds_to_mclks(
                final_range_us,
                timeouts.final_range_vcsel_period_pclks,
            )

            if (enables >> 6) & 0x01:
                final_range_mclks += timeouts.pre_range_mclks

            self.i2c.write_word_big_endian(
                R.FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI,
                self._encode_timeout(final_range_mclks),
            )
            return True

        return False

    def _perform_single_ref_calibration(self, vhv_init_byte: int) -> None:
        """Perform a reference calibration with one bounded recovery attempt."""
        for attempt in range(1, self._CALIBRATION_ATTEMPTS + 1):
            self.i2c.write_byte(R.SYSRANGE_START, 0x01 | vhv_init_byte)
            timed_out = False

            try:
                start = time.monotonic()
                while True:
                    status = self.i2c.read_byte(R.RESULT_INTERRUPT_STATUS)
                    if (status & R.INTERRUPT_STATUS_MASK) != 0x00:
                        return
                    if time.monotonic() - start > R.TIMEOUT_LIMIT:
                        timed_out = True
                        break
            finally:
                self.i2c.write_byte(R.SYSTEM_INTERRUPT_CLEAR, 0x01)
                self.i2c.write_byte(R.SYSRANGE_START, 0x00)

            if timed_out and attempt < self._CALIBRATION_ATTEMPTS:
                logger.warning(
                    "Reference calibration timed out; retrying (%d/%d)",
                    attempt + 1,
                    self._CALIBRATION_ATTEMPTS,
                )
                time.sleep(self._CALIBRATION_RETRY_DELAY_S)

        raise TimeoutError(
            f"Timeout during reference calibration after {self._CALIBRATION_ATTEMPTS} attempts"
        )

    def get_range(self) -> int:
        """Take a single blocking distance measurement."""
        if not self._initialized:
            raise RuntimeError("Sensor not initialized — call initialize()")

        self.i2c.write_byte(0x80, 0x01)
        self.i2c.write_byte(0xFF, 0x01)
        self.i2c.write_byte(0x00, 0x00)
        self.i2c.write_byte(0x91, self._stop_variable)
        self.i2c.write_byte(0x00, 0x01)
        self.i2c.write_byte(0xFF, 0x00)
        self.i2c.write_byte(0x80, 0x00)

        self.i2c.write_byte(R.SYSRANGE_START, 0x01)

        budget_s = self._measurement_timing_budget_us / 1_000_000.0
        timeout_s = max(1.0, budget_s + 0.1)

        start = time.time()
        while True:
            status = self.i2c.read_byte(R.RESULT_INTERRUPT_STATUS)
            if (status & R.INTERRUPT_STATUS_MASK) != 0x00:
                break
            if time.time() - start > timeout_s:
                raise TimeoutError(f"Measurement did not complete within {timeout_s:.1f}s")

        raw_mm = self.i2c.read_word_big_endian(R.RESULT_RANGE_STATUS + 0x0A)
        self.i2c.write_byte(R.SYSTEM_INTERRUPT_CLEAR, 0x01)
        return raw_mm - self.offset_mm

    def get_data(self) -> dict[str, Any]:
        """Get sensor data in standardized dictionary form."""
        try:
            raw_mm = self._get_raw_range()
            distance_mm = raw_mm - self.offset_mm
            return {
                "distance_mm": distance_mm,
                "is_valid": 0 < distance_mm < 8190,
                "raw_value": raw_mm,
                "timestamp": time.time(),
            }
        except Exception as exc:
            logger.error("Failed to get distance: %s", exc)
            return {
                "distance_mm": -1,
                "is_valid": False,
                "raw_value": None,
                "timestamp": time.time(),
            }

    def _get_raw_range(self) -> int:
        """Perform a measurement and return the raw mm value."""
        if not self._initialized:
            raise RuntimeError("Sensor not initialized — call initialize()")

        self.i2c.write_byte(0x80, 0x01)
        self.i2c.write_byte(0xFF, 0x01)
        self.i2c.write_byte(0x00, 0x00)
        self.i2c.write_byte(0x91, self._stop_variable)
        self.i2c.write_byte(0x00, 0x01)
        self.i2c.write_byte(0xFF, 0x00)
        self.i2c.write_byte(0x80, 0x00)

        self.i2c.write_byte(R.SYSRANGE_START, 0x01)

        budget_s = self._measurement_timing_budget_us / 1_000_000.0
        timeout_s = max(1.0, budget_s + 0.1)

        start = time.time()
        while True:
            status = self.i2c.read_byte(R.RESULT_INTERRUPT_STATUS)
            if (status & R.INTERRUPT_STATUS_MASK) != 0x00:
                break
            if time.time() - start > timeout_s:
                raise TimeoutError(f"Measurement did not complete within {timeout_s:.1f}s")

        raw_mm = self.i2c.read_word_big_endian(R.RESULT_RANGE_STATUS + 0x0A)
        self.i2c.write_byte(R.SYSTEM_INTERRUPT_CLEAR, 0x01)
        return raw_mm

    async def get_range_async(self) -> int:
        """Async wrapper for `get_range()`."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_range)

    def set_offset(self, offset_mm: int) -> None:
        """Set measurement offset in mm."""
        self.offset_mm = offset_mm

    def get_ranges(self, num_samples: int) -> list[int]:
        """Take multiple measurements and return them as a list."""
        if num_samples < 1:
            raise ValueError("num_samples must be at least 1")
        return [self.get_range() for _ in range(num_samples)]

    def calibrate(self, target_distance_mm: int, num_samples: int) -> int:
        """Calibrate by measuring against a known target distance."""
        if target_distance_mm < 1:
            raise ValueError("target_distance_mm must be at least 1")
        if num_samples < 1:
            raise ValueError("num_samples must be at least 1")

        logger.debug(
            "Calibrating: target=%dmm, samples=%d",
            target_distance_mm,
            num_samples,
        )

        saved_offset = self.offset_mm
        self.set_offset(0)

        try:
            samples = self.get_ranges(num_samples)
            invalid_samples = [sample for sample in samples if not 0 < sample < 8190]
            if invalid_samples:
                raise ValueError(
                    f"Calibration aborted: {len(invalid_samples)} of "
                    f"{num_samples} samples were invalid"
                )
            measured_distance = int(statistics.mean(samples))
        finally:
            self.set_offset(saved_offset)

        offset = measured_distance - target_distance_mm
        logger.debug(
            "Calibration result: measured=%dmm, offset=%dmm",
            measured_distance,
            offset,
        )
        return offset

    def health_check(self) -> bool:
        """Quick health check — verify sensor responds."""
        try:
            model_id = self.i2c.read_byte(R.IDENTIFICATION_MODEL_ID)
            return model_id == self._MODEL_ID
        except Exception:
            return False

    def reinitialize(self) -> None:
        """Full re-initialization for recovery from a stuck state."""
        logger.info("Reinitializing VL53L0X...")
        self._initialized = False
        self.initialize()

    def close(self) -> None:
        """Close the I2C connection."""
        self.i2c.close()

    def read_byte(self, register: int) -> int:
        """Read a single byte (backward compatibility shim)."""
        return self.i2c.read_byte(register)

    def write_byte(self, register: int, value: int) -> None:
        """Write a single byte (backward compatibility shim)."""
        self.i2c.write_byte(register, value)

    def read_word(self, register: int) -> int:
        """Read a 16-bit word, big-endian (backward compatibility shim)."""
        return self.i2c.read_word_big_endian(register)

    def write_word(self, register: int, value: int) -> None:
        """Write a 16-bit word, big-endian (backward compatibility shim)."""
        self.i2c.write_word_big_endian(register, value)

    def read_block(self, register: int, count: int) -> list[int]:
        """Read a block of bytes (backward compatibility shim)."""
        return self.i2c.read_block(register, count)

    def write_block(self, register: int, data: list[int]) -> None:
        """Write a block of bytes (backward compatibility shim)."""
        self.i2c.write_block(register, data)
