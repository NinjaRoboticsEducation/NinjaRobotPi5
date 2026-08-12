from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from ninjarobot_pi5_agent.testing import FakeProvider

from ninjarobot_pi5_agent import (
    AgentLoop,
    AgentRuntime,
    ConversationStore,
    EventBroker,
    MemoryKind,
    MemorySettings,
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
    prepare_identity_reset=None,
    commit_identity_reset=None,
    rollback_identity_reset=None,
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
        prepare_identity_reset=prepare_identity_reset,
        commit_identity_reset=commit_identity_reset,
        rollback_identity_reset=rollback_identity_reset,
        initial_memory_settings=MemorySettings(),
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
        assert "register user face" in created.text.casefold()
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

        runtime.arm_motion("web", confirmed=True)
        recognized_identity = "face-local-user"
        switched = await runtime.chat(session_id="web", text="/switch user Owner")
        assert "face verified. switched to owner" in switched.text.casefold()
        assert not runtime.motion_arms.is_armed("web")
        owner_history = await runtime.history("web")
        assert all(item["user_id"] == "local-user" for item in owner_history)
        assert not any(item["message"]["content"] == "Student" for item in owner_history)

        runtime.arm_motion("web", confirmed=True)
        mismatch = await runtime.chat(session_id="web", text="/switch user Student")
        assert "face did not match the selected user" in mismatch.text.casefold()
        assert "active user was not changed" in mismatch.text.casefold()
        assert not runtime.motion_arms.is_armed("web")
        mismatch_history = await runtime.history("web")
        assert all(item["user_id"] == "local-user" for item in mismatch_history)

        recognized_identity = f"face-{student.user_id}"
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


def test_profile_update_shows_status_and_supports_face_registration(tmp_path: Path) -> None:
    enrolled_ids: list[str] = []

    async def enroll(user_id: str) -> dict:
        enrolled_ids.append(user_id)
        return {
            "status": "enrolled",
            "identity": f"face-{user_id}",
            "profile_image_path": str(tmp_path / f"{user_id}.jpg"),
            "backend": "test",
            "raw_photo_retained": False,
        }

    async def exercise() -> None:
        runtime = _runtime(tmp_path, enroll_identity=enroll)
        await runtime.start()
        await runtime.chat(session_id="terminal", text="start")
        await runtime.chat(session_id="terminal", text="Owner")
        prompt = await runtime.chat(
            session_id="terminal",
            text="Please update my profile",
        )
        assert "name=<new name>" in prompt.text
        assert "Name: Owner" in prompt.text
        assert "Face: registered" in prompt.text
        assert "register user face" in prompt.text
        updated = await runtime.chat(
            session_id="terminal",
            text="name=Roger",
        )
        assert "profile updated for roger" in updated.text.casefold()
        rejected = await runtime.chat(
            session_id="terminal",
            text="/update profile robot_name=Pocky",
        )
        assert "ask it directly" in rejected.text.casefold()
        retry_prompt = await runtime.chat(session_id="terminal", text="/update profile")
        assert "Name: Roger" in retry_prompt.text
        refreshed = await runtime.chat(session_id="terminal", text="register user face")
        assert "face enrollment completed" in refreshed.text.casefold()
        owner = await runtime.memory.owner()  # type: ignore[union-attr]
        assert owner is not None
        assert owner.display_name == "Roger"
        assert owner.preferred_robot_name is None
        assert enrolled_ids == ["local-user", "local-user"]
        await runtime.close()

    asyncio.run(exercise())


def test_switch_user_rejects_unregistered_and_camera_failure_without_changing_user(
    tmp_path: Path,
) -> None:
    recognition_result: dict | BaseException = {"status": "no_face", "face_count": 0}
    recognition_calls = 0

    async def enroll(user_id: str) -> dict:
        return {
            "status": "enrolled",
            "identity": f"face-{user_id}",
            "profile_image_path": str(tmp_path / f"{user_id}.jpg"),
            "backend": "test",
            "raw_photo_retained": False,
        }

    async def identify() -> dict:
        nonlocal recognition_calls
        recognition_calls += 1
        if isinstance(recognition_result, BaseException):
            raise recognition_result
        return recognition_result

    async def exercise() -> None:
        nonlocal recognition_result
        runtime = _runtime(
            tmp_path,
            enroll_identity=enroll,
            recognize_identity=identify,
        )
        await runtime.start()
        await runtime.chat(session_id="terminal", text="start")
        await runtime.chat(session_id="terminal", text="Owner")
        await runtime.chat(session_id="terminal", text="/new user Pending")
        assert runtime.memory is not None
        pending = next(
            profile
            for profile in await runtime.memory.profiles()
            if profile.display_name == "Pending"
        )
        await runtime.memory.clear_face_profile(pending.user_id)

        unregistered = await runtime.chat(
            session_id="terminal",
            text="/switch user Pending",
        )
        assert "does not have a registered face" in unregistered.text.casefold()
        assert "register or replace user face" in unregistered.text.casefold()
        assert recognition_calls == 0

        no_face = await runtime.chat(session_id="terminal", text="/switch user Owner")
        assert "center the selected user's face" in no_face.text.casefold()
        assert recognition_calls == 1

        recognition_result = RuntimeError("camera offline")
        camera_error = await runtime.chat(session_id="terminal", text="/switch user Owner")
        assert "camera offline" in camera_error.text.casefold()
        history = await runtime.history("terminal")
        assert all(item["user_id"] == pending.user_id for item in history)
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


def test_management_can_register_inactive_face_and_reset_all_robot_memory(tmp_path: Path) -> None:
    reset_calls: list[str] = []

    async def enroll(user_id: str) -> dict:
        return {
            "status": "enrolled",
            "identity": f"face-{user_id}",
            "profile_image_path": str(tmp_path / f"{user_id}.jpg"),
            "backend": "test",
            "raw_photo_retained": False,
        }

    async def prepare_reset() -> str:
        reset_calls.append("prepare")
        return "reset-token"

    async def commit_reset(token: str) -> bool:
        assert token == "reset-token"
        reset_calls.append("commit")
        return True

    async def rollback_reset(token: str) -> None:
        assert token == "reset-token"
        reset_calls.append("rollback")

    async def exercise() -> None:
        runtime = _runtime(
            tmp_path,
            enroll_identity=enroll,
            prepare_identity_reset=prepare_reset,
            commit_identity_reset=commit_reset,
            rollback_identity_reset=rollback_reset,
        )
        await runtime.start()
        await runtime.chat(session_id="terminal", text="start")
        await runtime.chat(session_id="terminal", text="Owner")
        assert runtime.memory is not None
        member = await runtime.memory.create_profile("Pending Member")
        registered = await runtime.register_memory_profile_face(member.user_id)
        assert registered["face_registered"] is True
        await runtime.memory.add_memory(
            member.user_id,
            MemoryKind.SUCCESSFUL_BEHAVIOR,
            "Wave hello",
        )
        runtime.arm_motion("terminal", confirmed=True)

        result = await runtime.reset_all_memory()
        assert result["reset"] is True
        assert result["owner"] is None
        assert result["face_data_removed"] is True
        assert result["deleted"]["users"] == 2
        assert reset_calls == ["prepare", "commit"]
        assert await runtime.memory.profiles() == ()
        assert not runtime.motion_arms.is_armed("terminal")
        onboarding = await runtime.chat(session_id="terminal", text="hello again")
        assert "what is your name" in onboarding.text.casefold()
        await runtime.close()

    asyncio.run(exercise())


def test_full_memory_reset_rolls_back_face_quarantine_on_database_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reset_calls: list[str] = []

    async def prepare_reset() -> str:
        reset_calls.append("prepare")
        return "reset-token"

    async def commit_reset(_token: str) -> bool:
        reset_calls.append("commit")
        return True

    async def rollback_reset(token: str) -> None:
        assert token == "reset-token"
        reset_calls.append("rollback")

    async def fail_reset(_settings: MemorySettings) -> dict[str, int]:
        raise RuntimeError("database failure")

    async def exercise() -> None:
        runtime = _runtime(
            tmp_path,
            prepare_identity_reset=prepare_reset,
            commit_identity_reset=commit_reset,
            rollback_identity_reset=rollback_reset,
        )
        await runtime.start()
        await runtime.chat(session_id="terminal", text="start")
        await runtime.chat(session_id="terminal", text="Owner")
        assert runtime.memory is not None
        monkeypatch.setattr(runtime.memory, "reset_all", fail_reset)
        with pytest.raises(RuntimeError, match="database failure"):
            await runtime.reset_all_memory()
        assert reset_calls == ["prepare", "rollback"]
        assert await runtime.memory.owner() is not None
        await runtime.close()

    asyncio.run(exercise())
