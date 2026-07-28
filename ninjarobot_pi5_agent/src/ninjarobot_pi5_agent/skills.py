"""Confined, non-executable NinjaRobotAgent skill packages."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Annotated, Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from .models import ToolName

SkillID = Annotated[
    str,
    StringConstraints(min_length=1, max_length=63, pattern=r"^[a-z][a-z0-9-]*$"),
]
Version = Annotated[
    str,
    StringConstraints(min_length=5, max_length=32, pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$"),
]

_ALLOWED_FILES = frozenset({"skill.json", "instructions.md", "examples.json"})
_MAX_FILE_BYTES = {
    "skill.json": 65_536,
    "instructions.md": 65_536,
    "examples.json": 131_072,
}
_FORBIDDEN_INSTRUCTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|system|safety)\b", re.IGNORECASE),
    re.compile(r"\b(?:bypass|disable|override)\s+(?:the\s+)?safety\b", re.IGNORECASE),
    re.compile(r"\breveal\s+(?:the\s+)?system\s+prompt\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
)


class SkillLimits(BaseModel):
    """Bounded reasoning and execution budget for one skill."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_model_turns: Annotated[int, Field(ge=1, le=12)] = 4
    max_tool_calls: Annotated[int, Field(ge=0, le=20)] = 5
    timeout_seconds: Annotated[float, Field(ge=1, le=300)] = 60.0


class SkillSafety(BaseModel):
    """Declarative restrictions; never a source of additional permission."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    external_content: str = "untrusted"
    physical_motion: str = "session_armed"

    @field_validator("external_content")
    @classmethod
    def external_content_must_remain_untrusted(cls, value: str) -> str:
        if value != "untrusted":
            raise ValueError("external_content must remain untrusted")
        return value

    @field_validator("physical_motion")
    @classmethod
    def physical_motion_must_remain_armed(cls, value: str) -> str:
        if value != "session_armed":
            raise ValueError("physical_motion must remain session_armed")
        return value


class SkillManifest(BaseModel):
    """Strict versioned skill metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Annotated[int, Field(ge=1, le=1)]
    id: SkillID
    version: Version
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    description: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    activation_examples: tuple[Annotated[str, StringConstraints(min_length=1, max_length=300)], ...]
    allowed_tools: tuple[ToolName, ...]
    input_schema: dict[str, Any]
    limits: SkillLimits = SkillLimits()
    safety: SkillSafety = SkillSafety()

    @field_validator("activation_examples", "allowed_tools")
    @classmethod
    def tuples_must_be_nonempty_and_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("skill lists must not be empty")
        if len(values) != len(set(values)):
            raise ValueError("skill lists must not contain duplicates")
        return values

    @field_validator("input_schema")
    @classmethod
    def input_schema_must_be_strict_object(
        cls,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            Draft202012Validator.check_schema(value)
        except SchemaError as exc:
            raise ValueError(f"invalid input_schema: {exc.message}") from exc
        if value.get("type") != "object":
            raise ValueError("skill input_schema must describe an object")
        if value.get("additionalProperties") is not False:
            raise ValueError("skill input_schema must set additionalProperties to false")
        return value


class SkillExample(BaseModel):
    """One simulation-only skill scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    input: dict[str, Any]
    expected_tools: tuple[ToolName, ...]
    simulation_only: bool

    @field_validator("simulation_only")
    @classmethod
    def examples_must_be_simulation_only(cls, value: bool) -> bool:
        if not value:
            raise ValueError("skill examples must be simulation_only")
        return value


class SkillExamples(BaseModel):
    """Optional versioned example collection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Annotated[int, Field(ge=1, le=1)]
    examples: tuple[SkillExample, ...]


class LoadedSkill(BaseModel):
    """Validated skill ready for prompt composition or simulation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    manifest: SkillManifest
    instructions: str
    examples: SkillExamples | None = None
    path: Path
    bundled: bool
    enabled: bool


class SkillValidationError(ValueError):
    """Raised when a skill package violates format or confinement."""


class SkillRepository:
    """Read bundled skills and atomically manage confined user skills."""

    def __init__(
        self,
        user_directory: str | Path,
        *,
        bundled_directory: str | Path | None = None,
    ) -> None:
        self._user_directory = Path(user_directory).expanduser()
        self._bundled_directory = (
            Path(bundled_directory)
            if bundled_directory is not None
            else Path(__file__).with_name("bundled_skills")
        )
        self._disabled_path = self._user_directory / "disabled.json"

    def list(self) -> tuple[LoadedSkill, ...]:
        """Return bundled and user skills, rejecting duplicate IDs."""
        loaded: dict[str, LoadedSkill] = {}
        disabled = self._disabled_ids()
        for root, bundled in (
            (self._bundled_directory, True),
            (self._user_directory, False),
        ):
            if not root.exists():
                continue
            for path in sorted(root.iterdir()):
                if not path.is_dir() or path.is_symlink():
                    continue
                skill = self.load_path(path, bundled=bundled, enabled=path.name not in disabled)
                if skill.manifest.id in loaded:
                    raise SkillValidationError(f"duplicate skill ID: {skill.manifest.id}")
                loaded[skill.manifest.id] = skill
        return tuple(loaded[name] for name in sorted(loaded))

    def get(
        self,
        skill_id: str,
        *,
        available_tools: set[str] | None = None,
    ) -> LoadedSkill:
        """Return one enabled skill and optionally resolve its tool allowlist."""
        for skill in self.list():
            if skill.manifest.id == skill_id:
                if not skill.enabled:
                    raise SkillValidationError(f"skill is disabled: {skill_id}")
                self._validate_available_tools(skill, available_tools)
                return skill
        raise KeyError(f"unknown skill: {skill_id}")

    def load_path(
        self,
        path: str | Path,
        *,
        bundled: bool = False,
        enabled: bool = True,
        available_tools: set[str] | None = None,
    ) -> LoadedSkill:
        """Validate a flat, non-symlink skill directory."""
        directory = Path(path).expanduser()
        if directory.is_symlink() or not directory.is_dir():
            raise SkillValidationError("skill path must be a real directory, not a symlink")
        entries = tuple(directory.iterdir())
        names = {entry.name for entry in entries}
        unexpected = sorted(names - _ALLOWED_FILES)
        if unexpected:
            raise SkillValidationError(f"unexpected skill files: {', '.join(unexpected)}")
        missing = sorted({"skill.json", "instructions.md"} - names)
        if missing:
            raise SkillValidationError(f"missing skill files: {', '.join(missing)}")
        for entry in entries:
            if entry.is_symlink() or not entry.is_file():
                raise SkillValidationError("skill packages may contain only regular files")
            if entry.stat().st_size > _MAX_FILE_BYTES[entry.name]:
                raise SkillValidationError(f"skill file is too large: {entry.name}")
        try:
            manifest = SkillManifest.model_validate_json(
                (directory / "skill.json").read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise SkillValidationError(f"invalid skill.json: {exc}") from exc
        if directory.name != manifest.id:
            raise SkillValidationError("skill directory name must match manifest id")
        instructions = (directory / "instructions.md").read_text(encoding="utf-8").strip()
        if not instructions:
            raise SkillValidationError("instructions.md must not be empty")
        if "../" in instructions or re.search(
            r"(?<![:\w])/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+",
            instructions,
        ):
            raise SkillValidationError("instructions contain a forbidden filesystem path")
        if any(pattern.search(instructions) for pattern in _FORBIDDEN_INSTRUCTION_PATTERNS):
            raise SkillValidationError("instructions attempt to override protected policy")
        examples_path = directory / "examples.json"
        examples = (
            SkillExamples.model_validate_json(examples_path.read_text(encoding="utf-8"))
            if examples_path.exists()
            else None
        )
        if examples is not None:
            allowed = set(manifest.allowed_tools)
            for example in examples.examples:
                unknown = sorted(set(example.expected_tools) - allowed)
                if unknown:
                    raise SkillValidationError(
                        f"example uses tools outside skill allowlist: {', '.join(unknown)}"
                    )
                self.validate_input(manifest, example.input)
        loaded = LoadedSkill(
            manifest=manifest,
            instructions=instructions,
            examples=examples,
            path=directory.resolve(),
            bundled=bundled,
            enabled=enabled,
        )
        self._validate_available_tools(loaded, available_tools)
        return loaded

    def validate_input(self, manifest: SkillManifest, value: dict[str, Any]) -> None:
        """Validate runtime input against the skill's approved JSON Schema."""
        try:
            Draft202012Validator(manifest.input_schema).validate(value)
        except JSONSchemaValidationError as exc:
            raise SkillValidationError(f"skill input is invalid: {exc.message}") from exc

    def simulate(self, skill: LoadedSkill, value: dict[str, Any]) -> dict[str, Any]:
        """Return a hardware-free execution preview."""
        self.validate_input(skill.manifest, value)
        matching: tuple[dict[str, Any], ...] = ()
        if skill.examples is not None:
            matching = tuple(
                example.model_dump(mode="json")
                for example in skill.examples.examples
                if example.input == value
            )
        return {
            "skill": skill.manifest.id,
            "simulation_only": True,
            "input": value,
            "allowed_tools": list(skill.manifest.allowed_tools),
            "limits": skill.manifest.limits.model_dump(mode="json"),
            "matching_examples": matching,
            "warnings": [
                "No robot hardware or external MCP tool was executed.",
                "Physical motion would still require an armed session.",
            ],
        }

    def install(
        self,
        source: str | Path,
        *,
        ai_proposed: bool = False,
        confirmed: bool = False,
        simulation_input: dict[str, Any] | None = None,
    ) -> LoadedSkill:
        """Atomically install a validated user skill without overwriting."""
        skill = self.load_path(source)
        if ai_proposed and not confirmed:
            raise PermissionError("AI-proposed skills require explicit approval")
        if ai_proposed:
            if simulation_input is None:
                raise PermissionError("AI-proposed skills require a simulation preview")
            self.simulate(skill, simulation_input)
        destination = self._user_directory / skill.manifest.id
        if destination.exists():
            raise FileExistsError(f"skill already exists: {skill.manifest.id}")
        self._user_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._user_directory.chmod(0o700)
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{skill.manifest.id}-", dir=self._user_directory)
        )
        try:
            for filename in sorted(_ALLOWED_FILES & {item.name for item in skill.path.iterdir()}):
                source_file = skill.path / filename
                target_file = temporary / filename
                shutil.copyfile(source_file, target_file)
                target_file.chmod(0o600)
            temporary.rename(destination)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return self.load_path(destination)

    def set_enabled(self, skill_id: str, *, enabled: bool) -> None:
        """Persist a local enable/disable override."""
        self._find_any(skill_id)
        disabled = self._disabled_ids()
        if enabled:
            disabled.discard(skill_id)
        else:
            disabled.add(skill_id)
        self._write_disabled_ids(disabled)

    def remove(self, skill_id: str, *, confirmed: bool) -> None:
        """Remove one user skill after explicit confirmation."""
        if not confirmed:
            raise PermissionError("removing a skill requires explicit confirmation")
        target = self._user_directory / skill_id
        if target.is_symlink() or not target.is_dir():
            raise KeyError(f"unknown user skill: {skill_id}")
        loaded = self.load_path(target)
        if loaded.manifest.id != skill_id:
            raise SkillValidationError("skill identity mismatch")
        shutil.rmtree(target)
        disabled = self._disabled_ids()
        disabled.discard(skill_id)
        self._write_disabled_ids(disabled)

    def _find_any(self, skill_id: str) -> LoadedSkill:
        for skill in self.list():
            if skill.manifest.id == skill_id:
                return skill
        raise KeyError(f"unknown skill: {skill_id}")

    @staticmethod
    def _validate_available_tools(
        skill: LoadedSkill,
        available_tools: set[str] | None,
    ) -> None:
        if available_tools is None:
            return
        unavailable = sorted(set(skill.manifest.allowed_tools) - available_tools)
        if unavailable:
            raise SkillValidationError(
                f"skill references unavailable tools: {', '.join(unavailable)}"
            )

    def _disabled_ids(self) -> set[str]:
        if not self._disabled_path.exists():
            return set()
        payload = json.loads(self._disabled_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("disabled"), list):
            raise SkillValidationError("disabled skill state is malformed")
        values = payload["disabled"]
        if any(not isinstance(value, str) for value in values):
            raise SkillValidationError("disabled skill IDs must be strings")
        return set(values)

    def _write_disabled_ids(self, disabled: set[str]) -> None:
        self._user_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self._disabled_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"disabled": sorted(disabled)}, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(self._disabled_path)
        self._disabled_path.chmod(0o600)
