"""Tests for optional wake-word backends."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from pi5mic.errors import WakeWordError
from pi5mic.wakeword.openwakeword import OpenWakeWordDetector


class _FakeModel:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.reset_called = False
        self._results = iter(
            [
                {"ninja": 0.10},
                {"ninja": 0.91},
            ]
        )

    def predict(self, pcm_frame):
        del pcm_frame
        return next(self._results)

    def reset(self):
        self.reset_called = True


class _FakeArray(list):
    @property
    def ndim(self) -> int:
        return 1

    @property
    def shape(self) -> tuple[int]:
        return (len(self),)

    def reshape(self, *_shape):
        return self


def test_openwakeword_requires_model_file() -> None:
    with pytest.raises(WakeWordError, match="model file not found"):
        OpenWakeWordDetector(keyword="ninja", model_path="/missing/ninja.tflite")


def test_openwakeword_rejects_placeholder_extension_only_path() -> None:
    with pytest.raises(WakeWordError, match="incomplete"):
        OpenWakeWordDetector(keyword="ninja", model_path=".tflite")


def test_openwakeword_process_and_close(monkeypatch, tmp_path) -> None:
    model_path = tmp_path / "ninja.tflite"
    model_path.write_bytes(b"fake-model")
    fake_package = types.ModuleType("openwakeword")
    fake_model_module = types.ModuleType("openwakeword.model")
    captured: dict[str, object] = {}
    model = _FakeModel()

    def _fake_model_factory(**kwargs):
        captured.update(kwargs)
        return model

    fake_model_module.Model = _fake_model_factory
    fake_package.model = fake_model_module
    monkeypatch.setitem(sys.modules, "openwakeword", fake_package)
    monkeypatch.setitem(sys.modules, "openwakeword.model", fake_model_module)
    monkeypatch.setitem(
        sys.modules,
        "numpy",
        types.SimpleNamespace(
            asarray=lambda value, dtype=None: _FakeArray(value),
            int16="int16",
        ),
    )

    detector = OpenWakeWordDetector(
        keyword="ninja",
        model_path=model_path,
        threshold=0.5,
        vad_threshold=0.2,
        enable_noise_suppression=True,
        inference_framework="tflite",
    )

    miss = detector.process([0] * detector.frame_length)
    hit = detector.process([0] * detector.frame_length)

    assert captured["wakeword_models"] == [str(Path(model_path))]
    assert captured["vad_threshold"] == 0.2
    assert captured["enable_speex_noise_suppression"] is True
    assert captured["inference_framework"] == "tflite"
    assert miss.detected is False
    assert miss.score == 0.10
    assert hit.detected is True
    assert hit.keyword == "ninja"
    assert hit.score == 0.91

    detector.close()
    assert model.reset_called is True
