"""Bounded local child processes; no shell, retained stderr, or detached playback."""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path


async def run_audio_process(
    arguments: list[str],
    *,
    input_data: bytes = b"",
    timeout: float = 10,
    output_limit: int = 2_000_000,
    output_file: Path | None = None,
) -> bytes:
    """Own a child process group until exit, including timeout/cancellation cleanup."""
    spawning = asyncio.create_task(
        asyncio.create_subprocess_exec(
            *arguments,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "LC_NUMERIC": "C"},
        )
    )
    cancelled = False
    while not spawning.done():
        try:
            await asyncio.shield(spawning)
        except asyncio.CancelledError:
            cancelled = True
    process = await spawning

    async def exchange() -> bytes:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(input_data)
        try:
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        process.stdin.close()
        output = bytearray()
        while chunk := await process.stdout.read(65536):
            output.extend(chunk)
            if len(output) > output_limit:
                raise RuntimeError("audio_process_output_limit")
        if await process.wait() != 0:
            raise RuntimeError("audio_process_failed")
        return bytes(output)

    async def monitor() -> None:
        while True:
            if output_file is not None and output_file.exists():
                if output_file.stat().st_size > 8_000_000:
                    raise RuntimeError("speech_file_too_large")
            await asyncio.sleep(0.1)

    async def cleanup() -> None:
        # Descendants must not retain the audio device or pipe after the parent exits.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), 0.5)
        except TimeoutError:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()

    work = asyncio.create_task(exchange())
    watcher = asyncio.create_task(monitor())
    try:
        if cancelled:
            raise asyncio.CancelledError
        async with asyncio.timeout(timeout):
            done, _ = await asyncio.wait((work, watcher), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
            return await work
    finally:
        work.cancel()
        watcher.cancel()
        closing = asyncio.create_task(cleanup())
        while not closing.done():
            try:
                await asyncio.shield(closing)
            except asyncio.CancelledError:
                # Repeated cancellation cannot abandon a process owning audio.
                continue
        await closing
        await asyncio.gather(work, watcher, return_exceptions=True)
