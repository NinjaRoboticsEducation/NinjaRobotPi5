"""Strict V4-owned configuration; managed-driver files are never rewritten."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal

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
DEFAULT_SERVO_ENDPOINTS = (
    "gpio12",
    "gpio13",
)
SUPPORTED_SERVO_ENDPOINTS = (
    *DEFAULT_SERVO_ENDPOINTS,
    "hat_pwm1",
    "hat_pwm2",
    "hat_pwm3",
    "hat_pwm4",
)


class ConfigModel(BaseModel):
    """Base for strict configuration sections."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BuzzerConfig(ConfigModel):
    """Passive-buzzer wiring owned by V4."""

    enabled: bool = True
    gpio: Annotated[int, Field(ge=0, le=27)] = 27


class ServoConfig(ConfigModel):
    """Configured servo topology and motion safety gates."""

    enabled: bool = True
    endpoints: tuple[str, ...] = DEFAULT_SERVO_ENDPOINTS
    calibration_file: NonEmptyText = "~/.config/pi5servo/servo.json"
    motion_enabled: bool = False
    group_motion_enabled: bool = False

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
        """Require one or more supported, uniquely routed endpoints."""
        if not endpoints:
            raise ValueError("servo endpoints must not be empty")
        if len(endpoints) != len(set(endpoints)):
            raise ValueError("servo endpoints must not contain duplicates")
        unsupported = sorted(set(endpoints) - set(SUPPORTED_SERVO_ENDPOINTS))
        if unsupported:
            raise ValueError(f"unsupported servo endpoints: {', '.join(unsupported)}")
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
    warmup_seconds: Annotated[float, Field(ge=0, le=10)] = 1.0
    autofocus_mode: Literal["none", "manual", "auto", "continuous"] = "none"
    media_directory: NonEmptyText = "~/.local/share/ninjarobot_pi5/camera"
    retain_media_by_default: Literal[False] = False


class MicrophoneConfig(ConfigModel):
    """Initial privacy-safe USB microphone profile."""

    enabled: bool = True
    device_selector: NonEmptyText = "USB PnP Sound Device"
    sample_rate_hz: Annotated[int, Field(ge=8_000, le=192_000)] = 16_000
    channels: Literal[1] = 1
    max_capture_seconds: Annotated[float, Field(ge=1, le=30)] = 10.0
    media_directory: NonEmptyText = "~/.local/share/ninjarobot_pi5/microphone"
    retain_audio_by_default: Literal[False] = False


class BehaviorConfig(ConfigModel):
    """Behavior assets, drive roles, and approved distance-watch settings."""

    user_directory: NonEmptyText = "~/.config/ninjarobot_pi5/behaviors"
    safety_state_file: NonEmptyText = "~/.local/state/ninjarobot_pi5/safety.json"
    left_motor_role: NonEmptyText = "left_motor"
    right_motor_role: NonEmptyText = "right_motor"
    servo_roles: dict[str, str] = Field(
        default_factory=lambda: {
            "left_motor": "gpio12",
            "right_motor": "gpio13",
        }
    )
    obstacle_threshold_mm: Annotated[int, Field(ge=50, le=2_000)] = 50
    obstacle_consecutive_readings: Annotated[int, Field(ge=1, le=10)] = 3
    # Accepted only so Phase 4 configuration files continue to load. Movement no
    # longer waits for clear readings before energizing the servos.
    clear_readings_before_motion: Annotated[int, Field(ge=1, le=10)] = 3
    clear_reading_timeout_seconds: Annotated[float, Field(ge=1.0, le=30.0)] = 5.0
    distance_poll_interval_seconds: Annotated[float, Field(ge=0.02, le=2.0)] = 0.05
    watchdog_timeout_seconds: Annotated[float, Field(ge=0.1, le=10.0)] = 1.0
    system_stopped_display_seconds: Annotated[float, Field(ge=0.0, le=10.0)] = 2.0
    stop_on_invalid_distance: Literal[False] = False

    @model_validator(mode="after")
    def motor_roles_must_be_distinct_and_supported(self) -> BehaviorConfig:
        """Require two distinct logical motor roles mapped to supported endpoints."""
        if self.left_motor_role == self.right_motor_role:
            raise ValueError("left and right motor role names must be distinct")
        required = {self.left_motor_role, self.right_motor_role}
        missing = sorted(required - set(self.servo_roles))
        if missing:
            raise ValueError(f"servo_roles is missing required roles: {', '.join(missing)}")
        endpoints = tuple(self.servo_roles.values())
        if len(endpoints) != len(set(endpoints)):
            raise ValueError("servo_roles must map to distinct servo endpoints")
        unsupported = sorted(set(endpoints) - set(SUPPORTED_SERVO_ENDPOINTS))
        if unsupported:
            raise ValueError(
                f"servo_roles contains unsupported endpoints: {', '.join(unsupported)}"
            )
        return self


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
    request_timeout_seconds: Annotated[float, Field(gt=0, le=600)] = 600.0
    model_inactivity_timeout_seconds: Annotated[float, Field(gt=0, le=600)] = 120.0
    fallback_providers: tuple[NonEmptyText, ...] = ()

    @field_validator("fallback_providers", mode="before")
    @classmethod
    def normalize_fallback_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @field_validator("fallback_providers")
    @classmethod
    def fallback_providers_must_be_unique(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("agent fallback providers must be unique")
        return value

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_turn_timeout(cls, value: Any) -> Any:
        """Give existing Phase 5 configurations the new activity-aware defaults."""
        if not isinstance(value, dict) or "turn_timeout_seconds" not in value:
            return value
        migrated = dict(value)
        migrated.pop("turn_timeout_seconds")
        migrated.setdefault("request_timeout_seconds", 600.0)
        migrated.setdefault("model_inactivity_timeout_seconds", 120.0)
        return migrated


class ProviderConfig(ConfigModel):
    """Provider reference containing names and secret references, never secrets."""

    kind: Literal["ollama", "openai", "gemini", "anthropic"]
    model: NonEmptyText
    enabled: bool = False
    base_url: Annotated[str, StringConstraints(min_length=8, max_length=500)] | None = None
    auth_method: Literal["api_key"] = "api_key"
    api_key_env: EnvironmentVariable | None = None
    # Accepted only so pre-2026-08-01 files can load and be rewritten without
    # their removed web-login profile becoming an unknown-field error.
    oauth_profile: NonEmptyText | None = Field(default=None, exclude=True)
    project_id: NonEmptyText | None = None

    @field_validator("auth_method", mode="before")
    @classmethod
    def migrate_removed_web_login(cls, value: object) -> object:
        """Load legacy OAuth selections as API-key mode without using old tokens."""
        return "api_key" if value == "oauth" else value

    @model_validator(mode="after")
    def enabled_cloud_provider_requires_secret_reference(self) -> ProviderConfig:
        """Require the metadata needed by the selected cloud authentication mode."""
        if self.kind == "ollama":
            return self
        if self.api_key_env is None:
            raise ValueError("cloud providers using API keys require api_key_env")
        return self


class RobotConfig(ConfigModel):
    """Top-level V4 configuration schema."""

    schema_version: Literal[1] = 1
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)
    behaviors: BehaviorConfig = Field(default_factory=BehaviorConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def behavior_servo_roles_must_be_configured(self) -> RobotConfig:
        """Prevent a behavior role from resolving outside the active servo topology."""
        configured = set(self.hardware.servos.endpoints)
        missing = sorted(set(self.behaviors.servo_roles.values()) - configured)
        if missing:
            raise ValueError(
                "behavior servo roles require configured endpoints: " + ", ".join(missing)
            )
        return self

    @model_validator(mode="after")
    def default_provider_must_exist_and_be_enabled(self) -> RobotConfig:
        """Ensure startup never selects an absent or disabled provider."""
        provider = self.providers.get(self.agent.default_provider)
        if provider is None:
            raise ValueError("agent.default_provider must name a configured provider")
        if not provider.enabled:
            raise ValueError("agent.default_provider must be enabled")
        for fallback_id in self.agent.fallback_providers:
            fallback = self.providers.get(fallback_id)
            if fallback is None or not fallback.enabled:
                raise ValueError("agent fallback providers must name configured enabled providers")
            if fallback_id == self.agent.default_provider:
                raise ValueError("agent fallback providers must not include the default provider")
        return self


def load_robot_config(path: str | Path) -> RobotConfig:
    """Load and strictly validate a TOML configuration file."""
    config_path = Path(path).expanduser()
    try:
        with config_path.open("rb") as source:
            payload = tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"Unable to read configuration {config_path}: {exc}") from exc
    return RobotConfig.model_validate(payload)
