from __future__ import annotations

import asyncio
from pathlib import Path

from ninjarobot_pi5_ide.config import BehaviorConfig

from ninjarobot_pi5_ide import (
    ActionRequest,
    ActionStatus,
    build_robot_ide_client,
    load_robot_config,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"


def test_integrated_agent_ide_exposes_shared_simulated_robot_capabilities(
    tmp_path,
) -> None:
    async def exercise() -> None:
        base_config = load_robot_config(EXAMPLE)
        config = base_config.model_copy(
            update={
                "behaviors": BehaviorConfig(
                    user_directory=str(tmp_path / "behaviors"),
                    safety_state_file=str(tmp_path / "safety.json"),
                    system_stopped_display_seconds=0.0,
                ),
                "hardware": base_config.hardware.model_copy(
                    update={
                        "servos": base_config.hardware.servos.model_copy(
                            update={
                                "motion_enabled": True,
                                "group_motion_enabled": True,
                            }
                        )
                    }
                ),
            }
        )
        client = build_robot_ide_client(
            config,
            ledger_path=tmp_path / "ledger.sqlite3",
            simulated=True,
        )
        await client.start()

        descriptors = {descriptor.name: descriptor for descriptor in await client.capabilities()}
        names = set(descriptors)
        assert {
            "behavior.list",
            "behavior.run",
            "behavior.execute_expression",
            "behavior.execute_movement",
            "behavior.save_user",
            "behavior.stop",
            "motion.resume",
            "system.resume",
            "distance.read",
            "display.show_text",
            "camera.capture",
            "camera.preview",
            "microphone.capture",
            "microphone.transcribe",
        } <= names
        expression_schema = descriptors["behavior.execute_expression"].input_schema
        expression_mapping = expression_schema["$defs"]["_ExpressionStage"]["properties"][
            "operations"
        ]["items"]["discriminator"]["mapping"]
        assert "drive" not in expression_mapping
        movement_schema = descriptors["behavior.execute_movement"].input_schema
        target_schema = movement_schema["$defs"]["DriveOperation"]["properties"]["targets"]
        assert set(target_schema["properties"]) == {"left_motor", "right_motor"}
        assert target_schema["additionalProperties"] is False

        result = await client.execute(
            ActionRequest(
                action_id="list-1",
                capability="behavior.list",
                arguments={"category": "movement"},
                requested_by="test",
                session_id="test-session",
                idempotency_key="list-key-1",
            )
        )
        assert result.status is ActionStatus.SUCCEEDED
        assert result.data is not None
        behavior_names = {behavior["name"] for behavior in result.data["behaviors"]}
        assert {"move_forward", "move_backward", "turn_left", "turn_right"} <= (behavior_names)

        expression = await client.execute(
            ActionRequest(
                action_id="expression-1",
                capability="behavior.execute_expression",
                arguments={
                    "schema_version": 1,
                    "name": "agent_smile",
                    "description": "A transient agent-created smile and tone.",
                    "category": "expression",
                    "stages": [
                        {
                            "name": "smile",
                            "operations": [
                                {
                                    "kind": "face",
                                    "expression": "happy",
                                    "hold_seconds": 0.05,
                                },
                                {
                                    "kind": "tone",
                                    "frequency_hz": 880,
                                    "duration_seconds": 0.05,
                                    "volume": 32,
                                },
                            ],
                        }
                    ],
                },
                requested_by="test",
                session_id="test-session",
                idempotency_key="expression-key-1",
            )
        )
        assert expression.status is ActionStatus.SUCCEEDED

        saved_definition = {
            "schema_version": 1,
            "name": "saved_agent_smile",
            "description": "A saved agent-created expression.",
            "category": "expression",
            "stages": [
                {
                    "name": "smile",
                    "operations": [
                        {
                            "kind": "face",
                            "expression": "happy",
                            "hold_seconds": 0.05,
                        }
                    ],
                }
            ],
        }
        saved = await client.execute(
            ActionRequest(
                action_id="save-1",
                capability="behavior.save_user",
                arguments=saved_definition,
                requested_by="confirmed-test",
                session_id="test-session",
                idempotency_key="save-key-1",
            )
        )
        assert saved.status is ActionStatus.SUCCEEDED
        assert saved.data is not None
        assert saved.data["name"] == "saved_agent_smile"
        assert Path(saved.data["path"]).is_file()

        duplicate_save = await client.execute(
            ActionRequest(
                action_id="save-2",
                capability="behavior.save_user",
                arguments=saved_definition,
                requested_by="confirmed-test",
                session_id="test-session",
                idempotency_key="save-key-2",
            )
        )
        assert duplicate_save.status is ActionStatus.FAILED
        assert duplicate_save.error is not None
        assert "already exists" in duplicate_save.error.technical_detail

        movement = await client.execute(
            ActionRequest(
                action_id="movement-1",
                capability="behavior.execute_movement",
                arguments={
                    "schema_version": 1,
                    "name": "agent_roll",
                    "description": "A transient agent-created raised-wheel movement.",
                    "category": "movement",
                    "stages": [
                        {
                            "name": "roll",
                            "operations": [
                                {
                                    "kind": "face",
                                    "expression": "exciting",
                                    "hold_seconds": 0.05,
                                },
                                {
                                    "kind": "drive",
                                    "targets": {
                                        "left_motor": 20,
                                        "right_motor": -20,
                                    },
                                    "hold_seconds": 0.05,
                                },
                            ],
                        }
                    ],
                },
                requested_by="test",
                session_id="test-session",
                idempotency_key="movement-key-1",
            )
        )
        assert movement.status is ActionStatus.SUCCEEDED, movement.model_dump(mode="json")

        preview = await client.execute(
            ActionRequest(
                action_id="preview-1",
                capability="camera.preview",
                arguments={},
                requested_by="test",
                session_id="test-session",
                idempotency_key="preview-key-1",
            )
        )
        assert preview.status is ActionStatus.SUCCEEDED
        assert preview.data is not None
        assert preview.data["retained"] is False
        assert preview.data["path"] is None
        assert preview.data["jpeg_base64"]

        transcript = await client.execute(
            ActionRequest(
                action_id="transcript-1",
                capability="microphone.transcribe",
                arguments={"duration_seconds": 0.25, "language": "ja"},
                requested_by="test",
                session_id="test-session",
                idempotency_key="transcript-key-1",
            )
        )
        assert transcript.status is ActionStatus.SUCCEEDED
        assert transcript.data is not None
        assert transcript.data["transcript"] == "Simulated ja microphone prompt"
        assert transcript.data["audio_retained"] is False

        stop = await client.execute(
            ActionRequest(
                action_id="stop-1",
                capability="behavior.stop",
                arguments={},
                requested_by="test",
                session_id="test-session",
                idempotency_key="stop-key-1",
            )
        )
        assert stop.status is ActionStatus.SUCCEEDED
        await client.close()
        await client.close()

    asyncio.run(exercise())
