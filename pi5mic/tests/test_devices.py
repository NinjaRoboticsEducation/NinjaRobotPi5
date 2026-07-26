"""Tests for pi5mic audio-device helpers."""

from __future__ import annotations

import builtins

import pytest

from pi5mic.core import devices as devices_module
from pi5mic.errors import DeviceError


class _FakeDefault:
    def __init__(self, device):
        self.device = device


class _FakeInputOutputPair:
    def __init__(self, input_value, output_value) -> None:
        self._pair = [input_value, output_value]

    def __getitem__(self, index):
        return self._pair[index]


class _FakeSoundDevice:
    def __init__(self, devices, default_device=(2, 9), *, invalid_rates=None) -> None:
        self._devices = devices
        self.default = _FakeDefault(default_device)
        self._invalid_rates = set() if invalid_rates is None else set(invalid_rates)

    def query_devices(self):
        return list(self._devices)

    def check_input_settings(self, *, device=None, channels=None, dtype=None, samplerate=None):
        if samplerate in self._invalid_rates:
            raise ValueError("Invalid sample rate [PaErrorCode -9997]")


def test_list_input_devices_filters_output_only(monkeypatch) -> None:
    fake_devices = [
        {"name": "Speaker", "max_input_channels": 0, "default_samplerate": 48_000.0},
        {"name": "USB Mic", "max_input_channels": 1, "default_samplerate": 16_000.0},
        {"name": "HAT Mic", "max_input_channels": 2, "default_samplerate": 44_100.0},
    ]
    monkeypatch.setattr(
        devices_module,
        "_get_sounddevice",
        lambda: _FakeSoundDevice(fake_devices),
    )

    devices = devices_module.list_input_devices()

    assert [device.name for device in devices] == ["USB Mic", "HAT Mic"]
    assert devices[0].index == 1
    assert devices[1].max_input_channels == 2


def test_get_default_input_device_handles_tuple(monkeypatch) -> None:
    monkeypatch.setattr(
        devices_module,
        "_get_sounddevice",
        lambda: _FakeSoundDevice([], default_device=(4, 8)),
    )

    assert devices_module.get_default_input_device() == 4


def test_get_default_input_device_handles_input_output_pair(monkeypatch) -> None:
    monkeypatch.setattr(
        devices_module,
        "_get_sounddevice",
        lambda: _FakeSoundDevice([], default_device=_FakeInputOutputPair(6, 9)),
    )

    assert devices_module.get_default_input_device() == 6


def test_resolve_input_device_supports_index_and_name(monkeypatch) -> None:
    fake_devices = [
        {"name": "USB Microphone", "max_input_channels": 1, "default_samplerate": 16_000.0},
        {"name": "Desk Mic", "max_input_channels": 1, "default_samplerate": 48_000.0},
    ]
    monkeypatch.setattr(
        devices_module,
        "_get_sounddevice",
        lambda: _FakeSoundDevice(fake_devices),
    )

    assert devices_module.resolve_input_device(0) == 0
    assert devices_module.resolve_input_device("1") == 1
    assert devices_module.resolve_input_device("Desk Mic") == 1
    assert devices_module.resolve_input_device("USB") == 0


def test_resolve_input_device_rejects_ambiguous_name(monkeypatch) -> None:
    fake_devices = [
        {"name": "USB Mic A", "max_input_channels": 1, "default_samplerate": 16_000.0},
        {"name": "USB Mic B", "max_input_channels": 1, "default_samplerate": 16_000.0},
    ]
    monkeypatch.setattr(
        devices_module,
        "_get_sounddevice",
        lambda: _FakeSoundDevice(fake_devices),
    )

    with pytest.raises(DeviceError, match="Multiple input devices matched"):
        devices_module.resolve_input_device("USB")


def test_resolve_input_device_rejects_missing_device(monkeypatch) -> None:
    monkeypatch.setattr(
        devices_module,
        "_get_sounddevice",
        lambda: _FakeSoundDevice([]),
    )

    with pytest.raises(DeviceError, match="No input device found with index 5"):
        devices_module.resolve_input_device(5)


def test_get_sounddevice_reports_missing_portaudio(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sounddevice":
            raise OSError("PortAudio library not found")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(DeviceError, match="PortAudio library not found"):
        devices_module._get_sounddevice()


def test_resolve_supported_input_settings_falls_back_to_device_default(monkeypatch) -> None:
    fake_devices = [
        {"name": "USB Mic", "max_input_channels": 1, "default_samplerate": 48_000.0},
    ]
    monkeypatch.setattr(
        devices_module,
        "_get_sounddevice",
        lambda: _FakeSoundDevice(fake_devices, invalid_rates={16_000.0, 16_000}),
    )

    resolved_device, actual_rate, device_info, warning = (
        devices_module.resolve_supported_input_settings(
            selector=0,
            sample_rate=16_000,
            channels=1,
        )
    )

    assert resolved_device == 0
    assert actual_rate == 48_000
    assert device_info is not None
    assert "Using 48000 Hz instead" in str(warning)
