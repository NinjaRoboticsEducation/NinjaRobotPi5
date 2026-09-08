from __future__ import annotations

import asyncio
from pathlib import Path

import ninjarobot_pi5_ide.engine as engine_module
import pytest
from ninjarobot_pi5_ide.hardware_ownership import HardwareOwnership, HardwareOwnershipError
from ninjarobot_pi5_ide.registry import CapabilityRegistry

from ninjarobot_pi5_agent import cli

EXAMPLE = Path(__file__).resolve().parents[2] / "config/ninjarobot_pi5.toml.example"


@pytest.mark.parametrize(
    "device", ["distance", "buzzer", "display", "servo", "camera", "microphone"]
)
def test_all_real_legacy_builders_reject_competing_owner_before_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    device: str,
) -> None:
    lock = tmp_path / "owner.lock"
    owner = HardwareOwnership(lock)
    monkeypatch.setattr(engine_module, "HardwareOwnership", lambda: HardwareOwnership(lock))

    async def forbidden(_self) -> None:
        pytest.fail("hardware registry started before ownership was acquired")

    monkeypatch.setattr(CapabilityRegistry, "start", forbidden)

    async def exercise() -> None:
        owner.acquire()
        engine = getattr(cli, f"_build_{device}_engine")(
            real=True,
            config_path=str(EXAMPLE),
            ledger_path=str(tmp_path / "actions.sqlite3"),
        )
        try:
            with pytest.raises(HardwareOwnershipError, match="already owned"):
                await engine.start()
        finally:
            await engine.close()
            assert owner.owned
            owner.release()

    asyncio.run(exercise())
