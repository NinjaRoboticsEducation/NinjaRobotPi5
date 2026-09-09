"""Preview or explicitly download the pinned English Piper voice; never run audio."""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import time
import urllib.request
from pathlib import Path

REVISION = "1162a9173d0ce503555aed757976b7a9912eae4c"
BASE = f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/en/en_US/ljspeech/high"
FILES = {
    "en_US-ljspeech-high.onnx": (
        114199011,
        "5d4f08ba6a2a48c44592eed3ce56bf85e9de3dd4e20df90541ae68a8310c029a",
    ),
    "en_US-ljspeech-high.onnx.json": (
        4970,
        "7e1f4634af596d83cca997fb7a931ba80b70f8a316a2655ee69c55365e0ace14",
    ),
    "MODEL_CARD": (513, "289f7421072d689a3d91f6c632f486af46f9b8b04417536104a4ea667b8a394b"),
}


def matches(path: Path, size: int, digest: str) -> bool:
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
        return False
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest() == digest


def prepare(destination: Path, *, apply: bool = False) -> None:
    """Keep existing files; publish each verified download without overwriting."""
    print(f"English voice: en_US-ljspeech-high (114 MB); destination: {destination}")
    print(f"Source revision: {REVISION}; dataset: public domain; retain MODEL_CARD.")
    print("No package installation, robot configuration, pairing, service start or playback.")
    for name, (size, digest) in FILES.items():
        target = destination / name
        if target.exists() or target.is_symlink():
            if not matches(target, size, digest):
                raise ValueError(f"Preserving different existing file: {target}")
    if not apply:
        print("Preview only. Add --apply to download missing files and verify SHA-256 hashes.")
        return
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, (size, digest) in FILES.items():
        target = destination / name
        if matches(target, size, digest):
            print(f"Verified existing {name}")
            continue
        # Stage on the same filesystem. Link publishes atomically and refuses overwrite.
        with tempfile.TemporaryDirectory(prefix=".speech-download-", dir=destination) as temporary:
            staged = Path(temporary) / name
            deadline = time.monotonic() + 180
            with urllib.request.urlopen(f"{BASE}/{name}", timeout=20) as response:
                if not response.geturl().startswith("https://"):
                    raise ValueError("Refusing insecure download redirect")
                total = 0
                with staged.open("wb") as output:
                    while chunk := response.read(65536):
                        total += len(chunk)
                        if total > size or time.monotonic() > deadline:
                            raise ValueError("Voice download exceeded size or time limit")
                        output.write(chunk)
            if not matches(staged, size, digest):
                raise ValueError(f"Voice hash verification failed: {name}")
            try:
                os.link(staged, target)
            except FileExistsError:
                if not matches(target, size, digest):
                    raise ValueError(f"Preserving concurrently created file: {target}") from None
        print(f"Verified {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination", type=Path, default=Path("~/.local/share/ninjarobot_pi5/voices/en")
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Download the explicitly selected 114 MB English voice.",
    )
    args = parser.parse_args()
    prepare(args.destination.expanduser(), apply=args.apply)


if __name__ == "__main__":
    main()
