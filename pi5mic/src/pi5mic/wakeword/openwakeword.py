"""Optional openWakeWord wake-word backend."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from pi5mic.errors import WakeWordError
from pi5mic.install.openwakeword import resolve_openwakeword_model_path
from pi5mic.wakeword.base import WakeWordDetector, WakeWordResult


class OpenWakeWordDetector(WakeWordDetector):
    """Thin lazy-import wrapper around `openwakeword`."""

    def __init__(
        self,
        *,
        keyword: str,
        model_path: str | Path,
        threshold: float = 0.5,
        vad_threshold: float = 0.0,
        enable_noise_suppression: bool = False,
        inference_framework: str = "tflite",
    ) -> None:
        if not keyword.strip():
            raise WakeWordError("An openWakeWord keyword label is required.")
        if threshold <= 0 or threshold > 1:
            raise WakeWordError(
                "openWakeWord threshold must be greater than 0 and less than or equal to 1."
            )
        if vad_threshold < 0 or vad_threshold > 1:
            raise WakeWordError(
                "openWakeWord VAD threshold must be greater than or equal to 0 and less than or equal to 1."
            )

        resolved_model = resolve_openwakeword_model_path(model_path)
        try:
            from openwakeword.model import Model
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise WakeWordError(
                "The 'openwakeword' package is required for always-on wake-word support."
            ) from exc

        self._keyword = keyword.strip()
        self._model_name = resolved_model.stem
        self._threshold = float(threshold)
        self._frame_length = 1280
        self._sample_rate = 16000
        try:
            self._model = Model(
                wakeword_models=[str(resolved_model)],
                enable_speex_noise_suppression=enable_noise_suppression,
                vad_threshold=float(vad_threshold),
                inference_framework=inference_framework,
            )
        except Exception as exc:  # pragma: no cover - backend path
            raise WakeWordError(f"Could not initialize openWakeWord: {exc}") from exc

    @property
    def frame_length(self) -> int:
        """The number of PCM samples expected per frame."""
        return self._frame_length

    @property
    def sample_rate(self) -> int:
        """The expected sample rate for the backend."""
        return self._sample_rate

    def process(self, pcm_frame: Sequence[int]) -> WakeWordResult:
        """Run one frame through openWakeWord."""
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise WakeWordError(
                "The 'numpy' package is required for always-on wake-word support."
            ) from exc

        try:
            frame = np.asarray(pcm_frame, dtype=np.int16)
        except Exception as exc:  # pragma: no cover - defensive conversion path
            raise WakeWordError(
                f"Could not convert the wake-word frame into PCM audio: {exc}"
            ) from exc

        if frame.ndim != 1:
            frame = frame.reshape(-1)

        if frame.shape[0] != self._frame_length:
            raise WakeWordError(
                f"openWakeWord expects {self._frame_length} PCM samples per frame, got {frame.shape[0]}."
            )

        try:
            prediction = self._model.predict(frame)
        except Exception as exc:  # pragma: no cover - backend path
            raise WakeWordError(f"openWakeWord processing failed: {exc}") from exc

        score = float(prediction.get(self._model_name, 0.0))
        if score < self._threshold:
            return WakeWordResult(detected=False, keyword=self._keyword, score=score)

        return WakeWordResult(
            detected=True,
            keyword_index=0,
            keyword=self._keyword,
            score=score,
        )

    def reset(self) -> None:
        """Reset the rolling openWakeWord state between wake-word cycles."""
        reset = getattr(self._model, "reset", None)
        if callable(reset):
            reset()

    def close(self) -> None:
        """Release backend state."""
        self.reset()
