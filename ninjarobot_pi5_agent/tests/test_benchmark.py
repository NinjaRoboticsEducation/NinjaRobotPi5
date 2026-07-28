from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from ninjarobot_pi5_agent import (
    BenchmarkCase,
    FinishReason,
    ModelBenchmark,
    ModelRequest,
    ModelStreamEvent,
    ModelTurn,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthStatus,
    StreamEventType,
    SystemSnapshot,
    ToolCall,
    ToolDefinition,
)
from ninjarobot_pi5_ide import RiskLevel


def tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        version="1.0.0",
        description=f"Call {name}.",
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={"type": "object"},
        risk=RiskLevel.READ_ONLY,
        default_timeout_seconds=2.0,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
    )


class _Probe:
    def __init__(
        self,
        *,
        memory: float = 4.0,
        temperature: float = 55.0,
        undervoltage: bool = False,
        throttling: bool = False,
    ) -> None:
        self._snapshot = SystemSnapshot(
            total_memory_used_gb=memory,
            temperature_c=temperature,
            undervoltage_detected=undervoltage,
            throttling_detected=throttling,
        )

    def snapshot(self) -> SystemSnapshot:
        return self._snapshot


class _BenchmarkProvider:
    def __init__(self, *, correct: bool = True) -> None:
        self.correct = correct

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tools=True,
            streaming=True,
            images=False,
            audio=False,
            structured_output=True,
            usage_reporting=True,
            provider_conversation_state=False,
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="benchmark-fake",
            status=ProviderHealthStatus.READY,
            checked_at=datetime(2026, 7, 28, tzinfo=UTC),
        )

    async def stream(self, request: ModelRequest):
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.TEXT_DELTA,
            text="Hello",
        )
        yield ModelStreamEvent(
            request_id=request.request_id,
            event=StreamEventType.DONE,
            turn=ModelTurn(
                request_id=request.request_id,
                text="Hello.",
                finish_reason=FinishReason.STOP,
                diagnostics={"load_duration_seconds": 3.0},
            ),
        )

    async def generate(self, request: ModelRequest) -> ModelTurn:
        expected = request.tools[0].name
        selected = expected if self.correct else request.tools[-1].name
        return ModelTurn(
            request_id=request.request_id,
            finish_reason=FinishReason.TOOL_CALLS,
            tool_calls=(
                ToolCall(
                    call_id=f"{request.request_id}-call",
                    name=selected,
                    arguments={},
                ),
            ),
        )

    async def close(self) -> None:
        return None


class _Clock:
    def __init__(self) -> None:
        self.values = iter((0.0, 1.0, 2.0))

    def __call__(self) -> float:
        return next(self.values)


def cases() -> tuple[BenchmarkCase, ...]:
    correct = tool("robot.distance.read")
    wrong = tool("mcp.tavily.tavily-search")
    return tuple(
        BenchmarkCase(
            prompt=f"Read distance case {index}",
            expected_tool=correct.name,
            tools=(correct, wrong),
        )
        for index in range(10)
    )


def test_model_benchmark_accepts_only_measured_threshold_compliance(tmp_path) -> None:
    async def exercise() -> None:
        benchmark = ModelBenchmark(
            _BenchmarkProvider(),
            model="qwen3:4b-test",
            probe=_Probe(),
            clock=_Clock(),
        )

        report = await benchmark.run(
            simple_prompt="Reply with one short greeting.",
            tool_cases=cases(),
        )

        assert report.accepted
        assert report.metrics.first_token_seconds == 1.0
        assert report.metrics.simple_response_seconds == 2.0
        assert report.metrics.tool_call_correctness == 1.0
        assert report.metrics.model_load_seconds == 3.0
        path = report.save(tmp_path / "report.json")
        assert path.exists()
        assert "qwen3:4b-test" in path.read_text(encoding="utf-8")

    asyncio.run(exercise())


def test_model_benchmark_rejects_bad_tools_temperature_and_throttling() -> None:
    async def exercise() -> None:
        benchmark = ModelBenchmark(
            _BenchmarkProvider(correct=False),
            model="rejected-model",
            probe=_Probe(temperature=81.0, throttling=True),
            clock=_Clock(),
        )

        report = await benchmark.run(
            simple_prompt="Reply with one short greeting.",
            tool_cases=cases(),
        )

        assert not report.accepted
        assert report.metrics.tool_call_correctness == 0.0
        assert "tool-call correctness did not meet its threshold" in report.failures
        assert "thermal throttling was detected" in report.failures

    asyncio.run(exercise())
