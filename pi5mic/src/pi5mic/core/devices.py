"""Audio device helpers for pi5mic."""

from __future__ import annotations

from typing import Any, cast

from pi5mic.core.audio_backend import load_sounddevice
from pi5mic.errors import DeviceError
from pi5mic.models import AudioDeviceInfo


def _get_sounddevice():
    return load_sounddevice(
        purpose="microphone discovery and status checks",
        error_factory=DeviceError,
    )


def list_input_devices() -> list[AudioDeviceInfo]:
    """Return all discovered audio devices that support input."""
    sd = _get_sounddevice()
    try:
        raw_devices = cast(list[dict[str, Any]], sd.query_devices())
    except Exception as exc:  # pragma: no cover - backend error path
        raise DeviceError(f"Could not query audio devices: {exc}") from exc

    devices: list[AudioDeviceInfo] = []
    for index, raw in enumerate(raw_devices):
        max_input_channels = int(raw.get("max_input_channels", 0))
        if max_input_channels <= 0:
            continue
        samplerate = raw.get("default_samplerate")
        default_samplerate = float(samplerate) if samplerate is not None else None
        devices.append(
            AudioDeviceInfo(
                index=index,
                name=str(raw.get("name", f"input-{index}")),
                max_input_channels=max_input_channels,
                default_samplerate=default_samplerate,
                hostapi=int(raw["hostapi"]) if "hostapi" in raw else None,
            )
        )
    return devices


def _coerce_device_index(candidate: object) -> int | None:
    """Convert a sounddevice device selector into an integer index when possible."""
    if candidate in (None, -1):
        return None
    if isinstance(candidate, bool):
        return int(candidate)
    try:
        return int(candidate)
    except (TypeError, ValueError) as exc:
        raise DeviceError(
            f"Could not interpret the default input device returned by sounddevice: {candidate!r}"
        ) from exc


def get_default_input_device() -> int | None:
    """Return the default input device index, if available."""
    sd = _get_sounddevice()
    default_device = getattr(sd.default, "device", None)

    if default_device is None:
        return None

    try:
        candidate = default_device[0]
    except (TypeError, IndexError, KeyError):
        candidate = default_device

    return _coerce_device_index(candidate)


def get_input_device_info(selector: int | str | None) -> AudioDeviceInfo | None:
    """Return device info for the given selector or the default input device."""
    devices = list_input_devices()
    if selector is None or selector == "":
        default_index = get_default_input_device()
        if default_index is None:
            return None
        selector = default_index

    resolved_index = resolve_input_device(selector)
    if resolved_index is None:
        return None
    for device in devices:
        if device.index == resolved_index:
            return device
    raise DeviceError(f"No input device found with index {resolved_index}.")


def get_recommended_sample_rate(
    selector: int | str | None,
    *,
    fallback_rate: int,
) -> int:
    """Return a sensible sample-rate default for the selected input device."""
    try:
        device = get_input_device_info(selector)
    except DeviceError:
        return fallback_rate

    if device is None or device.default_samplerate is None:
        return fallback_rate
    suggested = int(round(device.default_samplerate))
    return suggested if suggested > 0 else fallback_rate


def resolve_supported_input_settings(
    *,
    selector: int | str | None,
    sample_rate: int,
    channels: int,
    dtype: str = "int16",
) -> tuple[int | None, int, AudioDeviceInfo | None, str | None]:
    """Validate the requested input settings and fall back to device defaults when needed."""
    sd = _get_sounddevice()
    resolved_device = resolve_input_device(selector)
    device_info = get_input_device_info(resolved_device)

    try:
        sd.check_input_settings(
            device=resolved_device,
            channels=channels,
            dtype=dtype,
            samplerate=float(sample_rate),
        )
        return resolved_device, sample_rate, device_info, None
    except Exception as exc:
        requested_error = str(exc).strip()

    recommended_rate = get_recommended_sample_rate(
        resolved_device,
        fallback_rate=sample_rate,
    )
    if recommended_rate != sample_rate:
        try:
            sd.check_input_settings(
                device=resolved_device,
                channels=channels,
                dtype=dtype,
                samplerate=float(recommended_rate),
            )
            device_label = (
                f"{device_info.name} [{device_info.index}]"
                if device_info is not None
                else "the default input device"
            )
            warning = (
                f"Configured sample rate {sample_rate} Hz is not supported by {device_label}. "
                f"Using {recommended_rate} Hz instead."
            )
            return resolved_device, recommended_rate, device_info, warning
        except Exception:
            pass

    device_label = (
        f"{device_info.name} [{device_info.index}]"
        if device_info is not None
        else "the default input device"
    )
    suggestion = f" Try {recommended_rate} Hz." if recommended_rate != sample_rate else ""
    raise DeviceError(
        f"Configured sample rate {sample_rate} Hz is not supported by {device_label}: "
        f"{requested_error}.{suggestion}"
    )


def resolve_input_device(selector: int | str | None) -> int | None:
    """Resolve a device selector into a concrete input-device index."""
    if selector is None or selector == "":
        return None

    devices = list_input_devices()
    if isinstance(selector, int):
        for device in devices:
            if device.index == selector:
                return device.index
        raise DeviceError(f"No input device found with index {selector}.")

    selector_text = str(selector).strip()
    if selector_text.isdigit():
        return resolve_input_device(int(selector_text))

    exact_matches = [
        device for device in devices if device.name.casefold() == selector_text.casefold()
    ]
    if len(exact_matches) == 1:
        return exact_matches[0].index
    if len(exact_matches) > 1:
        raise DeviceError(f"Multiple input devices matched the name '{selector_text}'.")

    fuzzy_matches = [
        device for device in devices if selector_text.casefold() in device.name.casefold()
    ]
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0].index
    if len(fuzzy_matches) > 1:
        raise DeviceError(
            f"Multiple input devices matched '{selector_text}': "
            + ", ".join(device.name for device in fuzzy_matches)
        )

    raise DeviceError(f"No input device matched '{selector_text}'.")
