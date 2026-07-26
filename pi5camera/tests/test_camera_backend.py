"""Tests for the camera backend (stub) and capture workflow."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from pi5camera.config.config_manager import CameraConfigManager
from pi5camera.core.camera_backend import StubCameraBackend, build_camera_backend
from pi5camera.core.capture import capture_photo
from pi5camera.errors import BackendNotAvailableError


def test_stub_backend_creates_valid_jpeg(tmp_path: Path) -> None:
    backend = StubCameraBackend(width=320, height=240)
    output = tmp_path / "stub.jpg"
    result = backend.capture(output)

    assert result.path == output.resolve()
    assert result.path.exists()
    assert result.metadata.get("stub") is True


def test_stub_backend_context_manager(tmp_path: Path) -> None:
    output = tmp_path / "ctx.jpg"
    with StubCameraBackend(width=160, height=120) as backend:
        result = backend.capture(output)
    assert result.path.exists()


def test_build_camera_backend_returns_stub_for_config(tmp_path: Path) -> None:
    manager = CameraConfigManager(tmp_path / "camera.json")
    config = manager.load()
    config["camera"]["backend"] = "stub"
    backend = build_camera_backend(config)
    assert isinstance(backend, StubCameraBackend)


def test_capture_photo_with_stub_backend(tmp_path: Path) -> None:
    manager = CameraConfigManager(tmp_path / "camera.json")
    config = manager.load()
    config["camera"]["backend"] = "stub"

    result = capture_photo(config)
    assert result.path.exists()
    assert result.path.suffix == ".jpg"


def test_capture_cli_reports_backend_unavailable_without_traceback(monkeypatch) -> None:
    capture_module = import_module("pi5camera.cli.capture_cmd")
    monkeypatch.setattr(
        capture_module,
        "load_manager",
        lambda _path: SimpleNamespace(config={}),
    )

    def unavailable(*_args, **_kwargs):
        raise BackendNotAvailableError("Picamera2 is unavailable")

    monkeypatch.setattr(capture_module, "capture_photo", unavailable)
    result = CliRunner().invoke(
        capture_module.capture_cmd,
        [],
        obj={"config_file": None},
    )

    assert result.exit_code == 1
    assert "Error: Picamera2 is unavailable" in result.output
    assert "Traceback" not in result.output
