"""Secure read-only defaults and private user behavior storage."""

from __future__ import annotations

import json
import os
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Iterable

from pydantic import TypeAdapter, ValidationError

from .behavior_models import BehaviorDefinition, BehaviorName

_BEHAVIOR_NAME_ADAPTER = TypeAdapter(BehaviorName)


class BehaviorAssetError(ValueError):
    """Raised when an asset name, path, or payload is unsafe or invalid."""


class BehaviorAssetRepository:
    """Load bundled assets and owner-controlled user assets by validated name."""

    def __init__(self, user_directory: str | Path) -> None:
        self._user_directory = Path(user_directory).expanduser()

    @property
    def user_directory(self) -> Path:
        """Return the configured private user-asset directory."""
        return self._user_directory

    def list(self, category: str = "all") -> list[BehaviorDefinition]:
        """Return validated definitions in stable name order."""
        if category not in {"all", "expression", "movement"}:
            raise BehaviorAssetError("category must be all, expression, or movement")
        definitions: dict[str, BehaviorDefinition] = {}
        for definition in self._bundled_definitions():
            definitions[definition.name] = definition
        for definition in self._user_definitions():
            if definition.name in definitions:
                raise BehaviorAssetError(
                    f"user behavior '{definition.name}' conflicts with a bundled behavior"
                )
            definitions[definition.name] = definition
        return [
            definition
            for definition in sorted(definitions.values(), key=lambda item: item.name)
            if category == "all" or definition.category == category
        ]

    def load(self, name: str) -> BehaviorDefinition:
        """Load one behavior without accepting a caller-controlled path."""
        safe_name = self._validate_name(name)
        bundled = self._bundled_by_name(safe_name)
        if bundled is not None:
            return bundled
        path = self._confined_user_path(safe_name, require_exists=False)
        return self._load_path(path, expected_name=safe_name)

    def save_user(self, definition: BehaviorDefinition, *, overwrite: bool = False) -> Path:
        """Atomically save a validated user behavior without silent overwrite."""
        if self._bundled_by_name(definition.name) is not None:
            raise BehaviorAssetError("bundled behaviors are read-only and cannot be overridden")
        directory = self._ensure_user_directory()
        target = self._confined_user_path(definition.name, require_exists=False)
        if target.exists() and not overwrite:
            raise BehaviorAssetError(f"user behavior already exists: {definition.name}")
        payload = definition.model_dump_json(indent=2) + "\n"
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{definition.name}-",
            suffix=".tmp",
            dir=directory,
            text=True,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(file_descriptor, 0o600)
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if overwrite:
                os.replace(temporary, target)
            else:
                try:
                    os.link(temporary, target)
                except FileExistsError as exc:
                    raise BehaviorAssetError(
                        f"user behavior already exists: {definition.name}"
                    ) from exc
                temporary.unlink()
            target.chmod(0o600)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return target

    def delete_user(self, name: str) -> None:
        """Delete one user asset; bundled assets can never be deleted."""
        safe_name = self._validate_name(name)
        if self._bundled_by_name(safe_name) is not None:
            raise BehaviorAssetError("bundled behaviors are read-only and cannot be deleted")
        path = self._confined_user_path(safe_name, require_exists=True)
        path.unlink()

    def _bundled_definitions(self) -> Iterable[BehaviorDefinition]:
        assets = files("ninjarobot_pi5_ide").joinpath("behavior_assets")
        for asset in sorted(assets.iterdir(), key=lambda item: item.name):
            if asset.name.endswith(".json"):
                yield self._parse(asset.read_text(encoding="utf-8"), source=asset.name)

    def _bundled_by_name(self, name: str) -> BehaviorDefinition | None:
        assets = files("ninjarobot_pi5_ide").joinpath("behavior_assets")
        asset = assets.joinpath(f"{name}.json")
        if not asset.is_file():
            return None
        definition = self._parse(asset.read_text(encoding="utf-8"), source=asset.name)
        if definition.name != name:
            raise BehaviorAssetError(f"bundled filename does not match behavior name: {name}")
        return definition

    def _user_definitions(self) -> Iterable[BehaviorDefinition]:
        if not self._user_directory.exists():
            return
        directory = self._ensure_user_directory()
        for path in sorted(directory.glob("*.json")):
            if path.is_symlink():
                raise BehaviorAssetError(f"user behavior must not be a symbolic link: {path.name}")
            yield self._load_path(path, expected_name=path.stem)

    def _load_path(self, path: Path, *, expected_name: str) -> BehaviorDefinition:
        if path.is_symlink():
            raise BehaviorAssetError(f"user behavior must not be a symbolic link: {path.name}")
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise BehaviorAssetError(f"unable to read behavior {expected_name}: {exc}") from exc
        definition = self._parse(source, source=str(path))
        if definition.name != expected_name:
            raise BehaviorAssetError(
                f"behavior filename '{expected_name}' does not match payload name "
                f"'{definition.name}'"
            )
        return definition

    def _ensure_user_directory(self) -> Path:
        self._user_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self._user_directory.is_symlink():
            raise BehaviorAssetError("user behavior directory must not be a symbolic link")
        directory = self._user_directory.resolve(strict=True)
        if not directory.is_dir():
            raise BehaviorAssetError("user behavior location must be a directory")
        directory.chmod(0o700)
        return directory

    def _confined_user_path(self, name: str, *, require_exists: bool) -> Path:
        directory = self._ensure_user_directory()
        path = directory / f"{name}.json"
        resolved = path.resolve(strict=require_exists)
        try:
            resolved.relative_to(directory)
        except ValueError as exc:
            raise BehaviorAssetError("behavior path escapes the user behavior directory") from exc
        return resolved

    @staticmethod
    def _validate_name(name: str) -> str:
        try:
            return _BEHAVIOR_NAME_ADAPTER.validate_python(name, strict=True)
        except ValidationError as exc:
            raise BehaviorAssetError(
                "behavior name must start with a lowercase letter and contain only "
                "lowercase letters, numbers, underscores, or hyphens"
            ) from exc

    @staticmethod
    def _parse(payload_text: str, *, source: str) -> BehaviorDefinition:
        try:
            payload = json.loads(payload_text)
            return BehaviorDefinition.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise BehaviorAssetError(f"invalid behavior asset {source}: {exc}") from exc
