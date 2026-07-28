"""Raspberry Pi acceptance benchmark for local agent model candidates."""

from __future__ import annotations

import asyncio
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    MessageRole,
    ModelMessage,
    ModelRequest,
    ProviderHealthStatus,
    StreamEventType,
    ToolDefinition,
)
from .providers import LLMProvider

Clock = Callable[[], float]


class BenchmarkThresholds(BaseModel):
    """Owner-approved initial Qwen3:4B Raspberry Pi acceptance limits."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    first_token_seconds: Annotated[float, Field(gt=0, le=120)] = 15.0
    simple_response_seconds: Annotated[float, Field(gt=0, le=300)] = 30.0
    tool_call_correctness: Annotated[float, Field(ge=0, le=1)] = 0.90
    peak_total_memory_gb: Annotated[float, Field(gt=0, le=64)] = 7.0
    maximum_temperature_c: Annotated[float, Field(gt=0, le=100)] = 80.0


class BenchmarkCase(BaseModel):
    """One non-executing native tool-selection test."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    prompt: str
    expected_tool: str
    tools: tuple[ToolDefinition, ...]


class SystemSnapshot(BaseModel):
    """One local memory, temperature, and throttle sample."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    total_memory_used_gb: Annotated[float, Field(ge=0)]
    temperature_c: Annotated[float, Field(ge=0)]
    undervoltage_detected: bool
    throttling_detected: bool


class BenchmarkMetrics(BaseModel):
    """Measured values; ``None`` means the metric was not produced."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model_load_seconds: float | None = None
    first_token_seconds: float | None = None
    simple_response_seconds: float | None = None
    tool_call_correctness: float | None = None
    peak_total_memory_gb: float | None = None
    maximum_temperature_c: float | None = None
    undervoltage_detected: bool = False
    throttling_detected: bool = False
    malformed_or_unsafe_events: int = 0


class BenchmarkReport(BaseModel):
    """Serializable benchmark evidence and acceptance result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: int = 1
    model: str
    measured_at: datetime
    thresholds: BenchmarkThresholds
    metrics: BenchmarkMetrics
    accepted: bool
    failures: tuple[str, ...]

    def save(self, path: str | Path) -> Path:
        """Atomically save a report without claiming unmeasured values."""
        destination = Path(path).expanduser()
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        temporary.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
        return destination


class SystemProbe(Protocol):
    """Read current Raspberry Pi resource and firmware state."""

    def snapshot(self) -> SystemSnapshot:
        """Return one non-mutating local sample."""


class LinuxSystemProbe:
    """Read Linux memory/thermal files and Raspberry Pi throttle flags."""

    def snapshot(self) -> SystemSnapshot:
        """Return safe local metrics, using zero temperature if unavailable."""
        flags = _throttle_flags()
        return SystemSnapshot(
            total_memory_used_gb=_memory_used_gb(Path("/proc/meminfo")),
            temperature_c=_temperature_c(Path("/sys/class/thermal/thermal_zone0/temp")),
            undervoltage_detected=bool(flags & ((1 << 0) | (1 << 16))),
            throttling_detected=bool(flags & ((1 << 2) | (1 << 3) | (1 << 18) | (1 << 19))),
        )


class ModelBenchmark:
    """Measure one provider candidate without executing returned tool calls."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        model: str,
        probe: SystemProbe | None = None,
        thresholds: BenchmarkThresholds | None = None,
        clock: Clock = time.monotonic,
    ) -> None:
        self._provider = provider
        self._model = model
        self._probe = probe or LinuxSystemProbe()
        self._thresholds = thresholds or BenchmarkThresholds()
        self._clock = clock

    async def run(
        self,
        *,
        simple_prompt: str,
        tool_cases: tuple[BenchmarkCase, ...],
    ) -> BenchmarkReport:
        """Run streaming latency, tool selection, and system sampling."""
        stop_sampling = asyncio.Event()
        samples: list[SystemSnapshot] = []
        sampler = asyncio.create_task(self._sample_until(stop_sampling, samples))
        first_token: float | None = None
        response_seconds: float | None = None
        load_seconds: float | None = None
        correctness: float | None = None
        unsafe_events = 0
        failures: list[str] = []
        try:
            health = await self._provider.health()
            if health.status is not ProviderHealthStatus.READY:
                failures.append(health.detail or "model provider is not ready")
            else:
                request = ModelRequest(
                    request_id="benchmark-simple",
                    session_id="benchmark",
                    messages=(ModelMessage(role=MessageRole.USER, content=simple_prompt),),
                    max_output_tokens=128,
                    timeout_seconds=self._thresholds.simple_response_seconds * 2,
                )
                started = self._clock()
                final = None
                try:
                    async for event in self._provider.stream(request):
                        if event.event is StreamEventType.TEXT_DELTA and first_token is None:
                            first_token = self._clock() - started
                        if event.event is StreamEventType.DONE:
                            final = event.turn
                    response_seconds = self._clock() - started
                    if final is None:
                        unsafe_events += 1
                        failures.append("stream ended without a final model turn")
                    else:
                        load_value = final.diagnostics.get("load_duration_seconds")
                        if isinstance(load_value, (int, float)) and not isinstance(
                            load_value, bool
                        ):
                            load_seconds = float(load_value)
                        if first_token is None and final.text:
                            first_token = response_seconds
                except Exception as exc:
                    unsafe_events += 1
                    failures.append(f"simple response failed: {type(exc).__name__}")

                correct = 0
                for index, case in enumerate(tool_cases, start=1):
                    try:
                        turn = await self._provider.generate(
                            ModelRequest(
                                request_id=f"benchmark-tool-{index}",
                                session_id="benchmark",
                                messages=(
                                    ModelMessage(
                                        role=MessageRole.USER,
                                        content=case.prompt,
                                    ),
                                ),
                                tools=case.tools,
                                max_output_tokens=128,
                                timeout_seconds=self._thresholds.simple_response_seconds,
                            )
                        )
                        if (
                            len(turn.tool_calls) == 1
                            and turn.tool_calls[0].name == case.expected_tool
                        ):
                            correct += 1
                        elif len(turn.tool_calls) > 1:
                            unsafe_events += 1
                    except Exception as exc:
                        unsafe_events += 1
                        failures.append(f"tool case {index} failed: {type(exc).__name__}")
                if tool_cases:
                    correctness = correct / len(tool_cases)
        finally:
            stop_sampling.set()
            await sampler

        metrics = BenchmarkMetrics(
            model_load_seconds=load_seconds,
            first_token_seconds=first_token,
            simple_response_seconds=response_seconds,
            tool_call_correctness=correctness,
            peak_total_memory_gb=max(
                (sample.total_memory_used_gb for sample in samples),
                default=None,
            ),
            maximum_temperature_c=max(
                (sample.temperature_c for sample in samples),
                default=None,
            ),
            undervoltage_detected=any(sample.undervoltage_detected for sample in samples),
            throttling_detected=any(sample.throttling_detected for sample in samples),
            malformed_or_unsafe_events=unsafe_events,
        )
        failures.extend(_threshold_failures(metrics, self._thresholds))
        return BenchmarkReport(
            model=self._model,
            measured_at=datetime.now(UTC),
            thresholds=self._thresholds,
            metrics=metrics,
            accepted=not failures,
            failures=tuple(dict.fromkeys(failures)),
        )

    async def _sample_until(
        self,
        stop: asyncio.Event,
        samples: list[SystemSnapshot],
    ) -> None:
        while not stop.is_set():
            samples.append(await asyncio.to_thread(self._probe.snapshot))
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.1)
            except TimeoutError:
                continue
        samples.append(await asyncio.to_thread(self._probe.snapshot))


def _threshold_failures(
    metrics: BenchmarkMetrics,
    thresholds: BenchmarkThresholds,
) -> list[str]:
    failures: list[str] = []
    maximum_inclusive = (
        (
            "first streamed token",
            metrics.first_token_seconds,
            thresholds.first_token_seconds,
        ),
        (
            "simple response",
            metrics.simple_response_seconds,
            thresholds.simple_response_seconds,
        ),
    )
    maximum_exclusive = (
        (
            "peak total memory",
            metrics.peak_total_memory_gb,
            thresholds.peak_total_memory_gb,
        ),
        (
            "maximum temperature",
            metrics.maximum_temperature_c,
            thresholds.maximum_temperature_c,
        ),
    )
    for name, measured, maximum in maximum_inclusive:
        if measured is None:
            failures.append(f"{name} was not measured")
        elif measured > maximum:
            failures.append(f"{name} did not meet its threshold")
    for name, measured, maximum in maximum_exclusive:
        if measured is None:
            failures.append(f"{name} was not measured")
        elif measured >= maximum:
            failures.append(f"{name} did not meet its threshold")
    correctness = metrics.tool_call_correctness
    if correctness is None:
        failures.append("tool-call correctness was not measured")
    elif correctness < thresholds.tool_call_correctness:
        failures.append("tool-call correctness did not meet its threshold")
    if metrics.undervoltage_detected:
        failures.append("undervoltage was detected")
    if metrics.throttling_detected:
        failures.append("thermal throttling was detected")
    if metrics.malformed_or_unsafe_events:
        failures.append("malformed or unsafe model behavior was observed")
    return failures


def _memory_used_gb(path: Path) -> float:
    values: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, remainder = line.partition(":")
            if separator:
                values[name] = int(remainder.strip().split()[0])
        return max(0.0, (values["MemTotal"] - values["MemAvailable"]) / 1024**2)
    except (OSError, KeyError, ValueError, IndexError):
        return 0.0


def _temperature_c(path: Path) -> float:
    try:
        return max(0.0, float(path.read_text(encoding="utf-8").strip()) / 1000)
    except (OSError, ValueError):
        return 0.0


def _throttle_flags() -> int:
    try:
        completed = subprocess.run(
            ["vcgencmd", "get_throttled"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        _, separator, value = completed.stdout.strip().partition("=")
        return int(value, 16) if separator else 0
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0
