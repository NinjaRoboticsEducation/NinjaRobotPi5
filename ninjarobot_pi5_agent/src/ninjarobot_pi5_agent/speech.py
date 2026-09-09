"""Optional local Piper synthesis; all audible output stays behind the IDE boundary."""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tempfile
import wave
from pathlib import Path
from typing import Any, Protocol

from ninjarobot_pi5_ide.audio_output import wav_duration
from ninjarobot_pi5_ide.audio_process import run_audio_process
from ninjarobot_pi5_ide.config import SpeechOutputConfig


class SpeechIDE(Protocol):
    async def speech_health(self) -> dict[str, Any]: ...
    async def speech_outputs(self) -> list[dict[str, str]]: ...
    async def play_speech(
        self, audio: bytes, *, generation: int | None = None
    ) -> dict[str, Any]: ...
    async def stop_speech(self) -> None: ...


class LocalSynthesizer:
    def __init__(self, config: SpeechOutputConfig) -> None:
        self.config = config

    def _paths(self, language: str) -> tuple[Path, Path]:
        if language not in {"en", "zh"}:
            raise ValueError("speech_language_unavailable")
        model = self.config.english_model if language == "en" else self.config.chinese_model
        if not model:
            raise ValueError("speech_model_not_configured")
        python = Path(self.config.piper_python).expanduser()
        path = Path(model).expanduser()
        if not python.is_file() or not os.access(python, os.X_OK):
            raise ValueError("piper_not_installed")
        if not path.is_file() or not Path(str(path) + ".json").is_file():
            raise ValueError("speech_model_missing")
        metadata_path = Path(str(path) + ".json")
        if metadata_path.stat().st_size > 100_000:
            raise ValueError("speech_model_config_too_large")
        metadata = json.loads(metadata_path.read_text())
        code = str((metadata.get("language") or {}).get("code", ""))
        if not code.startswith(language + "_"):
            raise ValueError("speech_model_language_mismatch")
        return python, path

    def status(self, language: str) -> dict[str, Any]:
        try:
            self._paths(language)
            return {
                "ready": True,
                "engine": "piper",
                "language": language,
                "detail": "Local files present; synthesis requires an actual test.",
            }
        except (OSError, ValueError, TypeError, AttributeError):
            return {
                "ready": False,
                "engine": "piper",
                "language": language,
                "reason": "check_piper_and_language_model",
            }

    async def synthesize(self, text: str, language: str) -> bytes:
        python, model = self._paths(language)
        # Private audio exists only for this call, never in the checkout or conversation store.
        with tempfile.TemporaryDirectory(prefix="ninjarobot-speech-") as directory:
            output = Path(directory) / "reply.wav"
            await run_audio_process(
                [str(python), "-m", "piper", "-m", str(model), "-f", str(output)],
                input_data=(text + "\n").encode("utf-8"),
                timeout=self.config.synthesis_timeout_seconds,
                output_limit=65536,
                output_file=output,
            )
            if not output.is_file() or output.stat().st_size > 8_000_000:
                raise ValueError("speech_audio_missing_or_large")
            audio = output.read_bytes()
            wav_duration(audio)
            return audio


class SimulatedSynthesizer(LocalSynthesizer):
    """Exercise coordination without loading models or invoking external programs."""

    def status(self, language: str) -> dict[str, Any]:
        return {"ready": True, "simulated": True, "language": language}

    async def synthesize(self, text: str, language: str) -> bytes:
        if language not in {"en", "zh"}:
            raise ValueError("speech_language_unavailable")
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
            writer.writeframes(b"\0\0" * 1600)
        return buffer.getvalue()


def spoken_text(text: str, limit: int) -> str:
    # Do not read fenced code, URL targets or presentation/phoneme markup aloud.
    text = re.sub(r"```.*?```", " Code omitted. ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", " link omitted ", text)
    text = re.sub(r"\[\[.*?\]\]", "", text, flags=re.S)
    text = re.sub(r"[<>`*_#]", "", text)
    return " ".join(text.split())[:limit].strip()


class SpeechService:
    def __init__(
        self,
        config: SpeechOutputConfig,
        ide: SpeechIDE,
        *,
        synthesizer: LocalSynthesizer | None = None,
    ) -> None:
        self.config = config
        self.ide = ide
        self.synthesizer = synthesizer or LocalSynthesizer(config)
        self.enabled = config.enabled
        self.language: str = config.language
        self._jobs: set[asyncio.Task[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()
        self._closed = False
        self._last: dict[str, Any] = {"status": "idle"}

    async def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "language": self.language,
            "pending": len(self._jobs),
            "synthesis": self.synthesizer.status(self.language),
            "playback": await self.ide.speech_health(),
            "last_result": dict(self._last),
        }

    async def control(self, operation: str) -> dict[str, Any]:
        if operation == "status":
            return await self.status()
        if operation == "outputs":
            return {"outputs": await self.ide.speech_outputs()}
        if operation == "on":
            if self._closed:
                raise RuntimeError("speech_service_closed")
            self.enabled = True
        elif operation == "off":
            self.enabled = False
            await self.stop()
        elif operation == "stop":
            await self.stop()
        elif operation in {"en", "zh"}:
            await self.stop()
            self.language = operation
        else:
            raise ValueError("Use speech on, off, stop, status, outputs, en or zh")
        return {
            "enabled": self.enabled,
            "language": self.language,
            "notice": "Service-session setting only; persisted microphone settings are unchanged.",
        }

    async def speak(self, text: str, *, language: str | None = None) -> dict[str, Any]:
        if self._closed or not self.enabled:
            return {"status": "disabled", "played": False}
        if len(self._jobs) >= 4:
            return {"status": "busy", "played": False}
        visible = spoken_text(text, self.config.max_characters)
        if not visible:
            return {"status": "empty", "played": False}

        async def work() -> dict[str, Any]:
            acquired = False
            # Bind output generation before queueing, so safety/foreground interruption
            # also invalidates work waiting behind another utterance.
            health = await self.ide.speech_health()
            if not health.get("ready"):
                return {"status": "output_unavailable", "played": False}
            try:
                async with asyncio.timeout(5):
                    await self._lock.acquire()
                    acquired = True
                if self._closed or not self.enabled:
                    return {"status": "disabled", "played": False}
                audio = await self.synthesizer.synthesize(visible, language or self.language)
                result = await self.ide.play_speech(audio, generation=health.get("generation"))
                return {
                    **result,
                    "status": "played" if result.get("played") else "simulated",
                    "shortened": len(text) > self.config.max_characters,
                }
            finally:
                if acquired:
                    self._lock.release()

        job = asyncio.create_task(work(), name="local-spoken-output")
        self._jobs.add(job)
        try:
            result = await job
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
            result = {"status": "cancelled", "played": False}
        except Exception:
            result = {
                "status": "failed",
                "played": False,
                "reason": "speech_unavailable_or_interrupted; text retained",
            }
        finally:
            self._jobs.discard(job)
        self._last = result
        return result

    async def stop(self) -> None:
        for job in tuple(self._jobs):
            job.cancel()
        await self.ide.stop_speech()
        await asyncio.gather(*tuple(self._jobs), return_exceptions=True)

    async def close(self) -> None:
        self._closed = True
        self.enabled = False
        await self.stop()
