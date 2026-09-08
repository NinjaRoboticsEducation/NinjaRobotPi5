from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from ninjarobot_pi5_agent.persistence import ConversationStore
from ninjarobot_pi5_agent.task_models import TaskStatus, exact_due_time
from ninjarobot_pi5_agent.task_service import TaskService


async def setup(tmp_path, notify):
    path = tmp_path / "tasks.sqlite3"
    store = ConversationStore(path)
    await store.start()
    now = [datetime(2026, 9, 8, tzinfo=UTC)]
    tasks = TaskService(path, notify, clock=lambda: now[0])
    await tasks.start(background=False)
    return store, tasks, now


async def preview(tasks, now, **overrides):
    values = {
        "scope": "session:test",
        "user_id": None,
        "session_id": "test",
        "title": "Tea",
        "due_at": (now[0] + timedelta(minutes=1)).isoformat(),
        "timezone": "UTC",
    }
    values.update(overrides)
    return await tasks.preview(**values)


def test_reminder_requires_review_and_claims_once_without_model(tmp_path):
    async def exercise():
        calls = []

        async def notify(task):
            calls.append(task.task_id)
            await asyncio.sleep(0.01)
            return True, "Saved to inbox; reading not confirmed."

        store, tasks, now = await setup(tmp_path, notify)
        try:
            item = await preview(tasks, now)
            assert not await tasks.tick()
            assert calls == []
            await tasks.change(item.owner_scope, item.task_id, "confirm")
            await tasks.change(item.owner_scope, item.task_id, "confirm")
            now[0] += timedelta(minutes=1)
            await asyncio.gather(tasks.tick(), tasks.tick())
            assert calls == [item.task_id]
            result = (await tasks.list(item.owner_scope))[0]
            assert result.status is TaskStatus.COMPLETED
            assert result.approved_at is not None
            assert result.steps[1].evidence.startswith("Saved")
            assert not await tasks.tick()
            with pytest.raises(KeyError):
                await tasks.change("session:other", item.task_id, "cancel")
            assert await tasks.list("session:other") == ()
        finally:
            await tasks.close()
            await store.close()

    asyncio.run(exercise())


def test_restart_missed_and_uncertain_do_not_repeat(tmp_path):
    async def exercise():
        async def forbidden(task):
            pytest.fail("missed/uncertain reminders must not be delivered automatically")

        store, tasks, now = await setup(tmp_path, forbidden)
        item = await preview(tasks, now)
        await tasks.change(item.owner_scope, item.task_id, "confirm")
        now[0] += timedelta(minutes=1)
        claimed = await asyncio.to_thread(tasks._claim_sync)
        assert claimed.status is TaskStatus.RUNNING
        await tasks.close()
        tasks = TaskService(store.path, forbidden, clock=lambda: now[0])
        await tasks.start(background=False)
        try:
            assert (await tasks.list(item.owner_scope))[0].status is TaskStatus.UNCERTAIN
            assert not await tasks.tick()
            snoozed = await tasks.change(item.owner_scope, item.task_id, "snooze", minutes=5)
            assert snoozed.status is TaskStatus.DRAFT
            await tasks.change(item.owner_scope, item.task_id, "confirm")
            now[0] += timedelta(minutes=7)
            assert await tasks.tick()
            assert (await tasks.list(item.owner_scope))[0].status is TaskStatus.MISSED
            await tasks.change(item.owner_scope, item.task_id, "cancel")
            assert not await tasks.tick()
        finally:
            await tasks.close()
            await store.close()

    asyncio.run(exercise())


def test_cancel_during_delivery_keeps_honest_outcome(tmp_path):
    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()

        async def notify(task):
            entered.set()
            await release.wait()
            return True, "Delivered"

        store, tasks, now = await setup(tmp_path, notify)
        try:
            item = await preview(tasks, now)
            await tasks.change(item.owner_scope, item.task_id, "confirm")
            now[0] += timedelta(minutes=1)
            running = asyncio.create_task(tasks.tick())
            await entered.wait()
            cancelled = await tasks.change(item.owner_scope, item.task_id, "cancel")
            assert "may already" in cancelled.result
            release.set()
            await running
            assert (await tasks.list(item.owner_scope))[0].status is TaskStatus.CANCELLED
        finally:
            await tasks.close()
            await store.close()

    asyncio.run(exercise())


def test_daily_recurrence_and_expired_preview(tmp_path):
    async def exercise():
        async def notify(task):
            return True, "Inbox record saved"

        store, tasks, now = await setup(tmp_path, notify)
        try:
            item = await preview(tasks, now, repeat="daily")
            await tasks.change(item.owner_scope, item.task_id, "confirm")
            now[0] += timedelta(minutes=1)
            await tasks.tick()
            repeated = (await tasks.list(item.owner_scope))[0]
            assert repeated.due_at == item.due_at + timedelta(days=1)
            assert repeated.occurrence == 1
            assert repeated.status is TaskStatus.QUEUED
            stale = await preview(tasks, now, due_at=(now[0] + timedelta(hours=1)).isoformat())
            now[0] += timedelta(minutes=11)
            with pytest.raises(ValueError, match="expired"):
                await tasks.change(stale.owner_scope, stale.task_id, "confirm")
        finally:
            await tasks.close()
            await store.close()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "value,zone",
    [
        ("2026-09-09T12:00:00", "Asia/Tokyo"),
        ("2026-09-09T12:00:00+00:00", "Asia/Tokyo"),
        ("2026-09-09T12:00:00+09:00", "Invalid/Zone"),
        ("2026-03-08T02:30:00-05:00", "America/New_York"),
    ],
)
def test_ambiguous_or_nonexistent_time_requires_clarification(value, zone):
    with pytest.raises(ValueError):
        exact_due_time(value, zone, datetime(2026, 1, 1, tzinfo=UTC))


def test_exact_repeated_clock_hour_and_past_time():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    first = exact_due_time("2026-11-01T01:30:00-04:00", "America/New_York", now)
    second = exact_due_time("2026-11-01T01:30:00-05:00", "America/New_York", now)
    assert second - first == timedelta(hours=1)
    with pytest.raises(ValueError, match="past times are not shifted"):
        exact_due_time("2026-01-01T00:00:00+00:00", "UTC", now)


def test_profile_deletion_and_reset_remove_local_tasks(tmp_path):
    from ninjarobot_pi5_agent.memory_models import MemorySettings
    from ninjarobot_pi5_agent.memory_store import MemoryStore

    async def exercise():
        async def notify(task):
            pytest.fail("deleted tasks must not notify")

        store, tasks, now = await setup(tmp_path, notify)
        memory = MemoryStore(store.path)
        await memory.start()
        try:
            owner = await memory.create_profile("Owner")
            member = await memory.create_profile("Member")
            for user in (owner, member):
                item = await preview(tasks, now, scope=f"user:{user.user_id}", user_id=user.user_id)
                await tasks.change(item.owner_scope, item.task_id, "confirm")
            await memory.delete_profile(member.user_id)
            assert await tasks.list(f"user:{member.user_id}") == ()
            assert len(await tasks.list(f"user:{owner.user_id}")) == 1
            await memory.reset_all(MemorySettings())
            assert await tasks.list(f"user:{owner.user_id}") == ()
            now[0] += timedelta(minutes=1)
            assert not await tasks.tick()
        finally:
            await tasks.close()
            await memory.close()
            await store.close()

    asyncio.run(exercise())


def test_snooze_keeps_daily_time_and_clock_gap_pauses_with_valid_record(tmp_path):
    async def exercise():
        async def notify(task):
            return True, "x" * 1000

        store, tasks, now = await setup(tmp_path, notify)
        try:
            item = await preview(tasks, now, repeat="daily")
            await tasks.change(item.owner_scope, item.task_id, "confirm")
            await tasks.change(item.owner_scope, item.task_id, "snooze", minutes=5)
            await tasks.change(item.owner_scope, item.task_id, "confirm")
            now[0] += timedelta(minutes=5)
            await tasks.tick()
            repeated = (await tasks.list(item.owner_scope))[0]
            assert repeated.due_at == item.due_at + timedelta(days=1)
            await tasks.change(item.owner_scope, item.task_id, "cancel")
            now[0] = datetime(2026, 3, 7, 7, 29, tzinfo=UTC)
            gap = await preview(
                tasks,
                now,
                repeat="daily",
                timezone="America/New_York",
                due_at="2026-03-07T02:30:00-05:00",
            )
            await tasks.change(gap.owner_scope, gap.task_id, "confirm")
            now[0] += timedelta(minutes=1)
            await tasks.tick()
            result = next(t for t in await tasks.list(gap.owner_scope) if t.task_id == gap.task_id)
            assert result.status is TaskStatus.MISSED
            assert "recurrence paused" in result.result
            assert len(result.result) <= 1000
        finally:
            await tasks.close()
            await store.close()

    asyncio.run(exercise())


def test_pause_joins_delivery_and_restart_does_not_repeat_uncertain_task(tmp_path):
    async def exercise():
        entered, cleaned = asyncio.Event(), asyncio.Event()
        calls = []

        async def notify(task):
            calls.append(task.task_id)
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        store, tasks, now = await setup(tmp_path, notify)
        try:
            item = await preview(tasks, now)
            await tasks.change(item.owner_scope, item.task_id, "confirm")
            now[0] += timedelta(minutes=1)
            await tasks.start()
            await asyncio.wait_for(entered.wait(), 2)
            async with tasks.paused():
                assert cleaned.is_set()
                assert not tasks.status()["running"]
                assert (await tasks.list(item.owner_scope))[0].status is TaskStatus.UNCERTAIN
            assert tasks.status()["running"]
            assert not await tasks.tick()
            assert calls == [item.task_id]
        finally:
            await tasks.close()
            await store.close()

    asyncio.run(exercise())
