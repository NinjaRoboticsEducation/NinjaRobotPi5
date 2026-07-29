"""Strict schemas for V4 behavior assets."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

BehaviorName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]
StageName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
ServoRole = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]
FaceName = Literal[
    "idle",
    "happy",
    "laughing",
    "sad",
    "cry",
    "angry",
    "surprising",
    "sleepy",
    "speaking",
    "shy",
    "scary",
    "exciting",
    "confusing",
    "greeting",
    "listening",
    "thinking",
    "curious",
    "success",
    "warning",
    "error",
    "camera",
]
FACE_EXPRESSIONS: tuple[FaceName, ...] = (
    "idle",
    "happy",
    "laughing",
    "sad",
    "cry",
    "angry",
    "surprising",
    "sleepy",
    "speaking",
    "shy",
    "scary",
    "exciting",
    "confusing",
    "greeting",
    "listening",
    "thinking",
    "curious",
    "success",
    "warning",
    "error",
)
EMBEDDED_FACE_EXPRESSIONS: tuple[FaceName, ...] = (*FACE_EXPRESSIONS, "camera")
FACE_ALIASES: dict[str, FaceName] = {
    "embarrassing": "shy",
    "embarrassed": "shy",
    "excited": "exciting",
    "surprised": "surprising",
    "crying": "cry",
}
MelodyName = Literal[
    "happy",
    "sad",
    "exciting",
    "angry",
    "confusing",
    "cry",
    "embarrassing",
    "idle",
    "laughing",
    "scary",
    "shy",
    "sleepy",
    "speaking",
    "surprising",
]
MELODIES: tuple[MelodyName, ...] = (
    "happy",
    "sad",
    "exciting",
    "angry",
    "confusing",
    "cry",
    "embarrassing",
    "idle",
    "laughing",
    "scary",
    "shy",
    "sleepy",
    "speaking",
    "surprising",
)


def normalize_face_name(value: str) -> FaceName:
    """Resolve a canonical embedded face name or a supported compatibility alias."""
    normalized = value.strip().lower().replace(" ", "_")
    alias = FACE_ALIASES.get(normalized)
    if alias is not None:
        return alias
    if normalized not in EMBEDDED_FACE_EXPRESSIONS:
        raise ValueError(f"unknown face expression: {value!r}")
    return normalized


class BehaviorModel(BaseModel):
    """Base for immutable, strict behavior definitions."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FaceOperation(BehaviorModel):
    """Render one approved procedural face."""

    kind: Literal["face"]
    expression: FaceName
    background: Color = "#000020"
    foreground: Color = "#FFFFFF"
    accent: Color = "#00BFFF"
    hold_seconds: Annotated[float, Field(ge=0.05, le=60.0)] | None = None

    @field_validator("expression", mode="before")
    @classmethod
    def normalize_expression(cls, value: object) -> object:
        """Accept the documented face aliases while storing canonical names."""
        return normalize_face_name(value) if isinstance(value, str) else value


class TextOperation(BehaviorModel):
    """Show bounded centered text."""

    kind: Literal["text"]
    text: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    font_size: Annotated[int, Field(ge=8, le=96)] = 32
    foreground: Color = "#FFFFFF"
    background: Color = "#000020"
    hold_seconds: Annotated[float, Field(ge=0.05, le=60.0)] | None = None


class MelodyOperation(BehaviorModel):
    """Play one existing pi5buzzer emotion melody."""

    kind: Literal["melody"]
    melody: MelodyName
    volume: Annotated[int, Field(ge=0, le=128)] = 64


class ToneOperation(BehaviorModel):
    """Play one bounded passive-buzzer tone."""

    kind: Literal["tone"]
    frequency_hz: Annotated[int, Field(ge=20, le=20_000)]
    duration_seconds: Annotated[float, Field(ge=0.05, le=2.0)] = 0.25
    volume: Annotated[int, Field(ge=1, le=128)] = 64


class DriveOperation(BehaviorModel):
    """Drive one or more logical continuous-rotation servo roles."""

    kind: Literal["drive"]
    targets: dict[ServoRole, Annotated[float, Field(ge=-90.0, le=90.0)]]
    speed_mode: Literal["S", "M", "F"] = "M"
    obstacle_policy: Literal["front_guarded", "warn_only"] = "front_guarded"
    hold_seconds: Annotated[float, Field(ge=0.05, le=60.0)] | None = None

    @model_validator(mode="after")
    def targets_must_not_be_empty(self) -> DriveOperation:
        """Require at least one target and reject duplicate normalized keys."""
        if not self.targets:
            raise ValueError("drive targets must not be empty")
        return self


class WaitOperation(BehaviorModel):
    """Wait within a stage without touching hardware."""

    kind: Literal["wait"]
    seconds: Annotated[float, Field(ge=0.01, le=60.0)]


BehaviorOperation = Annotated[
    FaceOperation
    | TextOperation
    | MelodyOperation
    | ToneOperation
    | DriveOperation
    | WaitOperation,
    Field(discriminator="kind"),
]


class BehaviorStage(BehaviorModel):
    """Operations in one stage start together and complete before the next stage."""

    name: StageName
    operations: tuple[BehaviorOperation, ...]

    @field_validator("operations", mode="before")
    @classmethod
    def normalize_operations(cls, operations: object) -> object:
        """Normalize JSON arrays before strict tuple validation."""
        return tuple(operations) if isinstance(operations, list) else operations

    @model_validator(mode="after")
    def stage_must_have_operations(self) -> BehaviorStage:
        """Reject empty or unreasonably large concurrent stages."""
        if not self.operations:
            raise ValueError("behavior stages must contain at least one operation")
        if len(self.operations) > 8:
            raise ValueError("behavior stages may contain at most 8 operations")
        kinds = [operation.kind for operation in self.operations]
        if len(kinds) != len(set(kinds)):
            raise ValueError("a behavior stage may contain each operation kind only once")
        display_operations = sum(kind in {"face", "text"} for kind in kinds)
        if display_operations > 1:
            raise ValueError("a behavior stage may contain only one display operation")
        buzzer_operations = sum(kind in {"melody", "tone"} for kind in kinds)
        if buzzer_operations > 1:
            raise ValueError("a behavior stage may contain only one buzzer operation")
        return self


class BehaviorDefinition(BehaviorModel):
    """One complete expression or movement asset."""

    schema_version: Literal[1] = 1
    name: BehaviorName
    description: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    category: Literal["expression", "movement"]
    stages: tuple[BehaviorStage, ...]

    @field_validator("stages", mode="before")
    @classmethod
    def normalize_stages(cls, stages: object) -> object:
        """Normalize JSON arrays before strict tuple validation."""
        return tuple(stages) if isinstance(stages, list) else stages

    @model_validator(mode="after")
    def structure_matches_category(self) -> BehaviorDefinition:
        """Bound stage count and keep movement operations out of expressions."""
        if not self.stages:
            raise ValueError("behaviors must contain at least one stage")
        if len(self.stages) > 16:
            raise ValueError("behaviors may contain at most 16 stages")
        has_drive = any(
            operation.kind == "drive" for stage in self.stages for operation in stage.operations
        )
        if self.category == "expression" and has_drive:
            raise ValueError("expression behaviors must not contain drive operations")
        if self.category == "movement" and not has_drive:
            raise ValueError("movement behaviors must contain a drive operation")
        indefinite_stages = [
            stage.name
            for stage in self.stages
            if any(
                isinstance(operation, (FaceOperation, TextOperation, DriveOperation))
                and operation.hold_seconds is None
                for operation in stage.operations
            )
        ]
        if any(stage_name != self.stages[-1].name for stage_name in indefinite_stages):
            raise ValueError("only the final behavior stage may contain indefinite operations")
        return self

    @property
    def contains_motion(self) -> bool:
        """Return whether any stage drives a servo role."""
        return any(
            operation.kind == "drive" for stage in self.stages for operation in stage.operations
        )

    @property
    def required_resources(self) -> tuple[str, ...]:
        """Return stable logical resources required by this behavior."""
        resources: set[str] = set()
        for stage in self.stages:
            for operation in stage.operations:
                if operation.kind in {"face", "text"}:
                    resources.add("display")
                elif operation.kind in {"melody", "tone"}:
                    resources.add("buzzer")
                elif operation.kind == "drive":
                    resources.update({"distance_sensor", "servo_bus"})
        return tuple(sorted(resources))
