"""Core driver and Pi 5 GPIO backend adapter for pi5buzzer."""

from __future__ import annotations

import gc
import logging
import queue
import threading
import time
from typing import Any, Optional, Protocol, runtime_checkable

try:
    from ninja_utils import Actuator, get_logger

    log = get_logger(__name__)
except ImportError:
    from abc import ABC, abstractmethod

    class Actuator(ABC):
        """Minimal Actuator interface for standalone mode."""

        @abstractmethod
        def initialize(self) -> None:
            """Initialize the actuator."""

        @abstractmethod
        def execute(self, command: dict[str, Any]) -> None:
            """Execute a hardware command."""

        @abstractmethod
        def off(self) -> None:
            """Turn the actuator off."""

    log = logging.getLogger(__name__)


MIN_FREQUENCY = 20
MAX_FREQUENCY = 20000
_STOP_SENTINEL = None
_PAUSE_KEY = "__pause__"
_DEFAULT_PWM_FREQUENCY = 440
_BACKEND_INSTALL_HINT = (
    "RPi.GPIO-compatible backend unavailable. On Raspberry Pi 5 install "
    "'rpi-lgpio' or install the package extra with 'pip install \".[pi]\"'."
)


@runtime_checkable
class PWMBackend(Protocol):
    """Minimal pigpio-like backend contract used by Buzzer."""

    OUTPUT: Any
    connected: bool

    def set_mode(self, pin: int, mode: Any) -> None:
        """Configure the pin as output."""

    def set_PWM_frequency(self, pin: int, frequency: int) -> int:
        """Set PWM frequency in Hz."""

    def set_PWM_dutycycle(self, pin: int, duty_cycle: int) -> None:
        """Set PWM duty cycle in 0..255 range."""

    def stop(self) -> None:
        """Release hardware resources."""


class RPiGPIOPWMBackend:
    """Adapter that exposes a pigpio-like API over an RPi.GPIO-compatible module."""

    OUTPUT = "output"

    def __init__(self, gpio_module: Any):
        self._gpio = gpio_module
        self.connected = True
        self._configured_pins: set[int] = set()
        self._mode_configured = False
        self._pwm_by_pin: dict[int, Any] = {}

    def set_mode(self, pin: int, mode: Any) -> None:
        """Configure BCM numbering and claim the pin as an output."""
        del mode
        if not self._mode_configured:
            if hasattr(self._gpio, "setwarnings"):
                self._gpio.setwarnings(False)
            self._gpio.setmode(self._gpio.BCM)
            self._mode_configured = True

        self._gpio.setup(pin, self._gpio.OUT)
        self._configured_pins.add(pin)

    def set_PWM_frequency(self, pin: int, frequency: int) -> int:
        """Create or update the PWM object for the pin."""
        self._ensure_pwm(pin, frequency)
        return frequency

    def set_PWM_dutycycle(self, pin: int, duty_cycle: int) -> None:
        """Translate pigpio-style duty-cycle values to percentage-based PWM."""
        pwm = self._pwm_by_pin.get(pin)
        if pwm is None:
            if duty_cycle <= 0:
                return
            pwm = self._ensure_pwm(pin, _DEFAULT_PWM_FREQUENCY)

        percent = max(0.0, min(100.0, duty_cycle * 100.0 / 255.0))
        pwm.ChangeDutyCycle(percent)

    def release_pwm(self, pin: int) -> None:
        """Stop and drop the PWM object for a pin before chip cleanup."""
        pwm = self._pwm_by_pin.pop(pin, None)
        if pwm is None:
            return

        try:
            pwm.ChangeDutyCycle(0)
        except Exception:  # pragma: no cover - defensive cleanup only
            pass

        try:
            pwm.stop()
        except Exception:  # pragma: no cover - defensive cleanup only
            pass

        pwm = None
        gc.collect()

    def stop(self) -> None:
        """Stop all PWM objects and release GPIO resources."""
        while self._pwm_by_pin:
            pin = next(iter(self._pwm_by_pin))
            self.release_pwm(pin)

        if self._mode_configured:
            self._gpio.cleanup()
            self._mode_configured = False
            self._configured_pins.clear()

        self.connected = False

    def _ensure_pwm(self, pin: int, frequency: int) -> Any:
        pwm = self._pwm_by_pin.get(pin)
        if pwm is None:
            pwm = self._gpio.PWM(pin, frequency)
            pwm.start(0)
            self._pwm_by_pin[pin] = pwm
            return pwm

        pwm.ChangeFrequency(frequency)
        return pwm


def create_default_backend() -> PWMBackend:
    """Create the default Raspberry Pi 5 backend."""
    try:
        import RPi.GPIO as gpio
    except ImportError as exc:  # pragma: no cover - depends on host runtime
        raise RuntimeError(_BACKEND_INSTALL_HINT) from exc

    return RPiGPIOPWMBackend(gpio)


class Buzzer(Actuator):
    """A non-blocking passive buzzer driver with pigpio-compatible semantics."""

    def __init__(
        self,
        pin: int,
        pi: Optional[PWMBackend] = None,
        volume: int = 128,
        backend: Optional[PWMBackend] = None,
    ):
        if pi is not None and backend is not None and pi is not backend:
            raise ValueError("Pass either 'pi' or 'backend', not both.")

        provided_backend = backend if backend is not None else pi
        self._is_external_pi = provided_backend is not None
        self.pi = provided_backend
        self.pin = pin
        self._volume = max(0, min(255, volume))
        self._sound_queue: queue.Queue[tuple[int | str, float] | None] = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the GPIO backend and start the playback worker."""
        if self._initialized:
            log.debug("Buzzer already initialized - skipping.")
            return

        if self.pi is None:
            self.pi = create_default_backend()

        if not getattr(self.pi, "connected", True):
            raise ConnectionError(
                "Could not connect to the GPIO backend. Verify GPIO access and "
                "that no other process has claimed the pin."
            )

        mode = getattr(self.pi, "OUTPUT", 1)
        self.pi.set_mode(self.pin, mode)
        self.pi.set_PWM_dutycycle(self.pin, 0)

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._sound_worker,
            daemon=True,
            name="BuzzerWorker",
        )
        self._worker_thread.start()
        self._initialized = True
        log.info("Buzzer initialized on pin %s (volume=%s)", self.pin, self._volume)

    def execute(self, command: dict[str, Any]) -> None:
        """Queue a tone for playback without blocking the caller."""
        if not self._initialized:
            log.warning("Buzzer not initialized. Call initialize() first.")
            return

        frequency = command.get("frequency", 0)
        duration = command.get("duration", 0.1)

        if isinstance(frequency, (int, float)) and frequency > 0:
            clamped = max(MIN_FREQUENCY, min(MAX_FREQUENCY, int(frequency)))
            self._sound_queue.put((clamped, float(duration)))

    def off(self) -> None:
        """Stop playback, silence the buzzer, and release internal resources."""
        while not self._sound_queue.empty():
            try:
                self._sound_queue.get_nowait()
            except queue.Empty:
                break

        self._stop_event.set()
        self._sound_queue.put(_STOP_SENTINEL)

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

        if self.pi and getattr(self.pi, "connected", True):
            release_pwm = getattr(self.pi, "release_pwm", None)
            if callable(release_pwm):
                release_pwm(self.pin)
            else:
                self.pi.set_PWM_dutycycle(self.pin, 0)

        if not self._is_external_pi and self.pi and getattr(self.pi, "connected", True):
            self.pi.stop()
            self.pi = None

        self._initialized = False

    def play_sound(self, frequency: int, duration: float) -> None:
        """Legacy helper that delegates to execute()."""
        self.execute({"frequency": frequency, "duration": duration})

    def queue_pause(self, duration: float) -> None:
        """Queue a silent pause between tones."""
        if self._initialized:
            self._sound_queue.put((_PAUSE_KEY, float(duration)))

    @property
    def is_initialized(self) -> bool:
        """Whether the buzzer has been initialized."""
        return self._initialized

    @property
    def volume(self) -> int:
        """Current PWM duty cycle in the 0..255 range."""
        return self._volume

    @volume.setter
    def volume(self, value: int) -> None:
        self._volume = max(0, min(255, int(value)))
        log.debug("Volume set to %s", self._volume)

    def __enter__(self) -> "Buzzer":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.off()
        return False

    def _sound_worker(self) -> None:
        """Process queued tones and pauses on a dedicated background thread."""
        while not self._stop_event.is_set():
            try:
                item = self._sound_queue.get(timeout=0.5)

                if item is _STOP_SENTINEL:
                    continue

                frequency, duration = item
                if frequency == _PAUSE_KEY:
                    time.sleep(max(0.0, duration))
                    continue

                if self.pi is None:
                    break

                self.pi.set_PWM_frequency(self.pin, int(frequency))
                self.pi.set_PWM_dutycycle(self.pin, self._volume)
                time.sleep(max(0.0, duration))
                self.pi.set_PWM_dutycycle(self.pin, 0)
            except queue.Empty:
                continue
            except Exception as exc:
                log.exception("Buzzer playback failed: %s", exc)
                if self.pi and getattr(self.pi, "connected", True):
                    self.pi.set_PWM_dutycycle(self.pin, 0)
