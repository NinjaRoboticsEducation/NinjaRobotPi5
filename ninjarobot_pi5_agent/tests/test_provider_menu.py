from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import pytest

from ninjarobot_pi5_agent import agent_cli

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"


def _arguments(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        config=EXAMPLE,
        secret_file=tmp_path / "secrets.env",
        benchmark_dir=tmp_path / "benchmarks",
    )


def _input_sequence(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str],
) -> None:
    answers = iter(responses)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))


def test_openai_menu_does_not_offer_web_login(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _input_sequence(monkeypatch, ["2", "0"])

    asyncio.run(agent_cli._interactive_model_selection(_arguments(tmp_path)))

    output = capsys.readouterr().out
    assert "Openai (openai)" in output
    assert "1. Enter API Key" in output
    assert "2. Continue with Current API Key" in output
    assert "Web Login" not in output


@pytest.mark.parametrize("provider_choice", ["2", "3", "4"])
def test_every_cloud_provider_menu_is_api_key_only(
    provider_choice: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _input_sequence(monkeypatch, [provider_choice, "0"])

    asyncio.run(agent_cli._interactive_model_selection(_arguments(tmp_path)))

    output = capsys.readouterr().out
    assert "1. Enter API Key" in output
    assert "2. Continue with Current API Key" in output
    assert "Web Login" not in output
