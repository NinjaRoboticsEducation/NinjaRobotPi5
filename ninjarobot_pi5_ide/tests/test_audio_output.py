"""Speech output tests use synthetic PCM and fake routing, never a speaker."""

import asyncio
import io
import json
import sys
import wave
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from ninjarobot_pi5_ide.audio_output import AudioOutput, wav_duration
from ninjarobot_pi5_ide.audio_process import run_audio_process
from ninjarobot_pi5_ide.config import SpeechOutputConfig


def audio():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        writer.writeframes(b"\0\0" * 1600)
    return buffer.getvalue()


class Microphone:
    @asynccontextmanager
    async def output_access(self):
        yield


@pytest.mark.parametrize("mode", ["success", "disconnect", "cancel", "busy", "paused_failure"])
def test_playback_cleanup_precedes_listener_restore(monkeypatch, mode):
    async def exercise():
        order = []
        started = asyncio.Event()
        voice = AsyncMock()
        voice.pause.side_effect = RuntimeError("busy") if mode == "paused_failure" else None
        voice.resume.side_effect = lambda: order.append("resume")
        probes = 0

        async def runner(args, **kwargs):
            nonlocal probes
            if args[0] == "pw-dump":
                probes += 1
                if mode == "disconnect" and probes > 1:
                    return b"[]"
                return json.dumps(
                    [
                        {
                            "info": {
                                "props": {
                                    "media.class": "Audio/Sink",
                                    "node.name": "bluez_output.test",
                                }
                            }
                        }
                    ]
                ).encode()
            assert "--target=bluez_output.test" in args
            assert kwargs["input_data"] == audio()
            started.set()
            try:
                if mode != "success":
                    await asyncio.Event().wait()
                return b""
            finally:
                order.append("playback_closed")

        @asynccontextmanager
        async def scene():
            yield

        monkeypatch.setattr("ninjarobot_pi5_ide.audio_output.shutil.which", lambda cmd: cmd)
        output = AudioOutput(
            SpeechOutputConfig(output_node="bluez_output.test", bluetooth_lead_in_seconds=0),
            voice=voice,
            microphone=Microphone(),
            permitted=lambda: True,
            scene=scene,
            runner=runner,
        )
        if mode == "paused_failure":
            with pytest.raises(RuntimeError, match="busy"):
                await output.play(audio())
            voice.resume.assert_not_awaited()
            assert not started.is_set()
            return
        task = asyncio.create_task(output.play(audio()))
        await asyncio.wait_for(started.wait(), 1)
        if mode == "busy":
            with pytest.raises(RuntimeError, match="busy"):
                await output.play(audio())
            await output.stop()
        if mode == "cancel":
            await output.stop()
        if mode in {"cancel", "busy"}:
            with pytest.raises(asyncio.CancelledError):
                await task
        elif mode == "disconnect":
            with pytest.raises(RuntimeError, match="disconnected"):
                await task
        else:
            assert (await task)["played"]
        assert order == ["playback_closed", "resume"]
        await output.close()

    asyncio.run(exercise())


def test_wav_validation_and_disabled_default():
    assert wav_duration(audio()) == 0.1
    assert not SpeechOutputConfig().enabled
    for payload in (b"bad", audio()[:-10], b"x" * 8_000_001):
        with pytest.raises((ValueError, wave.Error, EOFError)):
            wav_duration(payload)
    for node in ("auto", "0", "12", "x; touch file"):
        with pytest.raises(ValueError):
            SpeechOutputConfig(output_node=node)


def test_bounded_process_timeout_and_no_shell(tmp_path):
    async def exercise():
        result = await run_audio_process(
            [sys.executable, "-c", "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"],
            input_data=b"$(do not execute)",
        )
        assert result == b"$(do not execute)"
        with pytest.raises(TimeoutError):
            await run_audio_process(
                [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.05
            )
        with pytest.raises(RuntimeError, match="output_limit"):
            await run_audio_process([sys.executable, "-c", "print('x'*10000)"], output_limit=10)

    asyncio.run(exercise())


def test_foreground_priority_rejects_stale_synthesis_and_new_playback():
    async def scenario():
        @asynccontextmanager
        async def scene():
            yield

        output = AudioOutput(
            SpeechOutputConfig(),
            voice=AsyncMock(),
            microphone=Microphone(),
            permitted=lambda: True,
            scene=scene,
            simulated=True,
        )
        generation = output.generation
        async with output.foreground():
            with pytest.raises(RuntimeError, match="blocked"):
                await output.play(audio())
        with pytest.raises(RuntimeError, match="superseded"):
            await output.play(audio(), generation=generation)
        assert (await output.play(audio(), generation=output.generation))["simulated"]
        await output.close()
        with pytest.raises(RuntimeError, match="blocked"):
            await output.play(audio())

    asyncio.run(scenario())


@pytest.mark.parametrize("channels,rate", [(1, 16000), (1, 22050), (2, 48000)])
def test_startup_silence_preserves_every_original_sample(channels, rate):
    from ninjarobot_pi5_ide.audio_output import with_startup_silence

    raw = b"\x34\x12\x78\x56" * 1000 * channels
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(raw)
    original = buffer.getvalue()
    padded = with_startup_silence(original, 0.5)
    with wave.open(io.BytesIO(padded), "rb") as reader:
        assert reader.readframes(round(rate * 0.5)) == b"\0" * round(rate * 0.5) * channels * 2
        assert reader.readframes(reader.getnframes()) == raw
    assert wav_duration(padded) == pytest.approx(wav_duration(original) + 0.5)
    assert with_startup_silence(original, 0) == original
    with pytest.raises(ValueError):
        with_startup_silence(original, 3)


def test_bluetooth_profile_change_resolves_only_same_speaker(monkeypatch):
    async def exercise():
        node = "bluez_output.12_34_56_78_9A_BC.7"
        runner = AsyncMock(
            return_value=json.dumps(
                [{"info": {"props": {"media.class": "Audio/Sink", "node.name": node}}}]
            ).encode()
        )
        monkeypatch.setattr("ninjarobot_pi5_ide.audio_output.shutil.which", lambda cmd: cmd)
        output = AudioOutput(
            SpeechOutputConfig(output_node="bluez_output.12_34_56_78_9A_BC.1"),
            voice=AsyncMock(),
            microphone=Microphone(),
            permitted=lambda: True,
            scene=lambda: None,
            runner=runner,
        )
        assert (await output.health())["selected_output"] == node
        runner.return_value = json.dumps(
            [
                {
                    "info": {
                        "props": {
                            "media.class": "Audio/Sink",
                            "node.name": "bluez_output.AA_BB_CC_DD_EE_FF.1",
                        }
                    }
                }
            ]
        ).encode()
        assert not (await output.health())["ready"]

    asyncio.run(exercise())
