"""Wake-word backends for pi5mic."""

from pi5mic.wakeword.base import WakeWordDetector, WakeWordResult
from pi5mic.wakeword.openwakeword import OpenWakeWordDetector

__all__ = ["OpenWakeWordDetector", "WakeWordDetector", "WakeWordResult"]
