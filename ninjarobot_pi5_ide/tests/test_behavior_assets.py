from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from ninjarobot_pi5_ide.behavior_assets import (
    BehaviorAssetError,
    BehaviorAssetRepository,
)
from ninjarobot_pi5_ide.behavior_models import FACE_EXPRESSIONS, BehaviorDefinition
from pydantic import ValidationError

MOVEMENT_NAMES = {
    "celebrate",
    "move_backward",
    "move_forward",
    "turn_left",
    "turn_right",
}


def test_bundled_catalog_has_approved_names_and_motion_map(tmp_path: Path) -> None:
    repository = BehaviorAssetRepository(tmp_path / "behaviors")

    definitions = repository.list()

    assert {item.name for item in definitions} == {
        *FACE_EXPRESSIONS,
        "celebrate",
        "error_warning",
        "move_backward",
        "move_forward",
        "turn_left",
        "turn_right",
    }
    assert {item.name for item in definitions if item.category == "movement"} == MOVEMENT_NAMES
    assert "emergency_stop" not in {item.name for item in definitions}

    forward = repository.load("move_forward")
    drive = next(
        operation for operation in forward.stages[0].operations if operation.kind == "drive"
    )
    assert drive.targets == {"left_motor": 45.0, "right_motor": -45.0}
    assert forward.required_resources == ("display", "distance_sensor", "servo_bus")


def test_expression_catalog_combines_faces_and_matching_melodies(
    tmp_path: Path,
) -> None:
    repository = BehaviorAssetRepository(tmp_path / "behaviors")

    for name in FACE_EXPRESSIONS:
        definition = repository.load(name)
        kinds = {operation.kind for stage in definition.stages for operation in stage.operations}
        assert definition.category == "expression"
        assert "face" in kinds
        assert "melody" in kinds
        assert "drive" not in kinds


def test_normal_movement_catalog_has_a_face_and_drive_but_no_buzzer(
    tmp_path: Path,
) -> None:
    repository = BehaviorAssetRepository(tmp_path / "behaviors")

    for name in ("move_forward", "move_backward", "turn_left", "turn_right"):
        definition = repository.load(name)
        kinds = {operation.kind for stage in definition.stages for operation in stage.operations}
        assert definition.category == "movement"
        assert kinds == {"face", "drive"}


def test_special_behaviors_have_explicit_safe_semantics(tmp_path: Path) -> None:
    repository = BehaviorAssetRepository(tmp_path / "behaviors")

    celebrate = repository.load("celebrate")
    celebrate_kinds = {
        operation.kind for stage in celebrate.stages for operation in stage.operations
    }
    assert celebrate.category == "movement"
    assert celebrate_kinds == {"drive", "face", "melody"}

    error_warning = repository.load("error_warning")
    assert error_warning.category == "expression"
    assert not error_warning.contains_motion


def test_greeting_stages_are_sequential_and_second_stage_is_concurrent(
    tmp_path: Path,
) -> None:
    greeting = BehaviorAssetRepository(tmp_path / "behaviors").load("greeting")

    assert [stage.name for stage in greeting.stages] == [
        "greeting_face_and_sound",
        "greeting_text",
    ]
    assert [operation.kind for operation in greeting.stages[0].operations] == [
        "face",
        "melody",
    ]
    assert [operation.kind for operation in greeting.stages[1].operations] == ["text"]


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
    assert repository.list_user() == [definition]
    assert repository.list_user("movement") == []
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


def test_tone_operation_is_bounded_and_cannot_conflict_with_melody() -> None:
    payload = {
        "schema_version": 1,
        "name": "tone_test",
        "description": "A bounded transient tone.",
        "category": "expression",
        "stages": [
            {
                "name": "tone",
                "operations": [
                    {
                        "kind": "tone",
                        "frequency_hz": 880,
                        "duration_seconds": 0.25,
                        "volume": 48,
                    }
                ],
            }
        ],
    }

    definition = BehaviorDefinition.model_validate(payload)
    assert definition.required_resources == ("buzzer",)

    payload["stages"][0]["operations"][0]["frequency_hz"] = 20_001
    with pytest.raises(ValidationError, match="less than or equal to 20000"):
        BehaviorDefinition.model_validate(payload)

    payload["stages"][0]["operations"] = [
        {"kind": "tone", "frequency_hz": 880},
        {"kind": "melody", "melody": "happy"},
    ]
    with pytest.raises(ValidationError, match="only one buzzer operation"):
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
