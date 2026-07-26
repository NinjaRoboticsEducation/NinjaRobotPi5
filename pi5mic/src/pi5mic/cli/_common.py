"""Shared CLI helpers for pi5mic."""

from __future__ import annotations

from pathlib import Path

from pi5mic.config.config_manager import MicConfigManager
from pi5mic.errors import ConfigError, STTError
from pi5mic.integration.delivery import validate_delivery_config
from pi5mic.integration.presence import OpenClawPresenceController
from pi5mic.stt.gemini import GeminiBackend
from pi5mic.stt.whisper_cpp import WhisperCppBackend
from pi5mic.transport.openclaw_cli import OpenClawAgentTransport


def load_manager(config_file: Path | str | None) -> MicConfigManager:
    """Create and load a config manager for the given path."""
    manager = MicConfigManager(config_file)
    manager.load()
    return manager


def build_stt_backend(config: dict, backend_name: str | None = None):
    """Build an STT backend from the current config."""
    stt_config = config.get("stt")
    if not isinstance(stt_config, dict):
        raise ConfigError("Config key 'stt' must be an object.")

    selected = backend_name or stt_config.get("selected")
    if selected == "whisper_cpp":
        whisper_config = stt_config.get("whisper_cpp")
        if not isinstance(whisper_config, dict):
            raise ConfigError("Config key 'stt.whisper_cpp' must be an object.")
        model_path = whisper_config.get("model_path")
        if not model_path:
            raise STTError("Whisper model path is not configured.")
        return WhisperCppBackend(
            command=whisper_config.get("command"),
            model_path=model_path,
            language=str(whisper_config.get("language", "auto")),
            translate_to_english=bool(whisper_config.get("translate_to_english", False)),
            threads=(
                int(whisper_config["threads"])
                if whisper_config.get("threads") not in (None, "")
                else None
            ),
            timeout_seconds=int(whisper_config.get("timeout_seconds", 120)),
        )

    if selected == "gemini":
        gemini_config = stt_config.get("gemini")
        if not isinstance(gemini_config, dict):
            raise ConfigError("Config key 'stt.gemini' must be an object.")
        return GeminiBackend(
            model=str(gemini_config.get("model", "gemini-2.5-flash")),
            timeout_seconds=int(gemini_config.get("timeout_seconds", 60)),
            retry_limit=int(gemini_config.get("retry_limit", 2)),
        )

    raise ConfigError(f"Unsupported STT backend: {selected}")


def validate_openclaw_profile(config: dict) -> dict:
    """Validate and return the OpenClaw integration config."""
    integration_config = config.get("integration")
    if not isinstance(integration_config, dict):
        raise ConfigError("Config key 'integration' must be an object.")

    openclaw_config = integration_config.get("openclaw")
    if not isinstance(openclaw_config, dict):
        raise ConfigError("Config key 'integration.openclaw' must be an object.")

    required_keys = ("agent_id", "session_key")
    missing = [key for key in required_keys if not str(openclaw_config.get(key, "")).strip()]
    if missing:
        raise ConfigError("OpenClaw profile is missing required config keys: " + ", ".join(missing))

    validate_delivery_config(
        delivery_mode=str(integration_config.get("delivery_mode", "local_only")),
        reply_channel=openclaw_config.get("reply_channel"),
        reply_to=openclaw_config.get("reply_to"),
    )
    return openclaw_config


def build_openclaw_transport(
    config: dict,
    *,
    session_strategy_override: str | None = None,
) -> OpenClawAgentTransport:
    """Build the configured OpenClaw transport."""
    integration_config = config.get("integration")
    if not isinstance(integration_config, dict):
        raise ConfigError("Config key 'integration' must be an object.")

    openclaw_config = validate_openclaw_profile(config)
    return OpenClawAgentTransport(
        command=openclaw_config.get("command"),
        gateway_url=openclaw_config.get("gateway_url"),
        agent_id=str(openclaw_config["agent_id"]),
        session_key=str(openclaw_config["session_key"]),
        session_strategy=(
            session_strategy_override
            or str(openclaw_config.get("session_strategy", "dedicated_mic"))
        ),
        delivery_mode=str(integration_config.get("delivery_mode", "local_only")),
        reply_channel=openclaw_config.get("reply_channel"),
        reply_to=openclaw_config.get("reply_to"),
        reply_account=openclaw_config.get("reply_account"),
        timeout_seconds=int(openclaw_config.get("request_timeout_seconds", 180)),
    )


def build_presence_controller(config: dict) -> OpenClawPresenceController:
    """Build the configured presence controller."""
    openclaw_config = validate_openclaw_profile(config)
    return OpenClawPresenceController(
        command=openclaw_config.get("command"),
        gateway_url=openclaw_config.get("gateway_url"),
        timeout_seconds=int(openclaw_config.get("presence_timeout_seconds", 3)),
    )
