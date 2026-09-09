"""Local speech lifecycle coverage without loading a voice or opening devices."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from ninjarobot_pi5_agent.speech import (
    LocalSynthesizer,
    SimulatedSynthesizer,
    SpeechService,
    spoken_text,
)
from ninjarobot_pi5_ide.audio_output import wav_duration
from ninjarobot_pi5_ide.config import SpeechOutputConfig


def make_service(*, enabled=True):
    config = SpeechOutputConfig(enabled=enabled)
    ide = AsyncMock()
    ide.speech_health.return_value = {"ready": True, "generation": 7}
    ide.play_speech.return_value = {"played": True}
    synth = AsyncMock(spec=LocalSynthesizer)
    synth.synthesize.return_value = b"fake wav"
    return SpeechService(config, ide, synthesizer=synth), ide, synth


def test_disabled_and_missing_output_never_synthesize():
    async def scenario():
        service, ide, synth = make_service(enabled=False)
        assert (await service.speak("Hello"))["status"] == "disabled"
        await service.control("on")
        ide.speech_health.return_value = {"ready": False}
        assert (await service.speak("Hello"))["status"] == "output_unavailable"
        synth.synthesize.assert_not_awaited()
        ide.play_speech.assert_not_awaited()

    asyncio.run(scenario())


def test_success_preserves_language_and_generation_and_sanitizes():
    async def scenario():
        service, ide, synth = make_service()
        result = await service.speak(
            "Hello [friend](https://example.com) ```secret code```", language="zh"
        )
        assert result["played"]
        synth.synthesize.assert_awaited_once_with("Hello friend Code omitted.", "zh")
        ide.play_speech.assert_awaited_once_with(b"fake wav", generation=7)
        assert spoken_text("[[phonemes]] <hello> https://example.com", 100) == "hello link omitted"
        assert len(spoken_text("x" * 600, 500)) == 500
        with pytest.raises(ValueError):
            await service.control("ja")

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["stop", "off", "zh", "close"])
def test_control_cancels_current_and_queued_synthesis_without_cancelling_text_caller(operation):
    async def scenario():
        service, ide, synth = make_service()
        entered = asyncio.Event()
        cleaned = asyncio.Event()

        async def blocked(*args):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        synth.synthesize.side_effect = blocked
        calls = [asyncio.create_task(service.speak("hello")) for _ in range(4)]
        await asyncio.wait_for(entered.wait(), 1)
        assert (await service.speak("overflow"))["status"] == "busy"
        if operation == "close":
            await service.close()
        else:
            await service.control(operation)
        results = await asyncio.gather(*calls)
        assert all(result["status"] == "cancelled" for result in results)
        assert cleaned.is_set()
        assert not service._jobs
        ide.play_speech.assert_not_awaited()
        assert service.enabled == (operation in {"stop", "zh"})

    asyncio.run(scenario())


def test_parent_cancellation_and_synthesis_failure_do_not_claim_playback():
    async def scenario():
        service, ide, synth = make_service()
        synth.synthesize.side_effect = RuntimeError("private process diagnostic")
        result = await service.speak("private reply")
        assert result["status"] == "failed" and not result["played"]
        assert "private" not in str(result)
        entered = asyncio.Event()

        async def blocked(*args):
            entered.set()
            await asyncio.Event().wait()

        synth.synthesize.side_effect = blocked
        task = asyncio.create_task(service.speak("reply"))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not service._jobs
        ide.play_speech.assert_not_awaited()

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", [False, True])
def test_temporary_synthesis_files_are_removed(monkeypatch, tmp_path, failure):
    async def scenario():
        config = SpeechOutputConfig()
        synth = LocalSynthesizer(config)
        monkeypatch.setattr(
            synth, "_paths", lambda language: (Path("/fake/python"), Path("/fake/model"))
        )
        seen = []

        async def runner(args, **kwargs):
            path = kwargs["output_file"]
            seen.append(path)
            assert path.parent.stat().st_mode & 0o077 == 0
            assert args[:3] == ["/fake/python", "-m", "piper"]
            assert kwargs["input_data"] == b"hello\n"
            path.write_bytes(await SimulatedSynthesizer(config).synthesize("hello", "en"))
            if failure:
                raise RuntimeError("synthesis failed")
            return b""

        monkeypatch.setattr("ninjarobot_pi5_agent.speech.run_audio_process", runner)
        if failure:
            with pytest.raises(RuntimeError):
                await synth.synthesize("hello", "en")
        else:
            assert wav_duration(await synth.synthesize("hello", "en")) == 0.1
        assert seen and not seen[0].parent.exists()

    asyncio.run(scenario())


def test_simulation_does_not_require_models_or_processes(monkeypatch):
    async def scenario():
        runner = AsyncMock(side_effect=AssertionError("external process in simulation"))
        monkeypatch.setattr("ninjarobot_pi5_agent.speech.run_audio_process", runner)
        synth = SimulatedSynthesizer(SpeechOutputConfig())
        assert synth.status("en")["simulated"]
        assert wav_duration(await synth.synthesize("hello", "en")) == 0.1
        runner.assert_not_awaited()

    asyncio.run(scenario())
