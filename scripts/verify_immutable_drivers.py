"""Verify copied Pi5 libraries against their import and repair manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "docs" / "validation" / "immutable_driver_baseline.json"
DEFAULT_AUTHORIZATIONS = ROOT / "docs" / "validation" / "authorized_driver_changes.json"
IMMUTABLE_DRIVERS = (
    "pi5buzzer",
    "pi5camera",
    "pi5disp",
    "pi5mic",
    "pi5servo",
    "pi5vl53l0x",
)
IGNORED_DIRECTORY_NAMES = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}
IGNORED_FILE_NAMES = {".coverage", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".swp", ".swo"}
RUNTIME_FILE_PATHS = {
    "pi5buzzer/buzzer.json",
    "pi5servo/servo.json",
    "pi5vl53l0x/src/pi5vl53l0x/config/vl53l0x.json",
}
RUNTIME_DIRECTORY_PREFIXES = (
    "pi5camera/camera_data/",
    "pi5camera/photo/",
)


def _is_generated(path: Path) -> bool:
    normalized_path = path.as_posix()
    return (
        any(part in IGNORED_DIRECTORY_NAMES for part in path.parts)
        or path.name in IGNORED_FILE_NAMES
        or path.suffix in IGNORED_SUFFIXES
        or normalized_path in RUNTIME_FILE_PATHS
        or normalized_path.startswith(RUNTIME_DIRECTORY_PREFIXES)
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect_manifest() -> dict[str, dict[str, str | int]]:
    manifest: dict[str, dict[str, str | int]] = {}
    for driver in IMMUTABLE_DRIVERS:
        driver_root = ROOT / driver
        if not driver_root.is_dir():
            raise FileNotFoundError(f"Missing immutable driver directory: {driver_root}")
        for path in sorted(driver_root.rglob("*")):
            relative_path = path.relative_to(ROOT)
            if path.is_file() and not _is_generated(relative_path):
                manifest[relative_path.as_posix()] = {
                    "sha256": _sha256(path),
                    "size": path.stat().st_size,
                }
    return manifest


def write_baseline(path: Path) -> None:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "source": {
            "repository": "https://github.com/Nilcreator/NinjaClawBot.git",
            "branch": "clawbotV3_01",
            "commit": "1aa6700d403dff65d2a53ad6fda9718b60723cb7",
        },
        "drivers": list(IMMUTABLE_DRIVERS),
        "files": collect_manifest(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote immutable-driver baseline: {path}")


def _load_authorizations(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "files": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("files"), dict):
        raise ValueError(f"Invalid authorized-driver-change manifest: {path}")
    return payload


def record_authorized_changes(
    baseline_path: Path,
    authorizations_path: Path,
    requested_paths: list[Path],
    *,
    reason: str,
    authorized_by: str,
    authorized_on: str,
) -> int:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["files"]
    actual = collect_manifest()
    payload = _load_authorizations(authorizations_path)

    for requested_path in requested_paths:
        absolute_path = (
            requested_path if requested_path.is_absolute() else ROOT / requested_path
        ).resolve()
        try:
            relative_path = absolute_path.relative_to(ROOT).as_posix()
        except ValueError:
            print(f"outside repository: {requested_path}")
            return 1
        if relative_path not in actual:
            print(f"not a current managed driver file: {relative_path}")
            return 1
        if Path(relative_path).parts[0] not in IMMUTABLE_DRIVERS:
            print(f"not inside a managed driver: {relative_path}")
            return 1
        baseline_state = baseline.get(relative_path)
        if actual[relative_path] == baseline_state:
            print(f"unchanged from import baseline: {relative_path}")
            return 1
        payload["files"][relative_path] = {
            "approved": actual[relative_path],
            "authorized_by": authorized_by,
            "authorized_on": authorized_on,
            "baseline": baseline_state,
            "reason": reason,
        }

    authorizations_path.parent.mkdir(parents=True, exist_ok=True)
    authorizations_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Recorded {len(requested_paths)} authorized driver repair(s) in {authorizations_path}.")
    return 0


def verify(path: Path, authorizations_path: Path = DEFAULT_AUTHORIZATIONS) -> int:
    expected = json.loads(path.read_text(encoding="utf-8"))
    expected_files = expected["files"]
    authorizations = _load_authorizations(authorizations_path)["files"]
    actual_files = collect_manifest()

    missing = sorted(set(expected_files) - set(actual_files))
    unexpected: list[str] = []
    invalid_authorizations: list[str] = []
    changed: list[str] = []
    for relative_path in sorted(actual_files):
        authorization = authorizations.get(relative_path)
        baseline_state = expected_files.get(relative_path)
        approved = baseline_state
        if authorization is not None:
            required_fields = {"baseline", "approved", "authorized_by", "authorized_on", "reason"}
            if (
                not isinstance(authorization, dict)
                or not required_fields <= authorization.keys()
                or authorization["baseline"] != baseline_state
                or not all(
                    isinstance(authorization[field], str) and authorization[field].strip()
                    for field in ("authorized_by", "authorized_on", "reason")
                )
            ):
                invalid_authorizations.append(relative_path)
                continue
            approved = authorization["approved"]
        elif relative_path not in expected_files:
            unexpected.append(relative_path)
            continue
        if approved != actual_files[relative_path]:
            changed.append(relative_path)

    invalid_authorizations.extend(sorted(set(authorizations) - set(actual_files)))

    if missing or unexpected or changed or invalid_authorizations:
        for label, paths in (
            ("missing", missing),
            ("unexpected", unexpected),
            ("changed", changed),
            ("invalid authorization", sorted(set(invalid_authorizations))),
        ):
            for relative_path in paths:
                print(f"{label}: {relative_path}")
        return 1

    print(
        f"PASS: {len(actual_files)} tracked files across {len(IMMUTABLE_DRIVERS)} "
        f"drivers match the import baseline plus {len(authorizations)} authorized repairs."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Path to the original imported-driver baseline JSON.",
    )
    parser.add_argument(
        "--authorizations",
        type=Path,
        default=DEFAULT_AUTHORIZATIONS,
        help="Path to the authorized driver-change manifest JSON.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Create or replace the baseline instead of verifying it.",
    )
    parser.add_argument(
        "--record-authorized",
        action="append",
        type=Path,
        default=[],
        metavar="PATH",
        help="Record the current hash of one explicitly authorized repaired file.",
    )
    parser.add_argument(
        "--reason",
        help="Required repair rationale when --record-authorized is used.",
    )
    parser.add_argument(
        "--authorized-by",
        default="project owner",
        help="Authorizer recorded with a repaired file.",
    )
    parser.add_argument(
        "--authorized-on",
        default=date.today().isoformat(),
        help="Authorization date in YYYY-MM-DD form.",
    )
    args = parser.parse_args()

    if args.write_baseline:
        write_baseline(args.baseline)
        return 0
    if args.record_authorized:
        if not args.reason or not args.reason.strip():
            parser.error("--reason is required with --record-authorized")
        return record_authorized_changes(
            args.baseline,
            args.authorizations,
            args.record_authorized,
            reason=args.reason,
            authorized_by=args.authorized_by,
            authorized_on=args.authorized_on,
        )
    return verify(args.baseline, args.authorizations)


if __name__ == "__main__":
    raise SystemExit(main())
