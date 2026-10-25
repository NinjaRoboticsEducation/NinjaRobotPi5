"""IDE-only PipeWire playback, selected-device checks and listen-then-speak ownership."""

from __future__ import annotations

import asyncio
import io
import json
import math
import re
import shutil
import struct
import subprocess
import wave
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from .audio_process import run_audio_process
from .config import SpeechOutputConfig
from .microphone import MicrophoneDevice
from .voice_input import VoiceInputController

ProcessRunner = Callable[..., Coroutine[Any, Any, bytes]]

_I2S_SINK_PATTERNS = (
    "hifiberry",
    "soc_sound",
    "rpi_hifiberry_dac",
    "snd_rpi_hifiberry_dac",
    "googlevoicehat",
    "sndrpigooglevoi",
    "voicehat",
)


def _set_speaker_amplifier(gpio_pin: int | None, enabled: bool) -> None:
    """Drive the SunFounder Robot HAT speaker amplifier switch (GPIO 12 + Fusion 0x17 reg 0x31)."""
    if gpio_pin is None:
        return
    if shutil.which("pinctrl"):
        try:
            subprocess.run(
                ["pinctrl", "set", str(gpio_pin), "op", "dh" if enabled else "dl"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except Exception:
            pass
    try:
        sysfs_speaker = Path("/sys/class/fusion_hat/fusion_hat/speaker")
        if sysfs_speaker.exists():
            sysfs_speaker.write_text("1\n" if enabled else "0\n", encoding="utf-8")
    except Exception:
        pass
    try:
        import importlib

        if Path("/dev/i2c-1").exists():
            smbus2 = importlib.import_module("smbus2")
            with smbus2.SMBus(1) as bus:
                bus.read_i2c_block_data(0x17, 0x18, 2)
                bus.write_byte_data(0x17, 0x31, 1 if enabled else 0)
    except Exception:
        pass
    try:
        import importlib

        lgpio = importlib.import_module("lgpio")

        for chip in (4, 0):
            try:
                handle = lgpio.gpiochip_open(chip)
                break
            except Exception:
                continue
        else:
            return
        try:
            lgpio.gpio_claim_output(handle, gpio_pin, 1 if enabled else 0)
            lgpio.gpio_write(handle, gpio_pin, 1 if enabled else 0)
        finally:
            lgpio.gpiochip_close(handle)
    except Exception:
        pass


def _detect_alsa_i2s_device() -> str | None:
    """Return an ALSA playback device (e.g. 'plughw:2,0') if an onboard I2S DAC card is present."""
    if not shutil.which("aplay"):
        return None
    try:
        completed = subprocess.run(
            ["aplay", "-l"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        lowered = line.lower()
        if any(pattern in lowered for pattern in _I2S_SINK_PATTERNS):
            match = re.match(r"^card\s+(\d+):", line.strip())
            if match:
                return f"plughw:{match.group(1)},0"
    return None


def synthesize_test_chime_wav(sample_rate: int = 24000) -> bytes:
    """Generate a short two-tone PCM16 WAV chime for embedded speaker verification."""
    notes = ((523.25, 0.18), (659.25, 0.24))
    frames = bytearray()
    for freq_hz, duration_s in notes:
        total_samples = int(sample_rate * duration_s)
        for idx in range(total_samples):
            envelope = 1.0
            fade = min(400, max(1, total_samples // 6))
            if idx < fade:
                envelope = idx / fade
            elif idx > total_samples - fade:
                envelope = (total_samples - idx) / fade
            phase = 2.0 * math.pi * freq_hz * idx / sample_rate
            sample = int(32767 * 0.22 * envelope * math.sin(phase))
            frames.extend(struct.pack("<h", max(-32768, min(32767, sample))))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(bytes(frames))
    return buf.getvalue()


async def discover_i2s_output_node(runner: ProcessRunner = run_audio_process) -> str:
    """Inspect pw-dump (or ALSA aplay -l fallback) for an onboard I2S DAC sink."""
    if shutil.which("pw-dump"):
        try:
            data = await runner(["pw-dump"], timeout=3, output_limit=2_000_000)
            rows = json.loads(data)
        except Exception:
            rows = []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                info = row.get("info")
                if not isinstance(info, dict):
                    continue
                props = info.get("props")
                if not isinstance(props, dict):
                    continue
                if props.get("media.class") != "Audio/Sink":
                    continue
                node_name = props.get("node.name")
                if not isinstance(node_name, str) or not node_name:
                    continue
                description = str(props.get("node.description", "")).lower()
                haystack = f"{node_name.lower()} {description}"
                if any(pattern in haystack for pattern in _I2S_SINK_PATTERNS):
                    return node_name
        return ""
    alsa_dev = await asyncio.to_thread(_detect_alsa_i2s_device)
    if alsa_dev:
        return "alsa_output.platform-soc_sound.stereo-fallback"
    return ""


def wav_duration(data: bytes) -> float:
    if not data or len(data) > 8_000_000:
        raise ValueError("speech_audio_size_invalid")
    with wave.open(io.BytesIO(data), "rb") as reader:
        if reader.getcomptype() != "NONE" or reader.getsampwidth() != 2:
            raise ValueError("speech_requires_pcm16_wav")
        if reader.getnchannels() not in (1, 2) or not 8000 <= reader.getframerate() <= 48000:
            raise ValueError("speech_audio_format_invalid")
        frames = reader.getnframes()
        duration = frames / reader.getframerate()
        if not 0 < duration <= 120:
            raise ValueError("speech_audio_duration_invalid")
        if len(reader.readframes(frames)) != frames * reader.getnchannels() * 2:
            raise ValueError("speech_audio_truncated")
        return duration


def with_startup_silence(data: bytes, seconds: float) -> bytes:
    """Start the same output stream before speech without discarding any samples.

    Silence is bounded and included in existing size/duration limits. A physical
    cold-start listening test is still needed: some speakers gate silent input.
    """
    wav_duration(data)
    if not 0 <= seconds <= 2:
        raise ValueError("speech_lead_in_invalid")
    if seconds == 0:
        return data
    with wave.open(io.BytesIO(data), "rb") as reader:
        params = reader.getparams()
        silence = b"\0" * (round(seconds * params.framerate) * params.nchannels * params.sampwidth)
        frames = reader.readframes(params.nframes)
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams(params)
        writer.writeframes(silence + frames)
    result = output.getvalue()
    wav_duration(result)
    return result


class AudioOutput:
    """Playback is optional and never selects a replacement/default output."""

    def __init__(
        self,
        config: SpeechOutputConfig,
        *,
        voice: VoiceInputController,
        microphone: MicrophoneDevice,
        permitted: Callable[[], bool],
        scene: Callable[[], Any],
        simulated: bool = False,
        runner: ProcessRunner = run_audio_process,
    ) -> None:
        self.config = config
        self.voice = voice
        self.microphone = microphone
        self._permitted = permitted
        self._scene = scene
        self._simulated = simulated
        self._runner = runner
        self._active: asyncio.Task[Any] | None = None
        self._generation = 0
        self._closed = False
        self._foreground_users = 0
        self._target_node = config.output_node

    async def outputs(self) -> list[dict[str, str]]:
        if self._simulated:
            return [{"name": "simulation", "description": "Simulated speaker"}]
        data = await self._runner(["pw-dump"], timeout=3, output_limit=2_000_000)
        rows = json.loads(data)
        if not isinstance(rows, list):
            raise RuntimeError("invalid_audio_catalog")
        result = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            info = row.get("info")
            if not isinstance(info, dict):
                continue
            props = info.get("props")
            if not isinstance(props, dict):
                continue
            if props.get("media.class") == "Audio/Sink" and isinstance(props.get("node.name"), str):
                result.append(
                    {
                        "name": props["node.name"],
                        "description": str(props.get("node.description", ""))[:256],
                    }
                )
        return result[:128]

    @property
    def generation(self) -> int:
        return self._generation

    async def health(self) -> dict[str, Any]:
        if self._closed or self._foreground_users or not self._permitted():
            return {"ready": False, "reason": "speech_blocked_by_safety_or_foreground"}
        if self._simulated:
            return {"ready": True, "simulated": True, "selected_output": "simulation"}
        if not self.config.output_node:
            return {"ready": False, "reason": "select_output_node"}
        if not shutil.which("pw-play") or not shutil.which("pw-dump"):
            if not self.config.output_node.startswith("bluez_output.") and any(
                pattern in self.config.output_node.lower() for pattern in _I2S_SINK_PATTERNS
            ):
                alsa_dev = await asyncio.to_thread(_detect_alsa_i2s_device)
                if alsa_dev:
                    self._target_node = self.config.output_node
                    return {
                        "ready": True,
                        "reason": "available",
                        "selected_output": self.config.output_node,
                    }
            return {"ready": False, "reason": "pipewire_tools_missing"}
        try:
            available = await self.outputs()
            selected = self.config.output_node
            bluetooth = re.fullmatch(
                r"(bluez_output\.(?:[0-9A-F]{2}_){5}[0-9A-F]{2}\.).+", selected
            )
            if bluetooth:
                matches = [
                    row["name"] for row in available if row["name"].startswith(bluetooth.group(1))
                ]
                selected = matches[0] if len(matches) == 1 else ""
            ready = bool(selected) and any(row["name"] == selected for row in available)
            self._target_node = selected
            return {
                "ready": ready,
                "reason": "available" if ready else "selected_output_unavailable",
                "selected_output": selected,
            }
        except Exception:
            return {"ready": False, "reason": "audio_session_unavailable"}

    @asynccontextmanager
    async def _intake_paused(self) -> AsyncIterator[None]:
        async with self.microphone.output_access():
            await self.voice.pause(for_output=True)
            try:
                yield
            finally:
                await self.voice.resume()

    async def play(self, data: bytes, *, generation: int | None = None) -> dict[str, Any]:
        if not self._simulated and self.config.output_node.startswith("bluez_output."):
            data = with_startup_silence(data, self.config.bluetooth_lead_in_seconds)
        duration = wav_duration(data)
        if generation is not None and generation != self._generation:
            raise RuntimeError("speech_superseded")
        if self._closed or self._foreground_users or not self._permitted():
            raise RuntimeError("speech_blocked_by_safety")
        if self._active is not None:
            raise RuntimeError("speech_output_busy")
        current = asyncio.current_task()
        assert current is not None
        self._active = current
        generation = self._generation
        try:
            async with asyncio.timeout(self.config.playback_timeout_seconds):
                if not (await self.health())["ready"]:
                    raise RuntimeError("selected_output_unavailable")
                async with self._intake_paused(), self._scene():
                    if generation != self._generation or not self._permitted():
                        raise RuntimeError("speech_cancelled_before_playback")
                    if self._simulated:
                        await asyncio.sleep(0)
                        return {"played": False, "simulated": True, "duration_seconds": duration}
                    return await self._play_stream(data, duration, generation)
        finally:
            if self._active is current:
                self._active = None

    async def _play_stream(self, data: bytes, duration: float, generation: int) -> dict[str, Any]:
        playback: asyncio.Task[bytes] | None = None
        try:
            if self.config.speaker_enable_gpio is not None:
                await asyncio.to_thread(
                    _set_speaker_amplifier, self.config.speaker_enable_gpio, True
                )
            target = self._target_node
            if shutil.which("pw-play"):
                arguments = [
                    "pw-play",
                    "--target=" + target,
                    "--volume=" + str(self.config.volume),
                    "--properties="
                    + json.dumps(
                        {
                            "node.dont-reconnect": True,
                            "node.dont-fallback": True,
                            "node.linger": False,
                        }
                    ),
                    "-",
                ]
            else:
                alsa_dev = await asyncio.to_thread(_detect_alsa_i2s_device) or "default"
                arguments = ["aplay", "-q", "-D", alsa_dev, "-"]
            playback = asyncio.create_task(
                self._runner(
                    arguments,
                    input_data=data,
                    timeout=min(duration + 5, self.config.playback_timeout_seconds),
                    output_limit=65536,
                )
            )
            while not playback.done():
                done, _ = await asyncio.wait((playback,), timeout=0.25)
                if not done:
                    if not self._permitted() or generation != self._generation:
                        raise RuntimeError("speech_interrupted")
                    health = await self.health()
                    if not health["ready"] or health.get("selected_output") != target:
                        raise RuntimeError("speaker_disconnected")
            await playback
            if generation != self._generation or not self._permitted():
                raise RuntimeError("speech_interrupted")
            return {
                "played": True,
                "simulated": False,
                "duration_seconds": duration,
                "evidence": "playback_process_completed; hearing not verified",
            }
        finally:
            if playback is not None:
                playback.cancel()
                await asyncio.gather(playback, return_exceptions=True)

    async def stop(self) -> None:
        self._generation += 1
        if self._active is not None and self._active is not asyncio.current_task():
            self._active.cancel()
        # Dispatch-only: safety indicators must not wait behind their own scene cleanup.

    @asynccontextmanager
    async def foreground(self) -> AsyncIterator[None]:
        """Explicit device work preempts speech and blocks new playback until it exits."""
        self._foreground_users += 1
        active = self._active
        try:
            await self.stop()
            if active is not None and active is not asyncio.current_task():
                await asyncio.gather(active, return_exceptions=True)
            yield
        finally:
            self._foreground_users -= 1

    async def close(self) -> None:
        self._closed = True
        active = self._active
        await self.stop()
        if active is not None and active is not asyncio.current_task():
            await asyncio.gather(active, return_exceptions=True)
        if not self._simulated and self.config.speaker_enable_gpio is not None:
            await asyncio.to_thread(_set_speaker_amplifier, self.config.speaker_enable_gpio, False)
