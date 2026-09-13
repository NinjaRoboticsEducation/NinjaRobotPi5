"""Finite, opt-in distance game; all device work remains owned by the IDE."""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from statistics import median
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .models import ActionRequest, CapabilityDescriptor, ResourceHealth, RiskLevel

if TYPE_CHECKING:
    from .robot import RobotAssembly


class GameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    duration_seconds: Annotated[int, Field(ge=5, le=60)] = 30
    mode: Literal["distance_tone"] = "distance_tone"


Band = Literal["near", "middle", "far"]


def next_band(distance_mm: float, previous: Band | None) -> Band | None:
    if not math.isfinite(distance_mm) or not 50 <= distance_mm <= 600:
        return None
    if previous == "near" and distance_mm < 170:
        return "near"
    if previous == "middle" and 130 <= distance_mm < 320:
        return "middle"
    if previous == "far" and distance_mm >= 280:
        return "far"
    return "near" if distance_mm < 150 else "middle" if distance_mm < 300 else "far"


class SampleFilter:
    """Reject stale/cached samples and wall-clock jumps before smoothing."""

    def __init__(self) -> None:
        self.values: deque[int] = deque(maxlen=3)
        self.band: Band | None = None
        self.last_stamp: float | None = None
        self.last_completed: float | None = None

    def clear(self) -> None:
        self.values.clear()
        self.band = None

    def accept(
        self,
        sample: dict[str, Any],
        *,
        started: float,
        completed: float,
        wall_started: float,
        wall_completed: float,
    ) -> Band | None:
        distance = sample.get("distance_mm")
        raw = sample.get("raw_value")
        stamp = sample.get("sensor_timestamp")
        if (
            not isinstance(distance, int)
            or isinstance(distance, bool)
            or not isinstance(raw, int)
            or isinstance(raw, bool)
            or not isinstance(stamp, (float, int))
            or isinstance(stamp, bool)
        ):
            self.clear()
            return None
        valid = (
            type(distance) is int
            and 50 <= distance <= 600
            and type(raw) is int
            and 0 < raw < 8190
            and type(stamp) in {float, int}
            and math.isfinite(stamp)
            and 0 <= completed - started <= 0.25
            and 0 <= wall_completed - stamp <= 0.4
            and abs((wall_completed - wall_started) - (completed - started)) <= 0.1
            and (self.last_stamp is None or stamp > self.last_stamp)
        )
        if not valid:
            self.clear()
            return None
        if self.last_completed is not None and completed - self.last_completed > 0.4:
            self.clear()
        self.last_completed = completed
        self.last_stamp = stamp
        self.values.append(distance)
        self.band = next_band(median(self.values), self.band)
        return self.band


class DistanceGame:
    """Single session with independent cancellation and no servo capability."""

    def __init__(
        self,
        robot: RobotAssembly,
        *,
        enabled: bool,
        volume: int,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._clock, self._wall_clock, self._sleep = clock, wall_clock, sleep
        self.robot = robot
        self.enabled = enabled
        self.volume = volume
        self._admission = asyncio.Lock()
        self._other_actions = 0
        self._reserved: str | None = None
        self._task: asyncio.Task[Any] | None = None
        self._stopping = False
        self._cancel_requested = False
        self._state: dict[str, Any] = {"state": "idle", "reason": None}

    def status(self) -> dict[str, Any]:
        return {"enabled": self.enabled, **self._state}

    @asynccontextmanager
    async def admission(self, request: ActionRequest) -> AsyncIterator[None]:
        name = request.capability
        if name in {
            "game.distance.stop",
            "game.distance.status",
            "behavior.stop",
            "servo.stop",
            "buzzer.stop",
        }:
            yield
            return
        is_game = name == "game.distance.run"
        self.robot.ensure_action_allowed(name)
        if is_game:
            GameRequest.model_validate(request.arguments)
        async with self._admission:
            if is_game:
                if not self.enabled:
                    raise RuntimeError("distance game disabled; enable distance_game.enabled first")
                if (
                    self._reserved
                    or self._other_actions
                    or self._stopping
                    or self._state["state"] == "faulted"
                    or self.robot.motion.active
                    or self.robot._foreground_behaviors
                    or self.robot._ambient_face == "camera"
                ):
                    raise RuntimeError(
                        "distance game busy or faulted; stop/recover before a new request"
                    )
                self._reserved = request.action_id
                self._cancel_requested = False
            else:
                self._other_actions += 1
        try:
            if not is_game:
                if name != "system.resume":
                    await self.stop("incoming_action")
                if name in {"servo.move", "behavior.execute_movement", "behavior.run"}:
                    if self.robot.distance._recovery_required:
                        raise RuntimeError("distance recovery required before movement")
            yield
        finally:
            async with self._admission:
                if is_game:
                    self._reserved = None
                else:
                    self._other_actions -= 1

    async def stop(self, reason: str = "operator_stop") -> dict[str, Any]:
        self._cancel_requested = True
        task = self._task
        if task is None:
            if self._state["state"] == "faulted":
                raise RuntimeError("game cleanup unconfirmed; use system recovery before retrying")
            return self.status()
        if task is asyncio.current_task():
            return self.status()
        self._state["reason"] = reason
        self._stopping = True
        try:
            if not task.done() and not task.cancelling():
                task.cancel()
            # Silence independently of a blocked display/read. Never claim success
            # until both output and the owned run have actually completed.
            async with asyncio.timeout(1.0):
                await self.robot.buzzer.stop()
                await asyncio.shield(task)
        except asyncio.CancelledError:
            if not task.done():
                raise
        except Exception:
            self._state.update(state="faulted", reason="cleanup_unconfirmed")
            raise
        finally:
            self._stopping = False
        if self._state["state"] == "faulted":
            raise RuntimeError("game output cleanup failed; explicit system recovery required")
        return self.status()

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        request = GameRequest.model_validate(arguments)
        if not self.enabled or self._reserved is None or self._task is not None:
            raise RuntimeError("game requires one admitted request")
        if self._cancel_requested:
            return {"state": "cancelled", "reason": "stopped_before_start"}
        self.robot.ensure_action_allowed("game.distance.run")
        self._task = asyncio.current_task()
        started = self._clock()
        self._state = dict(
            state="running",
            run_id=self._reserved or uuid4().hex,
            reason=None,
            valid_samples=0,
            invalid_samples=0,
            tone_seconds=0.0,
        )
        foreground = False
        try:
            if not self.robot.display.enabled or not self.robot.buzzer.enabled:
                self._state.update(state="unavailable", reason="display_or_buzzer_disabled")
                return self.status()
            if any(
                value is not ResourceHealth.READY
                for value in await asyncio.gather(
                    self.robot.distance.health(),
                    self.robot.buzzer.health(),
                    self.robot.display.health(),
                )
            ):
                self._state.update(state="unavailable", reason="required_device_unavailable")
                return self.status()
            await self.robot._begin_foreground_behavior(game=True)
            foreground = True
            if self.robot.audio is None:
                await self._loop(request, started)
            else:
                async with self.robot.audio.foreground():
                    await self._loop(request, started)
            self._state["state"] = (
                "unavailable" if self._state["reason"] == "readings_unavailable" else "finished"
            )
        except asyncio.CancelledError:
            if self._state["state"] != "faulted":
                self._state.update(state="cancelled", reason=self._state["reason"] or "cancelled")
        except Exception as exc:
            self._state.update(state="faulted", reason=type(exc).__name__)
            raise
        finally:
            try:
                if foreground:
                    async with asyncio.timeout(1.0):
                        await self.robot.buzzer.stop()
            except BaseException:
                self._state.update(state="faulted", reason="silence_unconfirmed")
                raise
            finally:
                self._state["elapsed_seconds"] = round(self._clock() - started, 3)
                # Never write a final game frame over a higher-priority owner.
                try:
                    if foreground:
                        await self.robot._end_foreground_behavior()
                except BaseException:
                    self._state.update(state="faulted", reason="presentation_cleanup_unconfirmed")
                    raise
                finally:
                    self._task = None
        return self.status()

    async def _loop(self, request: GameRequest, started: float) -> None:
        samples = SampleFilter()
        last_valid = self._clock()
        last_pulse = -math.inf
        shown: str | None = None
        deadline = started + request.duration_seconds
        while self._clock() < deadline and not self._cancel_requested:
            self.robot.ensure_action_allowed("game.distance.run")
            tick, wall = self._clock(), self._wall_clock()
            band = None
            try:
                async with asyncio.timeout(min(0.25, max(0.001, deadline - tick))):
                    sample = await self.robot.distance.execute({})
                band = samples.accept(
                    sample,
                    started=tick,
                    completed=self._clock(),
                    wall_started=wall,
                    wall_completed=self._wall_clock(),
                )
            except Exception:
                samples.clear()
            if band is None:
                self._state["invalid_samples"] += 1
                await self.robot.buzzer.stop()
                label = "Hand: 5-60 cm\nStop: /game stop"
                if self._clock() - last_valid >= 2:
                    self._state["reason"] = "readings_unavailable"
                    return
            else:
                last_valid = self._clock()
                self._state["valid_samples"] += 1
                label = f"{band.upper()}\nStop: /game stop"
            if label != shown:
                async with asyncio.timeout(0.25):
                    await self.robot.display.show_text(
                        text=label, font_size=18, foreground="#FFFFFF", background="#000020"
                    )
                shown = label
            # Short pulses finish before freshness expires; no background melody,
            # read backlog or output watchdog that itself could outlive the game.
            now = self._clock()
            if (
                band is not None
                and now - tick < 0.29
                and now + 0.11 <= deadline
                and now - last_pulse >= 1 / 3
                and self._state["tone_seconds"] + 0.06 <= 10
            ):
                last_pulse = now
                self._state["tone_seconds"] += 0.06
                await self.robot.buzzer.play(
                    frequency_hz={"near": 880, "middle": 660, "far": 440}[band],
                    duration_seconds=0.06,
                    volume=self.volume,
                )
            await self._sleep(max(0, min(deadline - self._clock(), 0.2 - (self._clock() - tick))))


class DistanceGameAdapter:
    def __init__(self, game: DistanceGame, operation: Literal["run", "stop", "status"]) -> None:
        self.game = game
        self.operation = operation
        self.descriptor = CapabilityDescriptor(
            name=f"game.distance.{operation}",
            version="1.0.0",
            description=(
                "Explicitly play a finite hand-distance sound game. No wheels or capture. "
                "Closer hand means higher tone; stop independently with game.distance.stop."
            )
            if operation == "run"
            else f"{operation.title()} the distance game without starting hardware.",
            input_schema=GameRequest.model_json_schema()
            if operation == "run"
            else {"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object"},
            risk=RiskLevel.LOW if operation == "run" else RiskLevel.READ_ONLY,
            resources=("distance_sensor", "display", "buzzer", "i2c1", "vl53l0x-0x29")
            if operation == "run"
            else (),
            default_timeout_seconds=63.0 if operation == "run" else 2.0,
            idempotent=operation != "run",
            cancellable=True,
            confirmation_required=False,
        )

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass  # RobotAssembly owns the session and closes before devices.

    async def health(self) -> ResourceHealth:
        return (
            ResourceHealth.READY
            if self.operation != "run" or self.game.enabled
            else ResourceHealth.NOT_CONFIGURED
        )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.operation == "run":
            return await self.game.run(arguments)
        if arguments:
            raise ValueError("game stop/status accept no arguments")
        return await self.game.stop() if self.operation == "stop" else self.game.status()
