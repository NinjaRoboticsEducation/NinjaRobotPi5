from __future__ import annotations

import asyncio
from pathlib import Path

from ninjarobot_pi5_agent.testing import FakeProvider

from ninjarobot_pi5_agent import (
    AgentLoop,
    AgentRuntime,
    ConversationStore,
    EventBroker,
    MemoryKind,
    MemoryStore,
    MotionArmManager,
    PolicyEngine,
    PromptComposer,
    RecoveryPolicy,
    SkillRepository,
    ToolRegistry,
    UserRole,
)


def _runtime(
    tmp_path: Path,
    *,
    enroll_identity=None,
    recognize_identity=None,
    delete_identity=None,
) -> AgentRuntime:
    provider = FakeProvider(())
    tools = ToolRegistry(())
    database = tmp_path / "conversation.sqlite3"
    store = ConversationStore(database)
    memory = MemoryStore(database)
    arms = MotionArmManager()
    policy = PolicyEngine(arms)
    events = EventBroker()
    loop = AgentLoop(
        provider=provider,
        tools=tools,
        policy=policy,
        recovery=RecoveryPolicy(),
        store=store,
        prompts=PromptComposer(),
        events=events,
    )
    return AgentRuntime(
        provider=provider,
        tools=tools,
        store=store,
        loop=loop,
        policy=policy,
        motion_arms=arms,
        skills=SkillRepository(tmp_path / "skills"),
        events=events,
        memory=memory,
        enroll_identity=enroll_identity,
        recognize_identity=recognize_identity,
        delete_identity=delete_identity,
    )


def test_first_chat_enrolls_owner_and_camera_failure_does_not_block_chat(tmp_path: Path) -> None:
    async def unavailable(_user_id: str) -> dict:
        raise RuntimeError("camera unavailable")

    async def exercise() -> None:
        runtime = _runtime(tmp_path, enroll_identity=unavailable)
        await runtime.start()
        first = await runtime.chat(session_id="terminal", text="Hello")
        assert "what is your name" in first.text.casefold()
        created = await runtime.chat(session_id="terminal", text="Roger")
        assert "profile created" in created.text.casefold()
        assert "remains pending" in created.text.casefold()
        profiles = await runtime.memory.profiles()  # type: ignore[union-attr]
        assert len(profiles) == 1
        assert profiles[0].role is UserRole.OWNER
        assert profiles[0].user_id == "local-user"
        await runtime.close()

    asyncio.run(exercise())


def test_new_switch_identify_and_restart_default_are_user_isolated(tmp_path: Path) -> None:
    enrolled_ids: list[str] = []
    recognized_identity = ""

    async def enroll(user_id: str) -> dict:
        enrolled_ids.append(user_id)
        return {
            "status": "enrolled",
            "identity": f"face-{user_id}",
            "profile_image_path": str(tmp_path / f"{user_id}.jpg"),
            "backend": "test",
            "raw_photo_retained": False,
        }

    async def identify() -> dict:
        return {"status": "recognized", "identity": recognized_identity}

    async def exercise() -> None:
        nonlocal recognized_identity
        runtime = _runtime(
            tmp_path,
            enroll_identity=enroll,
            recognize_identity=identify,
        )
        await runtime.start()
        await runtime.chat(session_id="web", text="start")
        await runtime.chat(session_id="web", text="Owner")
        prompt = await runtime.chat(session_id="web", text="/new user")
        assert "new user's name" in prompt.text.casefold()
        created = await runtime.chat(session_id="web", text="Student")
        assert "profile created" in created.text.casefold()
        profiles = await runtime.memory.profiles()  # type: ignore[union-attr]
        student = next(profile for profile in profiles if profile.display_name == "Student")
        recognized_identity = f"face-{student.user_id}"

        runtime.arm_motion("web", confirmed=True)
        switched = await runtime.chat(session_id="web", text="/switch user Owner")
        assert "switched to owner" in switched.text.casefold()
        assert not runtime.motion_arms.is_armed("web")
        owner_history = await runtime.history("web")
        assert all(item["user_id"] == "local-user" for item in owner_history)
        assert not any(item["message"]["content"] == "Student" for item in owner_history)

        identified = await runtime.chat(session_id="web", text="/identify")
        assert "recognized and switched to student" in identified.text.casefold()
        student_history = await runtime.history("web")
        assert all(item["user_id"] == student.user_id for item in student_history)
        await runtime.close()

        restarted = _runtime(tmp_path)
        await restarted.start()
        restarted_history = await restarted.history("web")
        assert all(item["user_id"] == "local-user" for item in restarted_history)
        await restarted.close()

    asyncio.run(exercise())


def test_profile_updates_require_explicit_deterministic_syntax(tmp_path: Path) -> None:
    async def exercise() -> None:
        runtime = _runtime(tmp_path)
        await runtime.start()
        await runtime.chat(session_id="terminal", text="start")
        await runtime.chat(session_id="terminal", text="Owner")
        prompt = await runtime.chat(
            session_id="terminal",
            text="Please update my profile",
        )
        assert "name=<new name>" in prompt.text
        updated = await runtime.chat(
            session_id="terminal",
            text="name=Roger; robot_name=Ninja",
        )
        assert "profile updated for roger" in updated.text.casefold()
        owner = await runtime.memory.owner()  # type: ignore[union-attr]
        assert owner is not None
        assert owner.display_name == "Roger"
        assert owner.preferred_robot_name == "Ninja"
        await runtime.close()

    asyncio.run(exercise())


def test_deterministic_memory_management_enforces_profile_and_category_rules(
    tmp_path: Path,
) -> None:
    deleted_faces: list[str] = []

    async def delete_identity(user_id: str) -> bool:
        deleted_faces.append(user_id)
        return True

    async def exercise() -> None:
        runtime = _runtime(tmp_path, delete_identity=delete_identity)
        await runtime.start()
        await runtime.chat(session_id="terminal", text="start")
        await runtime.chat(session_id="terminal", text="Owner")
        assert runtime.memory is not None
        member = await runtime.memory.create_profile("Inactive Member")
        await runtime.memory.set_face_profile(
            member.user_id,
            face_index_name=f"face-{member.user_id}",
            profile_image_path=str(tmp_path / "member.jpg"),
            model_metadata={"backend": "test"},
        )
        item = await runtime.memory.add_memory(
            member.user_id,
            MemoryKind.SUCCESSFUL_BEHAVIOR,
            "Confirmed wave",
        )
        assert await runtime.delete_behavior_memory(member.user_id, item.memory_id)
        settings = await runtime.update_memory_settings(
            conversation_retention_days=14,
            failed_behavior_retention_days=90,
        )
        assert settings["settings"]["conversation_retention_days"] == 14
        await runtime.delete_memory_profile(member.user_id)
        assert deleted_faces == [member.user_id]
        assert len(await runtime.memory_profiles()) == 1
        await runtime.close()

    asyncio.run(exercise())
