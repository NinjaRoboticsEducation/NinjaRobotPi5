"""pi5mic - Standalone-first microphone capture tools for NinjaClawBot."""

from pi5mic.config.config_manager import (
    DEFAULT_CONFIG,
    MicConfigManager,
    get_default_config_filepath,
)
from pi5mic.core.devices import AudioDeviceInfo, get_default_input_device, list_input_devices
from pi5mic.core.listener import MicListener
from pi5mic.core.recorder import RecordedClip, RecorderSettings, record_temp_wav, record_wav
from pi5mic.core.session import ListenerSnapshot, ListenerState
from pi5mic.integration.presence import OpenClawPresenceController
from pi5mic.models import DispatchResult, TranscriptionResult
from pi5mic.stt.gemini import GeminiBackend
from pi5mic.stt.whisper_cpp import WhisperCppBackend
from pi5mic.transport.openclaw_cli import OpenClawAgentTransport
from pi5mic.vad.silence import SilenceStopDetector
from pi5mic.wakeword.openwakeword import OpenWakeWordDetector

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "AudioDeviceInfo",
    "DEFAULT_CONFIG",
    "DispatchResult",
    "ListenerSnapshot",
    "ListenerState",
    "MicConfigManager",
    "MicListener",
    "OpenClawAgentTransport",
    "OpenClawPresenceController",
    "OpenWakeWordDetector",
    "RecordedClip",
    "RecorderSettings",
    "SilenceStopDetector",
    "TranscriptionResult",
    "GeminiBackend",
    "WhisperCppBackend",
    "get_default_config_filepath",
    "get_default_input_device",
    "list_input_devices",
    "record_temp_wav",
    "record_wav",
]
