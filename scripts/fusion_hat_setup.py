"""Reviewed Fusion driver preparation and explicit installation; never operates actuators.

Run check first, then prepare a local source directory, then preview installation.
Only install --apply changes system files. Reboot is always an operator action.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[1] / "vendor/fusion-hat"
STATE = Path("/var/lib/ninjarobot-fusion")
BOOT = Path("/boot/firmware/config.txt")
RULES = Path("/etc/udev/rules.d/70-ninjarobot-fusion.rules")
LOCK_CONF = Path("/etc/tmpfiles.d/ninjarobot-fusion.conf")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest() -> dict:
    return json.loads((VENDOR / "manifest.json").read_text())


def verify_source(source: Path) -> None:
    for name, expected in manifest()["build_files"].items():
        path = source / name
        if path.is_symlink() or digest(path.read_bytes()) != expected:
            raise ValueError(f"Unreviewed build input: {name}")


def prepare(destination: Path) -> None:
    spec = manifest()
    if destination.exists():
        verify_source(destination)
        print("Prepared source already verified; unchanged.")
        return
    url = f"https://codeload.github.com/sunfounder/fusion-hat/tar.gz/{spec['revision']}"
    with urllib.request.urlopen(url, timeout=30) as response:
        archive = response.read(30_000_001)
    if len(archive) > 30_000_000 or digest(archive) != spec["archive_sha256"]:
        raise ValueError("Vendor archive checksum mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as work:
        source = Path(work) / "source"
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            for item in tar:
                parts = Path(item.name).parts[1:]
                if not parts or ".." in parts or item.name.startswith("/"):
                    continue
                if item.isfile() and (parts[0] == "driver" or parts == ("LICENSE",)):
                    target = source.joinpath(*parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    stream = tar.extractfile(item)
                    assert stream is not None
                    target.write_bytes(stream.read())
        for patch in spec["patches"]:
            data = (VENDOR / patch["path"]).read_bytes()
            if digest(data) != patch["sha256"]:
                raise ValueError("Patch checksum mismatch")
            subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1"],
                input=data,
                cwd=source,
                check=True,
                timeout=30,
            )
        verify_source(source)
        source.rename(destination)
    print(f"Verified patched source: {destination}")


def install_paths(kernel: str) -> list[Path]:
    return [
        Path(f"/lib/modules/{kernel}/updates/ninjarobot/fusion_hat.ko"),
        Path("/boot/firmware/overlays/sunfounder-fusionhat.dtbo"),
        BOOT,
        RULES,
        LOCK_CONF,
    ]


def preview() -> dict:
    kernel = platform.release()
    return {
        "driver_version": manifest()["driver_version"],
        "kernel": kernel,
        "headers_ready": Path(f"/lib/modules/{kernel}/build/Makefile").is_file(),
        "tools": {name: bool(shutil.which(name)) for name in ("make", "cc", "dtc", "patch")},
        "files": [str(p) for p in install_paths(kernel)],
        "group": "gpio (existing membership required)",
        "reboot_required": True,
        "loads_module": False,
        "changes_audio_defaults": False,
        "installs_packages": False,
    }


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install(source: Path, *, apply: bool) -> None:
    print(json.dumps(preview(), indent=2))
    verify_source(source)
    if not apply:
        return
    if os.geteuid() != 0:
        raise PermissionError("Explicit installation requires root; preview needs no privilege")
    if STATE.exists():
        raise RuntimeError("An installation record exists; use check/rollback before replacement")
    kernel = platform.release()
    headers = Path(f"/lib/modules/{kernel}/build")
    if not (headers / "Makefile").is_file() or not shutil.which("dtc"):
        raise RuntimeError("Install matching kernel headers and device-tree-compiler first")
    boot = BOOT.read_bytes()
    if any(token in boot.decode() for token in ("dtoverlay=hifiberry", "dtoverlay=googlevoicehat")):
        raise RuntimeError(
            "Existing sound overlay needs explicit review before Fusion installation"
        )
    if Path("/sys/class/fusion_hat").exists():
        raise RuntimeError("Driver is loaded; stop robot and schedule offline replacement first")
    with tempfile.TemporaryDirectory(prefix="ninja-fusion-build-") as directory:
        work = Path(directory)
        for name in manifest()["build_files"]:
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((source / name).read_bytes())
        verify_source(work)
        driver = work / "driver"
        # Do not invoke vendor all/install targets (they can install packages).
        subprocess.run(
            ["make", "-C", str(headers), f"M={driver}", "modules"],
            cwd=driver,
            check=True,
            timeout=300,
        )
        subprocess.run(
            [
                "dtc",
                "-@",
                "-I",
                "dts",
                "-O",
                "dtb",
                "-o",
                str(driver / "hat.dtbo"),
                str(driver / "sunfounder-fusionhat-overlay.dts"),
            ],
            check=True,
            timeout=30,
        )
        marker = b"\n# NinjaRobot reviewed Fusion driver\n[all]\ndtoverlay=sunfounder-fusionhat\n"
        contents = [
            (driver / "fusion_hat.ko").read_bytes(),
            (driver / "hat.dtbo").read_bytes(),
            boot if b"dtoverlay=sunfounder-fusionhat" in boot else boot + marker,
            b"",
            b"f /run/lock/ninjarobot-fusion.lock 0660 root gpio -\n",
        ]
        # Kernel attributes appear after binding. Restrict them to the existing gpio group.
        contents[3] = (
            'ACTION=="change", SUBSYSTEM=="fusion_hat", '
            'RUN+="/bin/chgrp -R gpio /sys%p/pwm", '
            'RUN+="/bin/chgrp gpio /sys%p/speaker"\n'
        ).encode()
        STATE.mkdir(mode=0o700)
        records = []
        for index, (path, content) in enumerate(zip(install_paths(kernel), contents)):
            previous = path.read_bytes() if path.exists() else None
            if previous is not None:
                (STATE / str(index)).write_bytes(previous)
            records.append(
                {
                    "path": str(path),
                    "backup": str(index) if previous is not None else None,
                    "installed_hash": digest(content),
                    "mode": path.stat().st_mode & 0o777 if path.exists() else 0o644,
                    "uid": path.stat().st_uid if path.exists() else 0,
                    "gid": path.stat().st_gid if path.exists() else 0,
                    "backup_hash": digest(previous) if previous is not None else None,
                }
            )
        (STATE / "transaction.json").write_text(json.dumps({"kernel": kernel, "files": records}))
        for path, content in zip(install_paths(kernel), contents):
            _write(path, content)
        subprocess.run(["depmod", "-a", kernel], check=True, timeout=60)
    print("Installed without loading. Reboot manually, then run check. Rollback record saved.")


def rollback(*, apply: bool) -> None:
    record = json.loads((STATE / "transaction.json").read_text())
    for item in record["files"]:
        path = Path(item["path"])
        print(f"Restore {path}")
        if item["backup"] is not None and item.get("backup_hash") is not None:
            if digest((STATE / item["backup"]).read_bytes()) != item["backup_hash"]:
                raise RuntimeError("Installation backup changed; manual review required")
        # Refuse to overwrite later user edits. A partially applied transaction is also safe.
        if path.exists() and digest(path.read_bytes()) != item["installed_hash"]:
            backup = STATE / item["backup"] if item["backup"] else None
            if backup is None or path.read_bytes() != backup.read_bytes():
                raise RuntimeError(f"Changed since installation; manual review required: {path}")
    if not apply:
        return
    if os.geteuid() != 0:
        raise PermissionError("Rollback requires root")
    if Path("/sys/class/fusion_hat").exists():
        raise RuntimeError("Driver is loaded; schedule offline rollback before changing files")
    for item in record["files"]:
        path = Path(item["path"])
        if item["backup"] is None:
            path.unlink(missing_ok=True)
        else:
            _write(path, (STATE / item["backup"]).read_bytes())
            path.chmod(item["mode"])
            os.chown(path, item.get("uid", 0), item.get("gid", 0))
    subprocess.run(["depmod", "-a", record["kernel"]], check=True, timeout=60)
    shutil.rmtree(STATE)
    print("Rollback complete; no module was loaded or unloaded.")


def check() -> dict:
    """Inspect prerequisites without enabling PWM, speaker or recording."""
    result = preview()
    root = Path("/sys/class/fusion_hat/fusion_hat")
    version = root / "version"
    result["installed_version"] = version.read_text().strip() if version.exists() else None
    attributes = [
        root / "pwm" / f"pwm{channel}" / name
        for channel in range(12)
        for name in ("period", "duty_cycle", "enable")
    ]
    result["pwm_interfaces_ready"] = all(path.is_file() for path in attributes)
    result["pwm_permissions_ready"] = all(os.access(path, os.W_OK) for path in attributes)
    result["speaker_ready"] = os.access(root / "speaker", os.W_OK)
    result["session_lock_ready"] = os.access("/run/lock/ninjarobot-fusion.lock", os.R_OK | os.W_OK)
    cards = Path("/proc/asound/cards")
    result["sound_card_ready"] = cards.exists() and any(
        token in cards.read_text().lower() for token in ("googlevoicehat", "sndrpigooglevoi")
    )
    try:
        voltage = int(Path("/sys/class/power_supply/fusion-hat/voltage_now").read_text())
        result["battery_readable"] = 500_000 < voltage <= 15_000_000
    except (OSError, ValueError):
        result["battery_readable"] = False
    result["ready"] = result["installed_version"] == manifest()["driver_version"] and all(
        result[key]
        for key in (
            "pwm_interfaces_ready",
            "pwm_permissions_ready",
            "speaker_ready",
            "session_lock_ready",
            "sound_card_ready",
            "battery_readable",
        )
    )
    result["qualification"] = "Read-only prerequisites only; physical acceptance remains manual"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "prepare", "install", "rollback"))
    parser.add_argument("--source", type=Path, default=Path("/tmp/ninjarobot-fusion-source"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.source.absolute())
    elif args.action == "install":
        install(args.source, apply=args.apply)
    elif args.action == "rollback":
        rollback(apply=args.apply)
    else:
        print(json.dumps(check(), indent=2))


if __name__ == "__main__":
    main()
