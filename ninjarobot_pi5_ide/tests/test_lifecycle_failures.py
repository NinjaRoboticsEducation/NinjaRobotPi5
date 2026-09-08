from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from ninjarobot_pi5_ide.integrated import RobotIDEClient

from ninjarobot_pi5_ide import CapabilityRegistry


def test_registry_rolls_back_partial_adapter_and_continues_after_cleanup_error() -> None:
    async def exercise() -> None:
        events = []

        class Adapter:
            def __init__(self, name):
                self.descriptor = SimpleNamespace(name=name)

            async def start(self):
                events.append("start " + self.descriptor.name)
                if self.descriptor.name == "b":
                    raise RuntimeError("original startup failure")

            async def close(self):
                events.append("close " + self.descriptor.name)
                if self.descriptor.name == "b":
                    raise OSError("cleanup failure")

        registry = CapabilityRegistry([Adapter("a"), Adapter("b"), Adapter("c")])
        with pytest.raises(RuntimeError, match="original startup failure"):
            await registry.start()
        assert events == ["start a", "start b", "close b", "close a"]

    asyncio.run(exercise())


def test_client_attempts_every_cleanup_before_reporting_first_failure() -> None:
    async def exercise() -> None:
        events = []

        class Resource:
            def __init__(self, name):
                self.name = name

            async def close(self):
                events.append(self.name)
                if self.name in {"voice", "identity"}:
                    raise RuntimeError(self.name + " failure")

            async def stop(self):
                await self.close()

        client = RobotIDEClient(
            Resource("robot"), Resource("engine"), Resource("identity"), Resource("voice")
        )
        with pytest.raises(RuntimeError, match="voice failure"):
            await client.close()
        assert events == ["voice", "identity", "engine", "robot"]
        await client.close()
        assert len(events) == 4

    asyncio.run(exercise())
