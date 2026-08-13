"""Deterministic tests for the IDE-owned always-on voice state machine."""

from __future__ import annotations

import asyncio
from array import array
from pathlib import Path

import pytest
from ninjarobot_pi5_ide.voice_input import (
    VoiceInputController,
    VoiceInputError,
    VoiceInputState,
    VoiceInputStatus,
    _PCMFrameAssembler,
    _whisper_language,
)


class FakeWakeResult:
    def __init__(self, detected: bool) -> None:
        self.detected = detected
        self.score = 0.9 if detected else 0.1


class FakeDetector:
    frame_length = 1280
    sample_rate = 16_000

    def __init__(self, detections: list[bool]) -> None:
        self._detections = iter(detections)
        self.reset_count = 0
        self.closed = False

    def process(self, pcm_frame: list[int]) -> FakeWakeResult:
        assert len(pcm_frame) == self.frame_length
        return FakeWakeResult(next(self._detections, False))

    def reset(self) -> None:
        self.reset_count += 1

    def close(self) -> None:
        self.closed = True


class FakeSource:
    sample_rate = 16_000

    def __init__(self, frames: list[bytes], *, overflow_at: int | None = None) -> None:
        self._frames = frames
        self._index = 0
        self._overflow_at = overflow_at
        self.started = False
        self.closed = False

    async def start(self) -> None:
        self.started = True

    async def read(self) -> tuple[bytes, bool]:
        await asyncio.sleep(0)
        index = self._index
        self._index += 1
        frame = self._frames[index] if index < len(self._frames) else self._frames[-1]
        return frame, index == self._overflow_at

    async def close(self) -> None:
        self.closed = True


class HangingSource(FakeSource):
    def __init__(self) -> None:
        super().__init__([pcm_frame(0)])
        self._forever = asyncio.Event()

    async def start(self) -> None:
        self.started = True
        await self._forever.wait()


class FailingSource(FakeSource):
    async def start(self) -> None:
        self.started = True
        raise OSError("USB microphone unavailable")


class FakeTranscriber:
    def __init__(self, text: str = "move forward") -> None:
        self.text = text
        self.paths: list[Path] = []
        self.languages: list[str] = []

    def available(self) -> bool:
        return True

    async def transcribe(self, wav_path: Path, *, language: str) -> str:
        assert wav_path.is_file()
        self.paths.append(wav_path)
        self.languages.append(language)
        return self.text


def pcm_frame(value: int, *, samples: int = 1280) -> bytes:
    values = array("h", [value] * samples)
    return values.tobytes()


def build_controller(
    detector: FakeDetector,
    sources: list[FakeSource],
    transcriber: FakeTranscriber,
    transcripts: list[tuple[str, str]],
    completed: asyncio.Event,
    statuses: list[VoiceInputStatus],
    *,
    vad_enabled: bool = True,
    retry_limit: int = 2,
    language: str = "en",
    startup_timeout_seconds: float = 10.0,
) -> VoiceInputController:
    source_iter = iter(sources)

    async def handle_transcript(text: str, locale: str) -> None:
        transcripts.append((text, locale))
        completed.set()

    async def handle_status(status: VoiceInputStatus) -> None:
        statuses.append(status)

    controller = VoiceInputController(
        detector_factory=lambda: detector,
        audio_source_factory=lambda: next(source_iter),
        transcriber=transcriber,
        max_command_seconds=1.0,
        silence_stop_seconds=0.25,
        cooldown_seconds=0.25,
        vad_enabled=vad_enabled,
        silence_rms_threshold=200,
        language=language,
        retry_limit=retry_limit,
        startup_timeout_seconds=startup_timeout_seconds,
    )
    controller.bind_handlers(
        transcript_handler=handle_transcript,
        status_handler=handle_status,
    )
    return controller


def test_wake_capture_silence_stop_dispatches_once_and_deletes_audio() -> None:
    async def scenario() -> None:
        detector = FakeDetector([True])
        source = FakeSource(
            [
                pcm_frame(0),
                pcm_frame(1200),
                pcm_frame(0),
                pcm_frame(0),
                pcm_frame(0),
                pcm_frame(0),
            ]
        )
        transcriber = FakeTranscriber()
        transcripts: list[tuple[str, str]] = []
        statuses: list[VoiceInputStatus] = []
        completed = asyncio.Event()
        controller = build_controller(
            detector,
            [source],
            transcriber,
            transcripts,
            completed,
            statuses,
        )

        await controller.start()
        await asyncio.wait_for(completed.wait(), timeout=2.0)
        await controller.stop()

        assert transcripts == [("move forward", "en")]
        assert transcriber.languages == ["en"]
        assert all(not path.exists() for path in transcriber.paths)
        assert source.closed is True
        assert detector.closed is True
        states = {status.state for status in statuses}
        assert {
            VoiceInputState.LISTENING,
            VoiceInputState.DETECTED,
            VoiceInputState.RECORDING,
            VoiceInputState.TRANSCRIBING,
            VoiceInputState.DISPATCHING,
        } <= states

    asyncio.run(scenario())


def test_negative_frames_never_dispatch_and_stop_is_prompt() -> None:
    async def scenario() -> None:
        detector = FakeDetector([False] * 20)
        source = FakeSource([pcm_frame(0)])
        transcripts: list[tuple[str, str]] = []
        controller = build_controller(
            detector,
            [source],
            FakeTranscriber(),
            transcripts,
            asyncio.Event(),
            [],
        )

        await controller.start()
        await asyncio.sleep(0.02)
        await controller.stop()

        assert transcripts == []
        assert controller.status()["state"] == "disabled"

    asyncio.run(scenario())


def test_start_waits_for_listening_readiness() -> None:
    async def scenario() -> None:
        detector = FakeDetector([False])
        source = FakeSource([pcm_frame(0)])
        controller = build_controller(
            detector,
            [source],
            FakeTranscriber(),
            [],
            asyncio.Event(),
            [],
        )

        status = await controller.start()

        assert status["state"] == "listening"
        assert status["listening_indicator"] is True
        await controller.stop()

    asyncio.run(scenario())


def test_hanging_microphone_start_times_out_and_cleans_up() -> None:
    async def scenario() -> None:
        source = HangingSource()
        controller = build_controller(
            FakeDetector([False]),
            [source],
            FakeTranscriber(),
            [],
            asyncio.Event(),
            [],
            startup_timeout_seconds=0.05,
        )

        with pytest.raises(VoiceInputError, match="listener_start_timeout"):
            await controller.start()

        assert source.started is True
        assert source.closed is True
        assert controller.status()["enabled"] is False
        assert controller.status()["state"] == "failed"
        assert controller.status()["last_error_code"] == "listener_start_timeout"

    asyncio.run(scenario())


def test_microphone_start_failure_is_returned_instead_of_staying_starting() -> None:
    async def scenario() -> None:
        source = FailingSource([pcm_frame(0)])
        controller = build_controller(
            FakeDetector([False]),
            [source],
            FakeTranscriber(),
            [],
            asyncio.Event(),
            [],
            retry_limit=0,
        )

        with pytest.raises(VoiceInputError, match="microphone_unavailable"):
            await controller.start()

        assert source.closed is True
        assert controller.status()["enabled"] is False
        assert controller.status()["state"] == "failed"
        assert controller.status()["last_error_code"] == "microphone_unavailable"

    asyncio.run(scenario())


def test_vad_disabled_uses_bounded_maximum_capture() -> None:
    async def scenario() -> None:
        detector = FakeDetector([True])
        source = FakeSource([pcm_frame(0), pcm_frame(500)])
        transcripts: list[tuple[str, str]] = []
        completed = asyncio.Event()
        controller = build_controller(
            detector,
            [source],
            FakeTranscriber("bounded"),
            transcripts,
            completed,
            [],
            vad_enabled=False,
        )

        await controller.start()
        await asyncio.wait_for(completed.wait(), timeout=2.0)
        await controller.stop()

        assert transcripts == [("bounded", "en")]

    asyncio.run(scenario())


def test_manual_pause_closes_stream_and_resume_reopens_listener() -> None:
    async def scenario() -> None:
        detector = FakeDetector([False] * 20)
        first = FakeSource([pcm_frame(0)])
        second = FakeSource([pcm_frame(0)])
        controller = build_controller(
            detector,
            [first, second],
            FakeTranscriber(),
            [],
            asyncio.Event(),
            [],
        )

        await controller.start()
        await asyncio.sleep(0.01)
        await controller.pause()
        assert first.closed is True
        assert controller.status()["state"] == "paused"
        await controller.resume()
        await asyncio.sleep(0.01)
        assert second.started is True
        await controller.stop()

    asyncio.run(scenario())


def test_audio_overflow_retries_then_reports_failed_without_dispatch() -> None:
    async def scenario() -> None:
        detector = FakeDetector([False])
        sources = [
            FakeSource([pcm_frame(0)], overflow_at=0),
            FakeSource([pcm_frame(0)], overflow_at=0),
        ]
        statuses: list[VoiceInputStatus] = []
        controller = build_controller(
            detector,
            sources,
            FakeTranscriber(),
            [],
            asyncio.Event(),
            statuses,
            retry_limit=1,
        )

        try:
            await controller.start()
        except VoiceInputError as exc:
            assert exc.code == "audio_overflow"
        for _ in range(100):
            if controller.status()["state"] == "failed":
                break
            await asyncio.sleep(0.03)
        await controller.stop()

        assert any(status.last_error_code == "audio_overflow" for status in statuses)
        assert any(status.state is VoiceInputState.FAILED for status in statuses)

    asyncio.run(scenario())


def test_streaming_resampler_is_bounded_and_emits_exact_detector_frames() -> None:
    assembler = _PCMFrameAssembler(
        source_rate=44_100,
        target_rate=16_000,
        frame_samples=1280,
    )
    output: list[bytes] = []
    for _ in range(20):
        output.extend(assembler.feed(pcm_frame(500, samples=2205)))

    assert output
    assert all(len(frame) == 2560 for frame in output)
    assert len(output) <= 13


def test_chinese_locales_use_whisper_chinese_code() -> None:
    assert _whisper_language("zh-TW") == "zh"
    assert _whisper_language("zh-CN") == "zh"
    assert _whisper_language("ja") == "ja"


def test_voice_runtime_never_imports_historical_openclaw_loop() -> None:
    root = Path(__file__).resolve().parents[2]
    controller_source = (
        root / "ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/voice_input.py"
    ).read_text(encoding="utf-8")
    integration_source = (
        root / "ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/microphone.py"
    ).read_text(encoding="utf-8")

    assert "pi5mic.core.voiceinput" not in controller_source + integration_source
    assert "pi5mic.integration.openclaw" not in controller_source + integration_source
    assert "pi5mic.transport.openclaw" not in controller_source + integration_source
