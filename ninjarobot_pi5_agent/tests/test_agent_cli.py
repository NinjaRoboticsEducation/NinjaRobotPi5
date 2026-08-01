from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from ninjarobot_pi5_agent.agent_cli import main
from ninjarobot_pi5_agent.mcp_config import load_mcp_configuration
from ninjarobot_pi5_agent.models import ProviderHealth, ProviderHealthStatus
from ninjarobot_pi5_agent.ollama import OllamaModelInfo, OllamaProvider
from ninjarobot_pi5_agent.secrets import SecretStore
from ninjarobot_pi5_ide.config_import import default_robot_config, save_robot_config

from ninjarobot_pi5_agent import agent_cli
from ninjarobot_pi5_ide import load_robot_config

from .test_skills import write_skill


def run_cli(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(arguments)
    assert exit_info.value.code == 0


def test_chat_resume_requires_confirmation_and_bypasses_the_model(
    monkeypatch,
    capsys,
) -> None:
    inputs = iter(("/help", "/resume", "RESUME", "/exit"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    service_request = AsyncMock(return_value=0)
    monkeypatch.setattr(agent_cli, "_service_request", service_request)

    result = asyncio.run(
        agent_cli._chat_repl(  # noqa: SLF001
            SimpleNamespace(),
            session_id="local-cli",
        )
    )

    assert result == 0
    service_request.assert_awaited_once_with(
        SimpleNamespace(),
        {
            "command": "resume_system",
            "session_id": "local-cli",
            "confirmed": True,
        },
    )
    output = capsys.readouterr().out
    assert "/resume" in output
    assert "Idle restored" in output
    assert "AI motion remains disarmed" in output


def test_chat_resume_cancellation_sends_no_service_request(monkeypatch, capsys) -> None:
    inputs = iter(("/resume", "NO", "/exit"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    service_request = AsyncMock(return_value=0)
    monkeypatch.setattr(agent_cli, "_service_request", service_request)

    result = asyncio.run(
        agent_cli._chat_repl(  # noqa: SLF001
            SimpleNamespace(),
            session_id="local-cli",
        )
    )

    assert result == 0
    service_request.assert_not_awaited()
    assert "System resume was cancelled." in capsys.readouterr().out


def test_chat_camera_grants_one_temporary_capture(monkeypatch, capsys) -> None:
    inputs = iter(("/camera", "/exit"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    service_request = AsyncMock(return_value=0)
    monkeypatch.setattr(agent_cli, "_service_request", service_request)

    result = asyncio.run(
        agent_cli._chat_repl(  # noqa: SLF001
            SimpleNamespace(),
            session_id="local-cli",
        )
    )

    assert result == 0
    service_request.assert_awaited_once_with(
        SimpleNamespace(),
        {
            "command": "grant_camera",
            "session_id": "local-cli",
            "confirmed": True,
        },
    )
    output = capsys.readouterr().out
    assert "one temporary photo" in output
    assert "failed capture keeps the grant" in output
    assert "use /camera again" in output


def test_agent_cli_manages_tavily_configuration(tmp_path, capsys) -> None:
    config = tmp_path / "mcp.toml"
    secrets = tmp_path / "secrets.env"
    common = ["--mcp-config", str(config), "--secret-file", str(secrets)]

    run_cli([*common, "mcp", "add", "--preset", "tavily", "--id", "search"])
    added = json.loads(capsys.readouterr().out)
    assert added["added"]["id"] == "search"
    assert added["added"]["token_environment"] == "TAVILY_API_KEY"

    run_cli([*common, "mcp", "disable", "search"])
    capsys.readouterr()
    assert not load_mcp_configuration(config).servers[0].enabled

    run_cli([*common, "mcp", "enable", "search"])
    capsys.readouterr()
    assert load_mcp_configuration(config).servers[0].enabled

    run_cli([*common, "mcp", "list"])
    listed = json.loads(capsys.readouterr().out)
    assert listed["servers"][0]["allowed_tools"] == ["tavily_search"]

    run_cli([*common, "mcp", "remove", "search", "--confirm"])
    capsys.readouterr()
    assert load_mcp_configuration(config).servers == ()


def test_agent_cli_secret_prompt_never_prints_value(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    config = tmp_path / "mcp.toml"
    secrets = tmp_path / "secrets.env"
    responses = iter(("private-api-key", "private-api-key"))
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(responses))

    run_cli(
        [
            "--mcp-config",
            str(config),
            "--secret-file",
            str(secrets),
            "secret",
            "set",
            "TAVILY_API_KEY",
        ]
    )

    output = capsys.readouterr().out
    assert "private-api-key" not in output
    assert SecretStore(secrets).get("TAVILY_API_KEY") == "private-api-key"


def test_agent_cli_validates_installs_simulates_and_removes_skill(
    tmp_path,
    capsys,
) -> None:
    source = write_skill(tmp_path / "source")
    skill_directory = tmp_path / "installed"
    common = ["--skill-dir", str(skill_directory)]

    run_cli([*common, "skill", "validate", str(source)])
    validated = json.loads(capsys.readouterr().out)
    assert validated == {"skill": "test-skill", "valid": True}

    run_cli([*common, "skill", "simulate-path", str(source), "--input", "{}"])
    preview = json.loads(capsys.readouterr().out)
    assert preview["simulation_only"] is True

    run_cli([*common, "skill", "install", str(source)])
    capsys.readouterr()
    run_cli([*common, "skill", "simulate", "test-skill", "--input", "{}"])
    installed_preview = json.loads(capsys.readouterr().out)
    assert installed_preview["skill"] == "test-skill"

    run_cli([*common, "skill", "remove", "test-skill", "--confirm"])
    capsys.readouterr()
    assert not (skill_directory / "test-skill").exists()


def test_agent_cli_exports_only_public_browser_trust_certificate(
    tmp_path,
    capsys,
) -> None:
    certificate = tmp_path / "tls" / "agent-cert.pem"
    key = tmp_path / "tls" / "agent-key.pem"
    exported = tmp_path / "phone" / "ninjarobot-ca.pem"

    run_cli(
        [
            "--web-certificate",
            str(certificate),
            "--web-key",
            str(key),
            "web",
            "export-ca",
            "--output",
            str(exported),
        ]
    )

    result = json.loads(capsys.readouterr().out)
    assert result["exported"] == str(exported)
    assert result["contains_private_key"] is False
    assert "BEGIN CERTIFICATE" in exported.read_text(encoding="ascii")
    assert "PRIVATE KEY" not in exported.read_text(encoding="ascii")


def test_agent_cli_lists_and_persists_an_offline_ollama_selection(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    config = tmp_path / "config.toml"
    save_robot_config(default_robot_config(), config, overwrite=False)

    async def list_models(_provider: OllamaProvider) -> tuple[OllamaModelInfo, ...]:
        return (
            OllamaModelInfo(
                name="qwen3:4b",
                size_bytes=2_600_000_000,
                parameter_size="4.0B",
                quantization="Q4_K_M",
            ),
            OllamaModelInfo(name="small:2b", size_bytes=1_200_000_000),
        )

    async def health(provider: OllamaProvider) -> ProviderHealth:
        return ProviderHealth(
            provider="ollama",
            status=ProviderHealthStatus.READY,
            checked_at=datetime.now(UTC),
            detail=f"{provider.config.model} is ready",
        )

    monkeypatch.setattr(OllamaProvider, "list_models", list_models)
    monkeypatch.setattr(OllamaProvider, "health", health)
    common = [
        "--config",
        str(config),
        "--service-socket",
        str(tmp_path / "missing.sock"),
        "--benchmark-dir",
        str(tmp_path / "reports"),
    ]

    run_cli([*common, "model", "list"])
    listed = json.loads(capsys.readouterr().out)
    assert [model["name"] for model in listed["models"]] == ["qwen3:4b", "small:2b"]

    run_cli([*common, "model", "select", "small:2b"])
    selected = json.loads(capsys.readouterr().out)
    assert selected["service_running"] is False
    assert load_robot_config(config).providers["ollama"].model == "small:2b"


def test_agent_cli_lists_cloud_capabilities_without_requiring_credentials(
    tmp_path,
    capsys,
) -> None:
    example = Path(__file__).resolve().parents[2] / "config" / "ninjarobot_pi5.toml.example"

    run_cli(
        [
            "--config",
            str(example),
            "--secret-file",
            str(tmp_path / "secrets.env"),
            "provider",
            "list",
        ]
    )

    listed = json.loads(capsys.readouterr().out)
    by_id = {provider["id"]: provider for provider in listed["providers"]}
    assert set(by_id) == {"ollama", "openai", "gemini", "anthropic"}
    assert all(provider["capabilities"]["native_tools"] for provider in by_id.values())
    assert all(provider["capabilities"]["streaming"] for provider in by_id.values())


def test_provider_login_compatibility_command_explains_api_key_migration(
    tmp_path,
    capsys,
) -> None:
    example = Path(__file__).resolve().parents[2] / "config" / "ninjarobot_pi5.toml.example"

    with pytest.raises(SystemExit) as exit_info:
        main(
            [
                "--config",
                str(example),
                "--secret-file",
                str(tmp_path / "secrets.env"),
                "provider",
                "login",
                "gemini",
            ]
        )

    assert exit_info.value.code == 2
    assert "provider set-api-key gemini" in capsys.readouterr().err
