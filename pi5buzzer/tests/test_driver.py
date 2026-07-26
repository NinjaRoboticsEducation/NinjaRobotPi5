"""Unit tests for pi5buzzer.core.driver.Buzzer."""

import time

import pytest


class FakePWM:
    """Simple PWM test double that records destructor behavior."""

    def __init__(self, gpio_module, pin, frequency):
        self.gpio_module = gpio_module
        self.pin = pin
        self.frequency = frequency

    def start(self, duty_cycle):
        self.gpio_module.events.append(("start", self.pin, duty_cycle))

    def ChangeDutyCycle(self, duty_cycle):
        self.gpio_module.events.append(("duty", self.pin, duty_cycle))

    def ChangeFrequency(self, frequency):
        self.frequency = frequency
        self.gpio_module.events.append(("frequency", self.pin, frequency))

    def stop(self):
        if not self.gpio_module.active:
            raise TypeError("chip closed")
        self.gpio_module.events.append(("stop", self.pin))

    def __del__(self):
        try:
            self.stop()
        except Exception as exc:  # pragma: no cover - destructor path
            self.gpio_module.events.append(("destructor_error", type(exc).__name__))


class FakeGPIOModule:
    """Minimal GPIO module test double for the Pi 5 backend wrapper."""

    BCM = 11
    OUT = 0

    def __init__(self):
        self.active = True
        self.events = []

    def setwarnings(self, enabled):
        self.events.append(("setwarnings", enabled))

    def setmode(self, mode):
        self.events.append(("setmode", mode))

    def setup(self, pin, mode):
        self.events.append(("setup", pin, mode))

    def PWM(self, pin, frequency):
        self.events.append(("create_pwm", pin, frequency))
        return FakePWM(self, pin, frequency)

    def cleanup(self):
        self.events.append(("cleanup",))
        self.active = False


class TestBuzzerInit:
    """Test Buzzer initialization."""

    def test_init_creates_instance(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        buzzer = Buzzer(pin=17, pi=mock_pi)
        assert buzzer.pin == 17
        assert buzzer.pi is mock_pi
        assert not buzzer.is_initialized

    def test_init_with_external_pi(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        buzzer = Buzzer(pin=17, pi=mock_pi)
        assert buzzer._is_external_pi is True

    def test_init_without_pi(self):
        from pi5buzzer.core.driver import Buzzer

        buzzer = Buzzer(pin=17)
        assert buzzer._is_external_pi is False
        assert buzzer.pi is None

    def test_init_default_volume(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        assert Buzzer(pin=17, pi=mock_pi).volume == 128

    def test_init_custom_volume(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        assert Buzzer(pin=17, pi=mock_pi, volume=64).volume == 64

    def test_init_volume_clamped(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        assert Buzzer(pin=17, pi=mock_pi, volume=999).volume == 255
        assert Buzzer(pin=17, pi=mock_pi, volume=-5).volume == 0


class TestBuzzerInitialize:
    """Test Buzzer.initialize()."""

    def test_initialize_starts_worker(self, buzzer):
        assert buzzer.is_initialized
        assert buzzer._worker_thread is not None
        assert buzzer._worker_thread.is_alive()

    def test_initialize_is_idempotent(self, buzzer):
        thread = buzzer._worker_thread
        buzzer.initialize()
        assert buzzer._worker_thread is thread

    def test_initialize_builds_internal_backend(self, mock_pi, mock_backend_factory):
        from pi5buzzer.core.driver import Buzzer

        buzzer = Buzzer(pin=17)
        buzzer.initialize()
        assert buzzer.pi is mock_pi
        mock_backend_factory.assert_called_once()
        buzzer.off()

    def test_initialize_fails_without_backend_connection(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        mock_pi.connected = False
        buzzer = Buzzer(pin=17, pi=mock_pi)
        with pytest.raises(ConnectionError):
            buzzer.initialize()

    def test_initialize_sets_pin_mode(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        buzzer = Buzzer(pin=17, pi=mock_pi)
        buzzer.initialize()
        mock_pi.set_mode.assert_called_once()
        buzzer.off()


class TestBuzzerExecute:
    """Test Buzzer.execute()."""

    def test_execute_queues_sound(self, buzzer):
        buzzer.execute({"frequency": 440, "duration": 0.1})
        time.sleep(0.3)
        buzzer.pi.set_PWM_frequency.assert_called()

    def test_execute_clamps_frequency(self, buzzer):
        buzzer.execute({"frequency": 5, "duration": 0.01})
        time.sleep(0.2)
        buzzer.pi.set_PWM_frequency.assert_called_with(17, 20)

    def test_execute_clamps_high_frequency(self, buzzer):
        buzzer.execute({"frequency": 99999, "duration": 0.01})
        time.sleep(0.2)
        buzzer.pi.set_PWM_frequency.assert_called_with(17, 20000)

    def test_execute_ignores_zero_frequency(self, buzzer):
        buzzer.execute({"frequency": 0, "duration": 0.1})
        time.sleep(0.2)
        buzzer.pi.set_PWM_frequency.assert_not_called()

    def test_execute_ignores_negative_frequency(self, buzzer):
        buzzer.execute({"frequency": -100, "duration": 0.1})
        time.sleep(0.2)
        buzzer.pi.set_PWM_frequency.assert_not_called()

    def test_execute_when_not_initialized(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        Buzzer(pin=17, pi=mock_pi).execute({"frequency": 440, "duration": 0.1})


class TestBuzzerPlaySound:
    """Test play_sound() compatibility."""

    def test_play_sound_delegates_to_execute(self, buzzer):
        buzzer.play_sound(440, 0.1)
        time.sleep(0.3)
        buzzer.pi.set_PWM_frequency.assert_called()


class TestBuzzerVolume:
    """Test volume property."""

    def test_volume_setter(self, buzzer):
        buzzer.volume = 200
        assert buzzer.volume == 200

    def test_volume_clamped(self, buzzer):
        buzzer.volume = 999
        assert buzzer.volume == 255
        buzzer.volume = -10
        assert buzzer.volume == 0

    def test_volume_applied_in_playback(self, buzzer):
        buzzer.volume = 64
        buzzer.execute({"frequency": 440, "duration": 0.01})
        time.sleep(0.2)
        buzzer.pi.set_PWM_dutycycle.assert_any_call(17, 64)


class TestBuzzerPause:
    """Test queue-based pause support."""

    def test_queue_pause(self, buzzer):
        buzzer.queue_pause(0.1)
        time.sleep(0.3)

    def test_queue_pause_when_not_initialized(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        Buzzer(pin=17, pi=mock_pi).queue_pause(0.1)


class TestBuzzerOff:
    """Test Buzzer.off()."""

    def test_off_stops_worker(self, buzzer):
        buzzer.off()
        assert not buzzer.is_initialized
        assert not buzzer._worker_thread.is_alive()

    def test_off_releases_pwm_on_backend(self, buzzer):
        buzzer.off()
        buzzer.pi.release_pwm.assert_called_once_with(17)

    def test_off_does_not_stop_external_pi(self, buzzer):
        buzzer.off()
        buzzer.pi.stop.assert_not_called()

    def test_off_stops_internal_backend(self, mock_pi, mock_backend_factory):
        from pi5buzzer.core.driver import Buzzer

        buzzer = Buzzer(pin=17)
        buzzer.initialize()
        buzzer.off()
        mock_pi.stop.assert_called_once()
        assert buzzer.pi is None


class TestBuzzerContextManager:
    """Test context manager support."""

    def test_context_manager(self, mock_pi):
        from pi5buzzer.core.driver import Buzzer

        with Buzzer(pin=17, pi=mock_pi) as buzzer:
            assert buzzer.is_initialized
        assert not buzzer.is_initialized


class TestRPiGPIOPWMBackend:
    """Test the Pi 5 backend wrapper cleanup behavior."""

    def test_stop_releases_pwm_before_cleanup(self):
        from pi5buzzer.core.driver import RPiGPIOPWMBackend

        gpio_module = FakeGPIOModule()
        backend = RPiGPIOPWMBackend(gpio_module)
        backend.set_mode(17, backend.OUTPUT)
        backend.set_PWM_frequency(17, 440)
        backend.set_PWM_dutycycle(17, 128)

        backend.stop()

        assert ("destructor_error", "TypeError") not in gpio_module.events
        assert ("cleanup",) in gpio_module.events
        assert backend.connected is False
        assert gpio_module.events.index(("stop", 17)) < gpio_module.events.index(("cleanup",))

    def test_stop_is_idempotent(self):
        from pi5buzzer.core.driver import RPiGPIOPWMBackend

        gpio_module = FakeGPIOModule()
        backend = RPiGPIOPWMBackend(gpio_module)
        backend.set_mode(17, backend.OUTPUT)
        backend.set_PWM_frequency(17, 440)

        backend.stop()
        backend.stop()

        assert gpio_module.events.count(("cleanup",)) == 1
