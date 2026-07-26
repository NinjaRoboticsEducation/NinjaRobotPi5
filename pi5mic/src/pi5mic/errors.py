"""Custom exceptions for pi5mic."""


class Pi5MicError(Exception):
    """Base exception for pi5mic."""


class ConfigError(Pi5MicError):
    """Configuration file or config value error."""


class DeviceError(Pi5MicError):
    """Microphone device discovery or selection error."""


class RecordingError(Pi5MicError):
    """Audio recording error."""


class ListenerBusyError(Pi5MicError):
    """Listener cannot accept a new trigger in the current state."""


class WakeWordError(Pi5MicError):
    """Wake-word backend setup or processing error."""


class STTError(Pi5MicError):
    """Speech-to-text backend setup or transcription error."""


class NoSpeechDetectedError(STTError):
    """Speech-to-text ran successfully, but no spoken transcript was detected."""


class TransportError(Pi5MicError):
    """OpenClaw transport setup or dispatch error."""


class IntegrationError(Pi5MicError):
    """Optional integration surface error, such as presence control."""
