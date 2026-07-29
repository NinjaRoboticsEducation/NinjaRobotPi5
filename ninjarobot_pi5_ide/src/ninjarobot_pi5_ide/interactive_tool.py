"""Blessed-style direct-control menus for the NinjaRobot IDE tool."""

from __future__ import annotations

import asyncio
import json
import platform
import sys
import textwrap
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import asdict, is_dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

import click
from blessed import Terminal

from .behavior_assets import BehaviorAssetRepository
from .behavior_models import (
    FACE_EXPRESSIONS,
    MELODIES,
    BehaviorDefinition,
    FaceOperation,
)
from .config import RobotConfig
from .robot import RobotAssembly
from .runtime_control import ActiveBehaviorRegistry
from .safety import SafetyStateStore

SimulationRunner = Callable[
    [RobotConfig, BehaviorDefinition, float],
    Coroutine[Any, Any, dict[str, Any]],
]

FACE_MENU: tuple[tuple[str, str], ...] = (
    ("happy", "A bright smile with the Happy melody."),
    ("idle", "A calm resting face with the Idle melody."),
    ("laughing", "A laughing animation with the Laughing melody."),
    ("sad", "A sad face with the Sad melody."),
    ("cry", "A crying animation with the Cry melody."),
    ("angry", "An angry face with the Angry melody."),
    ("surprising", "A surprised face with the Surprising melody."),
    ("sleepy", "A sleepy animation with the Sleepy melody."),
    ("speaking", "A speaking animation with the Speaking melody."),
    ("shy", "A shy face with the Shy melody."),
    ("scary", "A scary face with the Scary melody."),
    ("exciting", "An excited face with the Exciting melody."),
    ("confusing", "A confused face with the Confusing melody."),
    ("thinking", "A thinking face with the Confusing melody."),
    ("curious", "A curious face with the Confusing melody."),
)

MOVEMENT_MENU: tuple[tuple[str, str], ...] = (
    ("move_forward", "Drive forward with a happy face and front obstacle guard."),
    ("move_backward", "Drive backward with a warning face; the rear is not protected."),
    ("turn_left", "Turn left with a curious face; side and rear areas are not protected."),
    ("turn_right", "Turn right with a curious face; side and rear areas are not protected."),
)


class InteractiveConsole:
    """Small boxed console matching the standalone Pi5 tool style."""

    def __init__(self) -> None:
        self.term = Terminal()
        self.width = 72

    def menu(
        self,
        title: str,
        description: str,
        items: Sequence[tuple[str, str, str]],
        *,
        back: bool,
        emergency: bool = True,
    ) -> None:
        if self.term.is_a_tty:
            click.echo(self.term.clear + self.term.home, nl=False)
        click.echo(self.term.cyan("+" + "-" * (self.width - 2) + "+"))
        click.echo(
            self.term.cyan("|")
            + self.term.bold(f" {title}".ljust(self.width - 2))
            + self.term.cyan("|")
        )
        click.echo(self.term.cyan("+" + "-" * (self.width - 2) + "+"))
        for line in textwrap.wrap(description, self.width - 6):
            click.echo(
                self.term.cyan("|") + f"  {line}".ljust(self.width - 2) + self.term.cyan("|")
            )
        click.echo(self.term.cyan("+" + "-" * (self.width - 2) + "+"))
        for key, label, detail in items:
            click.echo(f"  {self.term.bold(key)}. {label}")
            for line in textwrap.wrap(detail, self.width - 10):
                click.echo(f"     {line}")
        if back:
            click.echo("  B. Back")
        if emergency:
            click.echo(self.term.red("  E. EMERGENCY STOP (available from every menu)"))
        click.echo()

    async def choose(self, choices: Sequence[str]) -> str:
        value = await asyncio.to_thread(
            click.prompt,
            "Select an option",
            type=click.Choice(list(choices), case_sensitive=False),
        )
        return cast(str, value).lower()

    def info(self, message: str) -> None:
        click.echo(self.term.green(message))

    def warning(self, message: str) -> None:
        click.echo(self.term.yellow(message))

    def error(self, message: str) -> None:
        click.echo(self.term.red(f"Error: {message}"))

    def json(self, payload: object) -> None:
        click.echo(json.dumps(payload, indent=2, default=_json_default))


class InteractiveRobotSession:
    """Own one real robot assembly and replace it after a Level 2 stop."""

    def __init__(self, config: RobotConfig) -> None:
        self.config = config
        self.repository = BehaviorAssetRepository(config.behaviors.user_directory)
        self.robot: RobotAssembly | None = None
        self.active_task: asyncio.Task[dict[str, Any]] | None = None
        self.active_name: str | None = None
        self.active_motion = False
        self.system_stopped = False
        self.registry = ActiveBehaviorRegistry()

    async def start_background(
        self,
        definition: BehaviorDefinition,
        *,
        loop_face: bool,
    ) -> None:
        """Replace the active behavior and return while it continues running."""
        await self.stop_active()
        robot = await self._ensure_robot()
        selected = loop_final_face(definition) if loop_face else definition
        self.registry.register(selected.name)
        self.active_task = asyncio.create_task(robot.run_definition(selected))
        self.active_name = selected.name
        self.active_motion = selected.contains_motion
        await asyncio.sleep(0)
        if self.active_task.done():
            await self.reap_active(raise_error=True)

    async def run_once(self, definition: BehaviorDefinition) -> dict[str, Any]:
        """Stop any background behavior and wait for one bounded behavior."""
        await self.stop_active()
        robot = await self._ensure_robot()
        self.registry.register(definition.name)
        try:
            return await robot.run_definition(definition)
        finally:
            self.registry.clear()

    async def stop_active(self) -> None:
        """Cancel a face or movement without issuing a Level 2 system stop."""
        task = self.active_task
        robot = self.robot
        if task is not None and not task.done() and robot is not None:
            await robot.behaviors.stop()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        self.active_task = None
        self.active_name = None
        self.active_motion = False
        self.registry.clear()

    async def reap_active(self, *, raise_error: bool = False) -> str | None:
        """Collect a completed background task and surface its result."""
        task = self.active_task
        if task is None or not task.done():
            return None
        name = self.active_name or "behavior"
        self.active_task = None
        self.active_name = None
        self.active_motion = False
        self.registry.clear()
        try:
            result = task.result()
        except asyncio.CancelledError:
            return f"{name} stopped."
        except Exception as exc:
            if self.robot is not None:
                self.system_stopped = self.robot.system_safety.stopped
            if raise_error:
                raise
            return f"{name} failed: {exc}"
        return f"{result['name']} completed."

    async def emergency_stop(self, reason: str = "operator_stop") -> dict[str, Any]:
        """Invoke the existing Level 2 stop and keep its sign on the display."""
        await self.stop_active()
        robot = await self._ensure_robot(allow_stopped=True)
        result = await robot.stop()
        self.system_stopped = True
        return result

    async def resume(self) -> dict[str, Any]:
        """Clear Level 1 or rebuild and probe every module after Level 2."""
        snapshot = SafetyStateStore(self.config.behaviors.safety_state_file).read()
        if not self.system_stopped and not snapshot.system_latched:
            robot = await self._ensure_robot()
            if snapshot.motion_latched:
                resumed = await robot.resume_motion(confirmed=True)
                result = {"level": 1, "state": asdict(resumed)}
            else:
                result = {"level": 0, "state": asdict(snapshot)}
            await self.start_background(self.repository.load("idle"), loop_face=True)
            return result

        await self.stop_active()
        previous = self.robot
        self.robot = None
        if previous is not None:
            await previous.close()

        candidate = RobotAssembly(config=self.config, simulated=False)
        self.robot = candidate
        try:
            resumed = await candidate.resume_system(confirmed=True)
        except Exception:
            try:
                await candidate.stop()
            finally:
                self.system_stopped = True
            raise
        self.system_stopped = False
        await self.start_background(self.repository.load("idle"), loop_face=True)
        return {"level": 2, "state": asdict(resumed)}

    async def close(self) -> None:
        """Stop active work and release all real devices on tool exit."""
        await self.stop_active()
        if self.robot is not None:
            await self.robot.close()
            self.robot = None

    async def _ensure_robot(self, *, allow_stopped: bool = False) -> RobotAssembly:
        if self.system_stopped and not allow_stopped:
            raise RuntimeError("the robot is stopped; use Resume Robot Movement first")
        if self.robot is None:
            self.robot = RobotAssembly(config=self.config, simulated=False)
            await self.robot.start()
        return self.robot


async def run_interactive(
    config: RobotConfig,
    *,
    simulation_runner: SimulationRunner,
) -> None:
    """Run the complete direct-control interactive experience."""
    console = InteractiveConsole()
    session = InteractiveRobotSession(config)
    try:
        while True:
            status = await session.reap_active()
            if status:
                console.warning(status)
            console.menu(
                "NinjaRobotPi5 Interactive Tool",
                "Choose a normal-user workflow. Selections execute directly; use "
                "Simulation when you do not want any physical module to run.",
                (
                    (
                        "1",
                        "Hardware Configurations",
                        "Display current robot wiring, software settings, and safety state.",
                    ),
                    (
                        "2",
                        "Run Robot Behaviors",
                        "Run built-in animated faces, movements, and special behaviors.",
                    ),
                    (
                        "3",
                        "Create Robot Behavior",
                        "Build and preview a private behavior one step at a time.",
                    ),
                    (
                        "4",
                        "Run User-Created Behaviors",
                        "Choose and directly run a behavior saved in your private catalog.",
                    ),
                    (
                        "5",
                        "Delete User-Created Behaviors",
                        "Review and safely delete only private user behaviors.",
                    ),
                    (
                        "6",
                        "Simulation",
                        "Run with simulated modules and no GPIO, PWM, I2C, or SPI access.",
                    ),
                    ("7", "Quit", "Stop active work, release hardware, and exit the tool."),
                ),
                back=False,
            )
            choice = await console.choose(("1", "2", "3", "4", "5", "6", "7", "e", "q"))
            try:
                if choice == "1":
                    await _hardware_menu(console, session)
                elif choice == "2":
                    await _built_in_menu(console, session)
                elif choice == "3":
                    await _create_menu(console, session, simulation_runner)
                elif choice == "4":
                    await _user_run_menu(console, session)
                elif choice == "5":
                    await _user_delete_menu(console, session)
                elif choice == "6":
                    await _simulation_menu(console, session, simulation_runner)
                elif choice == "e":
                    await _emergency(console, session)
                else:
                    return
            except click.Abort:
                raise
            except Exception as exc:
                console.error(str(exc))
    except (click.Abort, KeyboardInterrupt):
        if session.robot is not None:
            try:
                await session.emergency_stop("ctrl_c")
            except Exception:
                pass
        raise
    finally:
        await session.close()


async def _hardware_menu(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
) -> None:
    while True:
        config = session.config
        console.menu(
            "Hardware Configurations",
            "This page reads configuration only. It does not move a servo, play a "
            "sound, record media, or initialize a sensor.",
            (
                (
                    "1",
                    "Show Current Configuration",
                    "Display GPIO, buses, servo roles, calibration, and safety thresholds.",
                ),
            ),
            back=True,
        )
        choice = await console.choose(("1", "b", "e"))
        if choice == "b":
            return
        if choice == "e":
            await _emergency(console, session)
            continue
        calibration = Path(config.hardware.servos.calibration_file).expanduser()
        console.json(
            {
                "software": {
                    "ninjarobot_pi5_ide": _installed_version("ninjarobot-pi5-ide"),
                    "python": platform.python_version(),
                    "platform": sys.platform,
                },
                "display": config.hardware.display.model_dump(mode="json"),
                "buzzer_gpio": config.hardware.buzzer.gpio,
                "i2c": config.hardware.i2c.model_dump(mode="json"),
                "servo_endpoints": list(config.hardware.servos.endpoints),
                "servo_roles": config.behaviors.servo_roles,
                "servo_calibration_file": str(calibration),
                "servo_calibration_exists": calibration.is_file(),
                "motion_enabled": config.hardware.servos.motion_enabled,
                "group_motion_enabled": config.hardware.servos.group_motion_enabled,
                "obstacle_threshold_mm": config.behaviors.obstacle_threshold_mm,
                "safety": SafetyStateStore(config.behaviors.safety_state_file).read(),
                "user_behavior_directory": config.behaviors.user_directory,
            }
        )
        await _pause()


async def _built_in_menu(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
) -> None:
    while True:
        await _report_background(console, session)
        console.menu(
            "Run Robot Behaviors",
            "Built-in behaviors use the installed catalog. Face expressions loop "
            "until changed, stopped, or the tool exits.",
            (
                (
                    "1",
                    "Face Expressions",
                    "Animated faces and matching melodies; no servo movement.",
                ),
                (
                    "2",
                    "Robot Movements",
                    "Animated faces and wheel-servo movement; no buzzer sound.",
                ),
                (
                    "3",
                    "Special Behaviors",
                    "Greeting, Celebrate, Emergency Stop, Resume, and Error Warning.",
                ),
            ),
            back=True,
        )
        choice = await console.choose(("1", "2", "3", "b", "e"))
        if choice == "b":
            if session.active_motion:
                await session.stop_active()
            return
        if choice == "e":
            await _emergency(console, session)
        elif choice == "1":
            await _face_menu(console, session)
        elif choice == "2":
            await _movement_menu(console, session)
        else:
            await _special_menu(console, session)


async def _face_menu(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
) -> None:
    items = tuple(
        (str(index), name.replace("_", " ").title(), description)
        for index, (name, description) in enumerate(FACE_MENU, start=1)
    )
    while True:
        await _report_background(console, session)
        console.menu(
            "Face Expressions",
            "Selecting a face starts its animation immediately. Its melody plays "
            "once while the face continues looping.",
            items,
            back=True,
        )
        choices = tuple(str(index) for index in range(1, len(FACE_MENU) + 1))
        choice = await console.choose((*choices, "b", "e"))
        if choice == "b":
            return
        if choice == "e":
            await _emergency(console, session)
            continue
        name = FACE_MENU[int(choice) - 1][0]
        await session.start_background(session.repository.load(name), loop_face=True)
        console.info(f"{name.replace('_', ' ').title()} is now running.")


async def _movement_menu(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
) -> None:
    items = tuple(
        (str(index), name.replace("_", " ").title(), description)
        for index, (name, description) in enumerate(MOVEMENT_MENU, start=1)
    )
    while True:
        await _report_background(console, session)
        console.menu(
            "Robot Movements",
            "Real continuous-rotation servos will move. Keep the robot raised for "
            "the first test and keep the Emergency Stop shortcut ready.",
            items,
            back=True,
        )
        choice = await console.choose(("1", "2", "3", "4", "b", "e"))
        if choice == "b":
            await session.stop_active()
            return
        if choice == "e":
            await _emergency(console, session)
            continue
        name = MOVEMENT_MENU[int(choice) - 1][0]
        approved = await _confirm(
            f"Run {name.replace('_', ' ')} on the real wheel servos?",
            default=False,
        )
        if not approved:
            console.warning("Movement cancelled.")
            continue
        await session.start_background(session.repository.load(name), loop_face=False)
        console.info(f"{name.replace('_', ' ').title()} started. Choose Back to stop it.")


async def _special_menu(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
) -> None:
    while True:
        await _report_background(console, session)
        console.menu(
            "Special Behaviors",
            "Safety actions are executed directly and are not reusable behavior files.",
            (
                (
                    "1",
                    "Greeting",
                    "Greeting face and Happy melody, then Nice to meet you; no wheels.",
                ),
                (
                    "2",
                    "Celebrate",
                    "Exciting and Success faces, melody, and a short guarded wheel dance.",
                ),
                (
                    "3",
                    "Emergency Stop",
                    "Level 2: stop servos and sensors, silence sound, and show the sign.",
                ),
                (
                    "4",
                    "Resume Robot Movement",
                    "Health-check and reconstruct modules; never restart prior movement.",
                ),
                (
                    "5",
                    "Error Warning",
                    "Stop active wheels, then loop Error and Warning without new movement.",
                ),
            ),
            back=True,
        )
        choice = await console.choose(("1", "2", "3", "4", "5", "b", "e"))
        if choice == "b":
            if session.active_motion:
                await session.stop_active()
            return
        if choice in {"3", "e"}:
            await _emergency(console, session)
        elif choice == "1":
            result = await session.run_once(session.repository.load("greeting"))
            console.info(f"{result['name']} completed.")
        elif choice == "2":
            approved = await _confirm(
                "Run Celebrate, including its short real wheel movement?",
                default=False,
            )
            if approved:
                result = await session.run_once(session.repository.load("celebrate"))
                console.info(f"{result['name']} completed.")
        elif choice == "4":
            approved = await _confirm(
                "Resume after real hardware health checks?",
                default=False,
            )
            if approved:
                console.json(await session.resume())
                console.info("Robot modules are ready. No previous movement was restarted.")
        else:
            await session.stop_active()
            await session.start_background(
                session.repository.load("error_warning"),
                loop_face=True,
            )
            console.warning("Error Warning is running without servo movement.")


async def _create_menu(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
    simulation_runner: SimulationRunner,
) -> None:
    console.menu(
        "Create Robot Behavior",
        "Build one simultaneous stage from a face or text, an optional melody, "
        "and optional wheel movement. Example: Happy face + Happy melody + "
        "left 25/right -25. The tool validates and simulates it before saving.",
        (
            (
                "1",
                "Start Guided Creator",
                "Answer each prompt; nothing physical runs during the preview.",
            ),
        ),
        back=True,
    )
    choice = await console.choose(("1", "b", "e"))
    if choice == "b":
        return
    if choice == "e":
        await _emergency(console, session)
        return

    name = cast(str, await asyncio.to_thread(click.prompt, "Behavior name (lowercase)"))
    description = cast(str, await asyncio.to_thread(click.prompt, "Short description"))
    display_kind = await _prompt_choice(
        "Display output",
        ("face", "text", "none"),
        default="face",
    )
    operations: list[dict[str, object]] = []
    if display_kind == "face":
        face = await _prompt_choice("Face expression", FACE_EXPRESSIONS, default="happy")
        operations.append(
            {
                "kind": "face",
                "expression": face,
                "hold_seconds": 2.0,
            }
        )
    elif display_kind == "text":
        text = cast(str, await asyncio.to_thread(click.prompt, "Text to display"))
        operations.append({"kind": "text", "text": text, "hold_seconds": 2.0})

    if await _confirm("Add a buzzer melody?", default=True):
        melody = await _prompt_choice("Melody", MELODIES, default="happy")
        volume = cast(
            int,
            await asyncio.to_thread(
                click.prompt,
                "Volume (0-128)",
                type=click.IntRange(0, 128),
                default=64,
            ),
        )
        operations.append({"kind": "melody", "melody": melody, "volume": volume})

    contains_motion = await _confirm("Add wheel-servo movement?", default=False)
    if contains_motion:
        left = cast(
            float,
            await asyncio.to_thread(
                click.prompt,
                "Left motor value (-90 to 90)",
                type=click.FloatRange(-90.0, 90.0),
            ),
        )
        right = cast(
            float,
            await asyncio.to_thread(
                click.prompt,
                "Right motor value (-90 to 90)",
                type=click.FloatRange(-90.0, 90.0),
            ),
        )
        policy = await _prompt_choice(
            "Obstacle policy",
            ("front_guarded", "warn_only"),
            default="front_guarded",
        )
        continuous = await _confirm("Continue until explicitly stopped?", default=False)
        duration: float | None = None
        if not continuous:
            duration = cast(
                float,
                await asyncio.to_thread(
                    click.prompt,
                    "Movement seconds (0.1-30)",
                    type=click.FloatRange(0.1, 30.0),
                    default=2.0,
                ),
            )
        for operation in operations:
            if operation["kind"] in {"face", "text"}:
                operation["hold_seconds"] = duration
        operations.append(
            {
                "kind": "drive",
                "targets": {"left_motor": left, "right_motor": right},
                "speed_mode": "M",
                "obstacle_policy": policy,
                "hold_seconds": duration,
            }
        )
    if not operations:
        raise ValueError("a behavior must use at least one display, buzzer, or movement operation")

    definition = BehaviorDefinition.model_validate(
        {
            "schema_version": 1,
            "name": name,
            "description": description,
            "category": "movement" if contains_motion else "expression",
            "stages": [{"name": "combined_action", "operations": operations}],
        }
    )
    console.info("Running a two-second hardware-free preview.")
    preview = await simulation_runner(session.config, definition, 2.0)
    console.json({"definition": definition, "preview": preview})
    if not await _confirm("Save this private behavior?", default=False):
        console.warning("Behavior was not saved.")
        return
    overwrite = False
    try:
        path = session.repository.save_user(definition)
    except Exception as exc:
        if "already exists" not in str(exc):
            raise
        overwrite = await _confirm("That name exists. Replace it?", default=False)
        if not overwrite:
            return
        path = session.repository.save_user(definition, overwrite=True)
    console.info(f"Saved {definition.name} to {path}.")


async def _user_run_menu(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
) -> None:
    while True:
        await _report_background(console, session)
        definitions = session.repository.list_user()
        if not definitions:
            console.warning("No user-created behaviors are saved yet.")
            await _pause()
            return
        items = tuple(
            (str(index), definition.name, definition.description)
            for index, definition in enumerate(definitions, start=1)
        )
        console.menu(
            "Run User-Created Behaviors",
            "Select a private behavior. Movement always requires a separate confirmation.",
            items,
            back=True,
        )
        choices = tuple(str(index) for index in range(1, len(definitions) + 1))
        choice = await console.choose((*choices, "b", "e"))
        if choice == "b":
            if session.active_motion:
                await session.stop_active()
            return
        if choice == "e":
            await _emergency(console, session)
            continue
        definition = definitions[int(choice) - 1]
        if definition.contains_motion and not await _confirm(
            f"Run {definition.name} on real wheel servos?",
            default=False,
        ):
            continue
        loop_face = not definition.contains_motion and _has_final_face(definition)
        if definition.contains_motion or loop_face:
            await session.start_background(definition, loop_face=loop_face)
            console.info(f"{definition.name} started.")
        else:
            result = await session.run_once(definition)
            console.info(f"{result['name']} completed.")


async def _user_delete_menu(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
) -> None:
    while True:
        definitions = session.repository.list_user()
        if not definitions:
            console.warning("No user-created behaviors are available to delete.")
            await _pause()
            return
        items = tuple(
            (str(index), definition.name, definition.description)
            for index, definition in enumerate(definitions, start=1)
        )
        console.menu(
            "Delete User-Created Behaviors",
            "Only private user files can be deleted. Built-in behaviors are read-only.",
            items,
            back=True,
        )
        choices = tuple(str(index) for index in range(1, len(definitions) + 1))
        choice = await console.choose((*choices, "b", "e"))
        if choice == "b":
            return
        if choice == "e":
            await _emergency(console, session)
            continue
        definition = definitions[int(choice) - 1]
        if await _confirm(f"Permanently delete {definition.name}?", default=False):
            session.repository.delete_user(definition.name)
            console.info(f"Deleted {definition.name}.")


async def _simulation_menu(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
    simulation_runner: SimulationRunner,
) -> None:
    while True:
        definitions = session.repository.list()
        items = tuple(
            (str(index), definition.name, definition.description)
            for index, definition in enumerate(definitions, start=1)
        )
        console.menu(
            "Simulation",
            "Simulation uses fake display, buzzer, servo, and distance devices. "
            "It never accesses GPIO (general-purpose input/output), PWM "
            "(pulse-width modulation), I2C, SPI, the camera, or microphone.",
            items,
            back=True,
        )
        choices = tuple(str(index) for index in range(1, len(definitions) + 1))
        choice = await console.choose((*choices, "b", "e"))
        if choice == "b":
            return
        if choice == "e":
            await _emergency(console, session)
            continue
        definition = definitions[int(choice) - 1]
        console.info(
            f"Simulating {definition.name} for at most two seconds of continuous activity."
        )
        console.json(await simulation_runner(session.config, definition, 2.0))
        await _pause()


async def _emergency(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
) -> None:
    result = await session.emergency_stop()
    console.json(result)
    console.warning("SYSTEM STOPPED. The display keeps the emergency sign until Resume or Quit.")


async def _report_background(
    console: InteractiveConsole,
    session: InteractiveRobotSession,
) -> None:
    status = await session.reap_active()
    if status:
        console.warning(status)


def loop_final_face(definition: BehaviorDefinition) -> BehaviorDefinition:
    final = definition.stages[-1]
    if not any(isinstance(operation, FaceOperation) for operation in final.operations):
        raise ValueError("this behavior has no final face animation to loop")
    operations = tuple(
        operation.model_copy(update={"hold_seconds": None})
        if isinstance(operation, FaceOperation)
        else operation
        for operation in final.operations
    )
    stage = final.model_copy(update={"operations": operations})
    return definition.model_copy(update={"stages": (*definition.stages[:-1], stage)})


def _has_final_face(definition: BehaviorDefinition) -> bool:
    return any(
        isinstance(operation, FaceOperation) for operation in definition.stages[-1].operations
    )


async def _prompt_choice(
    prompt: str,
    choices: Sequence[str],
    *,
    default: str,
) -> str:
    value = await asyncio.to_thread(
        click.prompt,
        prompt,
        type=click.Choice(list(choices), case_sensitive=False),
        default=default,
    )
    return cast(str, value).lower()


async def _confirm(prompt: str, *, default: bool) -> bool:
    return cast(
        bool,
        await asyncio.to_thread(click.confirm, prompt, default=default),
    )


async def _pause() -> None:
    await asyncio.to_thread(
        click.prompt,
        "Press Enter to return",
        default="",
        show_default=False,
    )


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _installed_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "source-checkout"
