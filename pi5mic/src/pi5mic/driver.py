"""Compatibility re-exports for standalone pi5mic usage."""

from pi5mic.config.config_manager import (
    DEFAULT_CONFIG,
    MicConfigManager,
    get_default_config_filepath,
)
from pi5mic.core.devices import AudioDeviceInfo, get_default_input_device, list_input_devices
from pi5mic.core.recorder import RecordedClip, RecorderSettings, record_temp_wav, record_wav
from pi5mic.integration.presence import OpenClawPresenceController
from pi5mic.models import DispatchResult
from pi5mic.transport.openclaw_cli import OpenClawAgentTransport

__all__ = [
    "AudioDeviceInfo",
    "DEFAULT_CONFIG",
    "DispatchResult",
    "MicConfigManager",
    "OpenClawAgentTransport",
    "OpenClawPresenceController",
    "RecordedClip",
    "RecorderSettings",
    "get_default_config_filepath",
    "get_default_input_device",
    "list_input_devices",
    "record_temp_wav",
    "record_wav",
]
