"""Always-on voice input loop and service-state helpers for pi5mic."""

from __future__ import annotations

import audioop
import json
import math
import os
import tempfile
import wave
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock
from typing import Any, Callable

from pi5mic.core.audio_backend import load_sounddevice
from pi5mic.core.devices import resolve_supported_input_settings
from pi5mic.core.listener import MicListener
from pi5mic.errors import (
    ConfigError,
    DeviceError,
    IntegrationError,
    ListenerBusyError,
    NoSpeechDetectedError,
    RecordingError,
    STTError,
    TransportError,
    WakeWordError,
)
from pi5mic.install.openwakeword import (
    resolve_openwakeword_inference_framework,
    resolve_openwakeword_model_path,
    validate_openwakeword_runtime_assets,
)
from pi5mic.vad.silence import SilenceStopDetector
from pi5mic.wakeword.openwakeword import OpenWakeWordDetector

_TARGET_SAMPLE_WIDTH_BYTES = 2
_TIMESTAMP_KEYS = {
    "started_at",
    "last_updated_at",
    "last_triggered_at",
    "last_completed_at",
}
_VOICEINPUT_STATE_FILE = ".pi5mic-voiceinput-state.json"
_VOICEINPUT_LOG_FILE = ".pi5mic-voiceinput.log"
_DEFAULT_STREAM_LATENCY = "high"
_OVERFLOW_RECOVERY_THRESHOLD = 3
_DEFAULT_SERVICE_STATE: dict[str, Any] = {
    "running": False,
    "pid": None,
    "mode": "stopped",
    "profile": None,
    "config_file": None,
    "listener_state": "idle",
    "session_strategy": None,
    "wakeword_backend": None,
    "wakeword_keyword": None,
    "started_at": None,
    "last_updated_at": None,
    "last_triggered_at": None,
    "last_completed_at": None,
    "last_error": None,
    "wakeword_hits": 0,
    "cycles_completed": 0,
}


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_sounddevice():
    return load_sounddevice(
        purpose="always-on voice input",
        error_factory=RecordingError,
    )


def _coerce_iso_timestamp(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _is_process_running(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class VoiceInputRuntimePaths:
    """Runtime files used by the always-on voice input service."""

    config_path: Path
    state_file: Path
    log_file: Path


def build_voiceinput_runtime_paths(config_path: Path | str) -> VoiceInputRuntimePaths:
    """Return runtime file locations derived from the current config path."""
    resolved = Path(config_path).expanduser().resolve()
    parent = resolved.parent
    return VoiceInputRuntimePaths(
        config_path=resolved,
        state_file=parent / _VOICEINPUT_STATE_FILE,
        log_file=parent / _VOICEINPUT_LOG_FILE,
    )


def read_voiceinput_state(paths: VoiceInputRuntimePaths) -> dict[str, Any]:
    """Read the saved always-on service state from disk."""
    if not paths.state_file.exists():
        return dict(_DEFAULT_SERVICE_STATE)

    try:
        payload = json.loads(paths.state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULT_SERVICE_STATE)

    if not isinstance(payload, dict):
        return dict(_DEFAULT_SERVICE_STATE)

    state = dict(_DEFAULT_SERVICE_STATE)
    state.update(payload)
    state["running"] = bool(state.get("running", False))
    pid = state.get("pid")
    state["pid"] = int(pid) if isinstance(pid, (int, float)) and int(pid) > 0 else None
    for key in _TIMESTAMP_KEYS:
        state[key] = _coerce_iso_timestamp(state.get(key))
    state["wakeword_hits"] = int(state.get("wakeword_hits", 0) or 0)
    state["cycles_completed"] = int(state.get("cycles_completed", 0) or 0)

    if state["running"] and not _is_process_running(state["pid"]):
        state["running"] = False
        state["mode"] = "stopped"
        state["pid"] = None
    return state


def write_voiceinput_state(paths: VoiceInputRuntimePaths, payload: dict[str, Any]) -> None:
    """Persist always-on service state to disk."""
    state = dict(_DEFAULT_SERVICE_STATE)
    state.update(payload)
    state["last_updated_at"] = _utcnow_iso()
    paths.state_file.parent.mkdir(parents=True, exist_ok=True)
    paths.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


def update_voiceinput_state(paths: VoiceInputRuntimePaths, **updates: Any) -> dict[str, Any]:
    """Merge and persist service state updates."""
    state = read_voiceinput_state(paths)
    state.update(updates)
    write_voiceinput_state(paths, state)
    return state


def describe_voiceinput_install_help() -> str:
    """Return the recommended install command for always-on wake-word support."""
    return (
        "Install wake-word support with `uv sync --extra dev --extra voiceinput`, then "
        "register your custom model with `uv run pi5mic install openwakeword --model-path "
        "/path/to/ninja.tflite`."
    )


def normalize_voiceinput_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the always-on configuration block."""
    voiceinput = config.get("voiceinput")
    if not isinstance(voiceinput, dict):
        raise ConfigError("Config key 'voiceinput' must be an object.")

    wakeword = config.get("wakeword")
    if not isinstance(wakeword, dict):
        raise ConfigError("Config key 'wakeword' must be an object.")

    if not bool(voiceinput.get("enabled", False)):
        raise ConfigError(
            "Always-on voice input is disabled. Rerun `uv run pi5mic setup` and enable it first."
        )
    if not bool(wakeword.get("enabled", False)):
        raise ConfigError(
            "Wake-word detection is disabled. Rerun `uv run pi5mic setup` and enable always-on voice input."
        )

    backend = str(wakeword.get("backend", "openwakeword")).strip().lower()
    if backend != "openwakeword":
        raise ConfigError(f"Unsupported wake-word backend: {backend}")

    silence_timeout = float(voiceinput.get("silence_timeout_seconds", 3.0))
    max_capture = float(voiceinput.get("max_capture_seconds", 10.0))
    cooldown = float(voiceinput.get("cooldown_seconds", 1.5))
    vad_threshold = float(voiceinput.get("vad_rms_threshold", 200.0))
    session_strategy = str(voiceinput.get("session_strategy", "agent_main")).strip().lower()

    if silence_timeout <= 0:
        raise ConfigError("voiceinput.silence_timeout_seconds must be greater than 0.")
    if max_capture <= 0:
        raise ConfigError("voiceinput.max_capture_seconds must be greater than 0.")
    if cooldown < 0:
        raise ConfigError("voiceinput.cooldown_seconds must be greater than or equal to 0.")
    if vad_threshold < 0:
        raise ConfigError("voiceinput.vad_rms_threshold must be greater than or equal to 0.")
    if session_strategy not in {"agent_main", "dedicated_mic"}:
        raise ConfigError("voiceinput.session_strategy must be 'agent_main' or 'dedicated_mic'.")

    keyword = str(wakeword.get("keyword", "ninja")).strip() or "ninja"
    model_path = str(wakeword.get("model_path", "") or "").strip() or None
    threshold = float(wakeword.get("threshold", 0.5))
    wakeword_vad_threshold = float(wakeword.get("vad_threshold", 0.0))
    enable_noise_suppression = bool(wakeword.get("enable_noise_suppression", False))
    inference_framework = str(wakeword.get("inference_framework", "auto")).strip().lower() or "auto"

    if threshold <= 0 or threshold > 1:
        raise ConfigError("wakeword.threshold must be greater than 0 and less than or equal to 1.")
    if wakeword_vad_threshold < 0 or wakeword_vad_threshold > 1:
        raise ConfigError(
            "wakeword.vad_threshold must be greater than or equal to 0 and less than or equal to 1."
        )
    if inference_framework not in {"auto", "tflite", "onnx"}:
        raise ConfigError("wakeword.inference_framework must be one of: auto, tflite, onnx.")

    return {
        "backend": backend,
        "keyword": keyword,
        "model_path": model_path,
        "threshold": threshold,
        "wakeword_vad_threshold": wakeword_vad_threshold,
        "enable_noise_suppression": enable_noise_suppression,
        "inference_framework": inference_framework,
        "silence_timeout_seconds": silence_timeout,
        "max_capture_seconds": max_capture,
        "cooldown_seconds": cooldown,
        "vad_rms_threshold": vad_threshold,
        "session_strategy": session_strategy,
    }


def build_wakeword_detector(config: dict[str, Any]) -> OpenWakeWordDetector:
    """Build the configured wake-word detector for always-on voice input."""
    normalized = normalize_voiceinput_config(config)
    resolved_model = resolve_openwakeword_model_path(normalized["model_path"])
    resolved_framework = resolve_openwakeword_inference_framework(
        model_path=resolved_model,
        configured_framework=normalized["inference_framework"],
    )
    missing_assets = validate_openwakeword_runtime_assets(
        inference_framework=resolved_framework,
        include_vad=normalized["wakeword_vad_threshold"] > 0,
    )
    if missing_assets:
        missing_names = ", ".join(path.name for path in missing_assets)
        raise WakeWordError(
            "openWakeWord shared runtime assets are missing: "
            + missing_names
            + ". Run `uv run pi5mic install openwakeword --model-path "
            + str(resolved_model)
            + "` to download the required runtime files."
        )

    return OpenWakeWordDetector(
        keyword=normalized["keyword"],
        model_path=resolved_model,
        threshold=normalized["threshold"],
        vad_threshold=normalized["wakeword_vad_threshold"],
        enable_noise_suppression=normalized["enable_noise_suppression"],
        inference_framework=resolved_framework,
    )


def validate_voiceinput_readiness(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the always-on voice-input runtime and return detector details."""
    normalized = normalize_voiceinput_config(config)
    try:
        resolved_model = resolve_openwakeword_model_path(normalized["model_path"])
        resolved_framework = resolve_openwakeword_inference_framework(
            model_path=resolved_model,
            configured_framework=normalized["inference_framework"],
        )
    except WakeWordError as exc:
        raise WakeWordError(str(exc)) from exc

    detector = build_wakeword_detector(config)
    try:
        return {
            **normalized,
            "model_path": resolved_model,
            "resolved_inference_framework": resolved_framework,
            "detector_frame_length": detector.frame_length,
            "detector_sample_rate": detector.sample_rate,
        }
    finally:
        detector.close()


class _AudioResampler:
    """Incrementally resample live PCM into wake-word-compatible mono frames."""

    def __init__(
        self,
        *,
        source_sample_rate: int,
        source_channels: int,
        target_sample_rate: int,
    ) -> None:
        if source_channels not in {1, 2}:
            raise RecordingError(
                "Always-on voice input currently supports only mono or stereo microphone streams."
            )
        self._source_sample_rate = source_sample_rate
        self._source_channels = source_channels
        self._target_sample_rate = target_sample_rate
        self._state = None

    def convert(self, pcm_bytes: bytes) -> bytes:
        """Convert live int16 PCM into mono target-rate bytes."""
        mono_bytes = pcm_bytes
        if self._source_channels == 2:
            mono_bytes = audioop.tomono(mono_bytes, _TARGET_SAMPLE_WIDTH_BYTES, 0.5, 0.5)

        if self._source_sample_rate == self._target_sample_rate:
            return mono_bytes

        converted, self._state = audioop.ratecv(
            mono_bytes,
            _TARGET_SAMPLE_WIDTH_BYTES,
            1,
            self._source_sample_rate,
            self._target_sample_rate,
            self._state,
        )
        return converted

    def reset(self) -> None:
        """Clear any incremental resampling state after a paused capture cycle."""
        self._state = None


def _write_pcm_wav(path: Path, *, sample_rate: int, channels: int, pcm_bytes: bytes) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(_TARGET_SAMPLE_WIDTH_BYTES)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm_bytes)


def _best_effort_presence(
    controller, mode: str, *, reason: str, log: Callable[[str], None]
) -> None:
    try:
        controller.set_mode(mode, reason=reason)
    except (IntegrationError, TransportError) as exc:
        log(f"WARNING presence '{mode}' failed: {exc}")


class _AsyncPresenceUpdater:
    """Serialize best-effort presence updates off the live audio hot path."""

    def __init__(
        self,
        controller,
        *,
        log: Callable[[str], None],
    ) -> None:
        self._controller = controller
        self._log = log
        self._lock = Lock()
        self._enabled = True
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="pi5mic-presence",
        )

    def submit(self, mode: str, *, reason: str) -> None:
        with self._lock:
            if not self._enabled:
                return
        future = self._executor.submit(self._controller.set_mode, mode, reason=reason)
        future.add_done_callback(lambda completed: self._handle_result(mode, completed))

    def _handle_result(self, mode: str, future: Future[dict[str, Any]]) -> None:
        try:
            future.result()
        except (IntegrationError, TransportError) as exc:
            with self._lock:
                first_failure = self._enabled
                self._enabled = False
            self._log(f"WARNING presence '{mode}' failed: {exc}")
            if first_failure:
                self._log(
                    "WARNING OpenClaw presence updates will be skipped for the rest of this "
                    "listener session."
                )
        except Exception as exc:  # pragma: no cover - defensive background path
            with self._lock:
                first_failure = self._enabled
                self._enabled = False
            self._log(f"WARNING presence '{mode}' failed unexpectedly: {exc}")
            if first_failure:
                self._log(
                    "WARNING OpenClaw presence updates will be skipped for the rest of this "
                    "listener session."
                )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)


class VoiceInputLoop:
    """Run the always-on wake-word -> transcribe -> dispatch loop."""

    def __init__(
        self,
        *,
        config: dict[str, Any],
        config_path: Path,
        state_paths: VoiceInputRuntimePaths,
        status_callback: Callable[[dict[str, Any]], None] | None = None,
        event_logger: Callable[[str], None] | None = None,
        detail_logger: Callable[[str], None] | None = None,
    ) -> None:
        self._config = config
        self._config_path = config_path
        self._state_paths = state_paths
        self._status_callback = status_callback
        self._log = event_logger or (lambda _message: None)
        self._detail = detail_logger or (lambda _message: None)
        self._last_listener_state: str | None = None

    def _publish(self, **updates: Any) -> None:
        payload = update_voiceinput_state(self._state_paths, **updates)
        if self._status_callback is not None:
            self._status_callback(payload)

    def _publish_listener(self, listener: MicListener, **updates: Any) -> None:
        snapshot = listener.snapshot()
        payload = {"listener_state": snapshot.state.value, **updates}
        if snapshot.last_error is not None:
            payload["last_error"] = snapshot.last_error
        self._publish(**payload)
        self._last_listener_state = snapshot.state.value

    def _sync_listener_state(self, listener: MicListener) -> None:
        snapshot = listener.snapshot()
        if snapshot.state.value != self._last_listener_state:
            self._publish_listener(listener)

    def _process_capture(
        self,
        *,
        listener: MicListener,
        request_id: str,
        capture_pcm: bytes,
        sample_rate: int,
        stt_backend,
        transport,
        presence_updater,
    ) -> None:
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="pi5mic-voiceinput-",
                suffix=".wav",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
            _write_pcm_wav(
                temp_path,
                sample_rate=sample_rate,
                channels=1,
                pcm_bytes=capture_pcm,
            )

            listener.mark_transcribing(request_id)
            self._publish_listener(listener)
            transcription = stt_backend.transcribe(temp_path)
            self._log(
                f"Transcribed voice request ({len(transcription.text)} chars, backend={transcription.backend})."
            )
            self._detail(f"Transcript: {transcription.text}")

            if transport is not None:
                if presence_updater is not None:
                    presence_updater.submit("thinking", reason="pi5mic.voiceinput.dispatch")
                listener.mark_dispatching(request_id)
                self._publish_listener(listener)
                listener.mark_waiting_for_reply(request_id)
                self._publish_listener(listener)
                dispatch_result = transport.dispatch(transcription.text)
                reply_length = len(dispatch_result.reply_text or "")
                self._log(f"OpenClaw reply received ({reply_length} chars).")
                if dispatch_result.reply_text:
                    self._detail(f"OpenClaw reply: {dispatch_result.reply_text}")

            listener.complete(request_id)
            self._publish_listener(
                listener,
                cycles_completed=read_voiceinput_state(self._state_paths)["cycles_completed"] + 1,
                last_completed_at=_utcnow_iso(),
                last_error=None,
            )
        except NoSpeechDetectedError:
            listener.complete(request_id)
            self._publish_listener(
                listener,
                last_completed_at=_utcnow_iso(),
                last_error=None,
            )
            self._log(
                "No spoken command was detected after the wake word. The listener is re-arming."
            )
        except (
            ConfigError,
            DeviceError,
            IntegrationError,
            ListenerBusyError,
            RecordingError,
            STTError,
            TransportError,
            WakeWordError,
            ValueError,
        ) as exc:
            listener.fail(request_id, str(exc))
            self._publish_listener(listener, last_error=str(exc))
            self._log(f"ERROR voice cycle failed: {exc}")
            listener.reset()
            listener.arm()
            self._publish_listener(listener)
        finally:
            if presence_updater is not None:
                presence_updater.submit("idle", reason="pi5mic.voiceinput.idle")
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def run(self, stop_event: Event) -> None:
        """Run the live voice-input loop until the stop event is set."""
        normalized = normalize_voiceinput_config(self._config)
        audio_config = self._config["audio"]
        from pi5mic.cli._common import (
            build_openclaw_transport,
            build_presence_controller,
            build_stt_backend,
        )

        stt_backend = build_stt_backend(self._config)
        profile = str(self._config.get("profile", "standalone"))
        transport = None
        presence_updater = None
        if profile == "openclaw":
            transport = build_openclaw_transport(
                self._config,
                session_strategy_override=normalized["session_strategy"],
            )
            if bool(self._config.get("integration", {}).get("presence_enabled", True)):
                presence_updater = _AsyncPresenceUpdater(
                    build_presence_controller(self._config),
                    log=self._log,
                )

        detector = build_wakeword_detector(self._config)
        listener = MicListener(cooldown_seconds=normalized["cooldown_seconds"])
        listener.arm()
        self._publish(
            running=True,
            pid=os.getpid(),
            mode="running",
            profile=profile,
            config_file=str(self._config_path),
            session_strategy=normalized["session_strategy"],
            wakeword_backend=normalized["backend"],
            wakeword_keyword=normalized["keyword"],
            started_at=_utcnow_iso(),
            last_error=None,
        )
        self._publish_listener(listener)

        sd = _get_sounddevice()
        resolved_device, actual_rate, device_info, warning = resolve_supported_input_settings(
            selector=audio_config.get("input_device"),
            sample_rate=int(audio_config["sample_rate"]),
            channels=int(audio_config["channels"]),
        )
        if warning:
            self._log(warning)
        device_label = (
            f"{device_info.name} [{device_info.index}]"
            if device_info is not None
            else f"default ({resolved_device if resolved_device is not None else 'auto'})"
        )
        self._log(
            f"Voice input armed on {device_label} at {actual_rate} Hz with wake word '{normalized['keyword']}'."
        )

        resampler = _AudioResampler(
            source_sample_rate=actual_rate,
            source_channels=int(audio_config["channels"]),
            target_sample_rate=detector.sample_rate,
        )
        frame_bytes = detector.frame_length * _TARGET_SAMPLE_WIDTH_BYTES
        stop_after_silent_frames = max(
            1,
            math.ceil(
                normalized["silence_timeout_seconds"] * detector.sample_rate / detector.frame_length
            ),
        )
        vad = SilenceStopDetector(
            rms_threshold=normalized["vad_rms_threshold"],
            stop_after_silent_frames=stop_after_silent_frames,
        )
        max_capture_bytes = int(
            normalized["max_capture_seconds"] * detector.sample_rate * _TARGET_SAMPLE_WIDTH_BYTES
        )

        frame_buffer = bytearray()
        capture_pcm = bytearray()
        active_request_id: str | None = None
        capturing = False
        overflow_streak = 0

        try:
            while not stop_event.is_set():
                pending_capture: bytes | None = None
                pending_request_id: str | None = None
                recovered_from_overflow = False
                try:
                    with sd.RawInputStream(
                        samplerate=actual_rate,
                        blocksize=int(audio_config["block_size"]),
                        device=resolved_device,
                        channels=int(audio_config["channels"]),
                        dtype="int16",
                        latency=_DEFAULT_STREAM_LATENCY,
                    ) as stream:
                        while not stop_event.is_set():
                            self._sync_listener_state(listener)
                            data, overflowed = stream.read(int(audio_config["block_size"]))
                            if overflowed:
                                overflow_streak += 1
                                self._log(
                                    "WARNING audio overflow detected while monitoring the microphone."
                                )
                                frame_buffer.clear()
                                resampler.reset()
                                if overflow_streak >= _OVERFLOW_RECOVERY_THRESHOLD:
                                    recovered_from_overflow = True
                                    self._log(
                                        "WARNING repeated microphone overflows detected; "
                                        "recreating the live input stream."
                                    )
                                    if capturing and active_request_id is not None:
                                        overflow_message = (
                                            "Microphone audio overflow interrupted the active voice "
                                            "capture. The listener is re-arming."
                                        )
                                        listener.fail(active_request_id, overflow_message)
                                        self._publish_listener(
                                            listener,
                                            last_error=overflow_message,
                                        )
                                        listener.reset()
                                        listener.arm()
                                        self._publish_listener(listener)
                                    active_request_id = None
                                    capture_pcm.clear()
                                    vad.reset()
                                    capturing = False
                                    detector.reset()
                                    break
                                continue

                            overflow_streak = 0
                            frame_buffer.extend(resampler.convert(data))

                            while len(frame_buffer) >= frame_bytes:
                                frame = bytes(frame_buffer[:frame_bytes])
                                del frame_buffer[:frame_bytes]

                                if capturing and active_request_id is not None:
                                    capture_pcm.extend(frame)
                                    vad_result = vad.process(frame)
                                    if (
                                        len(capture_pcm) >= max_capture_bytes
                                        or vad_result.should_stop
                                    ):
                                        self._log(
                                            "Wake-word capture complete; starting transcription."
                                        )
                                        pending_capture = bytes(capture_pcm)
                                        pending_request_id = active_request_id
                                        active_request_id = None
                                        capture_pcm.clear()
                                        vad.reset()
                                        capturing = False
                                        frame_buffer.clear()
                                        resampler.reset()
                                        detector.reset()
                                        break
                                else:
                                    if not listener.can_accept_trigger():
                                        continue

                                    wake = detector.process(list(memoryview(frame).cast("h")))
                                    if wake.detected:
                                        snapshot = listener.start_listening()
                                        active_request_id = snapshot.active_request_id
                                        capture_pcm.clear()
                                        vad.reset()
                                        capturing = True
                                        if presence_updater is not None:
                                            presence_updater.submit(
                                                "listening",
                                                reason="pi5mic.voiceinput.listening",
                                            )
                                        current_state = read_voiceinput_state(self._state_paths)
                                        self._publish_listener(
                                            listener,
                                            wakeword_hits=current_state["wakeword_hits"] + 1,
                                            last_triggered_at=_utcnow_iso(),
                                            last_error=None,
                                        )
                                        self._log("Wake word detected; recording voice command.")

                                if pending_capture is not None:
                                    break

                            if pending_capture is not None:
                                break
                except Exception as exc:
                    raise RecordingError(
                        f"Always-on voice input could not read from the live microphone stream: {exc}"
                    ) from exc

                if stop_event.is_set():
                    break

                if recovered_from_overflow:
                    self._log("Voice input recovered and is waiting for the next wake word.")
                    continue

                if pending_capture is None or pending_request_id is None:
                    continue

                self._process_capture(
                    listener=listener,
                    request_id=pending_request_id,
                    capture_pcm=pending_capture,
                    sample_rate=detector.sample_rate,
                    stt_backend=stt_backend,
                    transport=transport,
                    presence_updater=presence_updater,
                )
                if not stop_event.is_set():
                    self._log("Voice input cycle finished; waiting for the next wake word.")
        finally:
            if presence_updater is not None:
                presence_updater.submit("idle", reason="pi5mic.voiceinput.stopped")
                presence_updater.shutdown()
            detector.close()
            self._publish(
                running=False,
                pid=None,
                mode="stopped",
                listener_state="idle",
            )
