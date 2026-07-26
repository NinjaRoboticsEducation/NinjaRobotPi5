from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from ninjarobot_pi5_ide import (
    BehaviorAssetError,
    BehaviorAssetRepository,
    BehaviorDefinition,
)


def test_bundled_catalog_has_approved_names_and_motion_map(tmp_path: Path) -> None:
    repository = BehaviorAssetRepository(tmp_path / "behaviors")

    definitions = repository.list()

    assert [item.name for item in definitions] == [
        "error",
        "greeting",
        "happy",
        "idle",
        "move_backward",
        "move_forward",
        "success",
        "thinking",
        "turn_left",
        "turn_right",
        "warning",
    ]
    forward = repository.load("move_forward")
    drive = next(
        operation for operation in forward.stages[0].operations if operation.kind == "drive"
    )
    assert drive.targets == {"left_motor": 45.0, "right_motor": -45.0}
    assert forward.required_resources == ("buzzer", "display", "distance_sensor", "servo_bus")


def test_greeting_stages_are_sequential_and_second_stage_is_concurrent(
    tmp_path: Path,
) -> None:
    greeting = BehaviorAssetRepository(tmp_path / "behaviors").load("greeting")

    assert [stage.name for stage in greeting.stages] == [
        "happy_face",
        "greeting_text_and_sound",
    ]
    assert [operation.kind for operation in greeting.stages[1].operations] == [
        "text",
        "melody",
    ]


@pytest.mark.parametrize("name", ["../../secret", "/tmp/secret", "BadName", "bad.name"])
def test_repository_rejects_caller_controlled_paths(tmp_path: Path, name: str) -> None:
    repository = BehaviorAssetRepository(tmp_path / "behaviors")

    with pytest.raises(BehaviorAssetError, match="behavior name"):
        repository.load(name)


def test_user_behavior_round_trip_is_private_and_no_overwrite(tmp_path: Path) -> None:
    repository = BehaviorAssetRepository(tmp_path / "behaviors")
    definition = BehaviorDefinition.model_validate(
        {
            "schema_version": 1,
            "name": "my_smile",
            "description": "A private user expression.",
            "category": "expression",
            "stages": [
                {
                    "name": "show",
                    "operations": [
                        {
                            "kind": "face",
                            "expression": "happy",
                            "hold_seconds": 1.0,
                        }
                    ],
                }
            ],
        }
    )

    path = repository.save_user(definition)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert repository.load("my_smile") == definition
    with pytest.raises(BehaviorAssetError, match="already exists"):
        repository.save_user(definition)
    repository.delete_user("my_smile")
    with pytest.raises(BehaviorAssetError, match="unable to read"):
        repository.load("my_smile")


def test_repository_rejects_symlinked_user_asset(tmp_path: Path) -> None:
    directory = tmp_path / "behaviors"
    directory.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    (directory / "escape.json").symlink_to(outside)

    with pytest.raises(BehaviorAssetError, match="symbolic link"):
        BehaviorAssetRepository(directory).list()


def test_definition_rejects_expression_motion_and_early_indefinite_stage() -> None:
    payload = {
        "schema_version": 1,
        "name": "unsafe",
        "description": "Invalid test definition.",
        "category": "expression",
        "stages": [
            {
                "name": "first",
                "operations": [{"kind": "face", "expression": "happy"}],
            },
            {
                "name": "second",
                "operations": [{"kind": "wait", "seconds": 1.0}],
            },
        ],
    }
    with pytest.raises(ValidationError, match="final behavior stage"):
        BehaviorDefinition.model_validate(payload)

    payload["stages"][0]["operations"] = [
        {
            "kind": "drive",
            "targets": {"left_motor": 10.0},
            "hold_seconds": 1.0,
        }
    ]
    with pytest.raises(ValidationError, match="must not contain drive"):
        BehaviorDefinition.model_validate(payload)


def test_repository_rejects_filename_payload_mismatch(tmp_path: Path) -> None:
    directory = tmp_path / "behaviors"
    directory.mkdir()
    payload = {
        "schema_version": 1,
        "name": "actual_name",
        "description": "A mismatched private expression.",
        "category": "expression",
        "stages": [
            {
                "name": "show",
                "operations": [
                    {
                        "kind": "text",
                        "text": "Hello",
                        "hold_seconds": 1.0,
                    }
                ],
            }
        ],
    }
    (directory / "wrong_name.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BehaviorAssetError, match="does not match payload name"):
        BehaviorAssetRepository(directory).load("wrong_name")
