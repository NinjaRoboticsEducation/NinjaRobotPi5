"""Offline handoff regressions: no tunnel, media, providers or actuators."""

from __future__ import annotations

import asyncio

import pytest
from ninjarobot_pi5_agent.web_control import (
    ControllerLeaseManager,
    ControllerLockedError,
    InvalidControllerLeaseError,
)


def test_disconnect_stops_now_reserves_then_hands_off_without_overlap() -> None:
    async def exercise() -> None:
        now = [0.0]
        stopping = asyncio.Event()
        stopped = asyncio.Event()
        calls = []
        available = []

        async def revoke(lease_id: str, reason: str) -> None:
            calls.append((lease_id, reason))
            stopping.set()
            await stopped.wait()

        async def free(lease_id: str, reason: str) -> None:
            available.append(lease_id)

        manager = ControllerLeaseManager(on_revoke=revoke, on_available=free, clock=lambda: now[0])
        first = await manager.acquire()
        loss = asyncio.create_task(manager.disconnect(first.lease_id, first.generation))
        await stopping.wait()
        with pytest.raises(InvalidControllerLeaseError):
            await manager.validate(first.lease_id, first.generation)
        reclaim = asyncio.create_task(manager.acquire(first.reconnect_token))
        await asyncio.sleep(0)
        assert not reclaim.done()
        stopped.set()
        await loss
        second = await reclaim
        assert second.lease_id == first.lease_id
        assert second.generation > first.generation
        await manager.disconnect(first.lease_id, first.generation)  # stale socket finalizer
        await manager.validate(second.lease_id, second.generation)
        await manager.disconnect(second.lease_id, second.generation)
        with pytest.raises(ControllerLockedError):
            await manager.acquire("competitor")
        assert available == []
        now[0] = 11
        third = await manager.acquire()
        assert third.lease_id != first.lease_id
        assert available == [first.lease_id]
        assert len(calls) == 2  # one cleanup for each actual attachment
        await manager.close()

    asyncio.run(exercise())


def test_silent_timeout_closes_transport_and_cleanup_fault_denies_admission() -> None:
    async def exercise() -> None:
        now = [0.0]
        closed = asyncio.Event()
        count = []

        async def revoke(lease_id: str, reason: str) -> None:
            count.append(reason)
            raise RuntimeError("simulated device cleanup fault")

        async def detach() -> None:
            closed.set()

        manager = ControllerLeaseManager(on_revoke=revoke, clock=lambda: now[0])
        first = await manager.acquire()
        await manager.attach(first, detach)
        now[0] = 16
        with pytest.raises(ControllerLockedError):
            await manager.acquire()
        assert closed.is_set()
        assert (await manager.status())["cleanup_failed"] is True
        with pytest.raises(InvalidControllerLeaseError):
            await manager.heartbeat(first.lease_id)
        await manager._expire()
        assert count == ["heartbeat_timeout"]
        await manager.close()

    asyncio.run(exercise())


def test_one_hundred_handoffs_finalize_once_and_shutdown_never_advertises() -> None:
    async def exercise() -> None:
        losses = []
        free = []

        async def revoke(lease_id: str, reason: str) -> None:
            losses.append(lease_id)

        async def available(lease_id: str, reason: str) -> None:
            free.append(lease_id)

        manager = ControllerLeaseManager(on_revoke=revoke, on_available=available)
        for _ in range(100):
            lease = await manager.acquire()
            await asyncio.gather(
                manager.release(lease.lease_id),
                manager.disconnect(lease.lease_id, lease.generation),
            )
            assert not (await manager.status())["lease_active"]
        assert len(losses) == len(set(losses)) == len(free) == 100
        await manager.acquire()
        await manager.close()
        assert len(losses) == 101 and len(free) == 100
        with pytest.raises(ControllerLockedError):
            await manager.acquire()

    asyncio.run(exercise())


def test_interrupted_cleanup_is_retried_by_shutdown() -> None:
    async def exercise() -> None:
        started = asyncio.Event()
        calls = []

        async def revoke(lease_id: str, reason: str) -> None:
            calls.append(reason)
            if len(calls) == 1:
                started.set()
                await asyncio.Event().wait()

        manager = ControllerLeaseManager(on_revoke=revoke)
        lease = await manager.acquire()
        cleanup = asyncio.create_task(manager.disconnect(lease.lease_id, lease.generation))
        await started.wait()
        cleanup.cancel()
        await asyncio.gather(cleanup, return_exceptions=True)
        await manager.close()
        assert calls == ["disconnect", "web_server_shutdown"]

    asyncio.run(exercise())


def test_terminal_takeover_of_browser_voice_is_preserved_on_loss() -> None:
    from ninjarobot_pi5_agent.runtime import AgentRuntime

    class Voice:
        enabled = False
        disables: list[bool]

        def __init__(self) -> None:
            self.disables = []

        def status(self) -> dict[str, object]:
            return {"enabled": self.enabled}

        async def enable(self) -> dict[str, object]:
            self.enabled = True
            return self.status()

        async def disable(self, *, persist: bool = True) -> dict[str, object]:
            self.disables.append(persist)
            self.enabled = False
            return self.status()

    async def exercise() -> None:
        runtime = object.__new__(AgentRuntime)
        runtime._started = True
        runtime._closed = False
        voice = Voice()
        runtime._voice_input = voice  # type: ignore[assignment]
        runtime._voice_input_owner = None
        await runtime.enable_voice_input(lease_id="browser")
        await runtime.enable_voice_input()  # explicit terminal ownership
        await runtime.release_browser_voice("browser")
        assert voice.enabled and not voice.disables
        await runtime.disable_voice_input(persist=False)
        await runtime.enable_voice_input(lease_id="browser")
        await runtime.release_browser_voice("browser")
        assert not voice.enabled and voice.disables == [False, False]

    asyncio.run(exercise())
