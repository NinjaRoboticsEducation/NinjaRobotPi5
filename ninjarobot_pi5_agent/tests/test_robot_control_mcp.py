from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from ninjarobot_pi5_agent.models import (
    ToolCall,
    ToolExecutionStatus,
    ToolInvocation,
    ToolTrust,
)
from ninjarobot_pi5_agent.robot_control_mcp import RobotControlMCPProvider
from ninjarobot_pi5_agent.tools import CancellationToken, IDEToolProvider, ToolRegistry
from ninjarobot_pi5_ide.testing import FakeIDEClient

from ninjarobot_pi5_ide import (
    ActionRequest,
    ActionResult,
    ActionStatus,
    CapabilityDescriptor,
    ErrorDetails,
    RetrySafety,
    RiskLevel,
)


def _descriptor(
    name: str,
    *,
    risk: RiskLevel,
    confirmation_required: bool = False,
    idempotent: bool = False,
    cancellable: bool = True,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name=name,
        version="1.0.0",
        description=f"Test {name} capability.",
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "name": {"type": "string", "maxLength": 64},
                "description": {"type": "string"},
                "stages": {"type": "array"},
            },
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        risk=risk,
        resources=("test",),
        default_timeout_seconds=5.0,
        idempotent=idempotent,
        cancellable=cancellable,
        confirmation_required=confirmation_required,
    )


def _behavior_descriptors() -> tuple[CapabilityDescriptor, ...]:
    return (
        _descriptor(
            "behavior.list",
            risk=RiskLevel.READ_ONLY,
            idempotent=True,
            cancellable=False,
        ),
        _descriptor(
            "behavior.preview",
            risk=RiskLevel.READ_ONLY,
            idempotent=True,
            cancellable=False,
        ),
        _descriptor("behavior.execute_expression", risk=RiskLevel.LOW),
        _descriptor(
            "behavior.execute_movement",
            risk=RiskLevel.MOTION,
            confirmation_required=True,
        ),
        _descriptor(
            "behavior.stop",
            risk=RiskLevel.EMERGENCY,
            idempotent=True,
            cancellable=False,
        ),
    )


def _fake_ide() -> FakeIDEClient:
    return FakeIDEClient(_behavior_descriptors())


def test_robot_control_mcp_exposes_fixed_trusted_catalog() -> None:
    async def exercise() -> None:
        provider = RobotControlMCPProvider(_fake_ide())
        await provider.start()

        tools = {tool.name: tool for tool in await provider.list_tools()}

        assert set(tools) == {
            "robot.behavior.catalog",
            "robot.behavior.preview",
            "robot.behavior.execute_expression",
            "robot.behavior.execute_movement",
            "robot.behavior.stop",
        }
        assert all(tool.source == "robot-control-mcp" for tool in tools.values())
        assert all(tool.trust is ToolTrust.TRUSTED for tool in tools.values())
        assert tools["robot.behavior.preview"].risk is RiskLevel.READ_ONLY
        movement = tools["robot.behavior.execute_movement"]
        assert movement.risk is RiskLevel.MOTION
        assert movement.confirmation_required is True

        await provider.close()

    asyncio.run(exercise())


def test_robot_control_mcp_translates_calls_to_ide_actions() -> None:
    async def exercise() -> None:
        ide = _fake_ide()
        provider = RobotControlMCPProvider(ide)
        await provider.start()
        invocation = ToolInvocation(
            call=ToolCall(
                call_id="behavior-call-1",
                name="robot.behavior.execute_expression",
                arguments={
                    "name": "hello_expression",
                    "description": "Show a face and play a tone.",
                    "stages": [
                        {
                            "face": "happy",
                            "tone": {"frequency_hz": 880},
                        }
                    ],
                },
            ),
            session_id="session-1",
            requested_by="agent-test",
        )

        result = await provider.call(invocation, CancellationToken())

        assert result.status is ToolExecutionStatus.SUCCEEDED
        assert result.action_id == "agent-behavior-call-1"
        assert result.data == {
            "simulated": True,
            "capability": "behavior.execute_expression",
        }
        request = ide.requests[0]
        assert request.capability == "behavior.execute_expression"
        assert request.session_id == "session-1"
        assert request.requested_by == "agent-test"
        assert request.idempotency_key == "behavior-call-1"
        assert request.arguments["category"] == "expression"
        assert request.arguments["stages"][0]["face"] == "happy"

        await provider.close()
        assert not ide.closed

    asyncio.run(exercise())


def test_robot_control_mcp_rejects_unexpected_arguments_before_ide_execution() -> None:
    async def exercise() -> None:
        ide = _fake_ide()
        provider = RobotControlMCPProvider(ide)
        await provider.start()
        invocation = ToolInvocation(
            call=ToolCall(
                call_id="invalid-call-1",
                name="robot.behavior.catalog",
                arguments={"unexpected": True},
            ),
            session_id="session-1",
        )

        result = await provider.call(invocation, CancellationToken())

        assert result.status is ToolExecutionStatus.FAILED
        assert "validation" in (result.error or "").lower()
        assert result.definitely_not_executed is True
        assert not ide.requests

        oversized = invocation.model_copy(
            update={
                "call": invocation.call.model_copy(
                    update={
                        "name": "robot.behavior.execute_expression",
                        "arguments": {
                            "name": "x" * 5000,
                            "description": "An oversized behavior name.",
                            "stages": [{"face": "happy"}],
                        },
                    }
                )
            }
        )
        oversized_result = await provider.call(oversized, CancellationToken())
        assert oversized_result.status is ToolExecutionStatus.FAILED
        assert len(oversized_result.error or "") <= 2000
        assert not ide.requests
        await provider.close()

    asyncio.run(exercise())


def test_robot_control_mcp_composes_with_remaining_ide_tools_without_collisions() -> None:
    async def exercise() -> None:
        ide = _fake_ide()
        registry = ToolRegistry(
            (
                IDEToolProvider(
                    ide,
                    excluded_capabilities={
                        "behavior.preview",
                        "behavior.execute_expression",
                        "behavior.execute_movement",
                        "behavior.stop",
                    },
                ),
                RobotControlMCPProvider(ide),
            )
        )

        await registry.start()
        tools = {tool.name: tool for tool in registry.list_tools()}

        assert tools["robot.behavior.list"].source == "ide"
        assert tools["robot.behavior.catalog"].source == "robot-control-mcp"
        assert tools["robot.behavior.execute_movement"].source == "robot-control-mcp"
        assert len(tools) == 6

        await registry.close()
        assert ide.closed

    asyncio.run(exercise())


def test_robot_control_mcp_propagates_cancellation_to_the_ide() -> None:
    class _SlowIDE(FakeIDEClient):
        def __init__(self) -> None:
            super().__init__(_behavior_descriptors())
            self.cancelled_actions: list[str] = []

        async def execute(self, request: ActionRequest) -> ActionResult:
            self.requests.append(request)
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def cancel(self, action_id: str) -> ActionResult:
            self.cancelled_actions.append(action_id)
            timestamp = datetime.now(UTC)
            return ActionResult(
                action_id=action_id,
                status=ActionStatus.CANCELLED,
                error=ErrorDetails(
                    code="ACTION_CANCELLED",
                    message="The simulated action was cancelled.",
                    definitely_not_executed=False,
                    retry_safety=RetrySafety.UNKNOWN,
                    action_id=action_id,
                ),
                started_at=timestamp,
                finished_at=timestamp,
                retry_safety=RetrySafety.UNKNOWN,
            )

    async def exercise() -> None:
        ide = _SlowIDE()
        provider = RobotControlMCPProvider(ide)
        await provider.start()
        cancellation = CancellationToken()
        invocation = ToolInvocation(
            call=ToolCall(
                call_id="cancel-call-1",
                name="robot.behavior.execute_movement",
                arguments={
                    "name": "cancelled_move",
                    "description": "A movement cancelled during testing.",
                    "stages": [{"movement": "move_forward"}],
                },
            ),
            session_id="session-1",
        )

        task = asyncio.create_task(provider.call(invocation, cancellation))
        while not ide.requests:
            await asyncio.sleep(0)
        cancellation.cancel()
        result = await task

        assert result.status is ToolExecutionStatus.CANCELLED
        assert result.retry_safety is RetrySafety.UNKNOWN
        assert ide.cancelled_actions == ["agent-cancel-call-1"]
        await provider.close()

    asyncio.run(exercise())
