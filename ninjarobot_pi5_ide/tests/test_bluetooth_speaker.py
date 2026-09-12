from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from ninjarobot_pi5_ide.bluetooth_setup import (
    install_service,
    reconnect_once,
    save_selection,
    service_text,
)
from ninjarobot_pi5_ide.bluetooth_speaker import (
    DEVICE,
    BluetoothError,
    BlueZSpeaker,
    SpeakerDevice,
    speaker_output,
)
from ninjarobot_pi5_ide.config import BluetoothSpeakerConfig, SpeechOutputConfig
from ninjarobot_pi5_ide.config_import import (
    default_robot_config,
    load_effective_config,
    save_robot_config,
)

ADDRESS = "12:34:56:78:9A:BC"
NODE = "bluez_output.12_34_56_78_9A_BC.2"
DEVICE_ROW = SpeakerDevice(
    "/org/bluez/hci0/dev_12_34_56_78_9A_BC", ADDRESS, "Speaker", True, True, True
)


def test_save_selection_preserves_speech_and_detects_concurrent_edits(tmp_path):
    path = tmp_path / "private" / "robot.toml"
    config = default_robot_config().model_copy(
        update={
            "speech_output": SpeechOutputConfig(
                enabled=True,
                english_model="/private/voice.onnx",
                chinese_model="/private/zh.onnx",
                volume=0.75,
                max_characters=350,
            )
        }
    )
    save_robot_config(config, path, overwrite=False)
    original = path.read_bytes()
    assert load_effective_config(path) == config
    save_selection(path, original, config, ADDRESS, "hci0", NODE)
    saved = load_effective_config(path)
    assert saved.speech_output == config.speech_output.model_copy(update={"output_node": NODE})
    assert saved.hardware == config.hardware
    assert saved.voice_input == config.voice_input
    assert saved.bluetooth_speaker.address == ADDRESS
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.with_name(path.name + ".before-speaker").read_bytes() == original
    with pytest.raises(BluetoothError, match="changed"):
        save_selection(path, original, config, ADDRESS, "hci0", NODE)


def test_output_never_falls_back_to_another_speaker():
    async def exercise():
        rows = [{"info": {"props": {"media.class": "Audio/Sink", "node.name": NODE}}}]
        runner = AsyncMock(return_value=json.dumps(rows).encode())
        assert await speaker_output(ADDRESS, runner=runner) == NODE
        runner.return_value = json.dumps(
            [{"info": {"props": {"media.class": "Audio/Sink", "node.name": "alsa_output.default"}}}]
        ).encode()
        with pytest.raises(BluetoothError, match="No unique"):
            await speaker_output(ADDRESS, runner=runner)
        runner.return_value = json.dumps(rows + rows).encode()
        with pytest.raises(BluetoothError, match="No unique"):
            await speaker_output(ADDRESS, runner=runner)

    asyncio.run(exercise())


def test_reconnect_has_no_pairing_or_scanning_and_closes_on_failure():
    async def exercise():
        backend = SimpleNamespace(start=AsyncMock(), close=AsyncMock(), connect=AsyncMock())
        config = default_robot_config().model_copy(
            update={
                "bluetooth_speaker": BluetoothSpeakerConfig(address=ADDRESS, auto_reconnect=True)
            }
        )
        output = AsyncMock(return_value=NODE)
        assert (
            await reconnect_once(config, backend_factory=lambda _: backend, output_resolver=output)
            == "ready"
        )
        backend.connect.assert_awaited_once_with(ADDRESS)
        backend.close.assert_awaited_once()
        backend.close.reset_mock()
        backend.connect.side_effect = TimeoutError()
        with pytest.raises(TimeoutError):
            await reconnect_once(config, backend_factory=lambda _: backend, output_resolver=output)
        backend.close.assert_awaited_once()
        assert (
            await reconnect_once(default_robot_config(), backend_factory=lambda _: pytest.fail())
            == "disabled"
        )

    asyncio.run(exercise())


def test_untrusted_device_is_not_repaired_by_background_connection():
    async def exercise():
        backend = BlueZSpeaker()
        backend.devices = AsyncMock(
            return_value=(SpeakerDevice(DEVICE_ROW.path, ADDRESS, "Speaker", True, False, False),)
        )
        backend.call = AsyncMock()
        with pytest.raises(BluetoothError, match="paired and trusted"):
            await backend.connect(ADDRESS)
        backend.call.assert_not_awaited()

    asyncio.run(exercise())


def test_failed_pairing_cancels_pending_pairing():
    async def exercise():
        backend = BlueZSpeaker()
        backend.devices = AsyncMock(
            return_value=(SpeakerDevice(DEVICE_ROW.path, ADDRESS, "Speaker", False, False, False),)
        )
        backend.call = AsyncMock(side_effect=[[], TimeoutError(), []])
        with pytest.raises(TimeoutError):
            await backend.connect(ADDRESS, pair=True)
        assert backend.call.call_args.args == (DEVICE_ROW.path, DEVICE, "CancelPairing")

    asyncio.run(exercise())


def test_service_preview_is_inert_and_install_is_user_only(tmp_path):
    async def exercise():
        runner = AsyncMock(return_value=b"")
        path = tmp_path / "robot.toml"
        directory = tmp_path / "units"
        unit = await install_service(path, directory=directory, runner=runner)
        assert not directory.exists()
        runner.assert_not_awaited()
        assert "ninjarobot_pi5_ide.bluetooth_setup" in unit
        assert "ninjarobot-agent" not in unit and "/etc/" not in unit
        await install_service(path, apply=True, directory=directory, runner=runner)
        assert all(call.args[0][:2] == ["systemctl", "--user"] for call in runner.call_args_list)
        assert "%%" in service_text(tmp_path / "100%.toml")
        assert "$$" in service_text(tmp_path / "$file.toml")
        with pytest.raises(ValueError):
            service_text(tmp_path / "bad\nfile.toml")

    asyncio.run(exercise())


def test_wizard_selects_snapshot_saves_only_after_audio_and_cleans_up(tmp_path, monkeypatch):
    from ninjarobot_pi5_ide.bluetooth_setup import connect_wizard

    async def exercise():
        path = tmp_path / "robot.toml"
        save_robot_config(default_robot_config(), path, overwrite=False)
        before = path.read_bytes()
        backend = SimpleNamespace(
            start=AsyncMock(),
            close=AsyncMock(),
            scan=AsyncMock(return_value=(DEVICE_ROW,)),
            connect=AsyncMock(),
        )
        prompt = AsyncMock(side_effect=["1", "n"])
        runner = AsyncMock(return_value=b"")
        resolver = AsyncMock(return_value=NODE)
        await connect_wizard(
            path,
            backend_factory=lambda *args, **kwargs: backend,
            prompt=prompt,
            runner=runner,
            output_resolver=resolver,
        )
        backend.connect.assert_awaited_once_with(ADDRESS, pair=True)
        resolver.assert_awaited_once_with(ADDRESS)
        backend.close.assert_awaited_once()
        assert load_effective_config(path).speech_output.output_node == NODE
        assert all("enable" not in call.args[0] for call in runner.call_args_list)
        path.write_bytes(before)
        backend.close.reset_mock()
        backend.connect.side_effect = BluetoothError("Rejected")
        with pytest.raises(BluetoothError):
            await connect_wizard(
                path,
                backend_factory=lambda *args, **kwargs: backend,
                prompt=AsyncMock(return_value="1"),
                runner=runner,
                output_resolver=resolver,
            )
        assert path.read_bytes() == before
        backend.close.assert_awaited_once()

    asyncio.run(exercise())


def test_pairing_does_not_authorize_another_device_or_service():
    dbus_fast = pytest.importorskip("dbus_fast")

    async def exercise():
        backend = BlueZSpeaker()
        backend.api = dbus_fast
        backend.bus = SimpleNamespace(send=AsyncMock())
        backend.selected = DEVICE_ROW.path
        for path, member, extra in [
            ("/org/bluez/hci0/dev_FF_FF_FF_FF_FF_FF", "RequestAuthorization", []),
            (DEVICE_ROW.path, "AuthorizeService", ["unknown-service"]),
        ]:
            request = dbus_fast.Message(
                path="/org/ninjarobot/SpeakerPairing",
                interface="org.bluez.Agent1",
                member=member,
                signature="os" if extra else "o",
                body=[path, *extra],
                sender=":1.2",
                serial=1,
            )
            await backend._answer_pairing(request)
            assert backend.bus.send.call_args.args[0].message_type is dbus_fast.MessageType.ERROR
        backend._bluez_owner = ":1.2"
        request = dbus_fast.Message(
            path="/org/ninjarobot/SpeakerPairing",
            interface="org.bluez.Agent1",
            member="RequestAuthorization",
            signature="o",
            body=[DEVICE_ROW.path],
            sender=":1.999",
            serial=2,
        )
        assert backend._agent_message(request) is None
        assert not backend._callbacks

    asyncio.run(exercise())
