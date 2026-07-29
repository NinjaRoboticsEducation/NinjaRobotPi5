"""Foreground entry point for the single-owner NinjaRobot agent service."""

from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path

from ninjarobot_pi5_ide import build_robot_ide_client, load_robot_config

from .agent_loop import AgentLoop, AgentLoopConfig
from .events import AgentEventType, EventBroker
from .ipc import AgentIPCServer
from .mcp_client import MCPToolProvider
from .mcp_config import load_mcp_configuration
from .model_selection import (
    BenchmarkRegistry,
    ModelCatalogEntry,
    ModelManager,
    ProviderRegistration,
    persist_model_selection,
)
from .ollama import OllamaConfig, OllamaProvider
from .persistence import ConversationStore
from .policy import MotionArmManager, PolicyEngine
from .presentation import RobotPresentationController
from .prompts import PromptComposer
from .recovery import RecoveryPolicy
from .runtime import AgentRuntime
from .secrets import SecretStore
from .service import ServiceOwnership
from .skills import SkillRepository
from .tools import IDEToolProvider, ToolProvider, ToolRegistry
from .web_app import WebServerManager, create_web_app
from .web_control import ControllerLeaseManager, WebRobotController


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the NinjaRobot agent service.")
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mcp-config", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    parser.add_argument("--skill-dir", type=Path, required=True)
    parser.add_argument("--whisper-command", type=Path, required=True)
    parser.add_argument("--whisper-model", type=Path, required=True)
    parser.add_argument("--whisper-threads", type=int, default=4)
    parser.add_argument("--web-host", default="0.0.0.0")
    parser.add_argument("--web-port", type=int, default=8443)
    parser.add_argument("--web-certificate", type=Path, required=True)
    parser.add_argument("--web-key", type=Path, required=True)
    parser.add_argument("--benchmark-dir", type=Path, required=True)
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--real", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    arguments = build_parser().parse_args(argv)
    asyncio.run(run_service(arguments))


async def run_service(arguments: argparse.Namespace) -> None:
    """Build all resources once and serve until a stop request or signal."""
    config = load_robot_config(arguments.config)
    ide = build_robot_ide_client(
        config,
        ledger_path=arguments.ledger,
        simulated=not arguments.real,
        whisper_command=arguments.whisper_command,
        whisper_model=arguments.whisper_model,
        whisper_threads=arguments.whisper_threads,
    )
    providers: list[ToolProvider] = [IDEToolProvider(ide)]
    optional_ids: set[str] = set()
    secrets = SecretStore(arguments.secret_file)
    for server_config in load_mcp_configuration(arguments.mcp_config).servers:
        if not server_config.enabled:
            continue
        provider = MCPToolProvider(server_config, secrets)
        providers.append(provider)
        optional_ids.add(provider.provider_id)
    tools = ToolRegistry(
        providers,
        optional_provider_ids=optional_ids,
    )
    provider_id = config.agent.default_provider
    provider_config = config.providers[provider_id]
    if provider_config.kind != "ollama":
        raise RuntimeError(
            f"provider kind '{provider_config.kind}' is configured but not implemented"
        )
    active_model = arguments.model or provider_config.model
    base_url = arguments.base_url or provider_config.base_url or "http://127.0.0.1:11434"

    def ollama_factory(model_name: str) -> OllamaProvider:
        return OllamaProvider(OllamaConfig(model=model_name, base_url=base_url))

    async def ollama_catalog() -> tuple[ModelCatalogEntry, ...]:
        catalog_provider = ollama_factory(active_model)
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
                )
                for model in await catalog_provider.list_models()
            )
        finally:
            await catalog_provider.close()

    model = ModelManager(
        active_provider_id=provider_id,
        active_model=active_model,
        active_provider=ollama_factory(active_model),
        registrations=(
            ProviderRegistration(
                provider_id=provider_id,
                factory=ollama_factory,
                catalog=ollama_catalog,
            ),
        ),
        benchmarks=BenchmarkRegistry(
            getattr(
                arguments,
                "benchmark_dir",
                Path("~/.local/share/ninjarobot_pi5/benchmarks"),
            )
        ),
        selection_writer=lambda selected_provider, selected_model: persist_model_selection(
            arguments.config,
            selected_provider,
            selected_model,
        ),
    )
    store = ConversationStore(arguments.database, retention_days=7)
    arms = MotionArmManager()
    events = EventBroker()
    policy = PolicyEngine(arms)
    loop = AgentLoop(
        provider=model,
        tools=tools,
        policy=policy,
        recovery=RecoveryPolicy(),
        store=store,
        prompts=PromptComposer(),
        events=events,
        config=AgentLoopConfig(
            max_model_turns=config.agent.max_model_turns,
            max_tool_calls=config.agent.max_tool_calls,
            request_timeout_seconds=config.agent.request_timeout_seconds,
            model_inactivity_timeout_seconds=(config.agent.model_inactivity_timeout_seconds),
        ),
        runtime_state=lambda session_id, lease_id: {
            "session_id": session_id,
            "controller_lease": lease_id,
            "motion_armed": arms.is_armed(session_id, lease_id=lease_id),
            "simulated": not arguments.real,
        },
        presentation=RobotPresentationController(ide),
    )
    runtime = AgentRuntime(
        provider=model,
        tools=tools,
        store=store,
        loop=loop,
        policy=policy,
        motion_arms=arms,
        skills=SkillRepository(arguments.skill_dir),
        events=events,
        model_manager=model,
    )
    web_controller = WebRobotController(runtime)
    leases = ControllerLeaseManager(on_revoke=web_controller.lease_revoked)
    web_app = create_web_app(
        runtime=runtime,
        controller=web_controller,
        leases=leases,
        static_directory=Path(__file__).with_name("web_static"),
    )
    web = WebServerManager(
        app=web_app,
        leases=leases,
        host=arguments.web_host,
        port=arguments.web_port,
        certificate_path=arguments.web_certificate,
        key_path=arguments.web_key,
    )
    server = AgentIPCServer(
        runtime=runtime,
        socket_path=arguments.socket,
        ownership=ServiceOwnership(arguments.lock),
        web=web,
    )
    loop_object = asyncio.get_running_loop()
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        loop_object.add_signal_handler(signal_number, server.request_stop)
    await server.start()
    try:
        await ide.start_liveliness()
        await events.publish(
            AgentEventType.SERVICE,
            "Startup greeting completed; silent idle animation is active.",
        )
    except Exception as exc:
        await events.publish(
            AgentEventType.ERROR,
            "Startup greeting failed; the agent service remains available.",
            data={"error": f"{type(exc).__name__}: {exc}"},
        )
    try:
        await server.serve()
    finally:
        await server.close()


if __name__ == "__main__":
    main()
