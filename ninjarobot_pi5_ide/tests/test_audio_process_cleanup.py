import asyncio
import gc
import sys

import pytest
from ninjarobot_pi5_ide.audio_process import run_audio_process


def test_early_child_exit_and_timeout_retrieve_pipe_errors():
    async def exercise():
        loop = asyncio.get_running_loop()
        errors = []
        loop.set_exception_handler(lambda loop, context: errors.append(context))
        await run_audio_process([sys.executable, "-c", "pass"], input_data=b"x" * 2_000_000)
        with pytest.raises(TimeoutError):
            await run_audio_process(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                input_data=b"x" * 2_000_000,
                timeout=0.1,
            )
        gc.collect()
        await asyncio.sleep(0.05)
        assert errors == []

    asyncio.run(exercise())
