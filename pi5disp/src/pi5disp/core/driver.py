"""ST7789V display driver for Raspberry Pi 5."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional, Tuple, Union

import numpy as np
from PIL import Image

from .renderer import ColorConverter, RegionOptimizer

log = logging.getLogger(__name__)

try:
    from ninja_utils import Actuator
except ImportError:
    from abc import ABC, abstractmethod

    class Actuator(ABC):
        @abstractmethod
        def initialize(self) -> None: ...

        @abstractmethod
        def execute(self, command: dict[str, Any]) -> None: ...

        @abstractmethod
        def off(self) -> None: ...


CMD_SWRESET = 0x01
CMD_SLPIN = 0x10
CMD_SLPOUT = 0x11
CMD_NORON = 0x13
CMD_INVON = 0x21
CMD_DISPOFF = 0x28
CMD_DISPON = 0x29
CMD_CASET = 0x2A
CMD_RASET = 0x2B
CMD_RAMWR = 0x2C
CMD_MADCTL = 0x36
CMD_COLMOD = 0x3A

MADCTL_MAP = {
    0: 0x00,
    90: 0x60,
    180: 0xC0,
    270: 0xA0,
}

SPI_CHUNK_SIZE = 4096


class Pi5GPIOBackendAdapter:
    """Pigpio-like adapter built on top of spidev and RPi.GPIO."""

    OUTPUT = 1

    def __init__(self, gpio_module: Any = None, spi_module: Any = None) -> None:
        if gpio_module is None:
            import RPi.GPIO as gpio_module  # type: ignore[import-not-found]

        if spi_module is None:
            import spidev as spi_module  # type: ignore[import-not-found]

        self._gpio = gpio_module
        self._spi_module = spi_module
        self._spi_devices: dict[int, Any] = {}
        self._pwms: dict[int, Any] = {}
        self._configured_pins: set[int] = set()
        self._next_spi_handle = 0
        self.connected = True

        if hasattr(self._gpio, "setwarnings"):
            self._gpio.setwarnings(False)
        if hasattr(self._gpio, "setmode") and hasattr(self._gpio, "BCM"):
            self._gpio.setmode(self._gpio.BCM)

    def set_mode(self, pin: int, mode: int) -> None:
        """Configure a GPIO pin as output."""
        del mode
        out_mode = getattr(self._gpio, "OUT", 1)
        self._gpio.setup(pin, out_mode)
        self._configured_pins.add(pin)

    def write(self, pin: int, value: int) -> None:
        """Write a digital value to a GPIO pin."""
        self._gpio.output(pin, value)

    def spi_open(self, channel: int, speed_hz: int, flags: int) -> int:
        """Open an SPI device and return a pigpio-like handle."""
        del flags
        spi = self._spi_module.SpiDev()
        spi.open(0, channel)
        spi.max_speed_hz = speed_hz
        spi.mode = 0
        handle = self._next_spi_handle
        self._next_spi_handle += 1
        self._spi_devices[handle] = spi
        return handle

    def spi_write(self, handle: int, data: Union[bytes, list[int]]) -> tuple[int, bytes]:
        """Write data to an open SPI handle."""
        spi = self._spi_devices[handle]
        payload = data if isinstance(data, bytes) else bytes(data)
        if hasattr(spi, "writebytes2"):
            spi.writebytes2(payload)
        elif hasattr(spi, "xfer3"):
            spi.xfer3(list(payload))
        elif hasattr(spi, "xfer2"):
            spi.xfer2(list(payload))
        else:
            spi.writebytes(list(payload))
        return len(payload), b""

    def spi_close(self, handle: int) -> None:
        """Close an SPI device handle."""
        spi = self._spi_devices.pop(handle, None)
        if spi is not None:
            spi.close()

    def set_PWM_dutycycle(self, pin: int, duty_cycle: int) -> None:
        """Set PWM duty cycle on a pin using a 0-255 pigpio-like scale."""
        duty_cycle = max(0, min(255, duty_cycle))
        percent = duty_cycle * 100.0 / 255.0
        pwm = self._pwms.get(pin)
        if pwm is None:
            pwm = self._gpio.PWM(pin, 1000)
            pwm.start(percent)
            self._pwms[pin] = pwm
        else:
            pwm.ChangeDutyCycle(percent)

    def stop(self) -> None:
        """Release PWM, SPI, and GPIO resources."""
        for pwm in self._pwms.values():
            try:
                pwm.stop()
            except Exception:
                pass
        self._pwms.clear()

        for handle in list(self._spi_devices):
            try:
                self.spi_close(handle)
            except Exception:
                pass

        if self._configured_pins:
            try:
                self._gpio.cleanup(sorted(self._configured_pins))
            except Exception:
                pass
            self._configured_pins.clear()

        self.connected = False


class ST7789V(Actuator):
    """Thread-safe ST7789V display driver with reliable full-frame rendering."""

    def __init__(
        self,
        pi=None,
        channel: int = 0,
        dc_pin: int = 14,
        rst_pin: int = 15,
        backlight_pin: int = 16,
        speed_hz: int = 32_000_000,
        width: int = 240,
        height: int = 320,
        rotation: int = 90,
    ) -> None:
        self._native_width = width
        self._native_height = height
        self._width = width
        self._height = height
        self._rotation = rotation

        self._spi_lock = threading.Lock()
        self._previous_image: Optional[Image.Image] = None
        self._color_converter = ColorConverter()
        self._region_optimizer = RegionOptimizer()

        self._is_external_pi = pi is not None
        self.pi = pi if self._is_external_pi else Pi5GPIOBackendAdapter()
        if not getattr(self.pi, "connected", True):
            raise RuntimeError("Could not initialize Raspberry Pi 5 display backend.")

        self.rst_pin = rst_pin
        self.dc_pin = dc_pin
        self.backlight_pin = backlight_pin

        for pin in [self.rst_pin, self.dc_pin, self.backlight_pin]:
            self.pi.set_mode(pin, getattr(self.pi, "OUTPUT", 1))

        self.spi_handle = self.pi.spi_open(channel, speed_hz, 0)
        if isinstance(self.spi_handle, int) and self.spi_handle < 0:
            raise RuntimeError(f"Failed to open SPI bus: handle={self.spi_handle}")

        self._init_display()
        self.set_rotation(self._rotation)
        log.info(
            "ST7789V initialized: %dx%d, rotation=%d",
            self._width,
            self._height,
            self._rotation,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        del exc_type, exc_val, exc_tb
        self.close()

    @property
    def width(self) -> int:
        """Current display width."""
        return self._width

    @property
    def height(self) -> int:
        """Current display height."""
        return self._height

    def _write_command(self, command: int) -> None:
        """Send a command byte to the display. Must hold _spi_lock."""
        self.pi.write(self.dc_pin, 0)
        self.pi.spi_write(self.spi_handle, [command])

    def _write_data(self, data: Union[int, bytes, list[int]]) -> None:
        """Send data byte(s) to the display. Must hold _spi_lock."""
        self.pi.write(self.dc_pin, 1)
        if isinstance(data, int):
            self.pi.spi_write(self.spi_handle, [data])
        else:
            self.pi.spi_write(self.spi_handle, data)

    def _write_pixels(self, pixel_bytes: bytes) -> None:
        """Write raw pixel data in chunks. Must hold _spi_lock."""
        self.pi.write(self.dc_pin, 1)
        data_len = len(pixel_bytes)
        if data_len <= SPI_CHUNK_SIZE:
            self.pi.spi_write(self.spi_handle, pixel_bytes)
            return

        for index in range(0, data_len, SPI_CHUNK_SIZE):
            self.pi.spi_write(self.spi_handle, pixel_bytes[index : index + SPI_CHUNK_SIZE])

    def _init_display(self) -> None:
        """Perform the hardware initialization sequence for ST7789V."""
        with self._spi_lock:
            self.pi.write(self.rst_pin, 1)
            time.sleep(0.01)
            self.pi.write(self.rst_pin, 0)
            time.sleep(0.01)
            self.pi.write(self.rst_pin, 1)
            time.sleep(0.150)

            self._write_command(CMD_SWRESET)
            time.sleep(0.150)
            self._write_command(CMD_SLPOUT)
            time.sleep(0.5)
            self._write_command(CMD_COLMOD)
            self._write_data(0x55)
            self._write_command(CMD_INVON)
            self._write_command(CMD_NORON)
            self._write_command(CMD_DISPON)
            time.sleep(0.1)

            self.pi.write(self.backlight_pin, 1)

    def _set_window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Set the active drawing window. Must hold _spi_lock."""
        self._write_command(CMD_CASET)
        self._write_data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self._write_command(CMD_RASET)
        self._write_data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
        self._write_command(CMD_RAMWR)

    def display(self, image: Image.Image) -> None:
        """Display an image on the screen using full-frame rendering."""
        if image.mode != "RGB":
            image = image.convert("RGB")

        if image.size != (self._width, self._height):
            image = image.resize((self._width, self._height))

        with self._spi_lock:
            self._write_full_frame(image)

    def _write_full_frame(self, image: Image.Image) -> None:
        """Write entire frame to the display. Must hold _spi_lock."""
        pixel_bytes = self._color_converter.rgb_to_rgb565_bytes(np.array(image))
        self._set_window(0, 0, self._width - 1, self._height - 1)
        self._write_pixels(pixel_bytes)

    def _write_partial_frame(
        self,
        region: Image.Image,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
    ) -> None:
        """Write a partial frame to the display. Must hold _spi_lock."""
        pixel_bytes = self._color_converter.rgb_to_rgb565_bytes(np.array(region))
        self._set_window(x0, y0, x1, y1)
        self._write_pixels(pixel_bytes)

    def display_region(
        self,
        image: Image.Image,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
    ) -> None:
        """Display a portion of an image in the specified region."""
        clamped = self._region_optimizer.clamp_region((x0, y0, x1, y1), self._width, self._height)
        if clamped[2] <= clamped[0] or clamped[3] <= clamped[1]:
            return

        region_img = image.crop(clamped)
        pixel_bytes = self._color_converter.rgb_to_rgb565_bytes(np.array(region_img))

        with self._spi_lock:
            self._set_window(clamped[0], clamped[1], clamped[2] - 1, clamped[3] - 1)
            self._write_pixels(pixel_bytes)

    def clear(self, color: Tuple[int, int, int] = (0, 0, 0)) -> None:
        """Fill the display with a solid color."""
        image = Image.new("RGB", (self._width, self._height), color)
        self.display(image)

    def set_brightness(self, percent: int) -> None:
        """Set backlight brightness using pigpio-like 0-255 PWM scaling."""
        percent = max(0, min(100, percent))
        duty_cycle = int(percent * 255 / 100)
        self.pi.set_PWM_dutycycle(self.backlight_pin, duty_cycle)

    def set_rotation(self, rotation: int) -> None:
        """Set display rotation."""
        if rotation not in MADCTL_MAP:
            raise ValueError("Rotation must be 0, 90, 180, or 270.")

        with self._spi_lock:
            self._write_command(CMD_MADCTL)
            self._write_data(MADCTL_MAP[rotation])

        if rotation in (90, 270):
            self._width = self._native_height
            self._height = self._native_width
        else:
            self._width = self._native_width
            self._height = self._native_height

        self._rotation = rotation
        log.debug("Rotation set to %d (display: %dx%d)", rotation, self._width, self._height)

    def sleep(self) -> None:
        """Put the display into low-power sleep mode."""
        with self._spi_lock:
            self._write_command(CMD_SLPIN)
        self.pi.write(self.backlight_pin, 0)

    def wake(self) -> None:
        """Wake the display from sleep mode."""
        with self._spi_lock:
            self._write_command(CMD_SLPOUT)
            time.sleep(0.5)
        self.pi.write(self.backlight_pin, 1)

    def close(self) -> None:
        """Release all resources."""
        log.info("Closing ST7789V display driver.")
        with self._spi_lock:
            try:
                self.pi.write(self.backlight_pin, 0)
                if hasattr(self, "spi_handle") and self.spi_handle >= 0:
                    self.pi.spi_close(self.spi_handle)
                    self.spi_handle = -1
            finally:
                if not self._is_external_pi and getattr(self.pi, "connected", False):
                    self.pi.stop()

    def health_check(self) -> bool:
        """Return True if the backend is connected and the SPI handle is open."""
        if self.pi is None:
            return False
        if not getattr(self.pi, "connected", False):
            return False
        if not hasattr(self, "spi_handle") or self.spi_handle < 0:
            return False
        return True

    def initialize(self) -> None:
        """Wake the display and set full brightness."""
        self.wake()
        self.set_brightness(100)

    def execute(self, command: dict[str, Any]) -> None:
        """Execute a display command dict."""
        if "image" in command:
            self.display(command["image"])
        elif command.get("clear"):
            self.clear()
        elif "brightness" in command:
            self.set_brightness(command["brightness"])
        elif "backlight" in command:
            self.pi.write(self.backlight_pin, 1 if command["backlight"] else 0)

    def off(self) -> None:
        """Turn off display output and backlight."""
        with self._spi_lock:
            self._write_command(CMD_DISPOFF)
        self.pi.write(self.backlight_pin, 0)
