"""Foreground entry point for the single-owner NinjaRobot agent service."""

from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path

from ninjarobot_pi5_ide import build_robot_ide_client, load_robot_config

from .agent_loop import AgentLoop, AgentLoopConfig
from .cloud_registry import ConfiguredProviderRegistry
from .events import AgentEventType, EventBroker
from .ipc import AgentIPCServer
from .mcp_client import MCPToolProvider
from .mcp_config import load_mcp_configuration
from .model_selection import (
    BenchmarkRegistry,
    ModelManager,
    persist_model_selection,
)
from .persistence import ConversationStore
from .policy import CameraGrantManager, MotionArmManager, PolicyEngine
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
    active_model = arguments.model or provider_config.model
    provider_registry = ConfiguredProviderRegistry(
        arguments.config,
        secrets,
        ollama_base_url_override=arguments.base_url,
    )

    model = ModelManager(
        active_provider_id=provider_id,
        active_model=active_model,
        active_provider=provider_registry.create(provider_id, active_model),
        registrations=provider_registry.registrations(),
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
        fallback_provider_ids=config.agent.fallback_providers,
    )
    store = ConversationStore(arguments.database, retention_days=7)
    arms = MotionArmManager()
    camera_grants = CameraGrantManager()
    events = EventBroker()
    policy = PolicyEngine(arms, camera_grants)

    def runtime_state(
        session_id: str,
        lease_id: str | None,
    ) -> dict[str, object]:
        camera_status = camera_grants.status(session_id, lease_id=lease_id)
        camera_authorized = bool(camera_status["authorized_for_next_preview"])
        return {
            "session_id": session_id,
            "controller_lease": lease_id,
            "execution_mode": "real" if arguments.real else "simulation",
            "physical_hardware_enabled": arguments.real,
            "motion_authorization": {
                "armed": arms.is_armed(session_id, lease_id=lease_id),
                "meaning": (
                    "trusted motion tools may execute for this session"
                    if arms.is_armed(session_id, lease_id=lease_id)
                    else "trusted motion tools must not execute for this session"
                ),
            },
            "motion_armed": arms.is_armed(session_id, lease_id=lease_id),
            "ai_camera": {
                **camera_status,
                "meaning": (
                    "The newest numbered grant authorizes robot.camera.preview "
                    "to capture one temporary photo now."
                    if camera_authorized
                    else "AI camera preview is not currently authorized. The user "
                    "may issue another one-photo grant in this same session."
                ),
                "required_tool": "robot.camera.preview",
            },
            "simulated": not arguments.real,
        }

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
        runtime_state=runtime_state,
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
