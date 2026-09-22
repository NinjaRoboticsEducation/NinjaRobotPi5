from __future__ import annotations

import argparse
import asyncio
import json
import stat
from collections import deque
from pathlib import Path

import pytest

from ninjarobot_pi5_agent import setup_wizard


class _Console:
    def __init__(self, answers: tuple[str, ...] = ()) -> None:
        self.answers = deque(answers)
        self.messages: list[str] = []

    def write(self, message: str = "") -> None:
        self.messages.append(message)

    def ask(self, _prompt: str) -> str:
        return self.answers.popleft()

    def secret(self, _prompt: str) -> str:
        return self.answers.popleft()


def _arguments(tmp_path: Path, **updates: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "onboard_status": False,
        "onboard_dry_run": False,
        "onboard_simulation": False,
        "onboard_step": None,
        "config": tmp_path / "config.toml",
        "secret_file": tmp_path / "secrets.env",
        "mcp_config": tmp_path / "mcp.toml",
    }
    values.update(updates)
    return argparse.Namespace(**values)


def test_dry_run_is_read_only_and_explains_every_setup_area(tmp_path) -> None:
    progress = tmp_path / "missing" / "progress.json"
    console = _Console()

    outcome = asyncio.run(
        setup_wizard.run_setup_wizard(
            _arguments(tmp_path, onboard_dry_run=True), console=console, progress_path=progress
        )
    )

    assert outcome.launch_mode is None
    assert not progress.parent.exists()
    rendered = "\n".join(console.messages)
    assert "buzzer (required)" in rendered
    assert "AI provider; external MCP tools" in rendered


def test_simulation_records_rehearsal_without_real_configuration(tmp_path) -> None:
    progress = tmp_path / "state" / "progress.json"
    console = _Console()

    asyncio.run(
        setup_wizard.run_setup_wizard(
            _arguments(tmp_path, onboard_simulation=True),
            console=console,
            progress_path=progress,
        )
    )

    payload = json.loads(progress.read_text(encoding="utf-8"))
    assert payload["steps"]["servo"]["verification"] == "simulated"
    assert payload["steps"]["mcp"]["detail"] == "offline_rehearsal"
    assert not Path(_arguments(tmp_path).config).exists()
    assert stat.S_IMODE(progress.stat().st_mode) == 0o600


def test_required_hardware_step_enforces_motion_confirmation(monkeypatch, tmp_path) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        setup_wizard,
        "hardware_setup_status",
        lambda _component: {"configuration_saved": True},
    )
    monkeypatch.setattr(
        setup_wizard,
        "run_hardware_setup",
        lambda component: opened.append(component) or 0,
    )
    console = _Console(("o", "not ready"))

    result = setup_wizard._hardware_step(console, "servo", index=4, total=5)

    assert result == ("needs_attention", "unverified", "confirmation_not_given")
    assert opened == []
    assert "raise both wheels" in "\n".join(console.messages).lower()


def test_multiple_mcp_selection_is_ordered_unique_and_validated() -> None:
    assert setup_wizard._parse_multiple_choices("3, 1, 3", maximum=3) == (3, 1)
    with pytest.raises(ValueError, match="1 through 3"):
        setup_wizard._parse_multiple_choices("4", maximum=3)


def test_progress_store_rejects_future_schema_without_overwriting(tmp_path) -> None:
    path = tmp_path / "state" / "progress.json"
    path.parent.mkdir()
    original = '{"schema_version": 999, "future": true}\n'
    path.write_text(original, encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(ValueError, match="unsupported setup progress"):
        with setup_wizard.ProgressStore(path) as store:
            store.load()

    assert path.read_text(encoding="utf-8") == original


def test_progress_store_prevents_two_wizards(tmp_path) -> None:
    path = tmp_path / "state" / "progress.json"

    with setup_wizard.ProgressStore(path):
        with pytest.raises(ValueError, match="another onboarding process"):
            with setup_wizard.ProgressStore(path):
                pass


def test_resume_reuses_only_completed_step_with_existing_configuration(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "state" / "progress.json"
    progress = setup_wizard.SetupProgress(
        steps={
            "buzzer": setup_wizard.StepRecord(
                status="complete",
                verification="operator_verified",
                detail="operator_confirmed",
            )
        }
    )
    with setup_wizard.ProgressStore(path) as store:
        store.save(progress)
    monkeypatch.setattr(
        setup_wizard,
        "hardware_setup_status",
        lambda _component: {"configuration_saved": True},
    )
    monkeypatch.setattr(
        setup_wizard,
        "_hardware_step",
        lambda *_args, **_kwargs: pytest.fail("completed setup should have been reused"),
    )
    console = _Console()

    asyncio.run(
        setup_wizard.run_setup_wizard(
            _arguments(tmp_path, resume=True, onboard_step="buzzer"),
            console=console,
            progress_path=path,
        )
    )

    assert "saved verification still present" in "\n".join(console.messages)
