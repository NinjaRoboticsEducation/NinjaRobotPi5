"""whisper.cpp speech-to-text backend."""

from __future__ import annotations

import audioop
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path

from pi5mic.core.system_info import is_raspberry_pi
from pi5mic.errors import NoSpeechDetectedError, STTError
from pi5mic.install.whisper_cpp import resolve_model_path, resolve_whisper_cpp_command
from pi5mic.models import TranscriptionResult

from .base import SpeechToTextBackend

_DEFAULT_PI_THREADS = 2
_TARGET_WAV_SAMPLE_RATE = 16_000


def recommend_whisper_threads(configured_threads: int | None = None) -> int | None:
    """Return a stable thread count for the current machine."""
    if configured_threads is not None:
        if configured_threads <= 0:
            raise STTError("whisper.cpp thread count must be greater than 0.")
        return configured_threads

    if is_raspberry_pi():
        cpu_count = os.cpu_count() or 1
        return 2 if cpu_count >= _DEFAULT_PI_THREADS else 1
    return None


def describe_whisper_runtime(configured_threads: int | None = None) -> str:
    """Return a short human-readable runtime description."""
    effective_threads = recommend_whisper_threads(configured_threads)
    if effective_threads is None:
        thread_text = "automatic"
    elif configured_threads is None:
        thread_text = f"{effective_threads} (safe Raspberry Pi default)"
    else:
        thread_text = str(effective_threads)

    return f"threads={thread_text}, wav normalization={_TARGET_WAV_SAMPLE_RATE} Hz mono"


def _maybe_prepare_wav_for_whisper(source: Path, work_dir: Path) -> Path:
    """Downmix/resample WAV input into a lighter 16 kHz mono file when needed."""
    if source.suffix.lower() not in {".wav", ".wave"}:
        return source

    try:
        with wave.open(str(source), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frames = handle.readframes(handle.getnframes())
    except (wave.Error, EOFError):
        return source

    if channels not in {1, 2}:
        return source

    normalized = False
    if sample_width != 2:
        frames = audioop.lin2lin(frames, sample_width, 2)
        sample_width = 2
        normalized = True

    if channels == 2:
        frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
        channels = 1
        normalized = True

    if sample_rate != _TARGET_WAV_SAMPLE_RATE:
        frames, _state = audioop.ratecv(
            frames,
            sample_width,
            channels,
            sample_rate,
            _TARGET_WAV_SAMPLE_RATE,
            None,
        )
        sample_rate = _TARGET_WAV_SAMPLE_RATE
        normalized = True

    if not normalized:
        return source

    prepared = work_dir / f"{source.stem}.pi5mic.wav"
    with wave.open(str(prepared), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(sample_width)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)
    return prepared


class WhisperCppBackend(SpeechToTextBackend):
    """Run local batch transcription through `whisper-cli`."""

    def __init__(
        self,
        *,
        command: str | Path | None,
        model_path: str | Path,
        language: str = "auto",
        translate_to_english: bool = False,
        threads: int | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self.command = resolve_whisper_cpp_command(command)
        self.model_path = resolve_model_path(model_path)
        self.language = language
        self.translate_to_english = translate_to_english
        self.threads = recommend_whisper_threads(threads)
        self.timeout_seconds = timeout_seconds

    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        """Transcribe an audio file through whisper.cpp."""
        source = Path(audio_path).expanduser().resolve()
        if not source.is_file():
            raise STTError(f"Audio file not found: {source}")

        with tempfile.TemporaryDirectory(prefix="pi5mic-whispercpp-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            output_prefix = temp_dir / source.stem
            prepared_source = _maybe_prepare_wav_for_whisper(source, temp_dir)
            command = [
                str(self.command),
                "-m",
                str(self.model_path),
                "-f",
                str(prepared_source),
                "-ojf",
                "-of",
                str(output_prefix),
                "-l",
                self.language,
                "-np",
            ]
            if self.threads is not None:
                command.extend(["-t", str(self.threads)])
            if self.translate_to_english:
                command.append("-tr")

            try:
                result = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise STTError("whisper.cpp transcription timed out.") from exc
            except OSError as exc:
                raise STTError(f"Could not start whisper.cpp: {exc}") from exc

            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
                raise STTError(f"whisper.cpp transcription failed: {stderr}")

            json_path = Path(f"{output_prefix}.json")
            if not json_path.exists():
                raise STTError("whisper.cpp completed without producing a JSON transcript.")

            with json_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)

        text = _extract_transcript_text(payload)
        language = payload.get("language")
        return TranscriptionResult(
            text=text,
            backend="whisper_cpp",
            model=self.model_path.name,
            language=str(language) if language is not None else None,
            raw=payload,
        )


def _extract_transcript_text(payload: dict[str, object]) -> str:
    direct_text = payload.get("text")
    if isinstance(direct_text, str):
        stripped_text = direct_text.strip()
        if stripped_text:
            return stripped_text
        raise NoSpeechDetectedError("whisper.cpp did not detect spoken text in the audio clip.")

    saw_segment_collection = False
    for key in ("transcription", "segments"):
        value = payload.get(key)
        if isinstance(value, list):
            saw_segment_collection = True
            parts = []
            for item in value:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"].strip())
            text = " ".join(part for part in parts if part).strip()
            if text:
                return text

    if saw_segment_collection or "result" in payload:
        raise NoSpeechDetectedError("whisper.cpp did not detect spoken text in the audio clip.")

    raise STTError("whisper.cpp JSON output did not contain transcript text.")
