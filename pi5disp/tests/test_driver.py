"""Unit tests for pi5disp.core.driver module."""

from __future__ import annotations

import threading

import pytest
from PIL import Image

from pi5disp.core.driver import ST7789V


class TestST7789VConstruction:
    """Tests for driver construction."""

    def test_default_construction(self, mock_pigpio) -> None:
        """Driver should initialize with default parameters."""
        lcd = ST7789V(pi=mock_pigpio)
        assert lcd.width == 320
        assert lcd.height == 240
        assert lcd._rotation == 90
        lcd.close()

    def test_custom_dimensions(self, mock_pigpio) -> None:
        """Driver should accept custom width/height with explicit rotation=0."""
        lcd = ST7789V(pi=mock_pigpio, width=240, height=320, rotation=0)
        assert lcd.width == 240
        assert lcd.height == 320
        lcd.close()

    def test_spi_opened(self, mock_pigpio) -> None:
        """SPI handle should be opened during construction."""
        lcd = ST7789V(pi=mock_pigpio)
        mock_pigpio.spi_open.assert_called_once()
        lcd.close()

    def test_gpio_configured(self, mock_pigpio) -> None:
        """GPIO pins should be configured as output."""
        lcd = ST7789V(pi=mock_pigpio, dc_pin=14, rst_pin=15, backlight_pin=16)
        assert mock_pigpio.set_mode.call_count == 3
        lcd.close()


class TestDisplay:
    """Tests for display rendering."""

    def test_display_full_frame(self, mock_pigpio) -> None:
        """First frame should do a full SPI write."""
        lcd = ST7789V(pi=mock_pigpio)
        image = Image.new("RGB", (240, 320), (255, 0, 0))
        lcd.display(image)
        assert mock_pigpio.spi_write.call_count > 0
        lcd.close()

    def test_display_identical_frames_always_writes(self, mock_pigpio) -> None:
        """Every frame should be written."""
        lcd = ST7789V(pi=mock_pigpio)
        image = Image.new("RGB", (320, 240), (255, 0, 0))

        lcd.display(image)
        mock_pigpio.spi_write.reset_mock()

        lcd.display(image)
        baseline_count = mock_pigpio.spi_write.call_count
        assert baseline_count > 0

        mock_pigpio.spi_write.reset_mock()

        lcd.display(image)
        assert mock_pigpio.spi_write.call_count == baseline_count
        lcd.close()

    def test_display_different_frames_full(self, mock_pigpio) -> None:
        """Different consecutive frames should also write full frame."""
        lcd = ST7789V(pi=mock_pigpio)
        img1 = Image.new("RGB", (320, 240), (255, 0, 0))
        lcd.display(img1)
        mock_pigpio.spi_write.reset_mock()

        lcd.display(img1)
        baseline_count = mock_pigpio.spi_write.call_count
        mock_pigpio.spi_write.reset_mock()

        img2 = img1.copy()
        img2.putpixel((120, 120), (0, 255, 0))
        lcd.display(img2)

        assert mock_pigpio.spi_write.call_count == baseline_count
        lcd.close()

    def test_display_resizes_image(self, mock_pigpio) -> None:
        """Images that don't match display size should be resized."""
        lcd = ST7789V(pi=mock_pigpio, width=240, height=320)
        image = Image.new("RGB", (100, 100), (0, 0, 255))
        lcd.display(image)
        assert mock_pigpio.spi_write.call_count > 0
        lcd.close()

    def test_clear(self, mock_pigpio) -> None:
        """Clear should fill display with given color."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.clear((0, 0, 0))
        assert mock_pigpio.spi_write.call_count > 0
        lcd.close()


class TestBrightness:
    """Tests for PWM brightness control."""

    def test_set_brightness_100(self, mock_pigpio) -> None:
        """100% brightness should set PWM duty cycle to 255."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.set_brightness(100)
        mock_pigpio.set_PWM_dutycycle.assert_called_with(16, 255)
        lcd.close()

    def test_set_brightness_0(self, mock_pigpio) -> None:
        """0% brightness should set PWM duty cycle to 0."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.set_brightness(0)
        mock_pigpio.set_PWM_dutycycle.assert_called_with(16, 0)
        lcd.close()

    def test_set_brightness_50(self, mock_pigpio) -> None:
        """50% brightness should set PWM duty cycle to ~127."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.set_brightness(50)
        mock_pigpio.set_PWM_dutycycle.assert_called_with(16, 127)
        lcd.close()

    def test_brightness_clamped(self, mock_pigpio) -> None:
        """Brightness values outside 0-100 should be clamped."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.set_brightness(150)
        mock_pigpio.set_PWM_dutycycle.assert_called_with(16, 255)
        lcd.set_brightness(-10)
        mock_pigpio.set_PWM_dutycycle.assert_called_with(16, 0)
        lcd.close()


class TestRotation:
    """Tests for display rotation."""

    def test_rotation_0(self, mock_pigpio) -> None:
        """Rotation 0 should keep native dimensions."""
        lcd = ST7789V(pi=mock_pigpio, width=240, height=320)
        lcd.set_rotation(0)
        assert lcd.width == 240
        assert lcd.height == 320
        lcd.close()

    def test_rotation_90(self, mock_pigpio) -> None:
        """Rotation 90 should swap width and height."""
        lcd = ST7789V(pi=mock_pigpio, width=240, height=320)
        lcd.set_rotation(90)
        assert lcd.width == 320
        assert lcd.height == 240
        lcd.close()

    def test_rotation_invalid(self, mock_pigpio) -> None:
        """Invalid rotation should raise ValueError."""
        lcd = ST7789V(pi=mock_pigpio)
        with pytest.raises(ValueError, match="Rotation must be"):
            lcd.set_rotation(45)
        lcd.close()

    def test_rotation_changes_dimensions(self, mock_pigpio) -> None:
        """Rotation change should swap width and height."""
        lcd = ST7789V(pi=mock_pigpio, rotation=0)
        assert lcd.width == 240
        assert lcd.height == 320

        lcd.set_rotation(90)
        assert lcd.width == 320
        assert lcd.height == 240
        lcd.close()


class TestExecute:
    """Tests for Actuator execute()."""

    def test_execute_image(self, mock_pigpio) -> None:
        """execute({'image': img}) should call display()."""
        lcd = ST7789V(pi=mock_pigpio)
        img = Image.new("RGB", (240, 320), (255, 0, 0))
        lcd.execute({"image": img})
        assert mock_pigpio.spi_write.call_count > 0
        lcd.close()

    def test_execute_clear(self, mock_pigpio) -> None:
        """execute({'clear': True}) should clear the display."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.execute({"clear": True})
        assert mock_pigpio.spi_write.call_count > 0
        lcd.close()

    def test_execute_brightness(self, mock_pigpio) -> None:
        """execute({'brightness': 50}) should set PWM brightness."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.execute({"brightness": 50})
        mock_pigpio.set_PWM_dutycycle.assert_called_with(16, 127)
        lcd.close()

    def test_execute_backlight(self, mock_pigpio) -> None:
        """execute({'backlight': False}) should turn off the backlight."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.execute({"backlight": False})
        mock_pigpio.write.assert_called_with(16, 0)
        lcd.close()


class TestPowerManagement:
    """Tests for sleep, wake, close, and health."""

    def test_close_releases_spi(self, mock_pigpio) -> None:
        """close() should release SPI handle."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.close()
        mock_pigpio.spi_close.assert_called_once()

    def test_health_check_valid(self, mock_pigpio) -> None:
        """health_check should return True for valid driver."""
        lcd = ST7789V(pi=mock_pigpio)
        assert lcd.health_check() is True
        lcd.close()

    def test_health_check_after_close(self, mock_pigpio) -> None:
        """health_check should return False after close."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.close()
        assert lcd.health_check() is False

    def test_off(self, mock_pigpio) -> None:
        """off() should send DISPOFF command."""
        lcd = ST7789V(pi=mock_pigpio)
        lcd.off()
        assert mock_pigpio.spi_write.call_count > 0
        lcd.close()


class TestThreadSafety:
    """Tests for thread-safety of SPI operations."""

    def test_concurrent_display(self, mock_pigpio) -> None:
        """Concurrent display calls should not raise exceptions."""
        lcd = ST7789V(pi=mock_pigpio)
        img1 = Image.new("RGB", (240, 320), (255, 0, 0))
        img2 = Image.new("RGB", (240, 320), (0, 0, 255))
        errors: list[Exception] = []

        def t1() -> None:
            try:
                for _ in range(10):
                    lcd.display(img1)
            except Exception as exc:
                errors.append(exc)

        def t2() -> None:
            try:
                for _ in range(10):
                    lcd.display(img2)
            except Exception as exc:
                errors.append(exc)

        thread1 = threading.Thread(target=t1)
        thread2 = threading.Thread(target=t2)
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        lcd.close()

    def test_concurrent_display_and_brightness(self, mock_pigpio) -> None:
        """Concurrent display + brightness changes should not raise."""
        lcd = ST7789V(pi=mock_pigpio)
        img = Image.new("RGB", (240, 320), (0, 255, 0))
        errors: list[Exception] = []

        def display_loop() -> None:
            try:
                for _ in range(10):
                    lcd.display(img)
            except Exception as exc:
                errors.append(exc)

        def brightness_loop() -> None:
            try:
                for index in range(10):
                    lcd.set_brightness(index * 10)
            except Exception as exc:
                errors.append(exc)

        thread_a = threading.Thread(target=display_loop)
        thread_b = threading.Thread(target=brightness_loop)
        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

        assert len(errors) == 0
        lcd.close()


class TestContextManager:
    """Tests for context manager support."""

    def test_context_manager(self, mock_pigpio) -> None:
        """Should support `with` statements."""
        with ST7789V(pi=mock_pigpio) as lcd:
            img = Image.new("RGB", (240, 320), (255, 0, 0))
            lcd.display(img)
        mock_pigpio.spi_close.assert_called()
