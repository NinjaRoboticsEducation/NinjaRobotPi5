"""Strict V4-owned configuration; managed-driver files are never rewritten."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

EnvironmentVariable = Annotated[
    str,
    StringConstraints(min_length=2, max_length=128, pattern=r"^[A-Z][A-Z0-9_]+$"),
]
NonEmptyText = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class ConfigModel(BaseModel):
    """Base for strict configuration sections."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BuzzerConfig(ConfigModel):
    """Passive-buzzer wiring owned by V4."""

    enabled: bool = True
    gpio: Annotated[int, Field(ge=0, le=27)] = 27


class ServoConfig(ConfigModel):
    """Native hardware-PWM servo endpoints selected by the boot overlay."""

    enabled: bool = True
    endpoints: tuple[str, ...] = ("gpio12", "gpio13")

    @field_validator("endpoints", mode="before")
    @classmethod
    def normalize_toml_array(cls, endpoints: object) -> object:
        """Convert TOML arrays explicitly instead of relying on loose coercion."""
        if isinstance(endpoints, list):
            return tuple(endpoints)
        return endpoints

    @field_validator("endpoints")
    @classmethod
    def endpoints_must_be_unique_and_explicit(cls, endpoints: tuple[str, ...]) -> tuple[str, ...]:
        """Require unambiguous native-GPIO endpoint names."""
        if not endpoints:
            raise ValueError("at least one servo endpoint is required when servos are enabled")
        if len(endpoints) != len(set(endpoints)):
            raise ValueError("servo endpoints must not contain duplicates")
        invalid = [item for item in endpoints if item not in {"gpio12", "gpio13"}]
        if invalid:
            raise ValueError("Phase 1 native servo endpoints must be gpio12 and/or gpio13")
        return endpoints


class DisplayConfig(ConfigModel):
    """ST7789V wiring and presentation settings owned by V4."""

    enabled: bool = True
    model: Literal["ST7789V"] = "ST7789V"
    width: Literal[240] = 240
    height: Literal[320] = 320
    spi_bus: Literal[0] = 0
    spi_device: Literal[0] = 0
    frequency_hz: Annotated[int, Field(ge=1_000_000, le=80_000_000)] = 32_000_000
    dc_gpio: Annotated[int, Field(ge=0, le=27)] = 4
    reset_gpio: Annotated[int, Field(ge=0, le=27)] = 5
    backlight_gpio: Annotated[int, Field(ge=0, le=27)] = 6
    rotation: Literal[0, 90, 180, 270] = 90
    brightness: Annotated[int, Field(ge=0, le=100)] = 75

    @model_validator(mode="after")
    def control_pins_must_be_distinct(self) -> DisplayConfig:
        """Reject a display configuration that shorts logical controls together."""
        pins = (self.dc_gpio, self.reset_gpio, self.backlight_gpio)
        if len(pins) != len(set(pins)):
            raise ValueError("display DC, reset, and backlight GPIO pins must be distinct")
        return self


class I2CConfig(ConfigModel):
    """Shared I2C bus and distinct device addresses."""

    bus: Literal[1] = 1
    dfr0566_address: Annotated[int, Field(ge=0x08, le=0x77)] = 0x10
    vl53l0x_address: Annotated[int, Field(ge=0x08, le=0x77)] = 0x29

    @model_validator(mode="after")
    def device_addresses_must_be_distinct(self) -> I2CConfig:
        """Prevent two configured devices from claiming one address."""
        if self.dfr0566_address == self.vl53l0x_address:
            raise ValueError("DFR0566 and VL53L0X I2C addresses must be distinct")
        return self


class CameraConfig(ConfigModel):
    """Initial CSI camera capture profile."""

    enabled: bool = True
    width: Annotated[int, Field(ge=1, le=7680)] = 1280
    height: Annotated[int, Field(ge=1, le=4320)] = 720
    retain_media_by_default: Literal[False] = False


class MicrophoneConfig(ConfigModel):
    """Initial privacy-safe USB microphone profile."""

    enabled: bool = True
    sample_rate_hz: Annotated[int, Field(ge=8_000, le=192_000)] = 16_000
    channels: Literal[1] = 1
    retain_audio_by_default: Literal[False] = False


class HardwareConfig(ConfigModel):
    """Authoritative V4 hardware mapping."""

    buzzer: BuzzerConfig = Field(default_factory=BuzzerConfig)
    servos: ServoConfig = Field(default_factory=ServoConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    i2c: I2CConfig = Field(default_factory=I2CConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    microphone: MicrophoneConfig = Field(default_factory=MicrophoneConfig)

    @model_validator(mode="after")
    def top_level_gpio_assignments_must_not_conflict(self) -> HardwareConfig:
        """Keep independently controlled GPIO assignments from overlapping."""
        display_pins = {
            self.display.dc_gpio,
            self.display.reset_gpio,
            self.display.backlight_gpio,
        }
        if self.buzzer.enabled and self.display.enabled and self.buzzer.gpio in display_pins:
            raise ValueError("buzzer GPIO must not overlap a display control GPIO")
        return self


class AgentConfig(ConfigModel):
    """Safe Phase 1 bounds for the future agent loop."""

    default_provider: NonEmptyText = "ollama"
    max_model_turns: Annotated[int, Field(ge=1, le=20)] = 6
    max_tool_calls: Annotated[int, Field(ge=0, le=50)] = 8
    turn_timeout_seconds: Annotated[float, Field(gt=0, le=600)] = 90.0


class ProviderConfig(ConfigModel):
    """Provider reference containing names and secret references, never secrets."""

    kind: Literal["ollama", "openai", "gemini", "anthropic"]
    model: NonEmptyText
    enabled: bool = False
    base_url: Annotated[str, StringConstraints(min_length=8, max_length=500)] | None = None
    api_key_env: EnvironmentVariable | None = None

    @model_validator(mode="after")
    def enabled_cloud_provider_requires_secret_reference(self) -> ProviderConfig:
        """Require an environment-variable reference for enabled cloud providers."""
        if self.enabled and self.kind != "ollama" and self.api_key_env is None:
            raise ValueError("enabled cloud providers require api_key_env")
        return self


class RobotConfig(ConfigModel):
    """Top-level V4 configuration schema."""

    schema_version: Literal[1] = 1
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def default_provider_must_exist_and_be_enabled(self) -> RobotConfig:
        """Ensure startup never selects an absent or disabled provider."""
        provider = self.providers.get(self.agent.default_provider)
        if provider is None:
            raise ValueError("agent.default_provider must name a configured provider")
        if not provider.enabled:
            raise ValueError("agent.default_provider must be enabled")
        return self


def load_robot_config(path: str | Path) -> RobotConfig:
    """Load and strictly validate a TOML configuration file."""
    config_path = Path(path)
    try:
        with config_path.open("rb") as source:
            payload = tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"Unable to read configuration {config_path}: {exc}") from exc
    return RobotConfig.model_validate(payload)
