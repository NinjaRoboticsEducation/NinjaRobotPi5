"""Phase 5 conversational-agent CLI and MCP administration entry point."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from ninjarobot_pi5_ide import RiskLevel, load_robot_config

from .benchmark import BenchmarkCase, ModelBenchmark
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
from .models import ToolCall, ToolDefinition, ToolInvocation
from .ollama import OllamaConfig, OllamaError, OllamaProvider
from .secrets import SecretStore
from .service_main import run_service
from .skills import LoadedSkill, SkillRepository, SkillValidationError
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

    session = commands.add_parser("session", help="Inspect or clear local conversations.")
    session_commands = session.add_subparsers(dest="session_command", required=True)
    session_commands.add_parser("list")
    history = session_commands.add_parser("history")
    history.add_argument("session_id")
    clear = session_commands.add_parser("clear")
    clear.add_argument("session_id")

    motion = commands.add_parser("motion", help="Manage one-time session motion consent.")
    motion_commands = motion.add_subparsers(dest="motion_command", required=True)
    arm = motion_commands.add_parser("arm")
    arm.add_argument("--session", default="local-cli")
    arm.add_argument("--confirm", action="store_true")
    disarm = motion_commands.add_parser("disarm")
    disarm.add_argument("--session", default="local-cli")

    model = commands.add_parser("model", help="List or select an agent model.")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_commands.add_parser("list", help="List locally installed provider models.")
    model_commands.add_parser("current", help="Show the active provider and model.")
    select_model = model_commands.add_parser("select", help="Select an installed model.")
    select_model.add_argument("model_name")
    select_model.add_argument("--provider")

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
    ) as exc:
        parser.error(_safe_error(exc))
    raise SystemExit(exit_code)


async def _run(arguments: argparse.Namespace) -> int:
    if arguments.command is None:
        return await _interactive(arguments)
    if arguments.command == "chat":
        return await _run_chat_command(arguments)
    if arguments.command == "status":
        return await _service_request(arguments, {"command": "status"})
    if arguments.command == "service":
        return await _run_service_command(arguments)
    if arguments.command == "session":
        return await _run_session_command(arguments)
    if arguments.command == "motion":
        return await _run_motion_command(arguments)
    if arguments.command == "model":
        return await _run_model_command(arguments)
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

    if arguments.command == "skill":
        return _run_skill(arguments)
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
            print(
                "/help  /exit  /clear  /status  /resume  /arm  /disarm  "
                "/confirm <request>\nOrdinary text is sent to NinjaRobot."
            )
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
        if text == "/resume":
            await _resume_from_chat(arguments, session_id=session_id)
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
    log_path = DEFAULT_SERVICE_LOG.expanduser()
    log_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    for _ in range(100):
        if process.poll() is not None:
            raise AgentIPCError(f"agent service exited during startup; inspect {log_path}")
        try:
            status = await client.request({"command": "status"})
        except AgentIPCError:
            await asyncio.sleep(0.1)
            continue
        _print_json(
            {
                "started": True,
                "pid": process.pid,
                "real_hardware": namespace.real,
                "log": str(log_path),
                "status": status["data"],
            }
        )
        return 0
    process.terminate()
    raise AgentIPCError(f"agent service did not become ready; inspect {log_path}")


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
        _print_json({"models": await _available_models(arguments)})
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


async def _available_models(arguments: argparse.Namespace) -> list[dict[str, Any]]:
    client = AgentIPCClient(arguments.service_socket)
    try:
        response = await client.request({"command": "models"})
    except AgentIPCError:
        return [entry.model_dump(mode="json") for entry in await _offline_ollama_catalog(arguments)]
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
        catalog = await _offline_ollama_catalog(arguments)
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
        persist_model_selection(arguments.config, selected_provider, model)
        return {
            **selected.model_copy(update={"current": True}).model_dump(mode="json"),
            "service_running": False,
        }
    data = response["data"]
    if not isinstance(data, dict):
        raise AgentIPCError("agent service model selection response is malformed")
    return {**data, "service_running": True}


async def _offline_ollama_catalog(
    arguments: argparse.Namespace,
) -> tuple[ModelCatalogEntry, ...]:
    provider_id, provider_config = _configured_provider(arguments)
    if provider_config.kind != "ollama":
        raise ModelSelectionError(
            f"provider kind '{provider_config.kind}' is configured but not implemented"
        )
    provider = OllamaProvider(
        OllamaConfig(
            model=provider_config.model,
            base_url=provider_config.base_url or "http://127.0.0.1:11434",
        )
    )
    benchmarks = BenchmarkRegistry(arguments.benchmark_dir)
    try:
        return tuple(
            ModelCatalogEntry(
                provider=provider_id,
                name=model.name,
                size_bytes=model.size_bytes,
                parameter_size=model.parameter_size,
                quantization=model.quantization,
                family=model.family,
                modified_at=model.modified_at,
                current=model.name == provider_config.model,
                accepted=benchmarks.accepted(model.name),
            )
            for model in await provider.list_models()
        )
    finally:
        await provider.close()


def _configured_provider(arguments: argparse.Namespace) -> tuple[str, Any]:
    config = load_robot_config(arguments.config)
    provider_id = config.agent.default_provider
    return provider_id, config.providers[provider_id]


async def _service_request(
    arguments: argparse.Namespace,
    payload: dict[str, Any],
) -> int:
    result = await AgentIPCClient(arguments.service_socket).request(payload)
    _print_json(result["data"])
    return 0


async def _interactive(arguments: argparse.Namespace) -> int:
    while True:
        print(
            "\nNinjaRobotAgent Interactive Tool\n"
            "1. Chat with NinjaRobot\n"
            "2. Agent Status\n"
            "3. Change Agent Model\n"
            "4. Start Agent Service\n"
            "5. Conversation Sessions\n"
            "6. Start Web Interface\n"
            "7. Web Interface Status\n"
            "8. Stop Web Interface\n"
            "9. Export Browser Trust Certificate\n"
            "10. MCP Tools\n"
            "11. Agent Skills\n"
            "12. Stop Agent Service\n"
            "13. Quit CLI\n"
        )
        choice = (await asyncio.to_thread(input, "Select an option: ")).strip()
        try:
            if choice == "1":
                await _chat_repl(arguments, session_id="local-cli")
            elif choice == "2":
                await _service_request(arguments, {"command": "status"})
            elif choice == "3":
                await _interactive_model_selection(arguments)
            elif choice == "4":
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
            elif choice == "5":
                await _service_request(arguments, {"command": "sessions"})
            elif choice == "6":
                await _service_request(arguments, {"command": "web_start"})
            elif choice == "7":
                await _service_request(arguments, {"command": "web_status"})
            elif choice == "8":
                await _service_request(arguments, {"command": "web_stop"})
            elif choice == "9":
                output = export_local_ca_certificate(
                    arguments.web_certificate,
                    arguments.web_key,
                    DEFAULT_WEB_CA_EXPORT,
                )
                _print_json(
                    {
                        "exported": str(output),
                        "contains_private_key": False,
                        "next_step": (
                            "Copy this file to your phone or computer, install it, "
                            "and enable certificate trust."
                        ),
                    }
                )
            elif choice == "10":
                configuration = load_mcp_configuration(arguments.mcp_config)
                _print_json(
                    {"servers": [server.redacted_dict() for server in configuration.servers]}
                )
            elif choice == "11":
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
            elif choice == "12":
                await _service_request(arguments, {"command": "stop"})
            elif choice == "13":
                print("CLI disconnected. Any running agent service continues.")
                return 0
            else:
                print("Please choose a number from 1 through 13.")
        except (
            AgentIPCError,
            KeyError,
            ModelSelectionError,
            OllamaError,
            ValueError,
        ) as exc:
            print(f"Error: {exc}")


async def _interactive_model_selection(arguments: argparse.Namespace) -> None:
    models = await _available_models(arguments)
    if not models:
        print("No local Ollama models are installed.")
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
        provider=str(selected["provider"]),
    )
    print(f"Agent model changed to {result['provider']}/{result['name']}.")
    if result.get("accepted") is not True:
        print(
            "This model has no accepted benchmark report. Benchmark status is "
            "informational; explicitly armed AI motion remains available through "
            "the normal IDE safety boundary."
        )


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


def _run_skill(arguments: argparse.Namespace) -> int:
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
            _print_json({"valid": True, "skill": skill.manifest.id})
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
            repository.set_enabled(arguments.skill_id, enabled=True)
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
