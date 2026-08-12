from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "validate_face_recognition_backend.py"
_SPEC = importlib.util.spec_from_file_location("validate_face_recognition_backend", _SCRIPT_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"could not load {_SCRIPT_PATH}")
_MODULE: Any = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
validate_backend = _MODULE.validate_backend


class _Classifier:
    def __init__(self, _path: str, *, empty: bool = False) -> None:
        self._empty = empty

    def empty(self) -> bool:
        return self._empty


def test_face_recognition_dependency_accepts_required_opencv_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cascade = tmp_path / "haarcascade_frontalface_alt2.xml"
    cascade.touch()
    module = SimpleNamespace(
        __version__="4.14.0",
        __file__="/test/cv2/__init__.py",
        data=SimpleNamespace(haarcascades=f"{tmp_path}/"),
        CascadeClassifier=_Classifier,
    )
    monkeypatch.setattr(importlib, "import_module", lambda _name: module)

    assert validate_backend()["status"] == "ready"


def test_face_recognition_dependency_rejects_incompatible_opencv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = SimpleNamespace(
        __version__="5.0.0",
        __file__="/test/cv2/__init__.py",
        data=SimpleNamespace(haarcascades="/test/cv2/data/"),
    )
    monkeypatch.setattr(importlib, "import_module", lambda _name: module)

    with pytest.raises(RuntimeError, match="opencv-python-headless>=4.8,<5"):
        validate_backend()
