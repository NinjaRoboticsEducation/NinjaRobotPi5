from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when project configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    root: Path
    bundle_root: Path
    raw_root: Path
    catalog_root: Path
    derived_root: Path
    allowed_types: tuple[str, ...]
    required_profile_fields: tuple[str, ...]
    freshness: dict[str, str | None]
    max_source_bytes: int
    max_image_pixels: int
    max_image_width: int
    max_image_height: int
    ocr_timeout_seconds: int
    max_ocr_characters: int
    allowed_extensions: tuple[str, ...]
    query_max_results: int = 20
    settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, start: Path | str = ".") -> "Config":
        root = find_project_root(Path(start))
        path = root / "llmwiki.yaml"
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigError(f"Could not read {path}: {exc}") from exc
        if raw.get("version") != 1:
            raise ConfigError("llmwiki.yaml must contain version: 1")
        allowed_keys = {
            "version", "bundle_root", "raw_root", "catalog_root", "derived_root",
            "allowed_types", "required_profile_fields", "freshness", "source_limits",
            "lint", "query", "review", "semantic_review",
        }
        unknown = sorted(set(raw) - allowed_keys)
        if unknown:
            raise ConfigError(f"Unknown llmwiki.yaml setting(s): {', '.join(unknown)}")

        def project_path(key: str, default: str) -> Path:
            value = raw.get(key, default)
            if not isinstance(value, str) or not value:
                raise ConfigError(f"{key} must be a non-empty path string")
            candidate = Path(value)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ConfigError(f"{key} must stay inside the project")
            resolved = (root / candidate).resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise ConfigError(f"{key} resolves outside the project") from exc
            return resolved

        limits = raw.get("source_limits", {})
        query = raw.get("query", {})
        semantic = raw.get("semantic_review") or {}
        if not isinstance(semantic, dict):
            raise ConfigError("semantic_review must be a mapping")
        for key in ("enabled", "strict_for_sourced_pages", "flag_absolute_language", "require_visual_review"):
            if key in semantic and not isinstance(semantic[key], bool):
                raise ConfigError(f"semantic_review.{key} must be true or false")
        strict_statuses = semantic.get("strict_for_status", ["stable"])
        if (
            not isinstance(strict_statuses, list)
            or not strict_statuses
            or any(item not in {"draft", "stable", "deprecated"} for item in strict_statuses)
        ):
            raise ConfigError("semantic_review.strict_for_status must list draft, stable, or deprecated")
        allowed_extensions = tuple(str(item).lower() for item in limits.get("allowed_extensions", []))
        if not allowed_extensions:
            raise ConfigError("source_limits.allowed_extensions cannot be empty")
        if any(not item.startswith(".") for item in allowed_extensions):
            raise ConfigError("Every allowed source extension must start with a dot")
        allowed_types = tuple(raw.get("allowed_types", []))
        required_fields = tuple(raw.get("required_profile_fields", []))
        if any(not isinstance(item, str) or not item for item in (*allowed_types, *required_fields)):
            raise ConfigError("Page types and required profile fields must be non-empty strings")
        freshness = dict(raw.get("freshness", {}))
        if any(value is not None and (not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*[dwm]", value)) for value in freshness.values()):
            raise ConfigError("Freshness values must be null or a duration such as 30d, 2w, or 6m")
        max_bytes = int(limits.get("max_bytes", 52_428_800))
        if max_bytes < 1:
            raise ConfigError("source_limits.max_bytes must be positive")
        max_image_pixels = int(limits.get("max_image_pixels", 40_000_000))
        max_image_width = int(limits.get("max_image_width", 10_000))
        max_image_height = int(limits.get("max_image_height", 10_000))
        ocr_timeout_seconds = int(limits.get("ocr_timeout_seconds", 60))
        max_ocr_characters = int(limits.get("max_ocr_characters", 200_000))
        if min(max_image_pixels, max_image_width, max_image_height, ocr_timeout_seconds, max_ocr_characters) < 1:
            raise ConfigError("Image and OCR limits must be positive")
        config = cls(
            root=root,
            bundle_root=project_path("bundle_root", "wiki"),
            raw_root=project_path("raw_root", "raw"),
            catalog_root=project_path("catalog_root", "raw/_catalog"),
            derived_root=project_path("derived_root", "raw/_derived"),
            allowed_types=allowed_types,
            required_profile_fields=required_fields,
            freshness=freshness,
            max_source_bytes=max_bytes,
            max_image_pixels=max_image_pixels,
            max_image_width=max_image_width,
            max_image_height=max_image_height,
            ocr_timeout_seconds=ocr_timeout_seconds,
            max_ocr_characters=max_ocr_characters,
            allowed_extensions=allowed_extensions,
            query_max_results=int(query.get("max_results", 20)),
            settings=raw,
        )
        for name, child in (("catalog_root", config.catalog_root), ("derived_root", config.derived_root)):
            try:
                child.relative_to(config.raw_root)
            except ValueError as exc:
                raise ConfigError(f"{name} must be inside raw_root") from exc
        return config


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "llmwiki.yaml").is_file():
            return candidate
    raise ConfigError(f"No llmwiki.yaml found from {start}")
