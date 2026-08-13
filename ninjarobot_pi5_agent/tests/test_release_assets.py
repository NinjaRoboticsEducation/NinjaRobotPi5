"""Release-asset provenance and package-data tests."""

from __future__ import annotations

import hashlib
import json
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

EXPECTED_WAKE_MODEL_SHA256 = "12c87f97ea41b08a356631dc1162af455aa30ac27ff6235963a31d0f5e39016a"
EXPECTED_WAKE_MODEL_SIZE = 206_276


def test_public_release_versions_and_packaged_phase_8_assets_are_consistent() -> None:
    import ninjarobot_pi5_agent
    import ninjarobot_pi5_ide

    assert ninjarobot_pi5_agent.__version__ == "1.0.0"
    assert ninjarobot_pi5_ide.__version__ == "1.0.0"
    assert version("ninjarobot-pi5-agent") == "1.0.0"
    assert version("ninjarobot-pi5-ide") == "1.0.0"
    agent = files("ninjarobot_pi5_agent")
    for relative in (
        ("web_static", "i18n", "en.json"),
        ("web_static", "i18n", "ja.json"),
        ("web_static", "i18n", "zh-TW.json"),
        ("web_static", "i18n", "zh-CN.json"),
        ("deployment", "ninjarobot-agent.service.in"),
        ("deployment", "ninjarobot-poweroff"),
        ("deployment", "ninjarobot-poweroff.sudoers.in"),
    ):
        assert agent.joinpath(*relative).is_file()


def test_packaged_wake_model_matches_approved_manifest() -> None:
    asset = files("ninjarobot_pi5_ide").joinpath("assets", "hey_Ninja.onnx")
    model_bytes = asset.read_bytes()

    assert len(model_bytes) == EXPECTED_WAKE_MODEL_SIZE
    assert hashlib.sha256(model_bytes).hexdigest() == EXPECTED_WAKE_MODEL_SHA256


def test_source_and_packaged_wake_models_match_manifest() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest_path = root / "docs" / "validation" / "phase-8-wake-model.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = root / manifest["source_asset"]
    packaged = root / manifest["asset"]

    assert manifest["wake_phrase"] == "Hey Ninja"
    assert manifest["format"] == "onnx"
    assert manifest["owner_approved_redistribution"] is True
    assert manifest["runtime_boot_download_allowed"] is False
    assert source.read_bytes() == packaged.read_bytes()
    assert source.stat().st_size == manifest["size_bytes"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["sha256"]


def test_openwakeword_runtime_assets_match_manifest_and_are_packaged() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (root / "docs/validation/phase-8-openwakeword-assets.json").read_text(encoding="utf-8")
    )

    assert manifest["runtime_boot_download_allowed"] is False
    for record in manifest["assets"]:
        source = root / record["path"]
        packaged = files("ninjarobot_pi5_ide").joinpath("assets", "openwakeword", source.name)
        source_bytes = source.read_bytes()
        packaged_bytes = packaged.read_bytes()
        assert source_bytes == packaged_bytes
        assert len(source_bytes) == record["size_bytes"]
        assert hashlib.sha256(source_bytes).hexdigest() == record["sha256"]
