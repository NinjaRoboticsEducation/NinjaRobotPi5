from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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

ROOT = Path(__file__).resolve().parents[2]


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
    service_request.assert_any_await(
        SimpleNamespace(),
        {"command": "controller_connected", "interface": "terminal"},
        print_result=False,
    )
    service_request.assert_any_await(
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
    service_request.assert_awaited_once_with(
        SimpleNamespace(),
        {"command": "controller_connected", "interface": "terminal"},
        print_result=False,
    )
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
    service_request.assert_any_await(
        SimpleNamespace(),
        {"command": "controller_connected", "interface": "terminal"},
        print_result=False,
    )
    service_request.assert_any_await(
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


def test_chat_voice_commands_bypass_the_model_and_use_exact_service_commands(
    monkeypatch,
    capsys,
) -> None:
    inputs = iter(
        (
            "/voice input status",
            "/voice input on",
            "/voice input off",
            "/exit",
        )
    )
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
    assert [call.args[1] for call in service_request.await_args_list] == [
        {"command": "controller_connected", "interface": "terminal"},
        {"command": "voice_status"},
        {"command": "voice_enable"},
        {"command": "voice_disable"},
    ]
    assert "/voice input status" not in capsys.readouterr().err


def test_memory_cli_requires_confirmation_and_sends_bounded_settings(monkeypatch) -> None:
    service_request = AsyncMock(return_value=0)
    monkeypatch.setattr(agent_cli, "_service_request", service_request)
    parser = agent_cli.build_parser()

    delete_arguments = parser.parse_args(["memory", "delete", "user-1", "memory-1", "--confirm"])
    assert asyncio.run(agent_cli._run_memory_command(delete_arguments)) == 0  # noqa: SLF001
    service_request.assert_awaited_with(
        delete_arguments,
        {
            "command": "memory_delete",
            "user_id": "user-1",
            "memory_id": "memory-1",
            "confirmed": True,
        },
    )

    retention_arguments = parser.parse_args(
        ["memory", "set-retention", "--conversations", "14", "--failed", "90"]
    )
    assert asyncio.run(agent_cli._run_memory_command(retention_arguments)) == 0  # noqa: SLF001
    service_request.assert_awaited_with(
        retention_arguments,
        {
            "command": "memory_update_settings",
            "conversation_retention_days": 14,
            "failed_behavior_retention_days": 90,
            "failed_behavior_cap": None,
        },
    )

    unconfirmed = parser.parse_args(["memory", "delete-profile", "user-1"])
    with pytest.raises(ValueError, match="requires --confirm"):
        asyncio.run(agent_cli._run_memory_command(unconfirmed))  # noqa: SLF001

    reset_arguments = parser.parse_args(["memory", "reset-all", "--confirm"])
    assert asyncio.run(agent_cli._run_memory_command(reset_arguments)) == 0  # noqa: SLF001
    service_request.assert_awaited_with(
        reset_arguments,
        {"command": "memory_reset_all", "confirmed": True},
    )

    register_arguments = parser.parse_args(["memory", "register-face", "user-1", "--confirm"])
    assert asyncio.run(agent_cli._run_memory_command(register_arguments)) == 0  # noqa: SLF001
    service_request.assert_awaited_with(
        register_arguments,
        {
            "command": "memory_register_face",
            "user_id": "user-1",
            "confirmed": True,
        },
    )


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


def test_remote_setup_hides_token_installs_only_explicitly_and_saves_pairing_secrets(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    token = "ngrok-secret-authtoken-value"
    prompts = iter((token, token))
    monkeypatch.setattr(agent_cli.getpass, "getpass", lambda _prompt: next(prompts))
    installed: list[Path] = []

    def install(path: str | Path) -> Path:
        destination = Path(path).expanduser()
        installed.append(destination)
        return destination

    monkeypatch.setattr(agent_cli, "install_ngrok_binary", install)
    parser = agent_cli.build_parser()
    secret_file = tmp_path / "secrets.env"
    arguments = parser.parse_args(
        [
            "--config",
            str(ROOT / "config/ninjarobot_pi5.toml.example"),
            "--secret-file",
            str(secret_file),
            "remote",
            "configure",
        ]
    )

    assert asyncio.run(agent_cli._run_remote_command(arguments)) == 0  # noqa: SLF001

    output = capsys.readouterr().out
    store = SecretStore(secret_file)
    assert token not in output
    assert installed == [Path("~/.local/share/ninjarobot_pi5/bin/ngrok").expanduser()]
    assert store.get("NGROK_AUTHTOKEN") == token
    assert store.contains("NINJAROBOT_PAIRING_SECRET")
    assert store.contains("NINJAROBOT_SESSION_SECRET")
    assert store.contains("NINJAROBOT_REMOTE_HEADER_SECRET")
    assert secret_file.stat().st_mode & 0o777 == 0o600


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


def test_service_start_waits_for_liveliness_result_before_reporting(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    pending = {
        "started": True,
        "ready": False,
        "startup": {"complete": False, "liveliness": "pending"},
    }
    degraded = {
        "started": True,
        "ready": False,
        "operational_state": "recovery_required",
        "startup": {"complete": True, "liveliness": "failed"},
    }
    detailed = {
        **degraded,
        "provider": {"provider": "gemini", "status": "ready"},
        "tool_providers": [],
    }

    class FakeClient:
        def __init__(self) -> None:
            self.requests = []
            self.responses = iter(
                (
                    agent_cli.AgentIPCError("not running"),
                    {"data": pending},
                    {"data": degraded},
                    {"data": detailed},
                )
            )

        async def request(self, payload):
            self.requests.append(payload)
            response = next(self.responses)
            if isinstance(response, Exception):
                raise response
            return response

    fake_client = FakeClient()
    process = SimpleNamespace(pid=4242, poll=Mock(return_value=None), terminate=Mock())
    namespace = SimpleNamespace(
        socket=tmp_path / "agent.sock",
        lock=tmp_path / "agent.lock",
        database=tmp_path / "conversation.sqlite3",
        ledger=tmp_path / "ledger.sqlite3",
        config=tmp_path / "config.toml",
        mcp_config=tmp_path / "mcp.toml",
        secret_file=tmp_path / "secrets.env",
        skill_dir=tmp_path / "skills",
        benchmark_dir=tmp_path / "benchmarks",
        whisper_command=tmp_path / "whisper-cli",
        whisper_model=tmp_path / "whisper.bin",
        whisper_threads=4,
        web_host="127.0.0.1",
        web_port=8443,
        web_certificate=tmp_path / "cert.pem",
        web_key=tmp_path / "key.pem",
        model=None,
        base_url=None,
        real=True,
    )
    monkeypatch.setattr(agent_cli, "AgentIPCClient", lambda _socket: fake_client)
    monkeypatch.setattr(agent_cli, "_service_namespace", lambda _arguments: namespace)
    monkeypatch.setattr(agent_cli, "DEFAULT_SERVICE_LOG", tmp_path / "agent.log")
    monkeypatch.setattr(agent_cli.subprocess, "Popen", Mock(return_value=process))
    sleep = AsyncMock()
    monkeypatch.setattr(agent_cli.asyncio, "sleep", sleep)

    result = asyncio.run(
        agent_cli._spawn_service(SimpleNamespace(service_socket=namespace.socket))  # noqa: SLF001
    )

    assert result == 0
    assert fake_client.requests == [
        {"command": "status"},
        {"command": "startup_status"},
        {"command": "startup_status"},
        {"command": "status"},
    ]
    sleep.assert_awaited_once_with(0.1)
    process.terminate.assert_not_called()
    output = json.loads(capsys.readouterr().out)
    assert output["started"] is True
    assert output["ready"] is False
    assert output["status"] == detailed
    log_text = (tmp_path / "agent.log").read_text(encoding="utf-8")
    assert "=== NinjaRobotAgent start " in log_text
    assert "source=" in log_text
    assert "mode=real" in log_text


def test_service_start_reports_onboarding_without_waiting_for_greeting(
    tmp_path, monkeypatch, capsys
) -> None:
    onboarding = {
        "started": True,
        "ready": True,
        "operational_state": "onboarding",
        "startup": {"complete": False, "liveliness": "pending"},
    }

    class FakeClient:
        def __init__(self) -> None:
            self.responses = iter(
                (
                    agent_cli.AgentIPCError("not running"),
                    {"data": onboarding},
                    {"data": onboarding},
                )
            )

        async def request(self, _payload):
            response = next(self.responses)
            if isinstance(response, Exception):
                raise response
            return response

    namespace = SimpleNamespace(
        socket=tmp_path / "agent.sock",
        lock=tmp_path / "agent.lock",
        database=tmp_path / "conversation.sqlite3",
        ledger=tmp_path / "ledger.sqlite3",
        config=tmp_path / "config.toml",
        mcp_config=tmp_path / "mcp.toml",
        secret_file=tmp_path / "secrets.env",
        skill_dir=tmp_path / "skills",
        benchmark_dir=tmp_path / "benchmarks",
        whisper_command=tmp_path / "whisper-cli",
        whisper_model=tmp_path / "whisper.bin",
        whisper_threads=4,
        web_host="127.0.0.1",
        web_port=8443,
        web_certificate=tmp_path / "cert.pem",
        web_key=tmp_path / "key.pem",
        model=None,
        base_url=None,
        real=True,
    )
    process = SimpleNamespace(pid=4242, poll=Mock(return_value=None), terminate=Mock())
    monkeypatch.setattr(agent_cli, "AgentIPCClient", lambda _socket: FakeClient())
    monkeypatch.setattr(agent_cli, "_service_namespace", lambda _arguments: namespace)
    monkeypatch.setattr(agent_cli, "DEFAULT_SERVICE_LOG", tmp_path / "agent.log")
    monkeypatch.setattr(agent_cli.subprocess, "Popen", Mock(return_value=process))

    result = asyncio.run(
        agent_cli._spawn_service(SimpleNamespace(service_socket=namespace.socket))  # noqa: SLF001
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out)["status"] == onboarding
    process.terminate.assert_not_called()


def test_service_log_is_private_rotated_and_rejects_symlinks(tmp_path) -> None:
    log = tmp_path / "private" / "agent-service.log"
    log.parent.mkdir()
    log.write_bytes(b"old-log-data")

    prepared = agent_cli._prepare_service_log(log, max_bytes=4)  # noqa: SLF001

    assert prepared == log
    assert not log.exists()
    backup = log.with_name("agent-service.log.1")
    assert backup.read_bytes() == b"old-log-data"
    assert backup.stat().st_mode & 0o777 == 0o600

    target = tmp_path / "target.log"
    target.write_text("do not touch", encoding="utf-8")
    log.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic links"):
        agent_cli._prepare_service_log(log)  # noqa: SLF001
    assert target.read_text(encoding="utf-8") == "do not touch"
