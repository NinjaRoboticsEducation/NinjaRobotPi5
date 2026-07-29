from __future__ import annotations

import json

import pytest
from ninjarobot_pi5_agent.agent_cli import main
from ninjarobot_pi5_agent.mcp_config import load_mcp_configuration
from ninjarobot_pi5_agent.secrets import SecretStore

from .test_skills import write_skill


def run_cli(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(arguments)
    assert exit_info.value.code == 0


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
    assert listed["servers"][0]["allowed_tools"] == ["tavily-search"]

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
