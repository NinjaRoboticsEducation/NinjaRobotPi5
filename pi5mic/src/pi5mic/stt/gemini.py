"""Gemini batch speech-to-text backend."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from pi5mic.errors import STTError
from pi5mic.models import TranscriptionResult

from .base import SpeechToTextBackend

_TRANSCRIPTION_PROMPT = (
    "Transcribe this audio. Preserve the spoken language and return only the transcript text."
)
_DEFAULT_TIMEOUT_SECONDS = 60
_DEFAULT_RETRY_LIMIT = 2


def resolve_gemini_api_key() -> tuple[str, str]:
    """Return the configured Gemini API key and the env var that provided it."""
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if google_api_key:
        return "GOOGLE_API_KEY", google_api_key

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        return "GEMINI_API_KEY", gemini_api_key

    raise STTError(
        "Gemini credentials are not configured in the environment. "
        "Set GOOGLE_API_KEY or GEMINI_API_KEY before using the Gemini backend."
    )


def describe_gemini_env_help() -> str:
    """Return a short actionable Gemini credential hint."""
    return 'Example: export GEMINI_API_KEY="your_api_key_here"'


class GeminiBackend(SpeechToTextBackend):
    """Run batch audio transcription through the Gemini API."""

    def __init__(
        self,
        *,
        model: str = "gemini-2.5-flash",
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
        retry_limit: int = _DEFAULT_RETRY_LIMIT,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.retry_limit = retry_limit

    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        """Transcribe an audio file through Gemini."""
        source = Path(audio_path).expanduser().resolve()
        if not source.is_file():
            raise STTError(f"Audio file not found: {source}")

        _credential_name, api_key = resolve_gemini_api_key()

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise STTError(
                "The 'google-genai' package is required for Gemini transcription."
            ) from exc

        mime_type = mimetypes.guess_type(source.name)[0] or "audio/wav"
        if mime_type in {"audio/x-wav", "audio/vnd.wave"}:
            mime_type = "audio/wav"
        audio_bytes = source.read_bytes()
        retry_options = types.HttpRetryOptions(
            attempts=max(1, self.retry_limit + 1),
            initial_delay=1.0,
            max_delay=10.0,
        )
        http_options = types.HttpOptions(
            timeout=max(1, int(self.timeout_seconds * 1000)),
            retry_options=retry_options,
        )

        try:
            with genai.Client(api_key=api_key, http_options=http_options) as client:
                response = client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                        _TRANSCRIPTION_PROMPT,
                    ],
                )
        except Exception as exc:  # pragma: no cover - network/backend path
            raise STTError(f"Gemini transcription failed: {exc}") from exc

        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise STTError("Gemini did not return transcript text.")

        return TranscriptionResult(
            text=text.strip(),
            backend="gemini",
            model=self.model,
            raw={"mime_type": mime_type},
        )
