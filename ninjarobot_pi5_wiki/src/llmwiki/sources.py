from __future__ import annotations

import json
import mimetypes
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .config import Config
from .paths import ensure_within, project_relative, sha256_file, slugify

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class SourceError(ValueError):
    """Raised when a source cannot be registered or validated."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_uri(value: str | None) -> None:
    if value is None:
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https", "urn"}:
        raise SourceError("Source URI must use https, http, or urn")


def _inspect_image(config: Config, source: Path) -> dict[str, Any]:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - installation contract
        raise SourceError("Image support requires Pillow; run 'uv sync --all-extras'") from exc

    expected = "PNG" if source.suffix.lower() == ".png" else "JPEG"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as image:
                actual = str(image.format or "").upper()
                width, height = image.size
                frames = int(getattr(image, "n_frames", 1))
                image.verify()
            with Image.open(source) as metadata_image:
                exif = metadata_image.getexif()
                contains_gps = bool(exif and 34853 in exif)
                sensitive_tags = {315, 33432, 40093, 42032, 42033, 42035}
                contains_sensitive = bool(exif and any(tag in exif for tag in sensitive_tags))
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise SourceError("Image exceeds the decoder's safe pixel limit") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise SourceError(f"Image cannot be decoded safely: {exc}") from exc
    if actual != expected:
        raise SourceError(f"Image extension says {expected}, but decoded format is {actual or 'unknown'}")
    if frames != 1:
        raise SourceError("Animated or multi-frame images are not supported")
    if width > config.max_image_width or height > config.max_image_height:
        raise SourceError(
            f"Image dimensions {width}x{height} exceed the configured "
            f"{config.max_image_width}x{config.max_image_height} limit"
        )
    if width * height > config.max_image_pixels:
        raise SourceError(f"Image has {width * height} pixels; limit is {config.max_image_pixels}")
    return {
        "format": actual,
        "width": width,
        "height": height,
        "frames": frames,
        "contains_gps_metadata": contains_gps,
        "contains_sensitive_metadata": contains_sensitive,
        "asset_status": "not-published",
    }


def _check_content_shape(config: Config, source: Path) -> dict[str, Any] | None:
    sample = source.read_bytes()[:8192]
    suffix = source.suffix.lower()
    if suffix == ".pdf" and not sample.startswith(b"%PDF-"):
        raise SourceError("File has a .pdf extension but does not contain a PDF header")
    if suffix in TEXT_EXTENSIONS and b"\x00" in sample:
        raise SourceError("Text source appears to contain binary data")
    if suffix in TEXT_EXTENSIONS:
        try:
            source.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise SourceError("Text source must use UTF-8 encoding") from exc
    if suffix in IMAGE_EXTENSIONS:
        return _inspect_image(config, source)
    return None


def load_record(config: Config, source_id: str) -> dict[str, Any]:
    path = config.catalog_root / f"{source_id}.yaml"
    if not path.is_file():
        raise SourceError(f"Unknown source ID: {source_id}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    validate_record(config, data)
    return data


def validate_record(config: Config, record: dict[str, Any]) -> None:
    schema = json.loads((config.root / "schemas/source-record.schema.json").read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(record),
        key=lambda item: list(item.path),
    )
    if errors:
        detail = "; ".join(error.message for error in errors)
        raise SourceError(f"Invalid source record: {detail}")


def rebuild_catalog_index(config: Config, catalog_root: Path | None = None) -> Path:
    catalog_root = catalog_root or config.catalog_root
    catalog_root.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(catalog_root.glob("src-*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        records.append(
            {
                "id": data.get("id"),
                "title": data.get("title"),
                "path": data.get("path"),
                "kind": data.get("kind"),
                "state": data.get("state"),
            }
        )
    content = {"version": 2, "generated_at": utc_now(), "sources": records}
    path = catalog_root / "index.yaml"
    path.write_text(yaml.safe_dump(content, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def save_record_to_catalog(config: Config, record: dict[str, Any], catalog_root: Path) -> Path:
    validate_record(config, record)
    catalog_root.mkdir(parents=True, exist_ok=True)
    path = catalog_root / f"{record['id']}.yaml"
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rebuild_catalog_index(config, catalog_root)
    return path


def save_record(config: Config, record: dict[str, Any]) -> Path:
    return save_record_to_catalog(config, record, config.catalog_root)


def add_source(
    config: Config,
    source: Path,
    *,
    title: str | None = None,
    original_uri: str | None = None,
    source_version: str | None = None,
) -> tuple[dict[str, Any], bool]:
    _validate_uri(original_uri)
    original = source.absolute()
    raw_absolute = config.raw_root.absolute()
    try:
        relative_parts = original.relative_to(raw_absolute).parts
    except ValueError:
        relative_parts = ()
    current = raw_absolute
    for part in relative_parts:
        current = current / part
        if current.is_symlink():
            raise SourceError("Symlinked source originals are not allowed")
    source = ensure_within(source, config.raw_root, must_exist=True)
    if not source.is_file():
        raise SourceError(f"Not a file: {source}")
    if source.parent in {config.catalog_root, config.derived_root} or config.catalog_root in source.parents or config.derived_root in source.parents:
        raise SourceError("Catalog and derived files cannot be registered as source originals")
    suffix = source.suffix.lower()
    if suffix not in config.allowed_extensions:
        raise SourceError(f"Unsupported source extension: {source.suffix or '<none>'}")
    media_root = (config.raw_root / "media").resolve()
    if suffix in IMAGE_EXTENSIONS and media_root not in source.parents:
        raise SourceError("Image originals must be placed under raw/media/")
    if source.stat().st_size > config.max_source_bytes:
        raise SourceError(f"Source exceeds {config.max_source_bytes} bytes")
    image_metadata = _check_content_shape(config, source)

    digest = sha256_file(source)
    relative = project_relative(source, config.root)
    for record in list_records(config):
        if record.get("path") == relative:
            if record.get("content_hash") == digest:
                return record, False
            record["state"] = "needs-review"
            record["previous_content_hash"] = record.get("content_hash")
            record["content_hash"] = digest
            record["changed_at"] = utc_now()
            record["normalized_at"] = None
            record["normalizer"] = None
            if image_metadata is not None:
                record["image"] = image_metadata
            save_record(config, record)
            return record, False

    base = f"src-{datetime.now(timezone.utc):%Y%m%d}-{slugify(source.stem)}"
    source_id = base
    counter = 2
    while (config.catalog_root / f"{source_id}.yaml").exists():
        source_id = f"{base}-{counter}"
        counter += 1
    media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    if suffix in {".md", ".markdown"}:
        media_type = "text/markdown"
    kind = "image" if suffix in IMAGE_EXTENSIONS else "document" if suffix == ".pdf" else "text"
    record: dict[str, Any] = {
        "id": source_id,
        "path": relative,
        "media_type": media_type,
        "kind": kind,
        "title": title or source.stem.replace("-", " ").replace("_", " ").strip().title(),
        "added_at": utc_now(),
        "content_hash": digest,
        "state": "pending",
        "original_uri": original_uri or f"urn:llmwiki:source:{source_id}",
        "source_version": source_version,
        "retrieved_at": utc_now() if original_uri else None,
        "normalized_at": None,
        "normalizer": None,
        "error": None,
    }
    if image_metadata is not None:
        record["image"] = image_metadata
    save_record(config, record)
    return record, True


def update_source(
    config: Config,
    source_id: str,
    *,
    title: str | None = None,
    original_uri: str | None = None,
    source_version: str | None = None,
) -> dict[str, Any]:
    if title is None and original_uri is None and source_version is None:
        raise SourceError("Provide at least one metadata field to update")
    _validate_uri(original_uri)
    record = load_record(config, source_id)
    if title is not None:
        if not title.strip():
            raise SourceError("Source title cannot be empty")
        record["title"] = title.strip()
    if original_uri is not None:
        record["original_uri"] = original_uri
    if source_version is not None:
        record["source_version"] = source_version
    record["metadata_updated_at"] = utc_now()
    save_record(config, record)
    return record


def list_records(config: Config) -> list[dict[str, Any]]:
    if not config.catalog_root.exists():
        return []
    records = []
    for path in sorted(config.catalog_root.glob("src-*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        validate_record(config, data)
        records.append(data)
    return records


def record_status(config: Config, record: dict[str, Any]) -> str:
    path = config.root / str(record["path"])
    if not path.is_file():
        return "missing"
    current = sha256_file(path)
    if current != record.get("content_hash"):
        return "needs-review"
    return str(record.get("state", "pending"))
