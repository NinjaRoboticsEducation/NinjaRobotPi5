from __future__ import annotations

import asyncio

from ninjarobot_pi5_agent.events import AgentEventType, EventBroker


def test_event_broker_bounds_slow_subscribers_and_history() -> None:
    async def exercise() -> None:
        broker = EventBroker(history_limit=2, subscriber_limit=1)
        queue = await broker.subscribe()

        first = await broker.publish(AgentEventType.STATUS, "first")
        await broker.publish(AgentEventType.WARNING, "second")
        third = await broker.publish(AgentEventType.ERROR, "third")

        assert first.event_id == "event-00000001"
        assert (await queue.get()).event_id == third.event_id
        assert [event.message for event in await broker.history()] == ["second", "third"]

        await broker.unsubscribe(queue)
        await broker.unsubscribe(queue)

    asyncio.run(exercise())
