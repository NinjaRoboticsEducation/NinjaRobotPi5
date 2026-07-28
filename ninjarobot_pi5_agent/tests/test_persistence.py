from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ninjarobot_pi5_agent.persistence import ConversationStore

from ninjarobot_pi5_agent import MessageRole, ModelMessage, ToolCall


def test_conversation_store_persists_orders_clears_and_prunes(tmp_path: Path) -> None:
    async def exercise() -> None:
        now = datetime(2026, 7, 28, tzinfo=UTC)
        store = ConversationStore(tmp_path / "agent.sqlite3", retention_days=7)
        await store.start()
        await store.create_session("session-old", now=now - timedelta(days=9))
        await store.append_message(
            "session-old",
            ModelMessage(role=MessageRole.USER, content="old"),
            message_id="message-old",
            now=now - timedelta(days=9),
        )
        await store.create_session("session-current", now=now)
        await store.append_message(
            "session-current",
            ModelMessage(role=MessageRole.USER, content="hello"),
            message_id="message-1",
            now=now,
            metadata={"source": "test"},
        )
        await store.append_message(
            "session-current",
            ModelMessage(role=MessageRole.ASSISTANT, content="hi"),
            message_id="message-2",
            now=now + timedelta(seconds=1),
        )

        messages = await store.messages("session-current")
        assert [item.message.content for item in messages] == ["hello", "hi"]
        assert messages[0].metadata == {"source": "test"}
        assert store.path.stat().st_mode & 0o777 == 0o600

        assert await store.prune(now=now) == 1
        assert [item.session_id for item in await store.sessions()] == ["session-current"]
        assert await store.clear_session("session-current") == 2
        assert await store.messages("session-current") == ()
        await store.close()
        await store.close()

    asyncio.run(exercise())


def test_conversation_store_migrates_and_persists_assistant_tool_calls(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE messages (
            message_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(session_id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            name TEXT,
            tool_call_id TEXT,
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        );
        """
    )
    connection.close()

    async def exercise() -> None:
        store = ConversationStore(path)
        await store.start()
        await store.create_session("session-1")
        call = ToolCall(
            call_id="call-1",
            name="robot.distance.read",
            arguments={},
        )
        await store.append_message(
            "session-1",
            ModelMessage(
                role=MessageRole.ASSISTANT,
                content="",
                tool_calls=(call,),
            ),
            message_id="message-1",
        )

        restored = (await store.messages("session-1"))[0].message
        assert restored.tool_calls == (call,)
        await store.close()

    asyncio.run(exercise())
