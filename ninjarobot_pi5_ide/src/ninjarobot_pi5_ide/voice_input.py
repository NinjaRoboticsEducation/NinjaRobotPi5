"""IDE-owned bounded wake-word, capture, and transcription state machine."""

from __future__ import annotations

import asyncio
import math
import os
import sys
import tempfile
import wave
from array import array
from collections.abc import Awaitable, Callable, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Protocol

from pydantic import Field, StringConstraints

from .models import ContractModel

VoiceErrorCode = Annotated[
    str,
    StringConstraints(min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_]*$"),
]
TranscriptHandler = Callable[[str, str], Awaitable[None]]
VoiceStatusHandler = Callable[["VoiceInputStatus"], Awaitable[None]]


class VoiceInputState(StrEnum):
    """Stable states for the single IDE-owned microphone listener."""

    DISABLED = "disabled"
    STARTING = "starting"
    LISTENING = "listening"
    DETECTED = "detected"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    DISPATCHING = "dispatching"
    COOLDOWN = "cooldown"
    PAUSED = "paused"
    DEGRADED = "degraded"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"


class VoiceInputStatus(ContractModel):
    """Privacy-safe listener status; transcripts and audio are never included."""

    enabled: bool
    state: VoiceInputState
    language: str
    model_loaded: bool = False
    wake_hits: Annotated[int, Field(ge=0)] = 0
    completed_cycles: Annotated[int, Field(ge=0)] = 0
    listening_indicator: bool = False
    last_error_code: VoiceErrorCode | None = None


class WakeWordResult(Protocol):
    """Minimum result returned by the approved pi5mic detector."""

    detected: bool
    score: float


class WakeWordDetector(Protocol):
    """Minimum approved wake detector interface consumed by V4."""

    @property
    def frame_length(self) -> int: ...

    @property
    def sample_rate(self) -> int: ...

    def process(self, pcm_frame: Sequence[int]) -> WakeWordResult: ...

    def reset(self) -> None: ...

    def close(self) -> None: ...


class VoiceAudioSource(Protocol):
    """One exclusive raw PCM source; implementation remains device-facing."""

    @property
    def sample_rate(self) -> int: ...

    async def start(self) -> None: ...

    async def read(self) -> tuple[bytes, bool]: ...

    async def close(self) -> None: ...


class VoiceTranscriber(Protocol):
    """Local transcription boundary shared with manual microphone capture."""

    async def transcribe(self, wav_path: Path, *, language: str) -> str: ...

    def available(self) -> bool: ...


DetectorFactory = Callable[[], WakeWordDetector]
AudioSourceFactory = Callable[[], VoiceAudioSource]


class VoiceInputError(RuntimeError):
    """Sanitized listener failure carrying a stable user-facing category."""

    def __init__(self, code: VoiceErrorCode) -> None:
        super().__init__(code)
        self.code = code


class VoiceInputController:
    """Own one wake stream and dispatch exactly one transcript per capture."""

    def __init__(
        self,
        *,
        detector_factory: DetectorFactory,
        audio_source_factory: AudioSourceFactory,
        transcriber: VoiceTranscriber,
        max_command_seconds: float,
        silence_stop_seconds: float,
        cooldown_seconds: float,
        vad_enabled: bool,
        silence_rms_threshold: int,
        language: str,
        retry_limit: int,
        startup_timeout_seconds: float = 10.0,
        transcript_handler: TranscriptHandler | None = None,
        status_handler: VoiceStatusHandler | None = None,
    ) -> None:
        if not 1.0 <= max_command_seconds <= 15.0:
            raise ValueError("voice max command duration must be from 1 through 15 seconds")
        if not 0.25 <= silence_stop_seconds <= 5.0:
            raise ValueError("voice silence stop must be from 0.25 through 5 seconds")
        if not 0.25 <= cooldown_seconds <= 10.0:
            raise ValueError("voice cooldown must be from 0.25 through 10 seconds")
        if silence_rms_threshold < 1:
            raise ValueError("voice silence RMS threshold must be positive")
        if language not in {"en", "ja", "zh-TW", "zh-CN"}:
            raise ValueError("voice language is unsupported")
        if not 0 <= retry_limit <= 5:
            raise ValueError("voice retry limit must be from 0 through 5")
        if not 0.05 <= startup_timeout_seconds <= 30.0:
            raise ValueError("voice startup timeout must be from 0.05 through 30 seconds")
        self._detector_factory = detector_factory
        self._audio_source_factory = audio_source_factory
        self._transcriber = transcriber
        self._max_command_seconds = max_command_seconds
        self._silence_stop_seconds = silence_stop_seconds
        self._cooldown_seconds = cooldown_seconds
        self._vad_enabled = vad_enabled
        self._silence_rms_threshold = silence_rms_threshold
        self._language = language
        self._retry_limit = retry_limit
        self._startup_timeout_seconds = startup_timeout_seconds
        self._transcript_handler = transcript_handler
        self._status_handler = status_handler
        self._status = VoiceInputStatus(
            enabled=False,
            state=VoiceInputState.DISABLED,
            language=language,
        )
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._resume_event = asyncio.Event()
        self._paused_event = asyncio.Event()
        self._startup_event = asyncio.Event()
        self._manual_pause_count = 0
        self._lifecycle_lock = asyncio.Lock()

    def bind_handlers(
        self,
        *,
        transcript_handler: TranscriptHandler,
        status_handler: VoiceStatusHandler,
    ) -> None:
        """Bind the agent boundary before activation without importing the agent."""
        if self._task is not None:
            raise RuntimeError("voice handlers cannot change while the listener is active")
        self._transcript_handler = transcript_handler
        self._status_handler = status_handler

    def status(self) -> dict[str, object]:
        """Return a synchronous status snapshot without probing the microphone."""
        return self._status.model_dump(mode="json")

    async def start(self) -> dict[str, object]:
        """Start and return only after the wake stream is confirmed listening."""
        async with self._lifecycle_lock:
            if self._task is not None and not self._task.done():
                if self._status.state is not VoiceInputState.STARTING:
                    return self.status()
            else:
                if self._transcript_handler is None or self._status_handler is None:
                    raise VoiceInputError("listener_not_bound")
                if not self._transcriber.available():
                    await self._set_status(
                        enabled=False,
                        state=VoiceInputState.FAILED,
                        last_error_code="transcriber_unavailable",
                    )
                    raise VoiceInputError("transcriber_unavailable")
                self._stop_event.clear()
                self._resume_event.set()
                self._paused_event.clear()
                self._startup_event.clear()
                await self._set_status(
                    enabled=True,
                    state=VoiceInputState.STARTING,
                    last_error_code=None,
                )
                self._task = asyncio.create_task(self._run(), name="ninjarobot-voice-input")
        try:
            await asyncio.wait_for(
                self._startup_event.wait(),
                timeout=self._startup_timeout_seconds,
            )
        except TimeoutError as exc:
            await self.stop()
            await self._set_status(
                enabled=False,
                state=VoiceInputState.FAILED,
                model_loaded=False,
                listening_indicator=False,
                last_error_code="listener_start_timeout",
            )
            raise VoiceInputError("listener_start_timeout") from exc

        status = self._status
        if status.state is VoiceInputState.LISTENING:
            return self.status()
        task = self._task
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        async with self._lifecycle_lock:
            if self._task is task:
                self._task = None
        code = status.last_error_code or "listener_start_cancelled"
        await self._set_status(
            enabled=False,
            state=VoiceInputState.FAILED,
            model_loaded=False,
            listening_indicator=False,
            last_error_code=code,
        )
        raise VoiceInputError(code)

    async def stop(self) -> dict[str, object]:
        """Stop the stream, discard partial audio, and release detector resources."""
        async with self._lifecycle_lock:
            task = self._task
            self._task = None
            if task is None:
                await self._set_status(
                    enabled=False,
                    state=VoiceInputState.DISABLED,
                    model_loaded=False,
                    listening_indicator=False,
                )
                return self.status()
            await self._set_status(
                enabled=False,
                state=VoiceInputState.STOPPING,
                listening_indicator=False,
            )
            self._stop_event.set()
            self._resume_event.set()
            self._startup_event.set()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
        except TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self._set_status(
            enabled=False,
            state=VoiceInputState.DISABLED,
            model_loaded=False,
            listening_indicator=False,
        )
        return self.status()

    async def pause(self) -> None:
        """Pause and release the stream for one explicit manual microphone user."""
        async with self._lifecycle_lock:
            self._manual_pause_count += 1
            if self._task is None or self._task.done():
                self._paused_event.set()
                return
            self._resume_event.clear()
            state = self._status.state
            if state not in {
                VoiceInputState.LISTENING,
                VoiceInputState.DETECTED,
                VoiceInputState.RECORDING,
            }:
                self._paused_event.set()
        try:
            await asyncio.wait_for(self._paused_event.wait(), timeout=2.0)
        except TimeoutError as exc:
            raise VoiceInputError("listener_pause_timeout") from exc

    async def resume(self) -> None:
        """Resume only after the final nested manual microphone user finishes."""
        async with self._lifecycle_lock:
            self._manual_pause_count = max(0, self._manual_pause_count - 1)
            if self._manual_pause_count > 0:
                return
            self._paused_event.clear()
            if self._task is not None and not self._task.done() and not self._stop_event.is_set():
                self._resume_event.set()

    async def _run(self) -> None:
        detector: WakeWordDetector | None = None
        failures = 0
        try:
            detector = await asyncio.to_thread(self._detector_factory)
            await self._set_status(model_loaded=True, last_error_code=None)
            while not self._stop_event.is_set():
                await self._resume_event.wait()
                if self._stop_event.is_set():
                    break
                try:
                    transcript = await self._listen_once(detector)
                    if transcript is None:
                        continue
                    failures = 0
                    await self._set_status(
                        state=VoiceInputState.DISPATCHING,
                        listening_indicator=False,
                    )
                    handler = self._transcript_handler
                    if handler is None:
                        raise VoiceInputError("listener_not_bound")
                    try:
                        await handler(transcript, self._language)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        raise VoiceInputError("dispatch_failed") from exc
                    await self._set_status(
                        state=VoiceInputState.COOLDOWN,
                        completed_cycles=self._status.completed_cycles + 1,
                    )
                    await self._wait_or_stop(self._cooldown_seconds)
                except VoiceInputError as exc:
                    failures += 1
                    await self._set_status(
                        state=(
                            VoiceInputState.FAILED
                            if failures > self._retry_limit
                            else VoiceInputState.DEGRADED
                        ),
                        listening_indicator=False,
                        last_error_code=exc.code,
                    )
                    if failures > self._retry_limit:
                        break
                    await self._wait_or_stop(min(float(2**failures), 10.0))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    failures += 1
                    code = _voice_error_code(exc)
                    await self._set_status(
                        state=(
                            VoiceInputState.FAILED
                            if failures > self._retry_limit
                            else VoiceInputState.DEGRADED
                        ),
                        listening_indicator=False,
                        last_error_code=code,
                    )
                    if failures > self._retry_limit:
                        break
                    await self._wait_or_stop(min(float(2**failures), 10.0))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._set_status(
                state=VoiceInputState.FAILED,
                listening_indicator=False,
                last_error_code=_voice_error_code(exc),
            )
        finally:
            if detector is not None:
                await asyncio.to_thread(detector.close)
            self._paused_event.set()
            if self._status.enabled and self._status.state is not VoiceInputState.FAILED:
                await self._set_status(
                    state=VoiceInputState.STOPPED,
                    listening_indicator=False,
                    model_loaded=False,
                )

    async def _listen_once(self, detector: WakeWordDetector) -> str | None:
        source = self._audio_source_factory()
        assembler: _PCMFrameAssembler | None = None
        capture = bytearray()
        capture_started = False
        speech_started = False
        silent_frames = 0
        try:
            await source.start()
            assembler = _PCMFrameAssembler(
                source_rate=source.sample_rate,
                target_rate=detector.sample_rate,
                frame_samples=detector.frame_length,
            )
            max_capture_bytes = int(self._max_command_seconds * detector.sample_rate * 2)
            silence_frames = max(
                1,
                math.ceil(
                    self._silence_stop_seconds * detector.sample_rate / detector.frame_length
                ),
            )
            self._paused_event.clear()
            await self._set_status(
                state=VoiceInputState.LISTENING,
                listening_indicator=True,
                last_error_code=None,
            )
            self._startup_event.set()
            while self._resume_event.is_set() and not self._stop_event.is_set():
                pcm, overflowed = await source.read()
                if overflowed:
                    raise VoiceInputError("audio_overflow")
                for frame in assembler.feed(pcm):
                    if capture_started:
                        capture.extend(frame)
                        if self._vad_enabled:
                            silent = _pcm_rms(frame) < self._silence_rms_threshold
                            if silent:
                                if speech_started:
                                    silent_frames += 1
                            else:
                                speech_started = True
                                silent_frames = 0
                        if len(capture) >= max_capture_bytes or (
                            self._vad_enabled and speech_started and silent_frames >= silence_frames
                        ):
                            return await self._transcribe(bytes(capture), detector.sample_rate)
                        continue
                    samples = _pcm_samples(frame)
                    wake = await asyncio.to_thread(detector.process, samples)
                    if wake.detected:
                        capture_started = True
                        capture.clear()
                        await self._set_status(
                            state=VoiceInputState.DETECTED,
                            listening_indicator=True,
                            wake_hits=self._status.wake_hits + 1,
                        )
                        await self._set_status(state=VoiceInputState.RECORDING)
            detector.reset()
            if not self._stop_event.is_set():
                await self._set_status(
                    state=VoiceInputState.PAUSED,
                    listening_indicator=False,
                )
            return None
        finally:
            await source.close()
            if not self._resume_event.is_set():
                self._paused_event.set()

    async def _transcribe(self, pcm: bytes, sample_rate: int) -> str:
        if not pcm:
            raise VoiceInputError("no_speech_detected")
        await self._set_status(
            state=VoiceInputState.TRANSCRIBING,
            listening_indicator=False,
        )
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="ninjarobot-voice-",
            suffix=".wav",
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        temporary.chmod(0o600)
        try:
            await asyncio.to_thread(_write_wav, temporary, pcm, sample_rate)
            transcript = (
                await self._transcriber.transcribe(
                    temporary,
                    language=_whisper_language(self._language),
                )
            ).strip()
            if not transcript:
                raise VoiceInputError("no_speech_detected")
            return transcript
        except VoiceInputError:
            raise
        except Exception as exc:
            raise VoiceInputError("transcription_failed") from exc
        finally:
            temporary.unlink(missing_ok=True)

    async def _set_status(self, **updates: object) -> None:
        payload = {**self._status.model_dump(mode="python"), **updates}
        self._status = VoiceInputStatus.model_validate(payload)
        if self._status.state is VoiceInputState.FAILED:
            self._startup_event.set()
        handler = self._status_handler
        if handler is not None:
            try:
                await handler(self._status)
            except Exception:
                # An interface subscriber must never terminate microphone ownership.
                return

    async def _wait_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except TimeoutError:
            return


class _PCMFrameAssembler:
    """Bounded streaming linear resampler and exact 80 ms frame assembler."""

    def __init__(self, *, source_rate: int, target_rate: int, frame_samples: int) -> None:
        if source_rate <= 0 or target_rate <= 0 or frame_samples <= 0:
            raise ValueError("PCM frame rates and size must be positive")
        self._source_rate = source_rate
        self._target_rate = target_rate
        self._frame_bytes = frame_samples * 2
        self._samples: list[int] = []
        self._position = 0.0
        self._output = bytearray()

    def feed(self, pcm: bytes) -> tuple[bytes, ...]:
        incoming = _pcm_samples(pcm)
        if self._source_rate == self._target_rate:
            self._output.extend(pcm)
        else:
            self._samples.extend(incoming)
            step = self._source_rate / self._target_rate
            while self._position + 1 < len(self._samples):
                left = int(self._position)
                fraction = self._position - left
                value = round(
                    self._samples[left] * (1.0 - fraction) + self._samples[left + 1] * fraction
                )
                self._output.extend(int(value).to_bytes(2, "little", signed=True))
                self._position += step
            consumed = int(self._position)
            if consumed:
                del self._samples[:consumed]
                self._position -= consumed
        frames: list[bytes] = []
        while len(self._output) >= self._frame_bytes:
            frames.append(bytes(self._output[: self._frame_bytes]))
            del self._output[: self._frame_bytes]
        return tuple(frames)


def _pcm_samples(pcm: bytes) -> list[int]:
    if len(pcm) % 2:
        raise VoiceInputError("invalid_pcm_frame")
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tolist()


def _pcm_rms(pcm: bytes) -> float:
    samples = _pcm_samples(pcm)
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def _write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm)


def _whisper_language(language: str) -> str:
    return "zh" if language in {"zh-TW", "zh-CN"} else language


def _voice_error_code(error: Exception) -> VoiceErrorCode:
    if isinstance(error, VoiceInputError):
        return error.code
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        return "dependency_unavailable"
    if isinstance(error, OSError):
        return "microphone_unavailable"
    return "listener_failed"
