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
        config = load_robot_config(EXAMPLE).model_copy(
            update={
                "behaviors": BehaviorConfig(
                    user_directory=str(tmp_path / "behaviors"),
                    safety_state_file=str(tmp_path / "safety.json"),
                    system_stopped_display_seconds=0.0,
                )
            }
        )
        client = build_robot_ide_client(
            config,
            ledger_path=tmp_path / "ledger.sqlite3",
            simulated=True,
        )
        await client.start()

        names = {descriptor.name for descriptor in await client.capabilities()}
        assert {
            "behavior.list",
            "behavior.run",
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
