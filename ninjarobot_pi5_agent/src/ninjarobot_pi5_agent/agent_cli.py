"""Conversational agent, provider, MCP, Skill, and web administration CLI."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import secrets as secure_random
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from ninjarobot_pi5_ide import RemoteAccessConfig, RiskLevel, load_robot_config

from .benchmark import BenchmarkCase, ModelBenchmark
from .cloud_common import CloudProviderError
from .cloud_registry import ConfiguredProviderRegistry
from .command_help import CHAT_HELP_TEXT
from .deployment import DeploymentManager, create_backup, current_spec, restore_backup
from .ipc import AgentIPCClient, AgentIPCError
from .mcp_client import (
    MCPProtocolError,
    MCPToolProvider,
    MCPUnavailableError,
)
from .mcp_config import (
    MCPConfiguration,
    MCPServerConfig,
    load_mcp_configuration,
    save_mcp_configuration,
    tavily_server_config,
)
from .model_selection import (
    BenchmarkRegistry,
    ModelCatalogEntry,
    ModelSelectionError,
    persist_model_selection,
)
from .models import ProviderHealthStatus, ToolCall, ToolDefinition, ToolInvocation
from .ollama import OllamaConfig, OllamaError, OllamaProvider
from .provider_auth import persist_api_key_authentication, web_login_removed
from .remote_access import (
    RemoteAccessError,
    install_ngrok_binary,
    ngrok_binary_ready,
    persist_remote_access_enabled,
)
from .secrets import SecretStore
from .service_main import run_service
from .skills import (
    LoadedSkill,
    SkillManifestV2,
    SkillRepository,
    SkillValidationError,
    compatible_tools,
)
from .tools import ToolRegistry, ToolRegistryError
from .web_app import (
    ensure_local_ca_certificate,
    export_local_ca_certificate,
    local_ca_paths,
    mdns_hostname,
)

DEFAULT_MCP_CONFIG = Path("~/.config/ninjarobot_pi5/mcp.toml")
DEFAULT_SECRET_FILE = Path("~/.config/ninjarobot_pi5/secrets.env")
DEFAULT_SKILL_DIRECTORY = Path("~/.config/ninjarobot_pi5/skills")
DEFAULT_BENCHMARK_REPORT = Path("~/.local/share/ninjarobot_pi5/benchmarks/qwen3-4b-latest.json")
DEFAULT_BENCHMARK_DIRECTORY = Path("~/.local/share/ninjarobot_pi5/benchmarks")
DEFAULT_SERVICE_SOCKET = Path("~/.local/state/ninjarobot_pi5/agent.sock")
DEFAULT_SERVICE_LOCK = Path("~/.local/state/ninjarobot_pi5/agent.lock")
DEFAULT_CONVERSATION_DB = Path("~/.local/share/ninjarobot_pi5/conversations.sqlite3")
DEFAULT_ACTION_LEDGER = Path("~/.local/state/ninjarobot_pi5/agent-actions.sqlite3")
DEFAULT_ROBOT_CONFIG = Path("~/.config/ninjarobot_pi5/config.toml")
DEFAULT_SERVICE_LOG = Path("~/.local/state/ninjarobot_pi5/agent-service.log")
DEFAULT_WHISPER_COMMAND = Path("~/whisper.cpp/build/bin/whisper-cli")
DEFAULT_WHISPER_MODEL = Path("~/whisper.cpp/models/ggml-base.bin")
DEFAULT_WEB_CERTIFICATE = Path("~/.config/ninjarobot_pi5/tls/agent-cert.pem")
DEFAULT_WEB_KEY = Path("~/.config/ninjarobot_pi5/tls/agent-key.pem")
DEFAULT_WEB_CA_EXPORT = Path("~/ninjarobotpi5-local-ca.pem")
MAX_SERVICE_LOG_BYTES = 5_000_000


def build_parser() -> argparse.ArgumentParser:
    """Build the scriptable Phase 5 command surface."""
    parser = argparse.ArgumentParser(
        prog="ninjarobot-agent",
        description="NinjaRobot conversational agent and extension manager.",
    )
    parser.add_argument(
        "--mcp-config",
        type=Path,
        default=DEFAULT_MCP_CONFIG,
        help="MCP server TOML file.",
    )
    parser.add_argument(
        "--secret-file",
        type=Path,
        default=DEFAULT_SECRET_FILE,
        help="Owner-only agent secret file.",
    )
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=DEFAULT_SKILL_DIRECTORY,
        help="Installed user-skill directory.",
    )
    parser.add_argument(
        "--service-socket",
        type=Path,
        default=DEFAULT_SERVICE_SOCKET,
        help="Local agent-service socket.",
    )
    parser.add_argument(
        "--service-lock",
        type=Path,
        default=DEFAULT_SERVICE_LOCK,
        help="Single-owner agent-service lock.",
    )
    parser.add_argument(
        "--conversation-db",
        type=Path,
        default=DEFAULT_CONVERSATION_DB,
        help="Seven-day conversation database.",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=DEFAULT_ACTION_LEDGER,
        help="Durable IDE action ledger.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_ROBOT_CONFIG,
        help="Imported NinjaRobotPi5 configuration.",
    )
    parser.add_argument(
        "--whisper-command",
        type=Path,
        default=DEFAULT_WHISPER_COMMAND,
        help="Local whisper.cpp executable used for USB-microphone transcription.",
    )
    parser.add_argument(
        "--whisper-model",
        type=Path,
        default=DEFAULT_WHISPER_MODEL,
        help="Local whisper.cpp model file.",
    )
    parser.add_argument("--whisper-threads", type=int, default=4)
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        default=DEFAULT_BENCHMARK_DIRECTORY,
        help="Directory containing model acceptance benchmark reports.",
    )
    parser.add_argument("--web-host", default="0.0.0.0")
    parser.add_argument("--web-port", type=int, default=8443)
    parser.add_argument(
        "--web-certificate",
        type=Path,
        default=DEFAULT_WEB_CERTIFICATE,
    )
    parser.add_argument("--web-key", type=Path, default=DEFAULT_WEB_KEY)
    commands = parser.add_subparsers(dest="command")

    chat = commands.add_parser("chat", help="Chat through the running agent service.")
    chat.add_argument("prompt", nargs="?")
    chat.add_argument("--session", default="local-cli")
    chat.add_argument("--skill")
    chat.add_argument("--confirmed", action="store_true")

    commands.add_parser("status", help="Show running service and provider status.")
    recipe = commands.add_parser("recipe", help="Preview, save and run owned read-only recipes.")
    recipe.add_argument(
        "operation",
        choices=(
            "list",
            "preview",
            "save",
            "show",
            "run",
            "disable",
            "enable",
            "delete",
            "rollback",
        ),
    )
    recipe.add_argument("recipe_id", nargs="?", default="")
    recipe.add_argument("--file", type=Path)
    recipe.add_argument("--version", type=int, default=0)
    recipe.add_argument("--review-hash", default="")
    recipe.add_argument("--inputs", default="{}")
    recipe.add_argument("--confirm", action="store_true")
    recipe.add_argument("--session", default="local-cli")
    game = commands.add_parser("game", help="Start, stop or inspect the optional distance game.")
    game.add_argument("operation", choices=("start", "stop", "status"))
    game.add_argument("--seconds", type=int, default=30)
    game.add_argument("--session", default="local-cli")

    service = commands.add_parser("service", help="Start, inspect, or stop the agent service.")
    service_commands = service.add_subparsers(dest="service_command", required=True)
    for service_command in ("run", "start"):
        service_parser = service_commands.add_parser(service_command)
        service_parser.add_argument("--real", action="store_true")
        service_parser.add_argument("--model")
        service_parser.add_argument("--base-url")
    service_commands.add_parser("status")
    service_commands.add_parser("stop")

    web = commands.add_parser("web", help="Start, inspect, or stop the HTTPS web interface.")
    web_commands = web.add_subparsers(dest="web_command", required=True)
    web_commands.add_parser("start")
    web_commands.add_parser("status")
    web_commands.add_parser("stop")
    web_commands.add_parser("certificate-status")
    export_ca = web_commands.add_parser("export-ca")
    export_ca.add_argument("--output", type=Path, default=DEFAULT_WEB_CA_EXPORT)

    remote = commands.add_parser("remote", help="Configure passwordless ngrok access.")
    remote_commands = remote.add_subparsers(dest="remote_command", required=True)
    remote_commands.add_parser(
        "configure",
        help="Explicitly install ngrok and save its authtoken privately.",
    )
    for remote_command in (
        "activate",
        "deactivate",
        "status",
        "pairing-url",
        "rotate-pairing",
    ):
        remote_commands.add_parser(remote_command)
    remote_remove = remote_commands.add_parser(
        "remove-credentials",
        help="Disable remote access and delete its private credentials.",
    )
    remote_remove.add_argument("--confirm", action="store_true")

    deployment = commands.add_parser("deployment", help="Manage opt-in systemd auto-start.")
    deployment_commands = deployment.add_subparsers(dest="deployment_command", required=True)
    for deployment_command in ("setup", "install", "upgrade", "enable", "uninstall"):
        item = deployment_commands.add_parser(deployment_command)
        item.add_argument("--confirm", action="store_true")
    for deployment_command in (
        "validate",
        "disable",
        "start",
        "stop",
        "restart",
        "status",
    ):
        deployment_commands.add_parser(deployment_command)
    deployment_logs = deployment_commands.add_parser("logs")
    deployment_logs.add_argument("--lines", type=int, default=100)
    deployment_backup = deployment_commands.add_parser("backup")
    deployment_backup.add_argument("--output", type=Path, required=True)
    deployment_rollback = deployment_commands.add_parser("rollback")
    deployment_rollback.add_argument("--backup", type=Path, required=True)
    deployment_rollback.add_argument("--confirm", action="store_true")

    session = commands.add_parser("session", help="Inspect or clear local conversations.")
    session_commands = session.add_subparsers(dest="session_command", required=True)
    session_commands.add_parser("list")
    history = session_commands.add_parser("history")
    history.add_argument("session_id")
    clear = session_commands.add_parser("clear")
    clear.add_argument("session_id")

    memory = commands.add_parser("memory", help="Manage persistent profiles and behavior memory.")
    memory_commands = memory.add_subparsers(dest="memory_command", required=True)
    memory_commands.add_parser("profiles", help="List local user profiles.")
    memory_commands.add_parser("settings", help="Show retention and retrieval settings.")
    memory_list = memory_commands.add_parser("list", help="List one behavior memory category.")
    memory_list.add_argument("user_id")
    memory_list.add_argument(
        "--kind",
        choices=(
            "successful_behavior",
            "failed_behavior",
            "task_recipe",
            "preference",
            "episodic_summary",
        ),
        default="successful_behavior",
    )
    memory_list.add_argument("--limit", type=int, default=100)
    memory_delete = memory_commands.add_parser("delete", help="Delete one behavior memory item.")
    memory_delete.add_argument("user_id")
    memory_delete.add_argument("memory_id")
    memory_delete.add_argument("--confirm", action="store_true")
    profile_delete = memory_commands.add_parser(
        "delete-profile",
        help="Delete one inactive, non-owner profile and its memory.",
    )
    profile_delete.add_argument("user_id")
    profile_delete.add_argument("--confirm", action="store_true")
    transfer_owner = memory_commands.add_parser(
        "transfer-owner",
        help="Transfer the default owner role before deleting the current owner.",
    )
    transfer_owner.add_argument("user_id")
    transfer_owner.add_argument("--confirm", action="store_true")
    register_face = memory_commands.add_parser(
        "register-face",
        help="Register or replace the face for one existing profile.",
    )
    register_face.add_argument("user_id")
    register_face.add_argument("--confirm", action="store_true")
    reset_all = memory_commands.add_parser(
        "reset-all",
        help="Delete all robot memory, including the owner and face profiles.",
    )
    reset_all.add_argument("--confirm", action="store_true")
    retention = memory_commands.add_parser(
        "set-retention",
        help="Set conversation or failed-behavior retention.",
    )
    retention.add_argument("--conversations", type=int)
    retention.add_argument("--failed", type=int)
    retention.add_argument("--failed-cap", type=int)

    motion = commands.add_parser("motion", help="Manage one-time session motion consent.")
    motion_commands = motion.add_subparsers(dest="motion_command", required=True)
    arm = motion_commands.add_parser("arm")
    arm.add_argument("--session", default="local-cli")
    arm.add_argument("--confirm", action="store_true")
    disarm = motion_commands.add_parser("disarm")
    disarm.add_argument("--session", default="local-cli")

    model = commands.add_parser("model", help="List or select an agent model.")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    list_models = model_commands.add_parser("list", help="List available provider models.")
    list_models.add_argument("--provider")
    model_commands.add_parser("current", help="Show the active provider and model.")
    select_model = model_commands.add_parser("select", help="Select an installed model.")
    select_model.add_argument("model_name")
    select_model.add_argument("--provider")

    provider = commands.add_parser("provider", help="Configure cloud provider access.")
    provider_commands = provider.add_subparsers(dest="provider_command", required=True)
    provider_commands.add_parser("list", help="List configured model providers.")
    provider_status = provider_commands.add_parser(
        "status",
        help="Show non-secret authentication status.",
    )
    provider_status.add_argument("provider_id")
    provider_health = provider_commands.add_parser(
        "health",
        help="Check provider credentials, service, and selected model.",
    )
    provider_health.add_argument("provider_id")
    provider_login = provider_commands.add_parser(
        "login",
        help="Explain the API-key migration for the retired web-login command.",
    )
    provider_login.add_argument("provider_id")
    provider_login.add_argument("--client-id-file", type=Path, help=argparse.SUPPRESS)
    provider_key = provider_commands.add_parser(
        "set-api-key",
        help="Save an API key using a hidden terminal prompt.",
    )
    provider_key.add_argument("provider_id")
    provider_logout = provider_commands.add_parser(
        "logout",
        help="Remove a stored provider API key.",
    )
    provider_logout.add_argument("provider_id")

    secret = commands.add_parser("secret", help="Manage agent secrets safely.")
    secret_commands = secret.add_subparsers(dest="secret_command", required=True)
    secret_set = secret_commands.add_parser("set", help="Set a secret using a hidden prompt.")
    secret_set.add_argument("name", help="Uppercase environment-style secret name.")

    mcp = commands.add_parser("mcp", help="Manage Model Context Protocol servers.")
    mcp_commands = mcp.add_subparsers(dest="mcp_command", required=True)
    add = mcp_commands.add_parser("add", help="Add an approved MCP preset.")
    add.add_argument("--preset", choices=("tavily",), required=True)
    add.add_argument("--id", default="tavily")
    mcp_commands.add_parser("list", help="List configured MCP servers.")
    for command, help_text in (
        ("health", "Connect and check one MCP server."),
        ("tools", "List allowlisted discovered tools."),
        ("inspect", "Show redacted server configuration."),
        ("reload", "Reconnect and refresh one MCP catalog."),
        ("enable", "Enable one configured MCP server."),
        ("disable", "Disable one configured MCP server."),
    ):
        subparser = mcp_commands.add_parser(command, help=help_text)
        subparser.add_argument("server_id")
    remove = mcp_commands.add_parser("remove", help="Remove one MCP server configuration.")
    remove.add_argument("server_id")
    remove.add_argument("--confirm", action="store_true", help="Confirm configuration removal.")
    test = mcp_commands.add_parser("test", help="Call one allowlisted read-only MCP tool.")
    test.add_argument("server_id")
    test.add_argument("--tool", required=True)
    test.add_argument("--arguments", default="{}")

    skill = commands.add_parser("skill", help="Validate and manage agent skills.")
    skill_commands = skill.add_subparsers(dest="skill_command", required=True)
    skill_commands.add_parser("list", help="List bundled and user skills.")
    for command, help_text in (
        ("validate", "Validate a skill directory without installing it."),
        ("inspect-path", "Inspect a validated skill directory."),
        ("simulate-path", "Preview a skill directory without executing tools."),
        ("install", "Install a validated skill without overwriting."),
    ):
        subparser = skill_commands.add_parser(command, help=help_text)
        subparser.add_argument("path", type=Path)
        subparser.add_argument("--check-live", action="store_true")
        if command == "simulate-path":
            subparser.add_argument("--input", default="{}")
        if command == "install":
            subparser.add_argument("--ai-proposed", action="store_true")
            subparser.add_argument("--confirm", action="store_true")
            subparser.add_argument("--simulation-input")
    for command, help_text in (
        ("inspect", "Inspect an installed or bundled skill."),
        ("simulate", "Preview an installed skill without executing tools."),
        ("enable", "Enable a skill."),
        ("disable", "Disable a skill."),
    ):
        subparser = skill_commands.add_parser(command, help=help_text)
        subparser.add_argument("skill_id")
        subparser.add_argument("--check-live", action="store_true")
        if command == "simulate":
            subparser.add_argument("--input", default="{}")
    remove_skill = skill_commands.add_parser("remove", help="Remove one user skill.")
    remove_skill.add_argument("skill_id")
    remove_skill.add_argument("--confirm", action="store_true")

    benchmark = commands.add_parser("benchmark", help="Benchmark a local model safely.")
    benchmark_commands = benchmark.add_subparsers(
        dest="benchmark_command",
        required=True,
    )
    ollama = benchmark_commands.add_parser(
        "ollama",
        help="Run the Qwen/Ollama Pi acceptance benchmark without executing tools.",
    )
    ollama.add_argument("--model", default="qwen3:4b")
    ollama.add_argument("--base-url", default="http://127.0.0.1:11434")
    ollama.add_argument("--output", type=Path, default=DEFAULT_BENCHMARK_REPORT)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run one scriptable agent command with sanitized error reporting."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        exit_code = asyncio.run(_run(arguments))
    except (
        KeyError,
        ValueError,
        ValidationError,
        MCPProtocolError,
        MCPUnavailableError,
        ToolRegistryError,
        SkillValidationError,
        PermissionError,
        FileExistsError,
        AgentIPCError,
        ModelSelectionError,
        OllamaError,
        CloudProviderError,
        RemoteAccessError,
    ) as exc:
        parser.error(_safe_error(exc))
    raise SystemExit(exit_code)


async def _run(arguments: argparse.Namespace) -> int:
    if arguments.command is None:
        return await _interactive(arguments)
    if arguments.command == "game":
        return await _service_request(
            arguments,
            {
                "command": "game",
                "operation": arguments.operation,
                "session_id": arguments.session,
                "duration_seconds": arguments.seconds,
            },
        )
    if arguments.command == "chat":
        return await _run_chat_command(arguments)
    if arguments.command == "status":
        return await _service_request(arguments, {"command": "status"})
    if arguments.command == "service":
        return await _run_service_command(arguments)
    if arguments.command == "session":
        return await _run_session_command(arguments)
    if arguments.command == "memory":
        return await _run_memory_command(arguments)
    if arguments.command == "motion":
        return await _run_motion_command(arguments)
    if arguments.command == "model":
        return await _run_model_command(arguments)
    if arguments.command == "provider":
        return await _run_provider_command(arguments)
    if arguments.command == "remote":
        return await _run_remote_command(arguments)
    if arguments.command == "deployment":
        return await asyncio.to_thread(_run_deployment_command, arguments)
    if arguments.command == "web":
        if arguments.web_command == "certificate-status":
            certificate, key = ensure_local_ca_certificate(
                arguments.web_certificate,
                arguments.web_key,
            )
            ca_certificate, _ca_key = local_ca_paths(certificate)
            _print_json(
                {
                    "certificate": str(certificate),
                    "key": str(key),
                    "local_ca_certificate": (
                        str(ca_certificate) if ca_certificate.is_file() else None
                    ),
                    "url": f"https://{mdns_hostname()}:{arguments.web_port}/",
                }
            )
            return 0
        if arguments.web_command == "export-ca":
            output = export_local_ca_certificate(
                arguments.web_certificate,
                arguments.web_key,
                arguments.output,
            )
            _print_json(
                {
                    "exported": str(output),
                    "contains_private_key": False,
                    "next_step": "Install this certificate on the controlling device.",
                }
            )
            return 0
        return await _service_request(
            arguments,
            {"command": f"web_{arguments.web_command}"},
        )

    secret_store = SecretStore(arguments.secret_file)
    if arguments.command == "secret":
        value = getpass.getpass(f"Enter {arguments.name}: ")
        confirmation = getpass.getpass(f"Enter {arguments.name} again: ")
        if value != confirmation:
            raise ValueError("secret values did not match")
        secret_store.set(arguments.name, value)
        _print_json(
            {
                "name": arguments.name,
                "saved": True,
                "path": str(secret_store.path),
            }
        )
        return 0

    if arguments.command == "recipe":
        data = {
            "operation": arguments.operation,
            "recipe_id": arguments.recipe_id,
            "version": arguments.version,
            "review_hash": arguments.review_hash,
            "inputs": _json_object(arguments.inputs),
            "confirmed": arguments.confirm,
        }
        if arguments.file is not None:
            with arguments.file.open("rb") as stream:
                raw = stream.read(16001)
            if len(raw) > 16000:
                raise ValueError("recipe file exceeds 16000 bytes")
            data["recipe"] = json.loads(raw)
        return await _service_request(
            arguments, {"command": "recipe", "session_id": arguments.session, "data": data}
        )
    if arguments.command == "skill":
        definitions = None
        repository = SkillRepository(arguments.skill_dir)
        operation = arguments.skill_command
        if operation in {"install", "enable"} or getattr(arguments, "check_live", False):
            selected = (
                repository.load_path(arguments.path)
                if hasattr(arguments, "path")
                else repository._find_any(arguments.skill_id)
            )
            if isinstance(selected.manifest, SkillManifestV2) or getattr(
                arguments, "check_live", False
            ):
                from .models import ToolDefinition

                catalog = await AgentIPCClient(arguments.service_socket).request(
                    {"command": "tool_catalog"}
                )
                definitions = tuple(
                    ToolDefinition.model_validate_json(json.dumps(item)) for item in catalog["data"]
                )
                compatible_tools(selected, definitions)
        return _run_skill(arguments, definitions=definitions)
    if arguments.command == "benchmark":
        return await _run_benchmark(arguments)

    config_path: Path = arguments.mcp_config
    configuration = load_mcp_configuration(config_path)
    command: str = arguments.mcp_command
    if command == "add":
        if any(server.id == arguments.id for server in configuration.servers):
            raise ValueError(f"MCP server already exists: {arguments.id}")
        server = tavily_server_config(arguments.id)
        save_mcp_configuration(
            MCPConfiguration(servers=(*configuration.servers, server)),
            config_path,
        )
        _print_json({"added": server.redacted_dict(), "path": str(config_path.expanduser())})
        return 0
    if command == "list":
        _print_json(
            {
                "servers": [
                    {
                        "id": server.id,
                        "enabled": server.enabled,
                        "transport": server.transport,
                        "allowed_tools": server.allowed_tools,
                    }
                    for server in configuration.servers
                ]
            }
        )
        return 0

    server = _server_by_id(configuration, arguments.server_id)
    if command in {"enable", "disable"}:
        enabled = command == "enable"
        replacement = server.model_copy(update={"enabled": enabled})
        _replace_server(configuration, replacement, config_path)
        _print_json({"id": server.id, "enabled": enabled})
        return 0
    if command == "remove":
        if not arguments.confirm:
            raise ValueError("removing an MCP server requires --confirm")
        remaining = tuple(item for item in configuration.servers if item.id != server.id)
        save_mcp_configuration(MCPConfiguration(servers=remaining), config_path)
        _print_json({"id": server.id, "removed": True})
        return 0
    if command == "inspect":
        _print_json({"configuration": server.redacted_dict()})
        return 0

    provider = MCPToolProvider(server, secret_store)
    registry = ToolRegistry((provider,))
    try:
        await registry.start()
        if command == "health":
            reports = await registry.health()
            _print_json({"health": [report.model_dump(mode="json") for report in reports]})
            return 0
        if command in {"tools", "reload"}:
            if command == "reload":
                await provider.refresh()
                await registry.refresh_catalog(provider.provider_id)
            _print_json({"tools": [tool.model_dump(mode="json") for tool in registry.list_tools()]})
            return 0
        if command == "test":
            raw_arguments = _json_object(arguments.arguments)
            tool_name = f"mcp.{server.id}.{arguments.tool}"
            result = await registry.call(
                ToolInvocation(
                    call=ToolCall(
                        call_id="manual-mcp-test",
                        name=tool_name,
                        arguments=raw_arguments,
                    ),
                    session_id="manual-mcp-test",
                    requested_by="local-cli",
                )
            )
            _print_json(result.model_dump(mode="json"))
            return 0 if result.status.value == "succeeded" else 1
        raise AssertionError(f"unhandled MCP command: {command}")
    finally:
        await registry.close()


async def _run_chat_command(arguments: argparse.Namespace) -> int:
    if arguments.prompt is None:
        return await _chat_repl(arguments, session_id=arguments.session)
    await _stream_chat(
        arguments,
        session_id=arguments.session,
        text=arguments.prompt,
        skill_id=arguments.skill,
        confirmed=arguments.confirmed,
    )
    return 0


async def _run_remote_command(arguments: argparse.Namespace) -> int:
    """Run explicit local-owner remote setup and lifecycle commands."""
    config = load_robot_config(arguments.config)
    remote = config.remote_access
    secret_store = SecretStore(arguments.secret_file)
    command = arguments.remote_command
    if command == "configure":
        token = getpass.getpass("Enter the ngrok authtoken: ").strip()
        confirmation = getpass.getpass("Enter the ngrok authtoken again: ").strip()
        if token != confirmation:
            raise ValueError("ngrok authtoken values did not match")
        if not token:
            raise ValueError("ngrok authtoken must not be empty")
        executable = await asyncio.to_thread(install_ngrok_binary, remote.executable)
        secret_store.set(remote.authtoken_env, token)
        for name in (
            remote.pairing_secret_env,
            remote.session_secret_env,
            remote.remote_header_secret_env,
        ):
            if not secret_store.contains(name):
                secret_store.set(name, secure_random.token_urlsafe(48))
        _print_json(
            {
                "configured": True,
                "authtoken_saved": True,
                "executable": str(executable),
                "browser_login_required": False,
                "next_step": "Activate ngrok Remote Access, then start the Agent service.",
            }
        )
        return 0
    if command == "remove-credentials":
        if not arguments.confirm:
            raise ValueError("removing remote credentials requires --confirm")
        try:
            await _service_request(arguments, {"command": "remote_deactivate"})
        except AgentIPCError as exc:
            if "not running" not in str(exc):
                raise
        await persist_remote_access_enabled(arguments.config, False)
        removed = {
            name: secret_store.delete(name)
            for name in (
                remote.authtoken_env,
                remote.pairing_secret_env,
                remote.session_secret_env,
                remote.remote_header_secret_env,
            )
        }
        private_config = Path(remote.config_file).expanduser()
        if private_config.is_symlink():
            raise ValueError("ngrok config path must not be a symbolic link")
        config_removed = private_config.is_file()
        private_config.unlink(missing_ok=True)
        _print_json(
            {
                "credentials_removed": removed,
                "private_config_removed": config_removed,
                "ngrok_executable_retained": True,
            }
        )
        return 0
    if command == "status":
        try:
            return await _service_request(arguments, {"command": "remote_status"})
        except AgentIPCError as exc:
            if "not running" not in str(exc):
                raise
            _print_json(_offline_remote_status(remote, secret_store))
            return 0
    if command == "activate":
        _validate_offline_remote_configuration(remote, secret_store)
        _ensure_remote_pairing_secrets(remote, secret_store)
        try:
            return await _service_request(arguments, {"command": "remote_activate"})
        except AgentIPCError as exc:
            if "not running" not in str(exc):
                raise
            await persist_remote_access_enabled(arguments.config, True)
            _print_json(
                {
                    **_offline_remote_status(remote, secret_store, enabled=True),
                    "next_step": "Start the Agent service to open ngrok and show the QR code.",
                }
            )
            return 0
    if command == "deactivate":
        try:
            return await _service_request(arguments, {"command": "remote_deactivate"})
        except AgentIPCError as exc:
            if "not running" not in str(exc):
                raise
            await persist_remote_access_enabled(arguments.config, False)
            _print_json(_offline_remote_status(remote, secret_store, enabled=False))
            return 0
    ipc_command = {
        "pairing-url": "remote_pairing_url",
        "rotate-pairing": "remote_rotate_pairing",
    }[command]
    return await _service_request(arguments, {"command": ipc_command})


def _validate_offline_remote_configuration(
    remote: RemoteAccessConfig,
    secret_store: SecretStore,
) -> None:
    if not secret_store.contains(remote.authtoken_env):
        raise RemoteAccessError("authtoken_unavailable")
    if not ngrok_binary_ready(remote.executable):
        raise RemoteAccessError("executable_unavailable")


def _ensure_remote_pairing_secrets(
    remote: RemoteAccessConfig,
    secret_store: SecretStore,
) -> None:
    for name in (
        remote.pairing_secret_env,
        remote.session_secret_env,
        remote.remote_header_secret_env,
    ):
        if not secret_store.contains(name):
            secret_store.set(name, secure_random.token_urlsafe(48))


def _offline_remote_status(
    remote: RemoteAccessConfig,
    secret_store: SecretStore,
    *,
    enabled: bool | None = None,
) -> dict[str, object]:
    configured = secret_store.contains(remote.authtoken_env) and ngrok_binary_ready(
        remote.executable
    )
    effective_enabled = remote.enabled if enabled is None else enabled
    if not configured:
        state = "configuration_required"
        next_step = "Set the ngrok token before activating Remote Access."
    elif effective_enabled:
        state = "enabled_for_next_agent_start"
        next_step = "Start the Agent service to open ngrok and show the QR code."
    else:
        state = "disabled"
        next_step = "Activate ngrok Remote Access when remote control is needed."
    return {
        "active_sessions": 0,
        "configured": configured,
        "enabled": effective_enabled,
        "pairing_available": False,
        "public_url": None,
        "service_running": False,
        "state": state,
        "next_step": next_step,
    }


async def _stream_chat(
    arguments: argparse.Namespace,
    *,
    session_id: str,
    text: str,
    skill_id: str | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    client = AgentIPCClient(arguments.service_socket)
    saw_delta = False
    final: dict[str, Any] | None = None
    async for message in client.stream(
        {
            "command": "chat",
            "session_id": session_id,
            "text": text,
            "skill_id": skill_id,
            "confirmed": confirmed,
        }
    ):
        message_type = message.get("type")
        if message_type == "delta":
            delta = message.get("text")
            if isinstance(delta, str):
                print(delta, end="", flush=True)
                saw_delta = True
        elif message_type == "error":
            if saw_delta:
                print()
            raise AgentIPCError(str(message.get("error", "unknown service error")))
        elif message_type == "result":
            data = message.get("data")
            if isinstance(data, dict):
                final = data
    if final is None:
        raise AgentIPCError("agent service returned no chat result")
    if saw_delta:
        print()
    else:
        print(final["text"])
    return final


async def _chat_repl(arguments: argparse.Namespace, *, session_id: str) -> int:
    await _service_request(
        arguments,
        {"command": "controller_connected", "interface": "terminal"},
        print_result=False,
    )
    print("NinjaRobot chat. Type /help for commands.")
    while True:
        try:
            text = (await asyncio.to_thread(input, "You> ")).strip()
        except EOFError:
            print()
            return 0
        if not text:
            continue
        if text == "/exit":
            return 0
        if text == "/help":
            print(CHAT_HELP_TEXT)
            continue
        if text == "/clear":
            await _service_request(
                arguments,
                {"command": "clear", "session_id": session_id},
            )
            continue
        if text == "/status":
            await _service_request(arguments, {"command": "status"})
            continue
        if text == "/show remote access":
            try:
                await _service_request(arguments, {"command": "remote_show_qr"})
            except AgentIPCError as exc:
                print(f"Remote QR display failed: {exc}")
            continue
        if text == "/resume":
            await _resume_from_chat(arguments, session_id=session_id)
            continue
        if text == "/camera":
            await _service_request(
                arguments,
                {
                    "command": "grant_camera",
                    "session_id": session_id,
                    "confirmed": True,
                },
            )
            print(
                "AI camera access is ready for one temporary photo. "
                "Ask NinjaRobot to take a photo; a failed capture keeps the grant "
                "available. After success, use /camera again for another photo."
            )
            continue
        if text == "/arm":
            confirmation = (
                await asyncio.to_thread(
                    input,
                    "Type ARM to allow physical motion for this session: ",
                )
            ).strip()
            if confirmation != "ARM":
                print("Motion was not armed.")
                continue
            await _service_request(
                arguments,
                {
                    "command": "arm_motion",
                    "session_id": session_id,
                    "confirmed": True,
                },
            )
            continue
        if text == "/disarm":
            await _service_request(
                arguments,
                {"command": "disarm_motion", "session_id": session_id},
            )
            continue
        if text in {"/voice input on", "/voice input off", "/voice input status"}:
            action = text.removeprefix("/voice input ")
            command = {
                "on": "voice_enable",
                "off": "voice_disable",
                "status": "voice_status",
            }[action]
            try:
                await _service_request(arguments, {"command": command})
            except AgentIPCError as exc:
                print(f"Voice input failed: {exc}")
            continue
        if text == "/confirm" or text.startswith("/confirm "):
            confirmed_text = text.removeprefix("/confirm").strip()
            if not confirmed_text:
                confirmed_text = (
                    await asyncio.to_thread(
                        input,
                        "Enter the request you explicitly approve: ",
                    )
                ).strip()
            if not confirmed_text:
                print("No confirmed request was sent.")
                continue
            try:
                await _stream_chat(
                    arguments,
                    session_id=session_id,
                    text=confirmed_text,
                    confirmed=True,
                )
            except AgentIPCError as exc:
                print(f"Error: {exc}")
            continue
        try:
            await _stream_chat(
                arguments,
                session_id=session_id,
                text=text,
            )
        except AgentIPCError as exc:
            print(f"Error: {exc}")


async def _resume_from_chat(arguments: argparse.Namespace, *, session_id: str) -> None:
    """Confirm and run health-checked system recovery without invoking the model."""
    confirmation = (
        await asyncio.to_thread(
            input,
            "Type RESUME to health-check and recover all robot modules: ",
        )
    ).strip()
    if confirmation != "RESUME":
        print("System resume was cancelled.")
        return
    try:
        await _service_request(
            arguments,
            {
                "command": "resume_system",
                "session_id": session_id,
                "confirmed": True,
            },
        )
    except AgentIPCError as exc:
        print(f"Resume failed: {exc}")
        return
    print(
        "Robot modules resumed and Idle restored. "
        "AI motion remains disarmed; use /arm before requesting servo movement."
    )


async def _run_service_command(arguments: argparse.Namespace) -> int:
    command = arguments.service_command
    if command == "run":
        await run_service(_service_namespace(arguments))
        return 0
    if command == "start":
        return await _spawn_service(arguments)
    if command == "status":
        return await _service_request(arguments, {"command": "status"})
    if command == "stop":
        return await _service_request(arguments, {"command": "stop"})
    raise AssertionError(f"unhandled service command: {command}")


def _run_deployment_command(arguments: argparse.Namespace) -> int:
    spec = current_spec(arguments)
    manager = DeploymentManager(spec)
    command = arguments.deployment_command
    if command == "setup":
        _print_json(manager.install_and_enable(confirmed=arguments.confirm))
    elif command in {"install", "upgrade"}:
        _print_json(
            manager.install(
                confirmed=arguments.confirm,
                upgrade=command == "upgrade",
            )
        )
    elif command == "enable":
        _print_json(manager.enable(confirmed=arguments.confirm))
    elif command == "disable":
        _print_json(manager.disable())
    elif command in {"start", "stop", "restart"}:
        _print_json(manager.action(command))
    elif command == "validate":
        _print_json(manager.validate())
    elif command == "status":
        _print_json(manager.status())
    elif command == "logs":
        result = manager.logs(lines=arguments.lines)
        print(result.stdout, end="")
        if result.returncode != 0:
            raise RuntimeError("journal query failed")
    elif command == "backup":
        _print_json({"backup": str(create_backup(spec, arguments.output))})
    elif command == "rollback":
        if not arguments.confirm:
            raise ValueError("backup rollback requires --confirm")
        manager.action("stop")
        _print_json(restore_backup(spec, arguments.backup, confirmed=True))
    elif command == "uninstall":
        _print_json(manager.uninstall(confirmed=arguments.confirm))
    else:
        raise AssertionError(f"unhandled deployment command: {command}")
    return 0


async def _spawn_service(arguments: argparse.Namespace) -> int:
    client = AgentIPCClient(arguments.service_socket)
    try:
        existing = await client.request({"command": "status"})
    except AgentIPCError:
        existing = None
    if existing is not None:
        _print_json({"already_running": True, "status": existing["data"]})
        return 0

    namespace = _service_namespace(arguments)
    command = [
        sys.executable,
        "-m",
        "ninjarobot_pi5_agent.service_main",
        "--socket",
        str(namespace.socket.expanduser()),
        "--lock",
        str(namespace.lock.expanduser()),
        "--database",
        str(namespace.database.expanduser()),
        "--ledger",
        str(namespace.ledger.expanduser()),
        "--config",
        str(namespace.config.expanduser()),
        "--mcp-config",
        str(namespace.mcp_config.expanduser()),
        "--secret-file",
        str(namespace.secret_file.expanduser()),
        "--skill-dir",
        str(namespace.skill_dir.expanduser()),
        "--benchmark-dir",
        str(namespace.benchmark_dir.expanduser()),
        "--whisper-command",
        str(namespace.whisper_command.expanduser()),
        "--whisper-model",
        str(namespace.whisper_model.expanduser()),
        "--whisper-threads",
        str(namespace.whisper_threads),
        "--web-host",
        namespace.web_host,
        "--web-port",
        str(namespace.web_port),
        "--web-certificate",
        str(namespace.web_certificate.expanduser()),
        "--web-key",
        str(namespace.web_key.expanduser()),
    ]
    if namespace.model is not None:
        command.extend(("--model", namespace.model))
    if namespace.base_url is not None:
        command.extend(("--base-url", namespace.base_url))
    if namespace.real:
        command.append("--real")
    log_path = _prepare_service_log(DEFAULT_SERVICE_LOG)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(log_path, flags, 0o600)
    with os.fdopen(descriptor, "ab") as log_handle:
        source = Path(__file__).resolve().parents[3]
        started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        marker = (
            f"\n=== NinjaRobotAgent start {started_at} "
            f"source={source} mode={'real' if namespace.real else 'simulated'} "
            f"python={sys.executable} ===\n"
        )
        log_handle.write(marker.encode("utf-8"))
        log_handle.flush()
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    for _ in range(600):
        if process.poll() is not None:
            raise AgentIPCError(f"agent service exited during startup; inspect {log_path}")
        try:
            status = await client.request({"command": "startup_status"})
        except AgentIPCError:
            await asyncio.sleep(0.1)
            continue
        status_data = status["data"]
        startup = status_data.get("startup")
        if (
            isinstance(startup, dict)
            and startup.get("complete") is False
            and status_data.get("operational_state") != "onboarding"
        ):
            await asyncio.sleep(0.1)
            continue
        try:
            detailed = await client.request({"command": "status"})
            status_data = detailed["data"]
        except AgentIPCError as exc:
            status_data["status_detail_error"] = str(exc)
        _print_json(
            {
                "started": True,
                "ready": status_data.get("ready", True),
                "pid": process.pid,
                "real_hardware": namespace.real,
                "log": str(log_path),
                "status": status_data,
            }
        )
        return 0
    process.terminate()
    raise AgentIPCError(f"agent service did not become ready; inspect {log_path}")


def _prepare_service_log(
    path: str | Path,
    *,
    max_bytes: int = MAX_SERVICE_LOG_BYTES,
) -> Path:
    """Create one owner-private bounded log path without following symlinks."""
    if max_bytes < 1:
        raise ValueError("service log size limit must be positive")
    candidate = Path(os.path.abspath(Path(path).expanduser()))
    current = candidate
    while current.parent != current:
        if current.is_symlink():
            raise ValueError("service log path must not contain symbolic links")
        current = current.parent
    candidate.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(candidate.parent, 0o700)
    if candidate.exists():
        mode = candidate.stat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError("service log path must be a regular file")
        if candidate.stat().st_size > max_bytes:
            backup = candidate.with_name(f"{candidate.name}.1")
            if backup.exists() and not stat.S_ISREG(backup.lstat().st_mode):
                raise ValueError("service log backup path must be a regular file")
            os.replace(candidate, backup)
            os.chmod(backup, 0o600)
        else:
            os.chmod(candidate, 0o600)
    return candidate


def _service_namespace(arguments: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        socket=arguments.service_socket,
        lock=arguments.service_lock,
        database=arguments.conversation_db,
        ledger=arguments.ledger,
        config=arguments.config,
        mcp_config=arguments.mcp_config,
        secret_file=arguments.secret_file,
        skill_dir=arguments.skill_dir,
        benchmark_dir=arguments.benchmark_dir,
        model=getattr(arguments, "model", None),
        base_url=getattr(arguments, "base_url", None),
        whisper_command=arguments.whisper_command,
        whisper_model=arguments.whisper_model,
        whisper_threads=arguments.whisper_threads,
        web_host=arguments.web_host,
        web_port=arguments.web_port,
        web_certificate=arguments.web_certificate,
        web_key=arguments.web_key,
        real=getattr(arguments, "real", False),
    )


async def _run_session_command(arguments: argparse.Namespace) -> int:
    if arguments.session_command == "list":
        return await _service_request(arguments, {"command": "sessions"})
    if arguments.session_command == "history":
        return await _service_request(
            arguments,
            {"command": "history", "session_id": arguments.session_id},
        )
    if arguments.session_command == "clear":
        return await _service_request(
            arguments,
            {"command": "clear", "session_id": arguments.session_id},
        )
    raise AssertionError(f"unhandled session command: {arguments.session_command}")


async def _run_memory_command(arguments: argparse.Namespace) -> int:
    command = arguments.memory_command
    if command == "profiles":
        return await _service_request(arguments, {"command": "memory_profiles"})
    if command == "settings":
        return await _service_request(arguments, {"command": "memory_settings"})
    if command == "list":
        return await _service_request(
            arguments,
            {
                "command": "memory_list",
                "user_id": arguments.user_id,
                "kind": arguments.kind,
                "limit": arguments.limit,
            },
        )
    if command in {"delete", "delete-profile", "transfer-owner", "register-face"}:
        if not arguments.confirm:
            raise ValueError(f"memory {command} requires --confirm")
        payload: dict[str, object] = {
            "command": f"memory_{command.replace('-', '_')}",
            "user_id": arguments.user_id,
            "confirmed": True,
        }
        if command == "delete":
            payload["memory_id"] = arguments.memory_id
        return await _service_request(arguments, payload)
    if command == "reset-all":
        if not arguments.confirm:
            raise ValueError("memory reset-all requires --confirm")
        return await _service_request(
            arguments,
            {"command": "memory_reset_all", "confirmed": True},
        )
    if command == "set-retention":
        if (
            arguments.conversations is None
            and arguments.failed is None
            and arguments.failed_cap is None
        ):
            raise ValueError("set-retention requires at least one retention option")
        return await _service_request(
            arguments,
            {
                "command": "memory_update_settings",
                "conversation_retention_days": arguments.conversations,
                "failed_behavior_retention_days": arguments.failed,
                "failed_behavior_cap": arguments.failed_cap,
            },
        )
    raise AssertionError(f"unhandled memory command: {command}")


async def _run_motion_command(arguments: argparse.Namespace) -> int:
    if arguments.motion_command == "arm":
        if not arguments.confirm:
            raise PermissionError("motion arm requires --confirm")
        return await _service_request(
            arguments,
            {
                "command": "arm_motion",
                "session_id": arguments.session,
                "confirmed": True,
            },
        )
    if arguments.motion_command == "disarm":
        return await _service_request(
            arguments,
            {
                "command": "disarm_motion",
                "session_id": arguments.session,
            },
        )
    raise AssertionError(f"unhandled motion command: {arguments.motion_command}")


async def _run_model_command(arguments: argparse.Namespace) -> int:
    if arguments.model_command == "list":
        _print_json(
            {
                "models": await _available_models(
                    arguments,
                    provider=arguments.provider,
                )
            }
        )
        return 0
    if arguments.model_command == "current":
        _print_json(await _current_model(arguments))
        return 0
    if arguments.model_command == "select":
        selected = await _select_model(
            arguments,
            model=arguments.model_name,
            provider=arguments.provider,
        )
        _print_json(selected)
        return 0
    raise AssertionError(f"unhandled model command: {arguments.model_command}")


async def _run_provider_command(arguments: argparse.Namespace) -> int:
    config = load_robot_config(arguments.config)
    secrets = SecretStore(arguments.secret_file)
    registry = ConfiguredProviderRegistry(arguments.config, secrets)
    if arguments.provider_command == "list":
        providers: list[dict[str, object]] = []
        for provider_id, provider in sorted(config.providers.items()):
            item: dict[str, object] = {
                "id": provider_id,
                "kind": provider.kind,
                "enabled": provider.enabled,
                "auth_method": ("local" if provider.kind == "ollama" else provider.auth_method),
                "current": provider_id == config.agent.default_provider,
            }
            if provider.enabled:
                adapter = registry.create(provider_id, provider.model)
                try:
                    item["capabilities"] = adapter.capabilities.model_dump(mode="json")
                finally:
                    await adapter.close()
            providers.append(item)
        _print_json(
            {
                "providers": providers,
            }
        )
        return 0
    try:
        provider = config.providers[arguments.provider_id]
    except KeyError as exc:
        raise ValueError(f"unknown configured provider: {arguments.provider_id}") from exc
    if arguments.provider_command == "status":
        _print_json(
            {
                "provider": arguments.provider_id,
                "kind": provider.kind,
                **registry.credential_status(arguments.provider_id),
            }
        )
        return 0
    if arguments.provider_command == "health":
        adapter = registry.create(arguments.provider_id, provider.model)
        try:
            health = await adapter.health()
        finally:
            await adapter.close()
        _print_json(health.model_dump(mode="json"))
        return 0 if health.status is ProviderHealthStatus.READY else 1
    if arguments.provider_command == "login":
        web_login_removed(arguments.provider_id)
    if arguments.provider_command == "set-api-key":
        if provider.kind == "ollama" or provider.api_key_env is None:
            raise ValueError(f"{provider.kind} does not have an API-key configuration")
        value = getpass.getpass(f"Enter {provider.api_key_env}: ")
        confirmation = getpass.getpass(f"Enter {provider.api_key_env} again: ")
        if value != confirmation:
            raise ValueError("API key values did not match")
        secrets.set(provider.api_key_env, value)
        persist_api_key_authentication(arguments.config, arguments.provider_id)
        _print_json(
            {
                "provider": arguments.provider_id,
                "authenticated": True,
                "method": "api_key",
                "secret_name": provider.api_key_env,
            }
        )
        return 0
    if arguments.provider_command == "logout":
        if provider.api_key_env is not None:
            removed = secrets.delete(provider.api_key_env)
        else:
            raise ValueError(f"{provider.kind} does not have removable credentials")
        _print_json(
            {
                "provider": arguments.provider_id,
                "credentials_removed": removed,
                "environment_override_may_remain": (
                    provider.api_key_env is not None
                    and secrets.get(provider.api_key_env) is not None
                ),
            }
        )
        return 0
    raise AssertionError(f"unhandled provider command: {arguments.provider_command}")


async def _available_models(
    arguments: argparse.Namespace,
    *,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    client = AgentIPCClient(arguments.service_socket)
    try:
        response = await client.request(
            {
                "command": "models",
                "provider": provider,
            }
        )
    except AgentIPCError:
        return [
            entry.model_dump(mode="json")
            for entry in await _offline_provider_catalog(arguments, provider=provider)
        ]
    data = response["data"]
    if not isinstance(data, list):
        raise AgentIPCError("agent service model catalog is malformed")
    return [cast(dict[str, Any], item) for item in data if isinstance(item, dict)]


async def _current_model(arguments: argparse.Namespace) -> dict[str, Any]:
    client = AgentIPCClient(arguments.service_socket)
    try:
        response = await client.request({"command": "model_current"})
    except AgentIPCError:
        provider_id, provider_config = _configured_provider(arguments)
        return {
            "provider": provider_id,
            "model": provider_config.model,
            "accepted": BenchmarkRegistry(arguments.benchmark_dir).accepted(provider_config.model),
            "service_running": False,
        }
    data = response["data"]
    if not isinstance(data, dict):
        raise AgentIPCError("agent service model selection is malformed")
    return {**data, "service_running": True}


async def _select_model(
    arguments: argparse.Namespace,
    *,
    model: str,
    provider: str | None,
) -> dict[str, Any]:
    provider_id, _provider_config = _configured_provider(arguments)
    selected_provider = provider or provider_id
    client = AgentIPCClient(arguments.service_socket)
    try:
        response = await client.request(
            {
                "command": "model_select",
                "provider": selected_provider,
                "model": model,
            }
        )
    except AgentIPCError as exc:
        if "agent service is not running" not in str(exc):
            raise
        catalog = await _offline_provider_catalog(
            arguments,
            provider=selected_provider,
        )
        selected = next(
            (
                entry
                for entry in catalog
                if entry.provider == selected_provider and entry.name == model
            ),
            None,
        )
        if selected is None:
            raise ModelSelectionError(
                f"model '{model}' is not installed for provider '{selected_provider}'"
            )
        registry = ConfiguredProviderRegistry(
            arguments.config,
            SecretStore(arguments.secret_file),
        )
        candidate = registry.create(selected_provider, model)
        try:
            health = await candidate.health()
        finally:
            await candidate.close()
        if health.status is not ProviderHealthStatus.READY:
            raise ModelSelectionError(
                health.detail or "selected model did not pass its provider health check"
            )
        persist_model_selection(arguments.config, selected_provider, model)
        return {
            **selected.model_copy(update={"current": True}).model_dump(mode="json"),
            "service_running": False,
        }
    data = response["data"]
    if not isinstance(data, dict):
        raise AgentIPCError("agent service model selection response is malformed")
    return {**data, "service_running": True}


async def _offline_provider_catalog(
    arguments: argparse.Namespace,
    *,
    provider: str | None = None,
) -> tuple[ModelCatalogEntry, ...]:
    configured_id, _provider_config = _configured_provider(arguments)
    provider_id = provider or configured_id
    registry = ConfiguredProviderRegistry(
        arguments.config,
        SecretStore(arguments.secret_file),
    )
    benchmarks = BenchmarkRegistry(arguments.benchmark_dir)
    config = load_robot_config(arguments.config)
    try:
        provider_config = config.providers[provider_id]
    except KeyError as exc:
        raise ModelSelectionError(f"unknown configured provider: {provider_id}") from exc
    return tuple(
        entry.model_copy(
            update={
                "current": (
                    provider_id == config.agent.default_provider
                    and entry.name == provider_config.model
                ),
                "accepted": benchmarks.accepted(entry.name),
            }
        )
        for entry in await registry.catalog(provider_id)
    )


def _configured_provider(arguments: argparse.Namespace) -> tuple[str, Any]:
    config = load_robot_config(arguments.config)
    provider_id = config.agent.default_provider
    return provider_id, config.providers[provider_id]


async def _service_request(
    arguments: argparse.Namespace,
    payload: dict[str, Any],
    *,
    print_result: bool = True,
) -> int:
    result = await AgentIPCClient(arguments.service_socket).request(payload)
    if print_result:
        _print_json(result["data"])
    return 0


async def _interactive_memory(arguments: argparse.Namespace) -> None:
    while True:
        print(
            "\nManage Memory\n"
            "1. List User Profiles\n"
            "2. Delete User Profile\n"
            "3. Transfer Robot Owner\n"
            "4. List Behavioral Memory\n"
            "5. Delete Behavioral Memory\n"
            "6. Set Raw Conversation Retention\n"
            "7. Set Failed Behavior Retention\n"
            "8. Register or Replace User Face\n"
            "9. Clean All Robot Memory\n"
            "10. Back\n"
        )
        choice = (await asyncio.to_thread(input, "Select an option: ")).strip()
        if choice == "10":
            return
        if choice == "1":
            await _service_request(arguments, {"command": "memory_profiles"})
            continue
        if choice in {"2", "3"}:
            user_id = (await asyncio.to_thread(input, "Enter the exact user_id: ")).strip()
            confirmation = (
                await asyncio.to_thread(
                    input,
                    "Type CONFIRM to continue with this profile operation: ",
                )
            ).strip()
            if confirmation != "CONFIRM":
                print("Profile operation cancelled.")
                continue
            await _service_request(
                arguments,
                {
                    "command": (
                        "memory_delete_profile" if choice == "2" else "memory_transfer_owner"
                    ),
                    "user_id": user_id,
                    "confirmed": True,
                },
            )
            continue
        if choice in {"4", "5"}:
            user_id = (await asyncio.to_thread(input, "Enter the exact user_id: ")).strip()
            kind_choice = (
                await asyncio.to_thread(
                    input,
                    "Category 1) successful 2) failed 3) task recipe [1]: ",
                )
            ).strip()
            kind = {
                "2": "failed_behavior",
                "3": "task_recipe",
            }.get(kind_choice, "successful_behavior")
            if choice == "4":
                await _service_request(
                    arguments,
                    {
                        "command": "memory_list",
                        "user_id": user_id,
                        "kind": kind,
                        "limit": 100,
                    },
                )
                continue
            memory_id = (await asyncio.to_thread(input, "Enter the exact memory_id: ")).strip()
            confirmation = (
                await asyncio.to_thread(input, "Type DELETE to remove this memory: ")
            ).strip()
            if confirmation != "DELETE":
                print("Behavior memory deletion cancelled.")
                continue
            await _service_request(
                arguments,
                {
                    "command": "memory_delete",
                    "user_id": user_id,
                    "memory_id": memory_id,
                    "confirmed": True,
                },
            )
            continue
        if choice in {"6", "7"}:
            prompt = (
                "Raw conversation retention in days (1-365): "
                if choice == "6"
                else "Failed behavior retention in days (1-3650): "
            )
            days = int((await asyncio.to_thread(input, prompt)).strip())
            await _service_request(
                arguments,
                {
                    "command": "memory_update_settings",
                    (
                        "conversation_retention_days"
                        if choice == "6"
                        else "failed_behavior_retention_days"
                    ): days,
                },
            )
            continue
        if choice == "8":
            user_id = (await asyncio.to_thread(input, "Enter the exact user_id: ")).strip()
            confirmation = (
                await asyncio.to_thread(
                    input,
                    "Type CONFIRM to capture and register this user's face: ",
                )
            ).strip()
            if confirmation != "CONFIRM":
                print("Face registration cancelled.")
                continue
            await _service_request(
                arguments,
                {
                    "command": "memory_register_face",
                    "user_id": user_id,
                    "confirmed": True,
                },
            )
            continue
        if choice == "9":
            confirmation = (
                await asyncio.to_thread(
                    input,
                    "Type DELETE ALL ROBOT MEMORY to erase every profile and memory: ",
                )
            ).strip()
            if confirmation != "DELETE ALL ROBOT MEMORY":
                print("Full memory reset cancelled.")
                continue
            await _service_request(
                arguments,
                {"command": "memory_reset_all", "confirmed": True},
            )
            continue
        print("Please choose a number from 1 through 10.")


async def _interactive_remote_access(arguments: argparse.Namespace) -> None:
    while True:
        print(
            "\nNgrok Remote Access\n"
            "1. Set ngrok token\n"
            "2. Activate ngrok remote access service\n"
            "3. Ngrok service status\n"
            "4. Show existing pairing URL\n"
            "5. Stop ngrok remote access service\n"
            "6. Back to the Interactive Tool\n"
        )
        choice = (await asyncio.to_thread(input, "Select an option: ")).strip()
        if choice == "6":
            return
        if choice == "1":
            arguments.remote_command = "configure"
            await _run_remote_command(arguments)
        elif choice == "2":
            arguments.remote_command = "activate"
            await _run_remote_command(arguments)
        elif choice == "3":
            arguments.remote_command = "status"
            await _run_remote_command(arguments)
        elif choice == "4":
            arguments.remote_command = "pairing-url"
            await _run_remote_command(arguments)
        elif choice == "5":
            arguments.remote_command = "deactivate"
            await _run_remote_command(arguments)
        else:
            print("Please choose a number from 1 through 6.")


async def _interactive(arguments: argparse.Namespace) -> int:
    while True:
        print(
            "\nNinjaRobotAgent Interactive Tool\n"
            "1. Set Agent Model\n"
            "2. Start Agent Service\n"
            "3. Agent Service Status\n"
            "4. Start NinjaRobot Chat Interface\n"
            "5. Local Web Interface\n"
            "6. Local Web Interface Status\n"
            "7. Stop Local Web Interface\n"
            "8. Ngrok Remote Access\n"
            "9. MCP Tools (Built-in and External)\n"
            "10. Agent Skills\n"
            "11. Agent Memory Management\n"
            "12. Startup Agent Deployment\n"
            "13. Stop Agent Service\n"
            "14. Exit\n"
            "15. Guided checks (read-only; service must be running)\n"
        )
        choice = (await asyncio.to_thread(input, "Select an option: ")).strip()
        try:
            if choice == "1":
                await _interactive_model_selection(arguments)
            elif choice == "2":
                mode = (
                    await asyncio.to_thread(
                        input,
                        "Start 1) simulation or 2) real hardware? [1]: ",
                    )
                ).strip()
                arguments.real = mode == "2"
                arguments.model = None
                arguments.base_url = None
                await _spawn_service(arguments)
            elif choice == "3":
                await _service_request(arguments, {"command": "status"})
            elif choice == "4":
                await _chat_repl(arguments, session_id="local-cli")
            elif choice == "5":
                await _service_request(arguments, {"command": "web_start"})
            elif choice == "6":
                await _service_request(arguments, {"command": "web_status"})
            elif choice == "7":
                await _service_request(arguments, {"command": "web_stop"})
            elif choice == "8":
                await _interactive_remote_access(arguments)
            elif choice == "9":
                configuration = load_mcp_configuration(arguments.mcp_config)
                service_status = await AgentIPCClient(arguments.service_socket).request(
                    {"command": "status"}
                )
                status_data = service_status.get("data", {})
                _print_json(
                    {
                        "loaded_tools": status_data.get("tools", []),
                        "loaded_tool_providers": status_data.get("tool_providers", []),
                        "external_servers": [
                            server.redacted_dict() for server in configuration.servers
                        ],
                        "note": (
                            "Robot, IDE, and memory providers are built in and load "
                            "without mcp.toml. external_servers contains only optional "
                            "third-party MCP servers."
                        ),
                    }
                )
            elif choice == "10":
                _print_json(
                    {
                        "skills": [
                            {
                                "id": skill.manifest.id,
                                "name": skill.manifest.name,
                                "enabled": skill.enabled,
                            }
                            for skill in SkillRepository(arguments.skill_dir).list()
                        ]
                    }
                )
            elif choice == "11":
                await _interactive_memory(arguments)
            elif choice == "12":
                await _interactive_deployment(arguments)
            elif choice == "13":
                await _service_request(arguments, {"command": "stop"})
            elif choice == "14":
                print("CLI disconnected. Any running agent service continues.")
                return 0
            elif choice == "15":
                while True:
                    step = (
                        await asyncio.to_thread(
                            input,
                            "Guide: 1 environment, 2 stop/resume, 3 text, 4 reminders, "
                            "5 help; Enter to leave: ",
                        )
                    ).strip()
                    if not step:
                        break
                    if step not in {"1", "2", "3", "4", "5"}:
                        print("Choose 1 through 5 or press Enter to skip.")
                        continue
                    await _service_request(
                        arguments, {"command": "guided_checks", "step": int(step) - 1}
                    )
            else:
                print("Please choose a number from 1 through 15.")
        except (
            AgentIPCError,
            CloudProviderError,
            KeyError,
            ModelSelectionError,
            OllamaError,
            RuntimeError,
            ValueError,
        ) as exc:
            print(f"Error: {exc}")


async def _interactive_deployment(arguments: argparse.Namespace) -> None:
    while True:
        print(
            "\nStartup Agent Deployment\n"
            "1. Install and deploy automatic startup Agent\n"
            "2. Disable and stop automatic startup Agent\n"
            "3. Show startup Agent status\n"
            "4. Back to the Interactive Tool\n"
        )
        choice = (await asyncio.to_thread(input, "Select an option: ")).strip()
        if choice == "4":
            return
        command = {
            "1": "setup",
            "2": "disable",
            "3": "status",
        }.get(choice)
        if command is None:
            print("Please choose a number from 1 through 4.")
            continue
        confirmed = command == "setup"
        if command == "setup":
            answer = (
                await asyncio.to_thread(
                    input,
                    "Type ENABLE to install, start, and enable the real-hardware Agent: ",
                )
            ).strip()
            if answer != "ENABLE":
                print("Deployment action cancelled.")
                continue
            await _stop_agent_before_deployment(arguments)
        namespace = argparse.Namespace(**vars(arguments))
        namespace.deployment_command = command
        namespace.confirm = confirmed
        namespace.lines = 100
        await asyncio.to_thread(_run_deployment_command, namespace)


async def _stop_agent_before_deployment(arguments: argparse.Namespace) -> None:
    """Release a manually started Agent before systemd takes ownership."""
    client = AgentIPCClient(arguments.service_socket)
    try:
        await client.request({"command": "status"})
    except AgentIPCError:
        return
    await client.request({"command": "stop"})
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 8.0
    while loop.time() < deadline:
        await asyncio.sleep(0.1)
        try:
            await client.request({"command": "status"})
        except AgentIPCError:
            return
    raise RuntimeError(
        "the running Agent did not stop; stop it before installing automatic startup"
    )


async def _interactive_model_selection(arguments: argparse.Namespace) -> None:
    config = load_robot_config(arguments.config)
    provider_order = {"ollama": 0, "openai": 1, "gemini": 2, "anthropic": 3}
    providers = sorted(
        (
            (provider_id, provider)
            for provider_id, provider in config.providers.items()
            if provider.enabled
        ),
        key=lambda item: (provider_order[item[1].kind], item[0]),
    )
    if not providers:
        print("No model providers are enabled in the robot configuration.")
        return
    print("\nChoose an Agent Provider")
    for index, (provider_id, provider) in enumerate(providers, start=1):
        current = " [current]" if provider_id == config.agent.default_provider else ""
        label = "Google" if provider.kind == "gemini" else provider.kind.title()
        print(f"{index}. {label} ({provider_id}){current}")
    print("0. Back")
    provider_choice = (await asyncio.to_thread(input, "Select a provider: ")).strip()
    if provider_choice == "0":
        return
    try:
        provider_id, provider = providers[int(provider_choice) - 1]
    except (ValueError, IndexError):
        print("Please select one of the displayed provider numbers.")
        return
    if provider.kind != "ollama":
        registry = ConfiguredProviderRegistry(
            arguments.config,
            SecretStore(arguments.secret_file),
        )
        status = registry.credential_status(provider_id)
        configured = status.get("configured") is True
        print(
            f"\n{provider_id} authentication is set to {provider.auth_method}. "
            f"Credential source ready: {'yes' if configured else 'not confirmed'}."
        )
        print("1. Enter API Key")
        print("2. Continue with Current API Key")
        print("0. Back")
        auth_choice = (await asyncio.to_thread(input, "Select authentication: ")).strip()
        if auth_choice == "0":
            return
        if auth_choice == "1":
            await _interactive_set_api_key(arguments, provider_id, provider.api_key_env)
        elif auth_choice != "2":
            print("Please choose 0, 1, or 2.")
            return
    models = await _available_models(arguments, provider=provider_id)
    if not models:
        print(f"No compatible {provider_id} models are available.")
        return
    print("\nAvailable Agent Models")
    for index, model in enumerate(models, start=1):
        current = " [current]" if model.get("current") is True else ""
        accepted = "accepted" if model.get("accepted") is True else "not benchmarked"
        details = " · ".join(
            str(value)
            for value in (
                model.get("parameter_size"),
                model.get("quantization"),
                _human_size(model.get("size_bytes")),
            )
            if value
        )
        suffix = f" · {details}" if details else ""
        print(f"{index}. {model['name']}{current} · {accepted}{suffix}")
    print("0. Back")
    choice = (await asyncio.to_thread(input, "Select a model: ")).strip()
    if choice == "0":
        return
    try:
        selected = models[int(choice) - 1]
    except (ValueError, IndexError):
        print("Please select one of the displayed model numbers.")
        return
    result = await _select_model(
        arguments,
        model=str(selected["name"]),
        provider=provider_id,
    )
    print(f"Agent model changed to {result['provider']}/{result['name']}.")
    if result.get("accepted") is not True:
        print(
            "This model has no accepted benchmark report. Benchmark status is "
            "informational; explicitly armed AI motion remains available through "
            "the normal IDE safety boundary."
        )


async def _interactive_set_api_key(
    arguments: argparse.Namespace,
    provider_id: str,
    api_key_env: str | None,
) -> None:
    """Collect and persist one cloud API key without echoing it."""
    if api_key_env is None:
        raise ValueError(f"{provider_id} has no API-key secret reference")
    secret = await asyncio.to_thread(
        getpass.getpass,
        f"Enter {api_key_env}: ",
    )
    confirmation = await asyncio.to_thread(
        getpass.getpass,
        f"Enter {api_key_env} again: ",
    )
    if secret != confirmation:
        raise ValueError("API key values did not match")
    SecretStore(arguments.secret_file).set(api_key_env, secret)
    persist_api_key_authentication(arguments.config, provider_id)


def _human_size(value: object) -> str | None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return None
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return None


async def _run_benchmark(arguments: argparse.Namespace) -> int:
    if arguments.benchmark_command != "ollama":
        raise AssertionError(f"unhandled benchmark command: {arguments.benchmark_command}")
    provider = OllamaProvider(
        OllamaConfig(
            base_url=arguments.base_url,
            model=arguments.model,
        )
    )
    try:
        report = await ModelBenchmark(
            provider,
            model=arguments.model,
        ).run(
            simple_prompt="Reply with one short friendly greeting.",
            tool_cases=_benchmark_cases(),
        )
        destination = report.save(arguments.output)
        output = report.model_dump(mode="json")
        output["report_path"] = str(destination)
        _print_json(output)
        return 0 if report.accepted else 1
    finally:
        await provider.close()


def _benchmark_cases() -> tuple[BenchmarkCase, ...]:
    distance = ToolDefinition(
        name="robot.distance.read",
        version="1.0.0",
        description="Read the robot's current forward distance sensor once.",
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={"type": "object"},
        risk=RiskLevel.READ_ONLY,
        default_timeout_seconds=2.0,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
    )
    search = ToolDefinition(
        name="mcp.tavily.tavily-search",
        version="1.0.0",
        description="Search the public web for current information.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        risk=RiskLevel.READ_ONLY,
        default_timeout_seconds=20.0,
        idempotent=True,
        cancellable=True,
        confirmation_required=False,
    )
    prompts = (
        ("Read the forward distance now.", distance.name),
        ("How far is the object in front of the robot?", distance.name),
        ("Check the distance sensor once.", distance.name),
        ("Is the front path clear according to the sensor?", distance.name),
        ("Give me the robot's current distance reading.", distance.name),
        ("Search the web for today's Raspberry Pi news.", search.name),
        ("Find the current weather report online.", search.name),
        ("Look up the latest official Ollama release.", search.name),
        ("Search for current public information about Qwen.", search.name),
        ("Find today's relevant technology news on the web.", search.name),
    )
    return tuple(
        BenchmarkCase(
            prompt=prompt,
            expected_tool=expected,
            tools=(distance, search),
        )
        for prompt, expected in prompts
    )


def _run_skill(arguments: argparse.Namespace, *, definitions: Any = None) -> int:
    repository = SkillRepository(arguments.skill_dir)
    command: str = arguments.skill_command
    if command == "list":
        _print_json(
            {
                "skills": [
                    {
                        "id": skill.manifest.id,
                        "name": skill.manifest.name,
                        "version": skill.manifest.version,
                        "bundled": skill.bundled,
                        "enabled": skill.enabled,
                    }
                    for skill in repository.list()
                ]
            }
        )
        return 0
    if command in {"validate", "inspect-path", "simulate-path", "install"}:
        skill = repository.load_path(arguments.path)
        if command == "validate":
            _print_json(
                {
                    "valid": True,
                    "skill": skill.manifest.id,
                    **(
                        {"live_compatibility_checked": definitions is not None}
                        if isinstance(skill.manifest, SkillManifestV2) or definitions is not None
                        else {}
                    ),
                }
            )
            return 0
        if command == "inspect-path":
            _print_json(_skill_inspection(skill))
            return 0
        if command == "simulate-path":
            _print_json(repository.simulate(skill, _json_object(arguments.input)))
            return 0
        simulation_input = (
            _json_object(arguments.simulation_input)
            if arguments.simulation_input is not None
            else None
        )
        installed = repository.install(
            arguments.path,
            ai_proposed=arguments.ai_proposed,
            confirmed=arguments.confirm,
            simulation_input=simulation_input,
            definitions=definitions,
        )
        output: dict[str, Any] = {
            "installed": installed.manifest.id,
            "path": str(installed.path),
        }
        if arguments.ai_proposed and simulation_input is not None:
            output["simulation"] = repository.simulate(installed, simulation_input)
        _print_json(output)
        return 0
    if command in {"inspect", "simulate", "enable", "disable", "remove"}:
        if command == "enable":
            repository.set_enabled(arguments.skill_id, enabled=True, definitions=definitions)
            _print_json({"skill": arguments.skill_id, "enabled": True})
            return 0
        if command == "disable":
            repository.set_enabled(arguments.skill_id, enabled=False)
            _print_json({"skill": arguments.skill_id, "enabled": False})
            return 0
        if command == "remove":
            repository.remove(arguments.skill_id, confirmed=arguments.confirm)
            _print_json({"skill": arguments.skill_id, "removed": True})
            return 0
        skill = repository.get(arguments.skill_id)
        if command == "inspect":
            _print_json(_skill_inspection(skill))
        else:
            _print_json(repository.simulate(skill, _json_object(arguments.input)))
        return 0
    raise AssertionError(f"unhandled skill command: {command}")


def _replace_server(
    configuration: MCPConfiguration,
    replacement: MCPServerConfig,
    path: Path,
) -> None:
    servers = tuple(
        replacement if server.id == replacement.id else server for server in configuration.servers
    )
    save_mcp_configuration(MCPConfiguration(servers=servers), path)


def _server_by_id(configuration: MCPConfiguration, server_id: str) -> MCPServerConfig:
    for server in configuration.servers:
        if server.id == server_id:
            return server
    raise KeyError(f"unknown MCP server: {server_id}")


def _json_object(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("--arguments must be a JSON object")
    return cast(dict[str, Any], decoded)


def _safe_error(exc: Exception) -> str:
    """Return an error type and message that never resolves secret values."""
    return f"{type(exc).__name__}: {exc}"


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _skill_inspection(skill: LoadedSkill) -> dict[str, Any]:
    return {
        "manifest": skill.manifest.model_dump(mode="json"),
        "instructions": skill.instructions,
        "path": str(skill.path),
        "bundled": skill.bundled,
        "enabled": skill.enabled,
    }
