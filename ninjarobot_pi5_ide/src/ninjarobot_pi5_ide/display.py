"""Serialized ST7789V display capabilities with a hardware-free simulation path."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
from typing import Any, Protocol, cast

from PIL import Image, ImageDraw

from .errors import IDEError
from .models import (
    CapabilityDescriptor,
    ErrorDetails,
    ResourceHealth,
    RetrySafety,
    RiskLevel,
)

MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 96
MAX_TEXT_LENGTH = 500
DEFAULT_FONT_SIZE = 32
DEFAULT_FOREGROUND = "#FFFFFF"
DEFAULT_BACKGROUND = "#000000"
DISPLAY_RESOURCES = ("display", "spi0", "gpio4", "gpio5", "gpio6")


class DisplayDriver(Protocol):
    """Narrow surface consumed from the standalone display library."""

    @property
    def width(self) -> int:
        """Return the rotation-adjusted drawable width."""
        ...

    @property
    def height(self) -> int:
        """Return the rotation-adjusted drawable height."""
        ...

    def display(self, image: Any) -> None:
        """Write one complete RGB frame."""

    def clear(self, color: tuple[int, int, int]) -> None:
        """Fill the display with one RGB color."""

    def set_brightness(self, percent: int) -> None:
        """Set backlight brightness from zero through one hundred percent."""

    def health_check(self) -> bool:
        """Return whether the backend and SPI handle are ready."""

    def close(self) -> None:
        """Turn off the backlight and release SPI/GPIO resources."""


DisplayFactory = Callable[..., DisplayDriver]


def _load_display(**settings: Any) -> DisplayDriver:
    """Import the managed display driver only for explicit real use."""
    module = importlib.import_module("pi5disp")
    display_type = getattr(module, "ST7789V", None)
    if display_type is None:
        raise ImportError("pi5disp.ST7789V is unavailable")
    return cast(DisplayDriver, display_type(**settings))


class DisplayDevice:
    """Share one serialized display instance across all display adapters."""

    def __init__(
        self,
        *,
        spi_bus: int = 0,
        spi_device: int = 0,
        dc_gpio: int = 4,
        reset_gpio: int = 5,
        backlight_gpio: int = 6,
        frequency_hz: int = 32_000_000,
        width: int = 240,
        height: int = 320,
        rotation: int = 90,
        initial_brightness: int = 75,
        driver_factory: DisplayFactory | None = None,
        simulated: bool = False,
    ) -> None:
        if spi_bus != 0 or spi_device != 0:
            raise ValueError("the managed ST7789V integration requires SPI bus 0, device 0")
        if len({dc_gpio, reset_gpio, backlight_gpio}) != 3:
            raise ValueError("display DC, reset, and backlight GPIO pins must be distinct")
        if any(not 0 <= pin <= 27 for pin in (dc_gpio, reset_gpio, backlight_gpio)):
            raise ValueError("display control pins must be valid Raspberry Pi BCM GPIO numbers")
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be greater than zero")
        if width <= 0 or height <= 0:
            raise ValueError("display width and height must be greater than zero")
        if rotation not in (0, 90, 180, 270):
            raise ValueError("rotation must be 0, 90, 180, or 270")
        if not 0 <= initial_brightness <= 100:
            raise ValueError("initial_brightness must be between 0 and 100")

        self._settings = {
            "channel": spi_device,
            "dc_pin": dc_gpio,
            "rst_pin": reset_gpio,
            "backlight_pin": backlight_gpio,
            "speed_hz": frequency_hz,
            "width": width,
            "height": height,
            "rotation": rotation,
        }
        self._rotation = rotation
        self._initial_brightness = initial_brightness
        self._brightness = initial_brightness
        self._driver_factory = driver_factory or _load_display
        self._simulated = simulated
        self._driver: DisplayDriver | None = None
        self._startup_error: str | None = None
        self._lock = asyncio.Lock()
        self._start_attempted = False
        self._closed = False

    @property
    def simulated(self) -> bool:
        """Return whether this device is explicitly hardware-free."""
        return self._simulated

    async def start(self) -> None:
        """Initialize once while retaining an unavailable diagnostic state."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("display device is closed")
            if self._start_attempted:
                return
            self._start_attempted = True
            await self._initialize_locked()

    async def show_text(
        self,
        *,
        text: str,
        font_size: int,
        foreground: str,
        background: str,
    ) -> dict[str, Any]:
        """Render centered multiline text and write one complete frame."""
        async with self._lock:
            driver = await self._require_driver_locked("display.show_text")
            image = Image.new("RGB", (driver.width, driver.height), _rgb(background))
            draw = ImageDraw.Draw(image)
            spacing = max(4, font_size // 5)
            bbox = draw.multiline_textbbox(
                (0, 0),
                text,
                spacing=spacing,
                align="center",
                font_size=font_size,
            )
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            if text_width > driver.width or text_height > driver.height:
                raise _invalid_arguments(
                    "rendered text does not fit the configured display; "
                    "use shorter text, line breaks, or a smaller font_size",
                    capability="display.show_text",
                )
            position = (
                (driver.width - text_width) // 2 - bbox[0],
                (driver.height - text_height) // 2 - bbox[1],
            )
            draw.multiline_text(
                position,
                text,
                fill=_rgb(foreground),
                spacing=spacing,
                align="center",
                font_size=font_size,
            )
            try:
                await asyncio.to_thread(driver.display, image)
            except Exception as exc:
                raise _display_error(
                    code="DISPLAY_WRITE_FAILED",
                    message="The ST7789V display could not write the text frame.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    definitely_not_executed=False,
                    capability="display.show_text",
                ) from exc
            return {
                "text": text,
                "font_size": font_size,
                "foreground": foreground,
                "background": background,
                "width": driver.width,
                "height": driver.height,
                "rotation": self._rotation,
                "brightness": self._brightness,
                "simulated": self._simulated,
            }

    async def clear(self, *, color: str) -> dict[str, Any]:
        """Fill the display with one bounded RGB color."""
        async with self._lock:
            driver = await self._require_driver_locked("display.clear")
            try:
                await asyncio.to_thread(driver.clear, _rgb(color))
            except Exception as exc:
                raise _display_error(
                    code="DISPLAY_CLEAR_FAILED",
                    message="The ST7789V display could not clear the frame.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    definitely_not_executed=False,
                    capability="display.clear",
                ) from exc
            return {
                "cleared": True,
                "color": color,
                "simulated": self._simulated,
            }

    async def set_brightness(self, *, percent: int) -> dict[str, Any]:
        """Set and remember one bounded backlight brightness."""
        async with self._lock:
            driver = await self._require_driver_locked("display.set_brightness")
            try:
                await asyncio.to_thread(driver.set_brightness, percent)
            except Exception as exc:
                raise _display_error(
                    code="DISPLAY_BRIGHTNESS_FAILED",
                    message="The ST7789V backlight brightness could not be changed.",
                    technical_detail=f"{type(exc).__name__}: {exc}",
                    definitely_not_executed=False,
                    capability="display.set_brightness",
                ) from exc
            self._brightness = percent
            return {
                "brightness": percent,
                "simulated": self._simulated,
            }

    async def health(self) -> ResourceHealth:
        """Report SPI/backend readiness without writing another frame."""
        async with self._lock:
            if self._driver is None:
                return ResourceHealth.UNAVAILABLE
            try:
                ready = await asyncio.to_thread(self._driver.health_check)
            except Exception:
                return ResourceHealth.DEGRADED
            return ResourceHealth.READY if ready else ResourceHealth.DEGRADED

    async def close(self) -> None:
        """Turn off the backlight and release the driver idempotently."""
        async with self._lock:
            if self._closed:
                return
            driver = self._driver
            self._driver = None
            self._closed = True
            if driver is not None:
                await asyncio.to_thread(driver.close)

    async def _initialize_locked(self) -> None:
        if self._driver is not None:
            return
        driver: DisplayDriver | None = None
        try:
            driver = await asyncio.to_thread(self._driver_factory, **self._settings)
            await asyncio.to_thread(driver.set_brightness, self._initial_brightness)
            self._brightness = self._initial_brightness
            self._driver = driver
            self._startup_error = None
        except Exception as exc:
            if driver is not None:
                try:
                    await asyncio.to_thread(driver.close)
                except Exception:
                    pass
            self._driver = None
            self._startup_error = f"{type(exc).__name__}: {exc}"

    async def _require_driver_locked(self, capability: str) -> DisplayDriver:
        if not self._start_attempted:
            self._start_attempted = True
            await self._initialize_locked()
        if self._driver is None:
            raise _display_error(
                code="DISPLAY_UNAVAILABLE",
                message="The configured ST7789V display is unavailable.",
                technical_detail=self._startup_error,
                definitely_not_executed=True,
                capability=capability,
            )
        return self._driver


class DisplayShowTextAdapter:
    """Expose bounded, centered text rendering."""

    descriptor = CapabilityDescriptor(
        name="display.show_text",
        version="1.0.0",
        description="Show bounded, centered text on the configured ST7789V display.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_TEXT_LENGTH,
                },
                "font_size": {
                    "type": "integer",
                    "minimum": MIN_FONT_SIZE,
                    "maximum": MAX_FONT_SIZE,
                    "default": DEFAULT_FONT_SIZE,
                },
                "foreground": {
                    "type": "string",
                    "pattern": "^#[0-9A-Fa-f]{6}$",
                    "default": DEFAULT_FOREGROUND,
                },
                "background": {
                    "type": "string",
                    "pattern": "^#[0-9A-Fa-f]{6}$",
                    "default": DEFAULT_BACKGROUND,
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "font_size": {"type": "integer"},
                "foreground": {"type": "string"},
                "background": {"type": "string"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "rotation": {"type": "integer"},
                "brightness": {"type": "integer"},
                "simulated": {"type": "boolean"},
            },
            "required": [
                "text",
                "font_size",
                "foreground",
                "background",
                "width",
                "height",
                "rotation",
                "brightness",
                "simulated",
            ],
            "additionalProperties": False,
        },
        risk=RiskLevel.LOW,
        resources=DISPLAY_RESOURCES,
        default_timeout_seconds=5.0,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, device: DisplayDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        unexpected = sorted(set(arguments) - {"text", "font_size", "foreground", "background"})
        if unexpected:
            raise _invalid_arguments(
                f"Unexpected argument keys: {unexpected}",
                capability="display.show_text",
            )
        text = arguments.get("text")
        font_size = arguments.get("font_size", DEFAULT_FONT_SIZE)
        foreground = arguments.get("foreground", DEFAULT_FOREGROUND)
        background = arguments.get("background", DEFAULT_BACKGROUND)
        if not isinstance(text, str) or not text or len(text) > MAX_TEXT_LENGTH:
            raise _invalid_arguments(
                f"text must contain from 1 through {MAX_TEXT_LENGTH} characters",
                capability="display.show_text",
            )
        if (
            not isinstance(font_size, int)
            or isinstance(font_size, bool)
            or not MIN_FONT_SIZE <= font_size <= MAX_FONT_SIZE
        ):
            raise _invalid_arguments(
                f"font_size must be an integer from {MIN_FONT_SIZE} through {MAX_FONT_SIZE}",
                capability="display.show_text",
            )
        foreground = _normalize_color(foreground, capability="display.show_text")
        background = _normalize_color(background, capability="display.show_text")
        return await self._device.show_text(
            text=text,
            font_size=font_size,
            foreground=foreground,
            background=background,
        )

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


class DisplayClearAdapter:
    """Expose an idempotent solid-color clear operation."""

    descriptor = CapabilityDescriptor(
        name="display.clear",
        version="1.0.0",
        description="Fill the configured ST7789V display with one solid RGB color.",
        input_schema={
            "type": "object",
            "properties": {
                "color": {
                    "type": "string",
                    "pattern": "^#[0-9A-Fa-f]{6}$",
                    "default": DEFAULT_BACKGROUND,
                }
            },
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "cleared": {"type": "boolean"},
                "color": {"type": "string"},
                "simulated": {"type": "boolean"},
            },
            "required": ["cleared", "color", "simulated"],
            "additionalProperties": False,
        },
        risk=RiskLevel.LOW,
        resources=DISPLAY_RESOURCES,
        default_timeout_seconds=5.0,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, device: DisplayDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        unexpected = sorted(set(arguments) - {"color"})
        if unexpected:
            raise _invalid_arguments(
                f"Unexpected argument keys: {unexpected}",
                capability="display.clear",
            )
        color = _normalize_color(
            arguments.get("color", DEFAULT_BACKGROUND),
            capability="display.clear",
        )
        return await self._device.clear(color=color)

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


class DisplayBrightnessAdapter:
    """Expose an idempotent bounded backlight control."""

    descriptor = CapabilityDescriptor(
        name="display.set_brightness",
        version="1.0.0",
        description="Set ST7789V backlight brightness from 0 through 100 percent.",
        input_schema={
            "type": "object",
            "properties": {
                "percent": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                }
            },
            "required": ["percent"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "brightness": {"type": "integer"},
                "simulated": {"type": "boolean"},
            },
            "required": ["brightness", "simulated"],
            "additionalProperties": False,
        },
        risk=RiskLevel.LOW,
        resources=DISPLAY_RESOURCES,
        default_timeout_seconds=5.0,
        idempotent=True,
        cancellable=False,
        confirmation_required=False,
    )

    def __init__(self, device: DisplayDevice) -> None:
        self._device = device

    async def start(self) -> None:
        await self._device.start()

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        unexpected = sorted(set(arguments) - {"percent"})
        if unexpected:
            raise _invalid_arguments(
                f"Unexpected argument keys: {unexpected}",
                capability="display.set_brightness",
            )
        percent = arguments.get("percent")
        if not isinstance(percent, int) or isinstance(percent, bool) or not 0 <= percent <= 100:
            raise _invalid_arguments(
                "percent must be an integer from 0 through 100",
                capability="display.set_brightness",
            )
        return await self._device.set_brightness(percent=percent)

    async def health(self) -> ResourceHealth:
        return await self._device.health()

    async def close(self) -> None:
        await self._device.close()


def _normalize_color(value: Any, *, capability: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 7
        or not value.startswith("#")
        or any(character not in "0123456789abcdefABCDEF" for character in value[1:])
    ):
        raise _invalid_arguments(
            "colors must use #RRGGBB hexadecimal notation, for example #FFFFFF",
            capability=capability,
        )
    return value.upper()


def _rgb(color: str) -> tuple[int, int, int]:
    return (
        int(color[1:3], 16),
        int(color[3:5], 16),
        int(color[5:7], 16),
    )


def _invalid_arguments(detail: str, *, capability: str) -> IDEError:
    return _display_error(
        code="INVALID_CAPABILITY_ARGUMENTS",
        message=f"{capability} received invalid arguments.",
        technical_detail=detail,
        definitely_not_executed=True,
        capability=capability,
    )


def _display_error(
    *,
    code: str,
    message: str,
    technical_detail: str | None,
    definitely_not_executed: bool,
    capability: str,
) -> IDEError:
    return IDEError(
        ErrorDetails(
            code=code,
            message=message,
            technical_detail=technical_detail,
            definitely_not_executed=definitely_not_executed,
            retry_safety=RetrySafety.SAFE,
            capability=capability,
        )
    )
