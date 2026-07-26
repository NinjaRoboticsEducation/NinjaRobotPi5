"""Interactive and scriptable Phase 4 NinjaRobot IDE tool."""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import click

from .behavior_assets import BehaviorAssetRepository
from .behavior_models import (
    FACE_EXPRESSIONS,
    MELODIES,
    BehaviorDefinition,
    BehaviorStage,
    DriveOperation,
    FaceOperation,
    TextOperation,
)
from .config import RobotConfig
from .config_import import (
    DEFAULT_USER_CONFIG,
    discover_pi5_configs,
    import_pi5_configs,
    load_effective_config,
    save_robot_config,
)
from .interactive_tool import loop_final_face, run_interactive
from .robot import RobotAssembly
from .runtime_control import ActiveBehaviorRegistry
from .safety import SafetyStateStore
from .simulation import (
    SimulatedBuzzerDriver,
    SimulatedDisplayDriver,
    SimulatedDistanceSensor,
    simulated_servo_runtime,
)


class ToolContext:
    """Configuration shared by Click subcommands."""

    def __init__(self, config_path: Path | None) -> None:
        self.config_path = config_path

    def config(self) -> RobotConfig:
        return load_effective_config(self.config_path)


class FriendlyGroup(click.Group):
    """Convert expected validation/runtime failures into concise CLI errors."""

    def invoke(self, context: click.Context) -> Any:
        try:
            return super().invoke(context)
        except (click.ClickException, click.Abort, click.exceptions.Exit):
            raise
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc


@click.group(cls=FriendlyGroup, invoke_without_command=True)
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path, dir_okay=False),
    help="V4 TOML configuration. Defaults to the private user config, then project example.",
)
@click.pass_context
def main(context: click.Context, config_path: Path | None) -> None:
    """Inspect, simulate, create, run, and stop NinjaRobot behaviors."""
    context.obj = ToolContext(config_path)
    if context.invoked_subcommand is None:
        _interactive_menu(context.obj)


@main.group("hardware")
def hardware_group() -> None:
    """Inspect the configured hardware without changing standalone settings."""


@hardware_group.command("status")
@click.option("--real", is_flag=True, help="Probe configured hardware without moving or recording.")
@click.pass_obj
def hardware_status(tool: ToolContext, real: bool) -> None:
    """Show wiring, safety gates, calibration path, and optional safe health probes."""
    config = tool.config()
    result: dict[str, Any] = {
        "mode": "real-safe-probe" if real else "configuration-only",
        "servo_endpoints": list(config.hardware.servos.endpoints),
        "servo_roles": config.behaviors.servo_roles,
        "calibration_file": str(Path(config.hardware.servos.calibration_file).expanduser()),
        "calibration_file_exists": Path(config.hardware.servos.calibration_file)
        .expanduser()
        .is_file(),
        "motion_enabled": config.hardware.servos.motion_enabled,
        "group_motion_enabled": config.hardware.servos.group_motion_enabled,
        "obstacle_threshold_mm": config.behaviors.obstacle_threshold_mm,
        "safety": SafetyStateStore(config.behaviors.safety_state_file).read(),
    }
    if real:
        result["components"] = asyncio.run(_real_health(config))
    _echo_json(result)


@main.group("config")
def config_group() -> None:
    """Discover and import existing standalone Pi5 hardware settings."""


@config_group.command("discover")
def config_discover() -> None:
    """List the read-only standalone configuration candidates."""
    _echo_json(
        [
            {
                "library": item.library,
                "path": str(item.path),
                "exists": item.exists,
            }
            for item in discover_pi5_configs()
        ]
    )


@config_group.command("import")
@click.option(
    "--destination",
    type=click.Path(path_type=Path, dir_okay=False),
    default=DEFAULT_USER_CONFIG,
    show_default=True,
)
@click.option("--apply", is_flag=True, help="Write the previewed private V4 TOML file.")
@click.option("--overwrite", is_flag=True, help="Replace an existing destination.")
@click.pass_obj
def config_import(
    tool: ToolContext,
    destination: Path,
    apply: bool,
    overwrite: bool,
) -> None:
    """Preview or apply imports; standalone Pi5 files remain untouched."""
    config, imported = import_pi5_configs(tool.config(), discover_pi5_configs())
    result: dict[str, Any] = {
        "destination": str(destination.expanduser()),
        "applied": False,
        "imported": imported,
        "configuration": config.model_dump(mode="json"),
    }
    if apply:
        result["destination"] = str(save_robot_config(config, destination, overwrite=overwrite))
        result["applied"] = True
    _echo_json(result)


@main.group("behavior")
def behavior_group() -> None:
    """List, inspect, simulate, run, create, validate, or stop behaviors."""


@behavior_group.command("list")
@click.option(
    "--category",
    type=click.Choice(["all", "expression", "movement"]),
    default="all",
    show_default=True,
)
@click.pass_obj
def behavior_list(tool: ToolContext, category: str) -> None:
    """List bundled and private validated behaviors."""
    repository = _repository(tool.config())
    _echo_json(
        [
            {
                "name": definition.name,
                "category": definition.category,
                "description": definition.description,
                "contains_motion": definition.contains_motion,
                "resources": definition.required_resources,
            }
            for definition in repository.list(category)
        ]
    )


@behavior_group.command("show")
@click.argument("name")
@click.pass_obj
def behavior_show(tool: ToolContext, name: str) -> None:
    """Show one validated behavior definition."""
    _echo_json(_repository(tool.config()).load(name))


@behavior_group.command("health")
@click.option("--real", is_flag=True, help="Probe real expression devices without output.")
@click.pass_obj
def behavior_health(tool: ToolContext, real: bool) -> None:
    """Check behavior components without running an action."""
    config = tool.config()
    if real:
        components = asyncio.run(_real_health(config))
    else:
        components = asyncio.run(_simulated_health(config))
    _echo_json(
        {
            "mode": "real-safe-probe" if real else "simulation",
            "components": components,
            "safety": SafetyStateStore(config.behaviors.safety_state_file).read(),
        }
    )


@behavior_group.command("simulate")
@click.argument("name")
@click.option(
    "--duration",
    type=click.FloatRange(min=0.1, max=30.0),
    default=2.0,
    show_default=True,
    help="Simulation duration for a continuous movement.",
)
@click.pass_obj
def behavior_simulate(tool: ToolContext, name: str, duration: float) -> None:
    """Run a hardware-free preview; continuous motion ends after duration."""
    config = tool.config()
    definition = _repository(config).load(name)
    result = asyncio.run(_run_simulated(config, definition, duration))
    _echo_json(result)


@behavior_group.command("run")
@click.argument("name")
@click.option("--real", is_flag=True, help="Use configured Raspberry Pi hardware.")
@click.option(
    "--confirm-motion",
    is_flag=True,
    help="Confirm that the area and power path are ready for physical movement.",
)
@click.option(
    "--duration",
    type=click.FloatRange(min=0.1, max=30.0),
    default=2.0,
    show_default=True,
    help="Simulation-only duration for a continuous movement.",
)
@click.option(
    "--loop",
    "loop_face",
    is_flag=True,
    help="Keep the final face animated until Ctrl+C; real mode only.",
)
@click.pass_obj
def behavior_run(
    tool: ToolContext,
    name: str,
    real: bool,
    confirm_motion: bool,
    duration: float,
    loop_face: bool,
) -> None:
    """Run a behavior; simulation is the default and real motion needs confirmation."""
    config = tool.config()
    definition = _repository(config).load(name)
    if loop_face:
        definition = loop_final_face(definition)
    if not real:
        _echo_json(asyncio.run(_run_simulated(config, definition, duration)))
        return
    if definition.contains_motion and not confirm_motion:
        raise click.UsageError("real movement requires --confirm-motion")
    registry = ActiveBehaviorRegistry()
    registry.register(definition.name)
    try:
        result = asyncio.run(_run_real(config, definition))
    except KeyboardInterrupt:
        _echo_json(asyncio.run(_full_stop_fresh(config, "ctrl_c")))
        raise click.Abort() from None
    finally:
        registry.clear()
    _echo_json(result)


@behavior_group.command("validate")
@click.argument("asset_file", type=click.Path(path_type=Path, dir_okay=False, exists=True))
def behavior_validate(asset_file: Path) -> None:
    """Validate a JSON behavior without saving or running it."""
    definition = _definition_from_file(asset_file)
    _echo_json(
        {
            "valid": True,
            "name": definition.name,
            "category": definition.category,
            "contains_motion": definition.contains_motion,
            "resources": definition.required_resources,
        }
    )


@behavior_group.command("create")
@click.option("--from-file", type=click.Path(path_type=Path, dir_okay=False, exists=True))
@click.option("--name")
@click.option("--description")
@click.option(
    "--face",
    type=click.Choice(list(FACE_EXPRESSIONS)),
)
@click.option("--text")
@click.option(
    "--melody",
    type=click.Choice(list(MELODIES)),
)
@click.option("--left-target", type=click.FloatRange(min=-90.0, max=90.0))
@click.option("--right-target", type=click.FloatRange(min=-90.0, max=90.0))
@click.option(
    "--obstacle-policy",
    type=click.Choice(["front_guarded", "warn_only"]),
    default="front_guarded",
    show_default=True,
)
@click.option("--overwrite", is_flag=True)
@click.option("--confirm-save", is_flag=True, help="Explicitly approve saving the preview.")
@click.pass_obj
def behavior_create(
    tool: ToolContext,
    from_file: Path | None,
    name: str | None,
    description: str | None,
    face: str | None,
    text: str | None,
    melody: str | None,
    left_target: float | None,
    right_target: float | None,
    obstacle_policy: str,
    overwrite: bool,
    confirm_save: bool,
) -> None:
    """Create a private action after schema validation and simulation preview."""
    config = tool.config()
    if from_file is not None:
        definition = _definition_from_file(from_file)
    else:
        definition = _definition_from_options(
            name=name,
            description=description,
            face=face,
            text=text,
            melody=melody,
            left_target=left_target,
            right_target=right_target,
            obstacle_policy=obstacle_policy,
        )
    preview = asyncio.run(_run_simulated(config, definition, 2.0))
    _echo_json({"preview": preview, "definition": definition})
    approved = confirm_save or click.confirm("Save this private behavior?", default=False)
    if not approved:
        raise click.Abort()
    path = _repository(config).save_user(definition, overwrite=overwrite)
    _echo_json({"saved": True, "path": str(path), "name": definition.name})


@behavior_group.command("delete")
@click.argument("name")
@click.option("--confirm", is_flag=True, help="Confirm deletion of the private behavior.")
@click.pass_obj
def behavior_delete(tool: ToolContext, name: str, confirm: bool) -> None:
    """Delete one private user behavior; bundled defaults remain read-only."""
    if not confirm:
        raise click.UsageError("behavior delete requires --confirm")
    repository = _repository(tool.config())
    repository.delete_user(name)
    _echo_json({"deleted": True, "name": name})


@behavior_group.command("stop")
@click.pass_obj
def behavior_stop(tool: ToolContext) -> None:
    """Request full cleanup; no motion confirmation is required for stopping."""
    registry = ActiveBehaviorRegistry()
    if registry.request_stop():
        _echo_json({"stop_requested": True, "method": "signal-active-process"})
        return
    _echo_json(asyncio.run(_full_stop_fresh(tool.config(), "operator_stop")))


@main.group("motion")
def motion_group() -> None:
    """Resume a Level 1 movement latch."""


@motion_group.command("resume")
@click.option("--confirm", is_flag=True, help="Confirm the obstacle or power issue is clear.")
@click.pass_obj
def motion_resume(tool: ToolContext, confirm: bool) -> None:
    """Clear only the motion latch; a system latch remains blocked."""
    if not confirm:
        raise click.UsageError("motion resume requires --confirm")
    state = SafetyStateStore(tool.config().behaviors.safety_state_file)
    _echo_json(state.clear_motion())


@main.group("system")
def system_group() -> None:
    """Resume a driver-failure Level 2 latch."""


@system_group.command("resume")
@click.option("--confirm", is_flag=True, help="Confirm a real hardware health probe.")
@click.pass_obj
def system_resume(tool: ToolContext, confirm: bool) -> None:
    """Probe every configured device and clear both latches only when ready."""
    if not confirm:
        raise click.UsageError("system resume requires --confirm")
    config = tool.config()
    robot = RobotAssembly(config=config, simulated=False)

    async def resume_and_close() -> Any:
        try:
            return await robot.resume_system(confirmed=True)
        finally:
            await robot.close()

    _echo_json(asyncio.run(resume_and_close()))


def _interactive_menu(tool: ToolContext) -> None:
    asyncio.run(
        run_interactive(
            tool.config(),
            simulation_runner=_run_simulated,
        )
    )


async def _real_health(config: RobotConfig) -> dict[str, Any]:
    robot = RobotAssembly(config=config, simulated=False)
    try:
        await asyncio.gather(
            robot.behaviors.start(),
            robot.servo.start(),
            robot.distance.start(),
            robot.camera.start(),
            robot.microphone.start(),
        )
        expression = await robot.behaviors.health()
        return {
            **expression,
            "servo": (await robot.servo.health()).value,
            "distance": (await robot.distance.health()).value,
            "camera": (await robot.camera.health()).value,
            "microphone": (await robot.microphone.health()).value,
            "servo_status": await robot.servo.status(),
        }
    finally:
        await robot.close()


async def _run_real(
    config: RobotConfig,
    definition: BehaviorDefinition,
) -> dict[str, Any]:
    robot = RobotAssembly(config=config, simulated=False)
    try:
        await robot.start()
        return await robot.run_definition(definition)
    finally:
        await robot.close()


async def _run_simulated(
    config: RobotConfig,
    definition: BehaviorDefinition,
    duration: float,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ninjarobot-simulation-") as directory:
        simulation_config = _simulation_config(config, Path(directory))
        robot = RobotAssembly(
            config=simulation_config,
            display_factory=SimulatedDisplayDriver,
            buzzer_factory=SimulatedBuzzerDriver,
            servo_factory=simulated_servo_runtime,
            distance_factory=SimulatedDistanceSensor,
            melody_provider=lambda _name: ((440, 0.01), (660, 0.01)),
            undervoltage_provider=lambda: False,
            simulated=True,
        )
        bounded = _bounded_simulation(definition, duration)
        try:
            await robot.start()
            return await robot.behaviors.run(bounded)
        finally:
            await robot.close()


async def _full_stop_fresh(config: RobotConfig, reason: str) -> dict[str, Any]:
    robot = RobotAssembly(config=config, simulated=False)
    try:
        await asyncio.gather(
            robot.servo.start(),
            robot.distance.start(),
            robot.buzzer.start(),
            return_exceptions=True,
        )
        return await robot.system_safety.full_stop(reason, latch=False)
    finally:
        await robot.close()


async def _simulated_health(config: RobotConfig) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="ninjarobot-simulation-") as directory:
        simulation_config = _simulation_config(config, Path(directory))
        robot = RobotAssembly(
            config=simulation_config,
            display_factory=SimulatedDisplayDriver,
            buzzer_factory=SimulatedBuzzerDriver,
            servo_factory=simulated_servo_runtime,
            distance_factory=SimulatedDistanceSensor,
            melody_provider=lambda _name: ((440, 0.01),),
            undervoltage_provider=lambda: False,
            simulated=True,
        )
        try:
            await asyncio.gather(
                robot.behaviors.start(),
                robot.servo.start(),
                robot.distance.start(),
            )
            expression = await robot.behaviors.health()
            return {
                **expression,
                "servo": (await robot.servo.health()).value,
                "distance": (await robot.distance.health()).value,
            }
        finally:
            await robot.close()


def _simulation_config(config: RobotConfig, directory: Path) -> RobotConfig:
    payload = config.model_dump(mode="python")
    payload["hardware"]["servos"]["motion_enabled"] = True
    payload["hardware"]["servos"]["group_motion_enabled"] = True
    payload["behaviors"]["user_directory"] = str(directory / "behaviors")
    payload["behaviors"]["safety_state_file"] = str(directory / "safety.json")
    payload["behaviors"]["system_stopped_display_seconds"] = 0.0
    return RobotConfig.model_validate(payload)


def _bounded_simulation(
    definition: BehaviorDefinition,
    duration: float,
) -> BehaviorDefinition:
    stages: list[BehaviorStage] = []
    for stage in definition.stages:
        operations = tuple(
            operation.model_copy(update={"hold_seconds": duration})
            if isinstance(operation, (DriveOperation, FaceOperation, TextOperation))
            and operation.hold_seconds is None
            else operation
            for operation in stage.operations
        )
        stages.append(stage.model_copy(update={"operations": operations}))
    return definition.model_copy(update={"stages": tuple(stages)})


def _repository(config: RobotConfig) -> BehaviorAssetRepository:
    return BehaviorAssetRepository(config.behaviors.user_directory)


def _definition_from_file(path: Path) -> BehaviorDefinition:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"unable to read behavior JSON: {exc}") from exc
    return BehaviorDefinition.model_validate(payload)


def _definition_from_options(
    *,
    name: str | None,
    description: str | None,
    face: str | None,
    text: str | None,
    melody: str | None,
    left_target: float | None,
    right_target: float | None,
    obstacle_policy: str,
) -> BehaviorDefinition:
    name = name or click.prompt("Behavior name")
    description = description or click.prompt("Short description")
    if (
        face is None
        and text is None
        and melody is None
        and left_target is None
        and right_target is None
    ):
        category = click.prompt(
            "Action type",
            type=click.Choice(["expression", "movement"]),
            default="expression",
        )
        display_kind = click.prompt(
            "Display operation",
            type=click.Choice(["face", "text", "none"]),
            default="face",
        )
        if display_kind == "face":
            face = click.prompt(
                "Face",
                type=click.Choice(["idle", "happy", "thinking", "success", "warning", "error"]),
                default="happy",
            )
        elif display_kind == "text":
            text = click.prompt("Text")
        melody_choice = click.prompt(
            "Melody",
            type=click.Choice(
                [
                    "none",
                    "happy",
                    "sad",
                    "exciting",
                    "angry",
                    "confusing",
                    "idle",
                    "surprising",
                ]
            ),
            default="none",
        )
        melody = None if melody_choice == "none" else melody_choice
        if category == "movement":
            left_target = click.prompt(
                "Left motor target (-90 through 90)",
                type=click.FloatRange(min=-90.0, max=90.0),
            )
            right_target = click.prompt(
                "Right motor target (-90 through 90)",
                type=click.FloatRange(min=-90.0, max=90.0),
            )
    if face is not None and text is not None:
        raise click.UsageError("choose either --face or --text, not both")
    operations: list[dict[str, Any]] = []
    if face is not None:
        operations.append({"kind": "face", "expression": face, "hold_seconds": 2.0})
    elif text is not None:
        operations.append({"kind": "text", "text": text, "hold_seconds": 2.0})
    if melody is not None:
        operations.append({"kind": "melody", "melody": melody})
    targets_supplied = left_target is not None or right_target is not None
    if targets_supplied:
        if left_target is None or right_target is None:
            raise click.UsageError("movement creation requires both motor targets")
        operations.append(
            {
                "kind": "drive",
                "targets": {
                    "left_motor": left_target,
                    "right_motor": right_target,
                },
                "obstacle_policy": obstacle_policy,
            }
        )
    if not operations:
        raise click.UsageError("provide --face, --text, --melody, or both motor target options")
    category = "movement" if targets_supplied else "expression"
    return BehaviorDefinition.model_validate(
        {
            "schema_version": 1,
            "name": name,
            "description": description,
            "category": category,
            "stages": [{"name": "stage_1", "operations": operations}],
        }
    )


def _echo_json(value: Any) -> None:
    click.echo(json.dumps(value, indent=2, sort_keys=True, default=_json_default))


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")
