"""Install and runtime helpers for openWakeWord."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pi5mic.errors import WakeWordError

SUPPORTED_MODEL_SUFFIXES = {".onnx", ".tflite"}
SUPPORTED_INFERENCE_FRAMEWORKS = {"auto", "onnx", "tflite"}


def is_placeholder_openwakeword_model_path(model_path: str | Path | None) -> bool:
    """Return True when the provided path only contains a bare model extension."""
    if model_path is None:
        return False
    raw_value = str(model_path).strip()
    if raw_value == "":
        return False
    return Path(raw_value).name.lower() in SUPPORTED_MODEL_SUFFIXES


def _import_openwakeword() -> Any:
    try:
        import openwakeword
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise WakeWordError(
            "The 'openwakeword' package is not installed. "
            "Install it with `uv sync --extra dev --extra voiceinput`."
        ) from exc

    return openwakeword


def resolve_openwakeword_model_path(model_path: str | Path | None) -> Path:
    """Resolve a custom openWakeWord model path."""
    if model_path is None or str(model_path).strip() == "":
        raise WakeWordError(
            "No openWakeWord model path is configured. "
            "Register one with `uv run pi5mic install openwakeword --model-path /path/to/ninja.tflite`."
        )
    if is_placeholder_openwakeword_model_path(model_path):
        raise WakeWordError(
            "The saved openWakeWord model path is incomplete. It points to only `.tflite` or "
            "`.onnx` without a real file name. Create or export a custom wake-word model such "
            "as `/path/to/hey_ninja.tflite`, then register it with "
            "`uv run pi5mic install openwakeword --model-path /path/to/hey_ninja.tflite`."
        )

    resolved = Path(model_path).expanduser().resolve()
    if not resolved.is_file():
        raise WakeWordError(f"openWakeWord model file not found: {resolved}")
    if resolved.suffix.lower() not in SUPPORTED_MODEL_SUFFIXES:
        raise WakeWordError("openWakeWord model files must end with `.tflite` or `.onnx`.")
    return resolved


def resolve_openwakeword_inference_framework(
    *,
    model_path: str | Path | None,
    configured_framework: str | None,
) -> str:
    """Resolve the effective openWakeWord inference framework."""
    configured = str(configured_framework or "auto").strip().lower() or "auto"
    if configured not in SUPPORTED_INFERENCE_FRAMEWORKS:
        raise WakeWordError("wakeword.inference_framework must be one of: auto, tflite, onnx.")

    resolved_path = resolve_openwakeword_model_path(model_path)
    if configured == "auto":
        return "onnx" if resolved_path.suffix.lower() == ".onnx" else "tflite"

    expected_suffix = f".{configured}"
    if resolved_path.suffix.lower() != expected_suffix:
        raise WakeWordError(
            "The configured openWakeWord inference framework does not match the model file "
            f"extension: expected `{expected_suffix}` but got `{resolved_path.suffix.lower()}`."
        )
    return configured


def get_openwakeword_resources_dir() -> Path:
    """Return the shared openWakeWord runtime resources directory."""
    openwakeword = _import_openwakeword()
    return Path(openwakeword.__file__).resolve().parent / "resources" / "models"


def get_openwakeword_runtime_asset_paths(
    *,
    inference_framework: str,
    include_vad: bool,
) -> list[Path]:
    """Return the shared runtime assets required by openWakeWord."""
    openwakeword = _import_openwakeword()
    resources_dir = get_openwakeword_resources_dir()
    paths: list[Path] = []

    for model_meta in openwakeword.FEATURE_MODELS.values():
        download_url = str(model_meta["download_url"])
        if inference_framework == "onnx":
            download_url = download_url.replace(".tflite", ".onnx")
        paths.append(resources_dir / Path(download_url).name)

    if include_vad:
        for model_meta in openwakeword.VAD_MODELS.values():
            download_url = str(model_meta["download_url"])
            paths.append(resources_dir / Path(download_url).name)

    return paths


def validate_openwakeword_runtime_assets(
    *,
    inference_framework: str,
    include_vad: bool,
) -> list[Path]:
    """Return any missing shared runtime assets needed by openWakeWord."""
    return [
        path
        for path in get_openwakeword_runtime_asset_paths(
            inference_framework=inference_framework,
            include_vad=include_vad,
        )
        if not path.is_file()
    ]


def ensure_openwakeword_runtime_assets(
    *,
    inference_framework: str,
    include_vad: bool,
) -> list[Path]:
    """Download any missing shared runtime assets needed by openWakeWord."""
    openwakeword = _import_openwakeword()
    try:
        from openwakeword.utils import download_file
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise WakeWordError(
            "openWakeWord is installed, but its download helper could not be imported."
        ) from exc

    resources_dir = get_openwakeword_resources_dir()
    try:
        resources_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WakeWordError(
            f"Could not create the openWakeWord resources directory: {resources_dir}"
        ) from exc

    downloaded: list[Path] = []

    for model_meta in openwakeword.FEATURE_MODELS.values():
        download_url = str(model_meta["download_url"])
        if inference_framework == "onnx":
            download_url = download_url.replace(".tflite", ".onnx")
        destination = resources_dir / Path(download_url).name
        if destination.is_file():
            continue
        try:
            download_file(download_url, str(resources_dir))
        except Exception as exc:  # pragma: no cover - network/download path
            raise WakeWordError(
                f"Could not download the shared openWakeWord runtime asset `{destination.name}`: {exc}"
            ) from exc
        downloaded.append(destination)

    if include_vad:
        for model_meta in openwakeword.VAD_MODELS.values():
            download_url = str(model_meta["download_url"])
            destination = resources_dir / Path(download_url).name
            if destination.is_file():
                continue
            try:
                download_file(download_url, str(resources_dir))
            except Exception as exc:  # pragma: no cover - network/download path
                raise WakeWordError(
                    f"Could not download the openWakeWord VAD asset `{destination.name}`: {exc}"
                ) from exc
            downloaded.append(destination)

    return downloaded
