from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from ninjarobot_pi5_ide.engine import ExecutionEngine
from ninjarobot_pi5_ide.ledger import ActionLedger
from ninjarobot_pi5_ide.models import CapabilityHealth, HealthReport, ResourceHealth
from ninjarobot_pi5_ide.registry import CapabilityRegistry
from ninjarobot_pi5_ide.robot import RobotAssembly


class ProbeAdapter:
    def __init__(self, name, mode):
        self.descriptor = SimpleNamespace(name=name, resources=("test_device",))
        self.mode = mode
        self.cancelled = False

    async def start(self):
        pass

    async def close(self):
        pass

    async def health(self):
        if self.mode == "failure":
            raise OSError("private-config-value")
        if self.mode == "wait":
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True
        return ResourceHealth.READY


def test_failed_and_timed_out_probes_preserve_other_capabilities(tmp_path: Path) -> None:
    async def exercise():
        waiting = ProbeAdapter("test.wait", "wait")
        engine = ExecutionEngine(
            CapabilityRegistry(
                [waiting, ProbeAdapter("test.failed", "failure"), ProbeAdapter("test.ok", "ok")]
            ),
            ActionLedger(tmp_path / "ledger.sqlite3"),
        )
        try:
            report = await engine.health()
            assert report.status is ResourceHealth.UNAVAILABLE
            assert report.capabilities["test.ok"].status is ResourceHealth.READY
            assert report.capabilities["test.failed"].reason_code == "probe_failed"
            assert report.capabilities["test.wait"].reason_code == "probe_timed_out"
            assert report.capabilities["test.ok"].dependencies == ("test_device",)
            assert report.checked_at.tzinfo is not None
            assert report.valid_for_seconds == 5.0
            assert "private-config-value" not in report.model_dump_json()
            assert waiting.cancelled
        finally:
            await engine.close()

    asyncio.run(exercise())


def test_health_cancellation_propagates_and_cleans_up_probes() -> None:
    async def exercise():
        waiting = ProbeAdapter("test.wait", "wait")
        registry = CapabilityRegistry([waiting])
        await registry.start()
        task = asyncio.create_task(registry.health())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert waiting.cancelled
        await registry.close()

    asyncio.run(exercise())


def test_disabled_and_stopped_are_explained_without_device_access() -> None:
    robot = object.__new__(RobotAssembly)
    robot._enabled_devices = {"display": False}
    robot.system_safety = SimpleNamespace(stopped=False)
    robot.safety_state = SimpleNamespace(
        read=lambda: SimpleNamespace(
            motion_latched=False, reason="operator_stop", fault_detail=None
        )
    )
    report = HealthReport(
        status=ResourceHealth.UNAVAILABLE,
        components={"display.clear": ResourceHealth.UNAVAILABLE},
        checked_at=datetime.now(UTC),
        capabilities={
            "display.clear": CapabilityHealth(
                status=ResourceHealth.UNAVAILABLE, reason_code="adapter_status", recovery="Check."
            )
        },
    )
    result = robot.annotate_health(report)
    assert result.capabilities["display.clear"].status is ResourceHealth.NOT_CONFIGURED
    assert result.capabilities["display.clear"].reason_code == "disabled_in_configuration"
    robot.system_safety.stopped = True
    result = robot.annotate_health(report)
    assert result.capabilities["display.clear"].execution_blocked
    assert result.capabilities["display.clear"].reason_code == "system_stopped"
    assert report.capabilities["display.clear"].reason_code == "adapter_status"
