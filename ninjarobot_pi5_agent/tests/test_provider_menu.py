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


def test_gemini_menu_requires_client_json_and_calls_native_login(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client_file = tmp_path / "client.json"
    _input_sequence(monkeypatch, ["3", "1", str(client_file)])
    called: dict[str, object] = {}

    async def login(
        config_path: Path,
        provider_id: str,
        *,
        secret_file: Path,
        client_id_file: Path | None,
    ) -> None:
        called.update(
            config_path=config_path,
            provider_id=provider_id,
            secret_file=secret_file,
            client_id_file=client_id_file,
        )

    async def no_models(
        _arguments: argparse.Namespace,
        *,
        provider: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        assert provider == "gemini"
        return ()

    monkeypatch.setattr(agent_cli, "web_login", login)
    monkeypatch.setattr(agent_cli, "_available_models", no_models)

    asyncio.run(agent_cli._interactive_model_selection(_arguments(tmp_path)))

    assert called["provider_id"] == "gemini"
    assert called["client_id_file"] == client_file
    assert called["secret_file"] == tmp_path / "secrets.env"
    output = capsys.readouterr().out
    assert "Google Desktop OAuth client JSON path" not in output
    assert "No compatible gemini models are available." in output


def test_gemini_menu_explains_missing_client_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _input_sequence(monkeypatch, ["3", "1", ""])

    asyncio.run(agent_cli._interactive_model_selection(_arguments(tmp_path)))

    assert "Gemini Web Login requires a Desktop OAuth client JSON file." in capsys.readouterr().out
