"""Preview or explicitly download the pinned English Piper voice; never run audio."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REVISION = "1162a9173d0ce503555aed757976b7a9912eae4c"
BASE = f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/en/en_US/ljspeech/high"
DEFAULT_VOICE_DIR = Path("~/.local/share/ninjarobot_pi5/voices/en")
DEFAULT_SPEECH_VENV = Path("~/.local/share/ninjarobot_pi5/speech")
DEFAULT_CONFIG_PATH = Path("~/.config/ninjarobot_pi5/config.toml")
REQUIREMENTS_FILE = Path(__file__).resolve().parents[1] / "requirements" / "local-speech.txt"
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


def install_piper_venv(
    venv_dir: Path = DEFAULT_SPEECH_VENV,
    *,
    requirements_file: Path = REQUIREMENTS_FILE,
    apply: bool = False,
) -> Path:
    """Create the isolated Piper speech virtualenv and install pinned requirements."""
    resolved_venv = venv_dir.expanduser()
    python_bin = resolved_venv / "bin" / "python"
    print(f"Piper speech environment: {resolved_venv}; requirements: {requirements_file}")
    if not apply:
        print("Preview only. Add --apply with --install-piper to create the speech venv.")
        return python_bin
    resolved_venv.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not python_bin.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(resolved_venv)], check=True)
    subprocess.run(
        [
            str(python_bin),
            "-m",
            "pip",
            "install",
            "--require-hashes",
            "-r",
            str(requirements_file),
        ],
        check=True,
    )
    return python_bin


def configure_speech_model(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    destination: Path = DEFAULT_VOICE_DIR,
    venv_dir: Path = DEFAULT_SPEECH_VENV,
    apply: bool = False,
) -> None:
    """Persist speech_output.english_model and piper_python in config.toml when ready."""
    resolved_config = config_path.expanduser()
    resolved_dest = destination.expanduser()
    resolved_venv = venv_dir.expanduser()
    model_path = resolved_dest / "en_US-ljspeech-high.onnx"
    python_bin = resolved_venv / "bin" / "python"
    print(f"Speech configuration target: {resolved_config} -> {model_path}")
    if not apply:
        print("Preview only. Add --apply with --configure to update config.toml.")
        return
    from ninjarobot_pi5_ide.config import RobotConfig
    from ninjarobot_pi5_ide.config_import import load_effective_config, save_robot_config

    current = load_effective_config(resolved_config if resolved_config.exists() else None)
    payload = current.model_dump()
    payload["speech_output"]["english_model"] = str(model_path)
    payload["speech_output"]["piper_python"] = str(python_bin)
    if python_bin.is_file() and model_path.is_file():
        payload["speech_output"]["enabled"] = True
    updated = RobotConfig.model_validate(payload)
    save_robot_config(updated, resolved_config, overwrite=resolved_config.exists())


def prepare(
    destination: Path,
    *,
    apply: bool = False,
    install_piper: bool = False,
    configure: bool = False,
    venv_dir: Path = DEFAULT_SPEECH_VENV,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    """Keep existing files; publish each verified download without overwriting."""
    print(f"English voice: en_US-ljspeech-high (114 MB); destination: {destination}")
    print(f"Source revision: {REVISION}; dataset: public domain; retain MODEL_CARD.")
    if not install_piper and not configure:
        print("No package installation, robot configuration, pairing, service start or playback.")
    for name, (size, digest) in FILES.items():
        target = destination / name
        if target.exists() or target.is_symlink():
            if not matches(target, size, digest):
                raise ValueError(f"Preserving different existing file: {target}")
    if install_piper:
        install_piper_venv(venv_dir, apply=apply)
    if not apply:
        if configure:
            configure_speech_model(
                config_path,
                destination=destination,
                venv_dir=venv_dir,
                apply=False,
            )
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
    if configure:
        configure_speech_model(
            config_path,
            destination=destination,
            venv_dir=venv_dir,
            apply=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=DEFAULT_VOICE_DIR,
    )
    parser.add_argument(
        "--venv-dir",
        type=Path,
        default=DEFAULT_SPEECH_VENV,
        help="Target virtualenv directory when --install-piper is specified.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Robot config.toml path when --configure is specified.",
    )
    parser.add_argument(
        "--install-piper",
        action="store_true",
        help="Install pinned Piper TTS runtime into the speech virtualenv.",
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="Write speech_output.english_model and piper_python into config.toml.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Download the explicitly selected 114 MB English voice and apply requested flags.",
    )
    args = parser.parse_args()
    prepare(
        args.destination.expanduser(),
        apply=args.apply,
        install_piper=args.install_piper,
        configure=args.configure,
        venv_dir=args.venv_dir,
        config_path=args.config,
    )


if __name__ == "__main__":
    main()
