from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from ninjarobot_pi5_agent.persistence import ConversationStore
from ninjarobot_pi5_agent.service import (
    AgentService,
    ServiceAlreadyRunningError,
    ServiceOwnership,
)
from ninjarobot_pi5_agent.testing import FakeProvider
from ninjarobot_pi5_ide.testing import FakeIDEClient


def test_service_owns_dependencies_and_rejects_second_owner(tmp_path: Path) -> None:
    async def exercise() -> None:
        lock_path = tmp_path / "agent.lock"
        provider = FakeProvider([])
        ide = FakeIDEClient()
        service = AgentService(
            provider=provider,
            ide=ide,
            store=ConversationStore(tmp_path / "agent.sqlite3"),
            ownership=ServiceOwnership(lock_path),
        )

        await service.start()
        await service.start()
        assert service.started is True
        assert lock_path.exists()

        competing = ServiceOwnership(lock_path)
        with pytest.raises(ServiceAlreadyRunningError, match="already running"):
            competing.acquire()

        await service.close()
        await service.close()
        assert provider.closed is True
        assert ide.closed is True
        assert not lock_path.exists()

    asyncio.run(exercise())
