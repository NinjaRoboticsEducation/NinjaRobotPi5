"""Durable local reminders with reviewed effects and conservative recovery."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .memory_migrations import migrate_agent_database
from .task_models import LocalTask, TaskStatus, TaskStep, exact_due_time, next_occurrence

Notification = Callable[[LocalTask], Awaitable[tuple[bool, str]]]


class TaskService:
    """Use the Agent database, never a model, to deliver saved reminders.

    The running Agent owns this lifecycle. SQLite transactions serialize claims;
    startup recovery requires exclusive service ownership, as enforced by IPC.
    """

    def __init__(
        self,
        path: Path,
        notify: Notification,
        *,
        clock: Callable[[], datetime] | None = None,
        retention_days: int = 7,
    ) -> None:
        if not 1 <= retention_days <= 365:
            raise ValueError("task retention must be 1 through 365 days")
        self._path = path
        self._notify = notify
        self._clock = clock or (lambda: datetime.now(UTC))
        self._retention_days = retention_days
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self._worker: asyncio.Task[None] | None = None
        self._closed = False
        self._closing = False
        self._pause_lock = asyncio.Lock()
        self._last_error: str | None = None

    async def start(self, *, background: bool = True) -> None:
        await asyncio.to_thread(self._start_sync)
        if background and self._worker is None:
            self._worker = asyncio.create_task(self._run(), name="local-reminders")

    def _start_sync(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("task service is closed")
            if self._connection is not None:
                return
            # ConversationStore creates this private database first. Never create
            # a second database silently if a configuration/path is wrong.
            connection = sqlite3.connect(
                self._path.resolve().as_uri() + "?mode=rw",
                uri=True,
                check_same_thread=False,
                timeout=5,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                migrate_agent_database(connection)
                with connection:
                    for row in connection.execute(
                        "SELECT record_json FROM local_tasks WHERE status = 'running'"
                    ).fetchall():
                        task = LocalTask.model_validate_json(row[0])
                        self._write(
                            connection,
                            task.model_copy(
                                update={
                                    "status": TaskStatus.UNCERTAIN,
                                    "updated_at": self._now(),
                                    "result": "Work was interrupted; an effect may have happened. "
                                    "Automatic repetition is disabled. Review before retrying.",
                                }
                            ),
                        )
            except BaseException:
                connection.close()
                raise
            self._connection = connection

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("task clock requires a time zone")
        return now.astimezone(UTC)

    def _db(self) -> sqlite3.Connection:
        if self._connection is None or self._closed:
            raise RuntimeError("task service is not running")
        return self._connection

    @staticmethod
    def _write(connection: sqlite3.Connection, task: LocalTask) -> None:
        connection.execute(
            "INSERT INTO local_tasks(task_id, owner_scope, user_id, status, due_at, updated_at, "
            "record_json, kind) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET status=excluded.status, "
            "due_at=excluded.due_at, updated_at=excluded.updated_at, "
            "record_json=excluded.record_json",
            (
                task.task_id,
                task.owner_scope,
                task.user_id,
                task.status.value,
                task.due_at.isoformat(),
                task.updated_at.isoformat(),
                task.model_dump_json(),
                task.kind,
            ),
        )

    @staticmethod
    def _get(connection: sqlite3.Connection, scope: str, task_id: str) -> LocalTask:
        row = connection.execute(
            "SELECT record_json FROM local_tasks WHERE owner_scope=? AND task_id=?",
            (scope, task_id),
        ).fetchone()
        if row is None:
            raise KeyError("task not found in the active user's scope")
        return LocalTask.model_validate_json(row[0])

    async def preview(
        self,
        *,
        scope: str,
        user_id: str | None,
        session_id: str,
        title: str,
        due_at: str,
        timezone: str,
        repeat: str = "none",
        notification: str = "text",
        notification_language: str = "en",
    ) -> LocalTask:
        now = self._now()
        task = LocalTask.model_validate(
            {
                "task_id": "task-" + uuid.uuid4().hex,
                "owner_scope": scope,
                "user_id": user_id,
                "source_session_id": session_id,
                "title": title.strip(),
                "created_at": now,
                "updated_at": now,
                "due_at": exact_due_time(due_at, timezone, now),
                "timezone": timezone,
                "repeat": repeat,
                "notification": notification,
                "notification_language": notification_language,
                "steps": (
                    TaskStep(description="Wait for the reviewed due time"),
                    TaskStep(description="Deliver the reviewed notification and record evidence"),
                ),
            }
        )
        if scope != (f"user:{user_id}" if user_id is not None else f"session:{session_id}"):
            raise ValueError("task scope must match the trusted active identity")
        await asyncio.to_thread(self._insert_sync, task)
        return task

    def _insert_sync(self, task: LocalTask) -> None:
        with self._lock, self._db() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM local_tasks WHERE owner_scope=? AND status IN "
                "('draft','queued','running')",
                (task.owner_scope,),
            ).fetchone()[0]
            if count >= 100:
                raise ValueError(
                    "review or cancel existing tasks; maximum 100 active tasks per scope"
                )
            self._write(connection, task)

    async def list(self, scope: str) -> tuple[LocalTask, ...]:
        def read() -> tuple[LocalTask, ...]:
            with self._lock:
                rows = (
                    self._db()
                    .execute(
                        "SELECT record_json FROM local_tasks WHERE owner_scope=? "
                        "ORDER BY updated_at DESC, task_id LIMIT 100",
                        (scope,),
                    )
                    .fetchall()
                )
                return tuple(LocalTask.model_validate_json(row[0]) for row in rows)

        return await asyncio.to_thread(read)

    async def model_page(
        self,
        scope: str,
        *,
        limit: int = 10,
        after: str = "",
        kind: str = "all",
        status: str = "all",
    ) -> dict[str, Any]:
        """Bounded model projection; ownership is applied before pagination.

        Immutable IDs give stable traversal without exposing execution evidence.
        Pages are live reads, not a snapshot across concurrent task changes.
        """
        if isinstance(limit, bool) or not 1 <= limit <= 20:
            raise ValueError("limit must be 1 through 20")
        if len(after) > 150 or kind not in {"all", "reminder", "request"}:
            raise ValueError("invalid task cursor or kind")
        if status not in {"all", "scheduled", *(item.value for item in TaskStatus)}:
            raise ValueError("invalid task status")

        def read() -> dict[str, Any]:
            clauses = ["owner_scope=?"]
            values: list[Any] = [scope]
            if kind != "all":
                clauses.append("kind=?")
                values.append(kind)
            if status == "scheduled":
                clauses.append("kind='reminder' AND status IN ('queued', 'running')")
            elif status != "all":
                clauses.append("status=?")
                values.append(status)
            where = " AND ".join(clauses)
            with self._lock:
                connection = self._db()
                total = connection.execute(
                    "SELECT COUNT(*) FROM local_tasks WHERE " + where, values
                ).fetchone()[0]
                rows = connection.execute(
                    "SELECT record_json FROM local_tasks WHERE "
                    + where
                    + " AND task_id>? ORDER BY task_id LIMIT ?",
                    [*values, after, limit + 1],
                ).fetchall()
            tasks = [LocalTask.model_validate_json(row[0]) for row in rows[:limit]]
            fields = {
                "task_id",
                "title",
                "kind",
                "status",
                "due_at",
                "timezone",
                "repeat",
                "notification",
                "notification_language",
            }
            projected = [task.model_dump(mode="json", include=fields) for task in tasks]
            # Account for JSON escaping as well as field length. Never split a
            # record or lose the last exposed cursor when shortening a page.
            while len(projected) > 1 and len(json.dumps(projected, ensure_ascii=False)) > 12_000:
                projected.pop()
            has_more = len(rows) > len(projected)
            return {
                "tasks": projected,
                "total": total,
                "has_more": has_more,
                "next_after": projected[-1]["task_id"] if has_more else None,
                "ordering": "task_id; live pages, not a snapshot",
            }

        return await asyncio.to_thread(read)

    async def begin_request(
        self,
        *,
        scope: str,
        user_id: str | None,
        session_id: str,
        title: str,
        limits: dict[str, int | float] | None = None,
    ) -> LocalTask:
        now = self._now()
        task = LocalTask(
            task_id="task-" + uuid.uuid4().hex,
            kind="request",
            owner_scope=scope,
            user_id=user_id,
            source_session_id=session_id,
            title=title[:200],
            status=TaskStatus.RUNNING,
            created_at=now,
            updated_at=now,
            due_at=now,
            timezone="UTC",
            steps=(
                TaskStep(
                    description="Produce a bounded response using approved tools",
                    status=TaskStatus.RUNNING,
                ),
            ),
            result="Working. Each tool still requires current Agent policy and IDE authorization.",
            limits=limits or {},
        )
        await asyncio.to_thread(self._insert_sync, task)
        return task

    async def record_request(
        self,
        scope: str,
        task_id: str,
        *,
        step: TaskStep | None = None,
        status: TaskStatus | None = None,
    ) -> None:
        def write() -> None:
            with self._lock, self._db() as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    task = self._get(connection, scope, task_id)
                except KeyError:
                    return
                if task.kind != "request" or task.status is not TaskStatus.RUNNING:
                    return
                steps = (*task.steps, step) if step is not None else task.steps
                updates: dict[str, Any] = {"steps": steps[-51:], "updated_at": self._now()}
                if status is not None:
                    statuses = {item.status for item in steps[1:]}
                    if TaskStatus.UNCERTAIN in statuses:
                        status_value = TaskStatus.UNCERTAIN
                    elif TaskStatus.FAILED in statuses and status is TaskStatus.COMPLETED:
                        status_value = TaskStatus.FAILED
                    else:
                        status_value = status
                    updates.update(
                        status=status_value,
                        result="Response processing ended. Review the recorded tool evidence; "
                        "a model reply alone does not verify an external outcome.",
                        steps=(steps[0].model_copy(update={"status": status_value}), *steps[1:]),
                    )
                self._write(connection, task.model_copy(update=updates))

        await asyncio.to_thread(write)

    async def change(
        self, scope: str, task_id: str, operation: str, *, minutes: int = 5
    ) -> LocalTask:
        """Only direct user controls call confirm/cancel/snooze, never model tools."""
        return await asyncio.to_thread(self._change_sync, scope, task_id, operation, minutes)

    def _change_sync(self, scope: str, task_id: str, operation: str, minutes: int) -> LocalTask:
        with self._lock, self._db() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = self._get(connection, scope, task_id)
            if task.kind == "request" and operation != "cancel":
                raise ValueError(
                    "request tasks can be cancelled; snooze/confirm apply only to reminders"
                )
            now = self._now()
            updates: dict[str, Any] = {"updated_at": now}
            if operation == "confirm":
                if task.status is TaskStatus.QUEUED:
                    return task  # A repeated confirmation must not create another delivery.
                if task.status is not TaskStatus.DRAFT:
                    raise ValueError("only the current draft can be confirmed")
                if now - task.updated_at > timedelta(minutes=10) or task.due_at <= now:
                    raise ValueError("preview expired or time passed; create a new preview")
                updates.update(
                    status=TaskStatus.QUEUED,
                    approved_at=now,
                    result="Saved; waiting.",
                    recurrence_anchor=task.recurrence_anchor or task.due_at,
                )
            elif operation == "cancel":
                if task.status is TaskStatus.COMPLETED:
                    raise ValueError("delivery already completed; cancellation cannot undo it")
                updates.update(
                    status=TaskStatus.CANCELLED,
                    result=(
                        "Cancelled during delivery; a notification may already have happened."
                        if task.status is TaskStatus.RUNNING
                        else "Cancelled; no further delivery."
                    ),
                )
            elif operation == "snooze":
                if (
                    isinstance(minutes, bool)
                    or not isinstance(minutes, int)
                    or not 1 <= minutes <= 1440
                ):
                    raise ValueError("snooze must be 1 through 1440 minutes")
                if task.status is TaskStatus.RUNNING:
                    raise ValueError("delivery is running; wait for its outcome before snoozing")
                updates.update(
                    status=TaskStatus.DRAFT,
                    due_at=now + timedelta(minutes=minutes),
                    approved_at=None,
                    occurrence=task.occurrence + 1,
                    result="Snooze preview only; confirm its new time and effect.",
                    steps=tuple(
                        step.model_copy(update={"status": TaskStatus.QUEUED, "evidence": ""})
                        for step in task.steps
                    ),
                )
            else:
                raise ValueError("use confirm, cancel or snooze")
            task = task.model_copy(update=updates)
            self._write(connection, task)
            return task

    def _claim_sync(self) -> LocalTask | None:
        with self._lock, self._db() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = self._now()
            connection.execute(
                "DELETE FROM local_tasks WHERE status IN "
                "('completed','failed','cancelled','missed','uncertain') AND updated_at < ?",
                ((now - timedelta(days=self._retention_days)).isoformat(),),
            )
            connection.execute(
                "DELETE FROM local_tasks WHERE status='draft' AND updated_at < ?",
                ((now - timedelta(minutes=10)).isoformat(),),
            )
            row = connection.execute(
                "SELECT record_json FROM local_tasks WHERE kind='reminder' "
                "AND status='queued' AND due_at<=? "
                "ORDER BY due_at, task_id LIMIT 1",
                (now.isoformat(),),
            ).fetchone()
            if row is None:
                return None
            task = LocalTask.model_validate_json(row[0])
            late = now - task.due_at > timedelta(seconds=60)
            task = task.model_copy(
                update={
                    "status": TaskStatus.MISSED if late else TaskStatus.RUNNING,
                    "updated_at": now,
                    "result": "Missed by more than 60 seconds; review or snooze."
                    if late
                    else "Delivering.",
                    "steps": (
                        task.steps[0].model_copy(update={"status": TaskStatus.COMPLETED}),
                        task.steps[1].model_copy(
                            update={"status": TaskStatus.MISSED if late else TaskStatus.RUNNING}
                        ),
                    ),
                }
            )
            self._write(connection, task)
            return task

    async def tick(self) -> bool:
        """Claim at most one due item; never retry an uncertain effect."""
        task = await asyncio.to_thread(self._claim_sync)
        if task is None:
            return False
        if task.status is TaskStatus.MISSED:
            return True
        try:
            async with asyncio.timeout(195 if task.notification == "speech" else 10):
                success, evidence = await self._notify(task)
            status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        except asyncio.CancelledError:
            await asyncio.to_thread(
                self._finish_sync,
                task,
                TaskStatus.UNCERTAIN,
                "Delivery interrupted; it may have happened. Review before retrying.",
            )
            raise
        except Exception:
            status, evidence = (
                TaskStatus.UNCERTAIN,
                "Delivery could not be verified. No automatic retry.",
            )
        await asyncio.to_thread(self._finish_sync, task, status, evidence[:1000])
        return True

    def _finish_sync(self, task: LocalTask, status: TaskStatus, evidence: str) -> None:
        with self._lock, self._db() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = self._get(connection, task.owner_scope, task.task_id)
            except KeyError:
                return  # A profile/reset operation removed the record; never resurrect it.
            if current.status is not TaskStatus.RUNNING or current.occurrence != task.occurrence:
                return
            updates: dict[str, Any] = {
                "status": status,
                "updated_at": self._now(),
                "result": evidence,
                "steps": (
                    task.steps[0],
                    task.steps[1].model_copy(
                        update={
                            "status": status,
                            "evidence": evidence,
                        }
                    ),
                ),
            }
            if status is TaskStatus.COMPLETED:
                try:
                    due = next_occurrence(task)
                except ValueError:
                    updates.update(
                        status=TaskStatus.MISSED,
                        result=evidence[:850] + " Next clock-change "
                        "occurrence needs review; automatic recurrence paused.",
                    )
                else:
                    if due is not None:
                        updates.update(
                            status=TaskStatus.QUEUED, due_at=due, occurrence=task.occurrence + 1
                        )
            self._write(connection, current.model_copy(update=updates))

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
                self._last_error = None
            except asyncio.CancelledError:
                raise
            except Exception:
                # A database failure must not kill reminders permanently or leak data.
                # Leave queued work intact and re-inspect later; never repeat a running claim.
                self._last_error = "task_database_unavailable"
            await asyncio.sleep(0.5)

    def status(self) -> dict[str, Any]:
        """Expose worker failure without private records or database exception text."""
        return {
            "running": self._worker is not None and not self._worker.done(),
            "error": self._last_error,
            "retention_days": self._retention_days,
            "missed_after_seconds": 60,
        }

    def set_retention_days(self, days: int) -> None:
        if not 1 <= days <= 365:
            raise ValueError("task retention must be 1 through 365 days")
        self._retention_days = days

    @asynccontextmanager
    async def paused(self) -> AsyncIterator[None]:
        """Quiesce notifications during profile deletion/reset without losing queued work."""
        async with self._pause_lock:
            restart = self._worker is not None
            if self._worker is not None:
                self._worker.cancel()
                await asyncio.gather(self._worker, return_exceptions=True)
                self._worker = None
            try:
                yield
            finally:
                if restart and not self._closing and not self._closed:
                    self._worker = asyncio.create_task(self._run(), name="local-reminders")

    async def close(self) -> None:
        self._closing = True
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None

        def close_connection() -> None:
            with self._lock:
                if self._connection is not None:
                    self._connection.close()
                    self._connection = None
                self._closed = True

        await asyncio.to_thread(close_connection)
