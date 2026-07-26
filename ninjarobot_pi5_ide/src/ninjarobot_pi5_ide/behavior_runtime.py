"""Sequential-stage, concurrent-operation behavior execution."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from .behavior_models import (
    BehaviorDefinition,
    BehaviorOperation,
    DriveOperation,
    FaceOperation,
    MelodyName,
    MelodyOperation,
    TextOperation,
    WaitOperation,
)
from .buzzer import BuzzerDevice
from .display import DisplayDevice
from .face_renderer import render_face

Melody = tuple[tuple[int | None, float], ...]
DriveHandler = Callable[[DriveOperation, str], Coroutine[Any, Any, dict[str, Any]]]
FailureHandler = Callable[[Exception], Coroutine[Any, Any, Any]]


class MelodyProvider(Protocol):
    """Resolve one approved existing pi5buzzer melody into bounded notes."""

    def __call__(self, name: MelodyName) -> Melody:
        """Return frequency/duration pairs; None represents a silent pause."""


def load_pi5buzzer_melody(name: MelodyName) -> Melody:
    """Load an existing pi5buzzer emotion without importing its CLI or runtime."""
    notes_module = importlib.import_module("pi5buzzer.notes")
    notes = cast(dict[str, int], getattr(notes_module, "NOTES"))
    emotions = cast(dict[str, list[tuple[str, float]]], getattr(notes_module, "EMOTION_SOUNDS"))
    try:
        source = emotions[name]
    except KeyError as exc:
        raise ValueError(f"pi5buzzer does not provide the '{name}' melody") from exc
    melody: list[tuple[int | None, float]] = []
    for note_name, duration in source:
        frequency = None if note_name == "pause" else notes.get(note_name)
        if note_name != "pause" and frequency is None:
            raise ValueError(f"pi5buzzer melody '{name}' contains unknown note '{note_name}'")
        if not 0.01 <= duration <= 5.0:
            raise ValueError(f"pi5buzzer melody '{name}' contains an unsafe duration")
        melody.append((frequency, duration))
    if not melody:
        raise ValueError(f"pi5buzzer melody '{name}' is empty")
    return tuple(melody)


@dataclass(frozen=True)
class StageResult:
    """Auditable result of one completed behavior stage."""

    name: str
    operations: tuple[dict[str, Any], ...]


class BehaviorRunner:
    """Run one expression at a time while sharing display and buzzer devices."""

    def __init__(
        self,
        *,
        display: DisplayDevice,
        buzzer: BuzzerDevice,
        melody_provider: MelodyProvider = load_pi5buzzer_melody,
        drive_handler: DriveHandler | None = None,
        failure_handler: FailureHandler | None = None,
    ) -> None:
        self._display = display
        self._buzzer = buzzer
        self._melody_provider = melody_provider
        self._drive_handler = drive_handler
        self._failure_handler = failure_handler
        self._run_lock = asyncio.Lock()
        self._active_task: asyncio.Task[Any] | None = None
        self._closed = False

    def set_drive_handler(self, handler: DriveHandler) -> None:
        """Attach the motion controller after robot assembly wiring."""
        self._drive_handler = handler

    def set_failure_handler(self, handler: FailureHandler) -> None:
        """Attach Level 2 driver-failure cleanup after assembly wiring."""
        self._failure_handler = handler

    async def start(self) -> None:
        """Initialize shared expression devices without producing output."""
        if self._closed:
            raise RuntimeError("behavior runner is closed")
        await asyncio.gather(self._display.start(), self._buzzer.start())

    async def run(self, definition: BehaviorDefinition) -> dict[str, Any]:
        """Run expression stages in order and operations within each stage together."""
        if definition.contains_motion and self._drive_handler is None:
            raise ValueError("movement execution is not enabled until the motion safety layer runs")
        if self._closed:
            raise RuntimeError("behavior runner is closed")
        async with self._run_lock:
            current = asyncio.current_task()
            if current is None:
                raise RuntimeError("behavior execution requires an asyncio task")
            self._active_task = current
            completed: list[StageResult] = []
            try:
                for stage in definition.stages:
                    operation_results = await self._run_concurrently(
                        tuple(
                            self._run_operation(operation, behavior_name=definition.name)
                            for operation in stage.operations
                        )
                    )
                    completed.append(
                        StageResult(name=stage.name, operations=tuple(operation_results))
                    )
            except asyncio.CancelledError:
                await self._buzzer.stop()
                raise
            except Exception as exc:
                await self._buzzer.stop()
                if self._failure_handler is not None:
                    await self._failure_handler(exc)
                raise
            finally:
                if self._active_task is current:
                    self._active_task = None
            return {
                "name": definition.name,
                "category": definition.category,
                "stages": [
                    {
                        "name": stage.name,
                        "operations": list(stage.operations),
                    }
                    for stage in completed
                ],
                "simulated": self._display.simulated and self._buzzer.simulated,
            }

    async def stop(self) -> dict[str, Any]:
        """Cancel the active expression and silence the buzzer."""
        active = self._active_task
        current = asyncio.current_task()
        if active is not None and active is not current and not active.done():
            active.cancel()
        await self._buzzer.stop()
        if active is not None and active is not current:
            await asyncio.gather(active, return_exceptions=True)
        return {"stopped": True}

    async def health(self) -> dict[str, str]:
        """Report expression-device readiness without producing output."""
        display_health, buzzer_health = await asyncio.gather(
            self._display.health(),
            self._buzzer.health(),
        )
        return {
            "display": display_health.value,
            "buzzer": buzzer_health.value,
        }

    async def close(self) -> None:
        """Cancel expression work, silence, and release both devices."""
        if self._closed:
            return
        try:
            await self.stop()
        finally:
            await asyncio.gather(
                self._buzzer.close(),
                self._display.close(),
                return_exceptions=True,
            )
            self._closed = True

    async def _run_operation(
        self,
        operation: BehaviorOperation,
        *,
        behavior_name: str,
    ) -> dict[str, Any]:
        if isinstance(operation, FaceOperation):
            return await self._show_face(operation)
        if isinstance(operation, TextOperation):
            result = await self._display.show_text(
                text=operation.text,
                font_size=operation.font_size,
                foreground=operation.foreground,
                background=operation.background,
            )
            await _hold(operation.hold_seconds)
            return {"kind": "text", **result}
        if isinstance(operation, MelodyOperation):
            return await self._play_melody(operation)
        if isinstance(operation, WaitOperation):
            await asyncio.sleep(operation.seconds)
            return {"kind": "wait", "seconds": operation.seconds}
        if isinstance(operation, DriveOperation):
            if self._drive_handler is None:
                raise ValueError("drive operations require the Phase 4.3 motion controller")
            return await self._drive_handler(operation, behavior_name)
        raise TypeError(f"unsupported behavior operation: {type(operation).__name__}")

    async def _show_face(self, operation: FaceOperation) -> dict[str, Any]:
        width, height = await self._display.dimensions()
        image = render_face(
            operation.expression,
            width=width,
            height=height,
            background=operation.background,
            foreground=operation.foreground,
            accent=operation.accent,
        )
        result = await self._display.show_image(
            image,
            source=f"face:{operation.expression}",
        )
        await _hold(operation.hold_seconds)
        return {"kind": "face", "expression": operation.expression, **result}

    async def _play_melody(self, operation: MelodyOperation) -> dict[str, Any]:
        melody = self._melody_provider(operation.melody)
        interrupted = False
        for frequency, duration in melody:
            if frequency is None:
                await asyncio.sleep(duration)
                continue
            result = await self._buzzer.play(
                frequency_hz=frequency,
                duration_seconds=duration,
                volume=operation.volume,
            )
            interrupted = interrupted or bool(result["interrupted"])
            if interrupted:
                break
        return {
            "kind": "melody",
            "melody": operation.melody,
            "notes": len(melody),
            "interrupted": interrupted,
        }

    @staticmethod
    async def _run_concurrently(
        coroutines: Sequence[Coroutine[Any, Any, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        tasks = [asyncio.create_task(coroutine) for coroutine in coroutines]
        try:
            return list(await asyncio.gather(*tasks))
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise


async def _hold(seconds: float | None) -> None:
    if seconds is not None:
        await asyncio.sleep(seconds)
