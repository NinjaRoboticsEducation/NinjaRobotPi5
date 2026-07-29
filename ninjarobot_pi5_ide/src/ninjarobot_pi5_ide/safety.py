"""Persistent two-level safety state and guarded drive execution."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .behavior_models import DriveOperation
from .config import BehaviorConfig
from .errors import IDEError
from .servo import ServoDevice


class DistanceReader(Protocol):
    """Distance surface used by the motion guard."""

    async def start(self) -> None:
        """Initialize ranging."""

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Read one validated distance."""

    async def close(self) -> None:
        """Stop ranging and release I2C."""


class AsyncClosable(Protocol):
    """Device that can be closed during a full system stop."""

    async def close(self) -> None:
        """Release the device."""


class MotionSafetyError(RuntimeError):
    """A policy or preflight block that is not a hardware-driver failure."""


@dataclass(frozen=True)
class SafetySnapshot:
    """Durable restart gates and their most recent reason."""

    schema_version: int = 1
    motion_latched: bool = False
    system_latched: bool = False
    reason: str | None = None
    updated_at: str | None = None


class SafetyStateStore:
    """Owner-private atomic safety state shared by separate CLI invocations."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        """Return the configured state path."""
        return self._path

    def read(self) -> SafetySnapshot:
        """Read state; malformed state fails closed for physical motion."""
        with self._lock:
            if not self._path.exists():
                return SafetySnapshot()
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
                if (
                    not isinstance(payload, dict)
                    or payload.get("schema_version") != 1
                    or not isinstance(payload.get("motion_latched"), bool)
                    or not isinstance(payload.get("system_latched"), bool)
                    or (
                        payload.get("reason") is not None
                        and not isinstance(payload.get("reason"), str)
                    )
                    or (
                        payload.get("updated_at") is not None
                        and not isinstance(payload.get("updated_at"), str)
                    )
                ):
                    raise ValueError("invalid safety state shape")
                return SafetySnapshot(
                    schema_version=1,
                    motion_latched=payload["motion_latched"],
                    system_latched=payload["system_latched"],
                    reason=payload["reason"],
                    updated_at=payload["updated_at"],
                )
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                return SafetySnapshot(
                    motion_latched=True,
                    system_latched=True,
                    reason="invalid_safety_state",
                    updated_at=_utc_now(),
                )

    def latch_motion(self, reason: str) -> SafetySnapshot:
        """Persist a Level 1 motion latch."""
        current = self.read()
        snapshot = SafetySnapshot(
            motion_latched=True,
            system_latched=current.system_latched,
            reason=reason,
            updated_at=_utc_now(),
        )
        self._write(snapshot)
        return snapshot

    def latch_system(self, reason: str) -> SafetySnapshot:
        """Persist a Level 2 system latch, which also blocks motion."""
        snapshot = SafetySnapshot(
            motion_latched=True,
            system_latched=True,
            reason=reason,
            updated_at=_utc_now(),
        )
        self._write(snapshot)
        return snapshot

    def clear_motion(self) -> SafetySnapshot:
        """Clear Level 1 only when no Level 2 latch remains."""
        current = self.read()
        if current.system_latched:
            raise RuntimeError("the system latch must be resumed before motion")
        snapshot = SafetySnapshot(updated_at=_utc_now())
        self._write(snapshot)
        return snapshot

    def clear_system(self) -> SafetySnapshot:
        """Clear both levels after explicit confirmation and health checks."""
        snapshot = SafetySnapshot(updated_at=_utc_now())
        self._write(snapshot)
        return snapshot

    def _write(self, snapshot: SafetySnapshot) -> None:
        with self._lock:
            directory = self._path.parent
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink():
                raise RuntimeError("safety state directory must not be a symbolic link")
            directory.chmod(0o700)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".safety-",
                suffix=".tmp",
                dir=directory,
                text=True,
            )
            temporary = Path(temporary_name)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(asdict(snapshot), handle, indent=2, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self._path)
                self._path.chmod(0o600)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise


UndervoltageProvider = Callable[[], bool]
WarningHandler = Callable[[str], Coroutine[Any, Any, Any]]


def raspberry_pi_undervoltage_active() -> bool:
    """Return current Raspberry Pi undervoltage state from `vcgencmd` bit zero."""
    completed = subprocess.run(
        ["vcgencmd", "get_throttled"],
        check=True,
        capture_output=True,
        text=True,
        timeout=2.0,
    )
    output = completed.stdout.strip()
    if not output.startswith("throttled=0x"):
        raise ValueError(f"unexpected vcgencmd output: {output}")
    return bool(int(output.removeprefix("throttled=0x"), 16) & 0x1)


class _WatchdogThread:
    """Stop PWM directly if the asyncio control loop stops updating."""

    def __init__(self, timeout_seconds: float, on_timeout: Callable[[], None]) -> None:
        self._timeout_seconds = timeout_seconds
        self._on_timeout = on_timeout
        self._heartbeat = time.monotonic()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self.beat()
        self._thread = threading.Thread(
            target=self._run,
            name="ninjarobot-motion-watchdog",
            daemon=True,
        )
        self._thread.start()

    def beat(self) -> None:
        with self._lock:
            self._heartbeat = time.monotonic()

    def close(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=min(self._timeout_seconds, 1.0))

    def _run(self) -> None:
        interval = min(max(self._timeout_seconds / 5, 0.02), 0.2)
        while not self._stop.wait(interval):
            with self._lock:
                elapsed = time.monotonic() - self._heartbeat
            if elapsed > self._timeout_seconds:
                self._on_timeout()
                return


class MotionController:
    """Execute continuous wheel commands behind approved safety gates."""

    def __init__(
        self,
        *,
        servo: ServoDevice,
        distance: DistanceReader,
        config: BehaviorConfig,
        state: SafetyStateStore,
        undervoltage_provider: UndervoltageProvider = raspberry_pi_undervoltage_active,
        warning_handler: WarningHandler | None = None,
    ) -> None:
        self._servo = servo
        self._distance = distance
        self._config = config
        self._state = state
        self._undervoltage_provider = undervoltage_provider
        self._warning_handler = warning_handler
        self._motion_lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._stop_reason: str | None = None
        self._warnings: list[str] = []
        self._fatal_error: Exception | None = None
        self._active = False

    @property
    def active(self) -> bool:
        """Return whether an integrated drive action currently owns the motors."""
        return self._active

    async def drive(self, operation: DriveOperation, behavior_name: str) -> dict[str, Any]:
        """Run one guarded continuous drive until a stop trigger or optional timeout."""
        async with self._motion_lock:
            snapshot = self._state.read()
            if snapshot.system_latched:
                raise MotionSafetyError(
                    f"system is latched ({snapshot.reason}); run system resume --confirm"
                )
            if snapshot.motion_latched:
                raise MotionSafetyError(
                    f"motion is latched ({snapshot.reason}); run motion resume --confirm"
                )
            targets = self._resolve_targets(operation)
            await asyncio.gather(self._servo.start(), self._distance.start())
            self._warnings = list(_direction_warnings(behavior_name))
            self._stop_event.clear()
            self._stop_reason = None
            self._fatal_error = None
            self._active = True
            loop = asyncio.get_running_loop()
            watchdog = _WatchdogThread(
                self._config.watchdog_timeout_seconds,
                lambda: self._watchdog_timeout(loop),
            )
            monitor_tasks = [
                asyncio.create_task(self._watchdog_heartbeat(watchdog)),
                asyncio.create_task(self._distance_monitor(operation)),
                asyncio.create_task(self._undervoltage_monitor()),
            ]
            watchdog.start()
            try:
                movement = await self._servo.move_group(
                    targets=targets,
                    speed_mode=operation.speed_mode,
                )
                if movement["interrupted"]:
                    await self.stop_motion("driver_interrupted", latch=True)
                if operation.hold_seconds is None:
                    while not self._stop_event.is_set():
                        watchdog.beat()
                        await asyncio.sleep(self._config.distance_poll_interval_seconds)
                else:
                    try:
                        async with asyncio.timeout(operation.hold_seconds):
                            while not self._stop_event.is_set():
                                watchdog.beat()
                                await asyncio.sleep(self._config.distance_poll_interval_seconds)
                    except TimeoutError:
                        await self.stop_motion("movement_duration_complete", latch=False)
                if self._fatal_error is not None:
                    raise self._fatal_error
            except asyncio.CancelledError:
                await self.stop_motion("cancelled", latch=False)
                raise
            except Exception:
                await self.stop_motion("servo_driver_failure", latch=False)
                raise
            finally:
                watchdog.close()
                for task in monitor_tasks:
                    task.cancel()
                await asyncio.gather(*monitor_tasks, return_exceptions=True)
                await self._servo.stop()
                self._active = False
            return {
                "kind": "drive",
                "targets": operation.targets,
                "resolved_endpoints": targets,
                "speed_mode": operation.speed_mode,
                "stop_reason": self._stop_reason,
                "warnings": list(self._warnings),
                "simulated": self._servo.simulated,
            }

    async def stop_motion(self, reason: str, *, latch: bool) -> dict[str, Any]:
        """Stop both motors and optionally persist a Level 1 restart gate."""
        if latch:
            self._state.latch_motion(reason)
        self._stop_reason = reason
        self._stop_event.set()
        servo_result = await self._servo.stop()
        return {
            "level": 1,
            "reason": reason,
            "latched": latch,
            "servo": servo_result,
        }

    def resume(self, *, confirmed: bool) -> SafetySnapshot:
        """Clear a Level 1 latch after explicit user confirmation."""
        if not confirmed:
            raise ValueError("motion resume requires explicit confirmation")
        if self._active:
            raise RuntimeError("motion cannot resume while a movement is active")
        return self._state.clear_motion()

    async def _distance_monitor(self, operation: DriveOperation) -> None:
        below_count = 0
        while not self._stop_event.is_set():
            try:
                reading = await self._distance.execute({})
            except IDEError as exc:
                below_count = 0
                if exc.details.code != "DEVICE_OUT_OF_RANGE":
                    await self._warn("distance reading unavailable; movement continues")
            except Exception:
                below_count = 0
                await self._warn("distance reading unavailable; movement continues")
            else:
                if not _fresh(reading):
                    below_count = 0
                    await self._warn("distance reading stale; movement continues")
                elif reading["distance_mm"] <= self._config.obstacle_threshold_mm:
                    below_count += 1
                    if (
                        operation.obstacle_policy == "front_guarded"
                        and below_count >= self._config.obstacle_consecutive_readings
                    ):
                        await self.stop_motion("front_obstacle", latch=True)
                        return
                else:
                    below_count = 0
            await asyncio.sleep(self._config.distance_poll_interval_seconds)

    async def _undervoltage_monitor(self) -> None:
        while not self._stop_event.is_set():
            try:
                active = await asyncio.to_thread(self._undervoltage_provider)
            except Exception:
                await self._warn("undervoltage status unavailable; movement continues")
            else:
                if active:
                    await self.stop_motion("undervoltage", latch=True)
                    return
            await asyncio.sleep(min(self._config.watchdog_timeout_seconds / 2, 1.0))

    async def _warn(self, warning: str) -> None:
        if warning in self._warnings:
            return
        self._warnings.append(warning)
        if self._warning_handler is None:
            return
        try:
            await self._warning_handler(warning)
        except Exception as exc:
            self._fatal_error = exc
            await self.stop_motion("warning_display_driver_failure", latch=False)

    async def _watchdog_heartbeat(self, watchdog: _WatchdogThread) -> None:
        interval = max(self._config.watchdog_timeout_seconds / 4, 0.01)
        while not self._stop_event.is_set():
            watchdog.beat()
            await asyncio.sleep(interval)

    def _watchdog_timeout(self, loop: asyncio.AbstractEventLoop) -> None:
        self._stop_reason = "software_watchdog"
        try:
            self._state.latch_motion("software_watchdog")
        except Exception:
            pass
        try:
            self._servo.emergency_stop_sync()
        finally:
            loop.call_soon_threadsafe(self._stop_event.set)

    def _resolve_targets(self, operation: DriveOperation) -> dict[str, float]:
        unknown = sorted(set(operation.targets) - set(self._config.servo_roles))
        if unknown:
            raise MotionSafetyError(f"movement contains unmapped servo roles: {', '.join(unknown)}")
        required = {self._config.left_motor_role, self._config.right_motor_role}
        missing = sorted(required - set(operation.targets))
        if missing:
            raise MotionSafetyError(
                f"movement is missing required motor roles: {', '.join(missing)}"
            )
        return {
            self._config.servo_roles[role]: target for role, target in operation.targets.items()
        }


FullStopCallback = Callable[[], Coroutine[Any, Any, Any]]


class SystemSafetyController:
    """Coordinate Level 2 cleanup and persistent driver-failure latching."""

    def __init__(
        self,
        *,
        motion: MotionController,
        state: SafetyStateStore,
        silence_buzzer: FullStopCallback,
        show_stopped: FullStopCallback,
        sensors: Sequence[AsyncClosable],
        display_hold_seconds: float = 2.0,
    ) -> None:
        self._motion = motion
        self._state = state
        self._silence_buzzer = silence_buzzer
        self._show_stopped = show_stopped
        self._sensors = tuple(sensors)
        self._display_hold_seconds = display_hold_seconds
        self._stop_lock = asyncio.Lock()
        self._locally_stopped = False

    @property
    def stopped(self) -> bool:
        """Return whether this assembly has completed a Level 2 stop."""
        return self._locally_stopped or self._state.read().system_latched

    async def full_stop(self, reason: str, *, latch: bool) -> dict[str, Any]:
        """Stop motion, ranging/capture devices, and sound; preserve the display."""
        async with self._stop_lock:
            if latch:
                snapshot = self._state.latch_system(reason)
            else:
                snapshot = self._state.read()
            results = await asyncio.gather(
                self._motion.stop_motion(reason, latch=False),
                self._silence_buzzer(),
                *(sensor.close() for sensor in self._sensors),
                return_exceptions=True,
            )
            try:
                await self._show_stopped()
                await asyncio.sleep(self._display_hold_seconds)
            except Exception:
                pass
            self._locally_stopped = True
            return {
                "level": 2,
                "reason": reason,
                "latched": latch,
                "persistent_state": asdict(snapshot),
                "cleanup_errors": [
                    f"{type(result).__name__}: {result}"
                    for result in results
                    if isinstance(result, BaseException)
                ],
            }

    async def resume_system(
        self,
        *,
        confirmed: bool,
        health_checks: Sequence[Callable[[], Coroutine[Any, Any, bool]]],
    ) -> SafetySnapshot:
        """Clear a driver-failure latch only after explicit healthy probes."""
        if not confirmed:
            raise ValueError("system resume requires explicit confirmation")
        results = await asyncio.gather(*(check() for check in health_checks))
        if not all(results):
            raise RuntimeError("system resume refused because a required health check failed")
        self._locally_stopped = False
        return self._state.clear_system()


def _fresh(reading: dict[str, Any]) -> bool:
    timestamp = reading.get("sensor_timestamp")
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
        return False
    return abs(time.time() - float(timestamp)) <= 2.0


def _direction_warnings(name: str) -> tuple[str, ...]:
    if name == "move_backward":
        return ("front sensor does not protect the rear",)
    return ()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
