from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from ninjarobot_pi5_ide.config_import import DiscoveredConfig, load_effective_config

from ninjarobot_pi5_ide import audio_output, fusion, hardware_setup, microphone


def test_missing_embedded_output_never_saves_fabricated_sink(monkeypatch, tmp_path):
    monkeypatch.setattr(fusion, "require_fusion_driver", lambda: None)

    async def missing():
        return ""

    monkeypatch.setattr(audio_output, "discover_i2s_output_node", missing)
    path = tmp_path / "config.toml"
    with pytest.raises(RuntimeError, match="sound card missing"):
        asyncio.run(hardware_setup.configure_sunfounder_i2s_speaker(path))
    assert not path.exists()


def test_embedded_microphone_selection_does_not_record(monkeypatch, tmp_path):
    from ninjarobot_pi5_ide import config_import

    mic = tmp_path / "mic.json"
    path = tmp_path / "config.toml"
    monkeypatch.setattr(fusion, "require_fusion_driver", lambda: None)
    monkeypatch.setattr(
        config_import, "discover_pi5_configs", lambda: [DiscoveredConfig("pi5mic", mic, False)]
    )
    backend = SimpleNamespace(
        list_input_devices=lambda: [
            SimpleNamespace(name="snd_rpi_googlevoicehat_soundcar (hw:2,0)", max_input_channels=1)
        ]
    )
    monkeypatch.setattr(microphone, "_load_microphone_backend", lambda: backend)
    selected = fusion.configure_fusion_microphone(path)
    assert selected == "snd_rpi_googlevoicehat_soundcar"
    assert load_effective_config(path).hardware.microphone.device_selector == selected
    assert selected in mic.read_text()


def test_fusion_amp_never_uses_gpio_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(fusion, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="prerequisite"):
        fusion.set_fusion_speaker(True)
    assert not (tmp_path / "speaker").exists()
    (tmp_path / "version").write_text(fusion.VERSION)
    (tmp_path / "speaker").write_text("0")
    fusion.set_fusion_speaker(True)
    assert (tmp_path / "speaker").read_text() == "1\n"
    fusion.set_fusion_speaker(False)
    assert (tmp_path / "speaker").read_text() == "0\n"


def test_amplifier_enable_is_joined_before_cancel_cleanup(monkeypatch):
    import threading

    async def exercise():
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def set_amp(enabled):
            if enabled:
                entered.set()
                assert release.wait(2)
            calls.append(enabled)

        monkeypatch.setattr(fusion, "set_fusion_speaker", set_amp)

        async def playback():
            try:
                await fusion.set_fusion_speaker_async(True)
            finally:
                await fusion.set_fusion_speaker_async(False)

        task = asyncio.create_task(playback())
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert calls == []
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert calls == [True, False]

    asyncio.run(exercise())
