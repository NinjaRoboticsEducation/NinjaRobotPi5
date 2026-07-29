"""Model-friendly behavior drafts compiled into strict IDE definitions."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any, cast

from pydantic import TypeAdapter, ValidationError

from .behavior_assets import BehaviorAssetRepository
from .behavior_models import (
    FACE_EXPRESSIONS,
    MELODIES,
    BehaviorDefinition,
    BehaviorOperation,
    BehaviorStage,
    DriveOperation,
    FaceOperation,
    MelodyOperation,
    TextOperation,
    ToneOperation,
    WaitOperation,
)

_OPERATION_ADAPTER: TypeAdapter[BehaviorOperation] = TypeAdapter(BehaviorOperation)
_BEHAVIOR_CATEGORIES = {"expression", "movement"}
_MOVEMENT_ALIASES = {
    "forward": "move_forward",
    "drive_forward": "move_forward",
    "move_forward": "move_forward",
    "backward": "move_backward",
    "drive_backward": "move_backward",
    "move_backward": "move_backward",
    "left": "turn_left",
    "turn_left": "turn_left",
    "right": "turn_right",
    "turn_right": "turn_right",
    "stop": "stop",
}
_MOVEMENTS = ("move_forward", "move_backward", "turn_left", "turn_right", "stop")
_ROOT_KEYS = {"schema_version", "name", "description", "category", "stages"}
_COMMON_STAGE_KEYS = {
    "name",
    "operations",
    "face",
    "text",
    "melody",
    "tone",
    "movement",
    "drive_targets",
    "speed_mode",
    "obstacle_policy",
    "duration_seconds",
    "wait_seconds",
}
_DISPLAY_KINDS = {"face", "text"}
_BUZZER_KINDS = {"melody", "tone"}
_NOTE_PATTERN: re.Pattern[str] = re.compile(r"^([A-Ga-g])([#b]?)([0-8])$")


class BehaviorDraftError(ValueError):
    """A model draft cannot be translated without guessing unsafe intent."""


class BehaviorDraftCompiler:
    """Translate a compact model draft into the canonical strict behavior schema."""

    def __init__(
        self,
        *,
        assets: BehaviorAssetRepository,
        servo_roles: tuple[str, ...],
    ) -> None:
        self._assets = assets
        self._servo_roles = frozenset(servo_roles)

    def input_schema(self, *, motion: bool) -> dict[str, Any]:
        """Return a compact Ollama-friendly schema without unions or JSON references."""
        stage_properties: dict[str, Any] = {
            "name": {
                "type": "string",
                "pattern": "^[a-z][a-z0-9_-]*$",
                "maxLength": 64,
                "description": "Optional stage name; generated when omitted.",
            },
            "face": {
                "type": "string",
                "enum": list(FACE_EXPRESSIONS),
                "description": "One animated face. Do not combine face and text in one stage.",
            },
            "text": {
                "type": "string",
                "minLength": 1,
                "maxLength": 160,
                "description": "Centered display text. Do not combine text and face in one stage.",
            },
            "melody": {
                "type": "string",
                "enum": list(MELODIES),
                "description": "One built-in melody. Do not combine melody and tone in one stage.",
            },
            "tone": {
                "type": "object",
                "description": "One short tone. Do not combine tone and melody in one stage.",
                "properties": {
                    "frequency_hz": {
                        "type": "integer",
                        "minimum": 20,
                        "maximum": 20_000,
                    },
                    "duration_seconds": {
                        "type": "number",
                        "minimum": 0.05,
                        "maximum": 2.0,
                    },
                    "volume": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 128,
                    },
                },
                "required": ["frequency_hz"],
                "additionalProperties": False,
            },
            "duration_seconds": {
                "type": "number",
                "minimum": 0.05,
                "maximum": 60.0,
                "description": (
                    "How long face, text, or movement remains active. Defaults to "
                    "one second when omitted."
                ),
            },
            "wait_seconds": {
                "type": "number",
                "minimum": 0.01,
                "maximum": 60.0,
            },
        }
        if motion:
            stage_properties.update(
                {
                    "movement": {
                        "type": "string",
                        "enum": list(_MOVEMENTS),
                        "description": (
                            "A safe configured movement preset. Prefer this over custom "
                            "drive_targets for ordinary movement."
                        ),
                    },
                    "drive_targets": {
                        "type": "object",
                        "description": (
                            "Advanced logical motor targets. Never use GPIO numbers. "
                            "Do not combine with movement."
                        ),
                        "properties": {
                            role: {
                                "type": "number",
                                "minimum": -90.0,
                                "maximum": 90.0,
                            }
                            for role in sorted(self._servo_roles)
                        },
                        "additionalProperties": False,
                        "minProperties": 1,
                    },
                    "speed_mode": {
                        "type": "string",
                        "enum": ["S", "M", "F"],
                    },
                    "obstacle_policy": {
                        "type": "string",
                        "enum": ["front_guarded", "warn_only"],
                    },
                }
            )
        category = "movement" if motion else "expression"
        return {
            "type": "object",
            "description": (
                f"A finite {category} draft. Fields in one stage run concurrently; "
                "stages run in order."
            ),
            "properties": {
                "schema_version": {"type": "integer", "const": 1, "default": 1},
                "name": {
                    "type": "string",
                    "pattern": "^[a-z][a-z0-9_-]*$",
                    "maxLength": 64,
                },
                "description": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 300,
                },
                "category": {"type": "string", "const": category},
                "stages": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 16,
                    "items": {
                        "type": "object",
                        "properties": stage_properties,
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["name", "description", "stages"],
            "additionalProperties": False,
        }

    def compile(
        self,
        arguments: Mapping[str, Any],
        *,
        motion: bool,
    ) -> BehaviorDefinition:
        """Compile canonical input or a supported compact/shorthand draft."""
        try:
            return self._compile(arguments, motion=motion)
        except BehaviorDraftError:
            raise
        except ValidationError as exc:
            raise BehaviorDraftError(_validation_summary(exc)) from exc

    def _compile(
        self,
        arguments: Mapping[str, Any],
        *,
        motion: bool,
    ) -> BehaviorDefinition:
        """Compile after converting validation errors into the stable draft error."""
        canonical = self._canonical(arguments, motion=motion)
        if canonical is not None:
            return canonical

        payload = dict(arguments)
        self._reject_unknown_keys(payload, _ROOT_KEYS, context="behavior")
        schema_version = payload.get("schema_version", 1)
        if schema_version != 1:
            raise BehaviorDraftError("schema_version must be 1")
        expected_category = "movement" if motion else "expression"
        category = payload.get("category", expected_category)
        if category not in _BEHAVIOR_CATEGORIES or category != expected_category:
            raise BehaviorDraftError(
                f"{expected_category} tool requires category '{expected_category}'"
            )
        name = payload.get("name", f"agent_{expected_category}")
        description = payload.get(
            "description",
            f"Transient agent-created {expected_category}.",
        )
        raw_stages = payload.get("stages")
        if not isinstance(raw_stages, (list, tuple)) or not raw_stages:
            raise BehaviorDraftError("stages must be a non-empty array")
        if len(raw_stages) > 16:
            raise BehaviorDraftError("behaviors may contain at most 16 stages")

        stages: list[BehaviorStage] = []
        for stage_index, raw_stage in enumerate(raw_stages, start=1):
            compiled = self._compile_stage(raw_stage, stage_index=stage_index, motion=motion)
            stages.extend(compiled)
        if motion and not any(
            operation.kind == "drive" for stage in stages for operation in stage.operations
        ):
            raise BehaviorDraftError(
                "movement draft requires movement or drive_targets in at least one stage"
            )
        try:
            return BehaviorDefinition.model_validate(
                {
                    "schema_version": 1,
                    "name": name,
                    "description": description,
                    "category": expected_category,
                    "stages": [
                        stage.model_dump(mode="json", exclude_none=False) for stage in stages
                    ],
                }
            )
        except ValidationError as exc:
            raise BehaviorDraftError(_validation_summary(exc)) from exc

    def _canonical(
        self,
        arguments: Mapping[str, Any],
        *,
        motion: bool,
    ) -> BehaviorDefinition | None:
        try:
            definition = BehaviorDefinition.model_validate(dict(arguments))
        except ValidationError:
            return None
        expected_category = "movement" if motion else "expression"
        if definition.category != expected_category:
            raise BehaviorDraftError(
                f"{expected_category} tool requires category '{expected_category}'"
            )
        self._validate_roles(definition)
        return definition

    def _compile_stage(
        self,
        raw_stage: object,
        *,
        stage_index: int,
        motion: bool,
    ) -> list[BehaviorStage]:
        if not isinstance(raw_stage, Mapping):
            raise BehaviorDraftError(f"stages[{stage_index - 1}] must be an object")
        stage = dict(raw_stage)
        allowed = (
            _COMMON_STAGE_KEYS
            if motion
            else _COMMON_STAGE_KEYS
            - {
                "movement",
                "drive_targets",
                "speed_mode",
                "obstacle_policy",
            }
        )
        self._reject_unknown_keys(stage, allowed, context=f"stages[{stage_index - 1}]")
        duration = _bounded_number(
            stage.get("duration_seconds", 1.0),
            name="duration_seconds",
            minimum=0.05,
            maximum=60.0,
        )
        base_name = stage.get("name", f"stage_{stage_index}")
        operations: list[BehaviorOperation] = []
        raw_operations = stage.get("operations")
        if raw_operations is not None:
            if not isinstance(raw_operations, (list, tuple)) or not raw_operations:
                raise BehaviorDraftError("stage operations must be a non-empty array")
            operations.extend(
                self._compile_operation(
                    operation,
                    motion=motion,
                    duration=duration,
                    stage=stage,
                )
                for operation in raw_operations
            )
        operations.extend(self._flat_operations(stage, motion=motion, duration=duration))
        if not operations:
            raise BehaviorDraftError(f"stage '{base_name}' contains no operations")

        groups = _compatible_groups(operations)
        compiled: list[BehaviorStage] = []
        for group_index, group in enumerate(groups, start=1):
            name = str(base_name) if len(groups) == 1 else f"{base_name}_{group_index}"
            try:
                compiled.append(BehaviorStage(name=name, operations=tuple(group)))
            except ValidationError as exc:
                raise BehaviorDraftError(_validation_summary(exc)) from exc
        return compiled

    def _flat_operations(
        self,
        stage: Mapping[str, Any],
        *,
        motion: bool,
        duration: float,
    ) -> list[BehaviorOperation]:
        operations: list[BehaviorOperation] = []
        if "face" in stage:
            operations.append(
                FaceOperation(
                    kind="face",
                    expression=cast(Any, stage["face"]),
                    hold_seconds=duration,
                )
            )
        if "melody" in stage:
            operations.append(
                MelodyOperation(
                    kind="melody",
                    melody=cast(Any, _normalize_melody(stage["melody"])),
                )
            )
        if motion:
            drive = self._flat_drive(stage, duration=duration)
            if drive is not None:
                operations.append(drive)
        if "text" in stage:
            operations.append(
                TextOperation(
                    kind="text",
                    text=cast(str, stage["text"]),
                    hold_seconds=duration,
                )
            )
        if "tone" in stage:
            operations.append(_tone_operation(stage["tone"]))
        if "wait_seconds" in stage:
            operations.append(
                WaitOperation(
                    kind="wait",
                    seconds=_bounded_number(
                        stage["wait_seconds"],
                        name="wait_seconds",
                        minimum=0.01,
                        maximum=60.0,
                    ),
                )
            )
        return operations

    def _flat_drive(
        self,
        stage: Mapping[str, Any],
        *,
        duration: float,
    ) -> DriveOperation | None:
        movement = stage.get("movement")
        targets = stage.get("drive_targets")
        if movement is not None and targets is not None:
            raise BehaviorDraftError("use either movement or drive_targets, not both")
        speed_mode = stage.get("speed_mode", "M")
        obstacle_policy = stage.get("obstacle_policy")
        if movement is not None:
            return self._movement_operation(
                movement,
                duration=duration,
                speed_mode=speed_mode,
                obstacle_policy=obstacle_policy,
            )
        if targets is None:
            return None
        if not isinstance(targets, Mapping) or not targets:
            raise BehaviorDraftError("drive_targets must be a non-empty object")
        unknown = sorted(set(targets) - self._servo_roles)
        if unknown:
            raise BehaviorDraftError(
                "drive_targets contain unconfigured logical roles: " + ", ".join(unknown)
            )
        try:
            return DriveOperation(
                kind="drive",
                targets={str(role): float(value) for role, value in targets.items()},
                speed_mode=cast(Any, speed_mode),
                obstacle_policy=cast(Any, obstacle_policy or "front_guarded"),
                hold_seconds=duration,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise BehaviorDraftError(f"invalid drive_targets: {exc}") from exc

    def _compile_operation(
        self,
        raw_operation: object,
        *,
        motion: bool,
        duration: float,
        stage: Mapping[str, Any],
    ) -> BehaviorOperation:
        if not isinstance(raw_operation, Mapping):
            raise BehaviorDraftError("each operation must be an object")
        operation = dict(raw_operation)
        if "kind" in operation:
            try:
                parsed = _OPERATION_ADAPTER.validate_python(operation)
            except ValidationError as exc:
                raise BehaviorDraftError(_validation_summary(exc)) from exc
            if parsed.kind == "drive":
                if not motion:
                    raise BehaviorDraftError("expression drafts cannot contain drive operations")
                self._validate_drive_roles(parsed)
            return _with_default_duration(parsed, duration)
        if len(operation) == 1:
            key, value = next(iter(operation.items()))
            if key == "face":
                return FaceOperation(
                    kind="face",
                    expression=cast(Any, value),
                    hold_seconds=duration,
                )
            if key == "text":
                return TextOperation(kind="text", text=cast(str, value), hold_seconds=duration)
            if key == "melody":
                return MelodyOperation(
                    kind="melody",
                    melody=cast(Any, _normalize_melody(value)),
                )
            if key == "tone":
                return _tone_operation(value)
            if key in {"movement", "servo_role"}:
                if not motion:
                    raise BehaviorDraftError("expression drafts cannot contain movement")
                return self._movement_operation(
                    value,
                    duration=duration,
                    speed_mode=stage.get("speed_mode", "M"),
                    obstacle_policy=stage.get("obstacle_policy"),
                )
        role = operation.get("role")
        if motion and isinstance(role, str):
            value = operation.get("value")
            movement = value if role == "drive" and isinstance(value, str) else role
            magnitude = value if isinstance(value, (int, float)) else None
            return self._movement_operation(
                movement,
                duration=duration,
                speed_mode=stage.get("speed_mode", "M"),
                obstacle_policy=stage.get("obstacle_policy"),
                magnitude=magnitude,
            )
        raise BehaviorDraftError(
            "operation must use kind or one shorthand key: face, text, melody, tone, "
            "movement, or servo_role"
        )

    def _movement_operation(
        self,
        value: object,
        *,
        duration: float,
        speed_mode: object,
        obstacle_policy: object,
        magnitude: int | float | None = None,
    ) -> DriveOperation:
        if not isinstance(value, str):
            raise BehaviorDraftError("movement must be a named movement string")
        normalized = _MOVEMENT_ALIASES.get(value.strip().lower().replace(" ", "_"))
        if normalized is None:
            raise BehaviorDraftError(
                "unknown movement; use move_forward, move_backward, turn_left, turn_right, or stop"
            )
        if normalized == "stop":
            targets = {role: 0.0 for role in sorted(self._servo_roles)}
            source_policy = "front_guarded"
        else:
            definition = self._assets.load(normalized)
            source = next(
                operation
                for behavior_stage in definition.stages
                for operation in behavior_stage.operations
                if isinstance(operation, DriveOperation)
            )
            targets = dict(source.targets)
            source_policy = source.obstacle_policy
        unknown = sorted(set(targets) - self._servo_roles)
        if unknown:
            raise BehaviorDraftError(
                "movement preset references unconfigured logical roles: " + ", ".join(unknown)
            )
        if magnitude is not None:
            bounded = _bounded_number(
                magnitude,
                name="movement magnitude",
                minimum=0.0,
                maximum=90.0,
            )
            targets = {
                role: math.copysign(bounded, target) if target else 0.0
                for role, target in targets.items()
            }
        try:
            return DriveOperation(
                kind="drive",
                targets=targets,
                speed_mode=cast(Any, speed_mode),
                obstacle_policy=cast(Any, obstacle_policy or source_policy),
                hold_seconds=duration,
            )
        except ValidationError as exc:
            raise BehaviorDraftError(_validation_summary(exc)) from exc

    def _validate_roles(self, definition: BehaviorDefinition) -> None:
        for stage in definition.stages:
            for operation in stage.operations:
                if isinstance(operation, DriveOperation):
                    self._validate_drive_roles(operation)

    def _validate_drive_roles(self, operation: DriveOperation) -> None:
        unknown = sorted(set(operation.targets) - self._servo_roles)
        if unknown:
            raise BehaviorDraftError(
                "drive targets contain unconfigured logical roles: " + ", ".join(unknown)
            )

    @staticmethod
    def _reject_unknown_keys(
        value: Mapping[str, Any],
        allowed: set[str],
        *,
        context: str,
    ) -> None:
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise BehaviorDraftError(f"{context} contains unknown fields: {', '.join(unknown)}")


def _with_default_duration(
    operation: BehaviorOperation,
    duration: float,
) -> BehaviorOperation:
    if isinstance(operation, (FaceOperation, TextOperation, DriveOperation)):
        if operation.hold_seconds is None:
            return operation.model_copy(update={"hold_seconds": duration})
    return operation


def _compatible_groups(
    operations: list[BehaviorOperation],
) -> list[list[BehaviorOperation]]:
    groups: list[list[BehaviorOperation]] = [[]]
    for operation in operations:
        current = groups[-1]
        kinds = {item.kind for item in current}
        conflict = operation.kind in kinds
        if operation.kind in _DISPLAY_KINDS:
            conflict = conflict or bool(kinds & _DISPLAY_KINDS)
        if operation.kind in _BUZZER_KINDS:
            conflict = conflict or bool(kinds & _BUZZER_KINDS)
        if conflict:
            groups.append([])
            current = groups[-1]
        current.append(operation)
    return [group for group in groups if group]


def _tone_operation(value: object) -> ToneOperation:
    if isinstance(value, str):
        frequency = _note_frequency(value)
        return ToneOperation(kind="tone", frequency_hz=frequency)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ToneOperation(kind="tone", frequency_hz=round(value))
    if not isinstance(value, Mapping):
        raise BehaviorDraftError("tone must be a frequency, note name, or tone object")
    payload = dict(value)
    if "frequency_hz" not in payload and "note" in payload:
        payload["frequency_hz"] = _note_frequency(payload.pop("note"))
    try:
        return ToneOperation.model_validate({"kind": "tone", **payload})
    except ValidationError as exc:
        raise BehaviorDraftError(_validation_summary(exc)) from exc


def _note_frequency(value: object) -> int:
    if not isinstance(value, str):
        raise BehaviorDraftError("tone note must look like C5 or F#4")
    match = _NOTE_PATTERN.fullmatch(value.strip())
    if match is None:
        raise BehaviorDraftError("tone note must look like C5 or F#4")
    note, accidental, octave_text = match.groups()
    semitones = {
        "C": 0,
        "D": 2,
        "E": 4,
        "F": 5,
        "G": 7,
        "A": 9,
        "B": 11,
    }
    offset = semitones[note.upper()] + (1 if accidental == "#" else -1 if accidental == "b" else 0)
    midi = (int(octave_text) + 1) * 12 + offset
    frequency = int(round(440.0 * (2.0 ** ((midi - 69) / 12.0))))
    if not 20 <= frequency <= 20_000:
        raise BehaviorDraftError("tone note is outside the supported frequency range")
    return frequency


def _normalize_melody(value: object) -> str:
    if not isinstance(value, str):
        raise BehaviorDraftError("melody must be a built-in melody name")
    normalized = value.strip().lower().replace(" ", "_")
    if normalized.endswith("_tune"):
        normalized = normalized.removesuffix("_tune")
    if normalized not in MELODIES:
        raise BehaviorDraftError("unknown melody; use one of: " + ", ".join(MELODIES))
    return normalized


def _bounded_number(
    value: object,
    *,
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BehaviorDraftError(f"{name} must be a number")
    number = float(value)
    if not minimum <= number <= maximum:
        raise BehaviorDraftError(f"{name} must be between {minimum} and {maximum}")
    return number


def _validation_summary(error: ValidationError) -> str:
    details: list[str] = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "behavior"
        details.append(f"{location}: {item['msg']}")
        if len(details) == 4:
            break
    return "invalid behavior draft: " + "; ".join(details)
