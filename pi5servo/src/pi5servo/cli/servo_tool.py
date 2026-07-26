"""Interactive servo control tool."""

from __future__ import annotations

import json
import time
from collections.abc import Callable

import click

from ..config import ConfigManager
from ..core import Servo, ServoCalibration, ServoGroup
from ._common import (
    LEGACY_BACKENDS,
    backend_options,
    close_runtime_handle,
    create_group_from_config,
    create_servo_from_config,
    format_endpoint_label,
    parse_endpoint_value,
    resolve_backend_settings,
    sort_endpoint_keys,
)
from .calib import CalibApp

try:
    from blessed import Terminal

    HAS_BLESSED = True
except ImportError:
    HAS_BLESSED = False


@click.command("servo-tool")
@click.option(
    "-c",
    "--config",
    "config_path",
    default="servo.json",
    help="Path to calibration config file.",
)
@backend_options
def servo_tool(
    config_path: str,
    backend_name: str | None,
    chip: int | None,
    bus_id: int | None,
    frequency_hz: int | None,
    address: str | None,
    pin_channel_map: str | None,
    channel_map: str | None,
) -> None:
    """Interactive servo control and configuration tool."""
    if not HAS_BLESSED:
        click.echo("❌ 'blessed' library required for interactive mode.")
        click.echo("   Install with: uv add blessed")
        return

    term = Terminal()
    manager = ConfigManager(config_path)
    manager.load()
    known_pins: list[int | str] = []

    persistent_group = None
    runtime = None
    resolved_backend = None
    backend_kwargs = None

    def reload_manager() -> None:
        manager.load()

    def refresh_persistent_group(*, center_on_load: bool) -> None:
        nonlocal known_pins, persistent_group, manager, runtime, resolved_backend, backend_kwargs

        old_group = persistent_group
        old_runtime = runtime

        reload_manager()
        known_pins = sort_endpoint_keys(
            [endpoint.legacy_key for endpoint in manager.get_known_endpoints()]
        )
        persistent_group = None
        runtime = None

        if old_group is not None:
            old_group.close()
        close_runtime_handle(old_runtime)

        resolved_backend, backend_kwargs = resolve_backend_settings(
            manager,
            backend_name=backend_name,
            chip=chip,
            bus_id=bus_id,
            frequency_hz=frequency_hz,
            address=address,
            pin_channel_map=pin_channel_map,
            channel_map=channel_map,
        )
        if not known_pins:
            return

        persistent_group, manager, runtime, resolved_backend, backend_kwargs = (
            create_group_from_config(
                pins=known_pins,
                config_path=config_path,
                backend_name=backend_name,
                chip=chip,
                bus_id=bus_id,
                frequency_hz=frequency_hz,
                address=address,
                pin_channel_map=pin_channel_map,
                channel_map=channel_map,
            )
        )

        if center_on_load:
            persistent_group.center_all()
            time.sleep(0.1)
            labels = ", ".join(format_endpoint_label(pin) for pin in known_pins)
            click.echo(term.green(f"✓ All servos centered (0°): {labels}"))

    def release_persistent_group() -> None:
        nonlocal persistent_group, runtime

        old_group = persistent_group
        old_runtime = runtime
        persistent_group = None
        runtime = None

        if old_group is not None:
            old_group.close()
        close_runtime_handle(old_runtime)

    def _build_backend_group(pins: list[int | str]) -> tuple[ServoGroup, object | None]:
        if resolved_backend in LEGACY_BACKENDS:
            group, _, temp_runtime, _, _ = create_group_from_config(
                pins=pins,
                config_path=config_path,
                backend_name=backend_name,
                chip=chip,
                bus_id=bus_id,
                frequency_hz=frequency_hz,
                address=address,
                pin_channel_map=pin_channel_map,
                channel_map=channel_map,
            )
            return group, temp_runtime

        calibrations = {pin: manager.get_calibration(pin) for pin in pins}
        return (
            ServoGroup(
                runtime,
                pins=pins,
                calibrations=calibrations,
                backend=resolved_backend,
                backend_kwargs=backend_kwargs,
            ),
            None,
        )

    def build_temp_group(pins: list[int | str]) -> tuple[ServoGroup, object | None]:
        if persistent_group is not None and set(pins).issubset(set(persistent_group.pins)):
            return persistent_group, None
        return _build_backend_group(pins)

    def build_temp_servo(pin: int | str) -> tuple[Servo, object | None]:
        if resolved_backend in LEGACY_BACKENDS:
            servo, _, temp_runtime, _, _ = create_servo_from_config(
                pin=pin,
                config_path=config_path,
                backend_name=backend_name,
                chip=chip,
                bus_id=bus_id,
                frequency_hz=frequency_hz,
                address=address,
                pin_channel_map=pin_channel_map,
                channel_map=channel_map,
            )
            return servo, temp_runtime

        return (
            Servo(
                runtime,
                pin,
                manager.get_calibration(pin),
                backend=resolved_backend,
                backend_kwargs=backend_kwargs,
            ),
            None,
        )

    def get_persistent_servo(pin: int | str) -> Servo | None:
        if persistent_group is None:
            return None
        return persistent_group.get_servo(pin)

    def run_with_isolated_temp_servo(
        pin: int | str,
        callback: Callable[[Servo], None],
    ) -> None:
        """Run a temporary single-servo session without overlapping live backends."""
        servo = None
        temp_runtime = None

        release_persistent_group()
        try:
            servo, temp_runtime = build_temp_servo(pin)
            callback(servo)
        finally:
            if servo is not None:
                servo.close()
            close_runtime_handle(temp_runtime)
            refresh_persistent_group(center_on_load=False)

    try:
        refresh_persistent_group(center_on_load=True)
        if not known_pins:
            click.echo(
                term.yellow(
                    "No configured endpoints found. Use explicit endpoints like 'gpio12' or 'hat_pwm1'."
                )
            )

        def show_menu() -> None:
            click.echo(term.clear())
            click.echo(term.bold("╔" + "═" * 58 + "╗"))
            click.echo(
                term.bold("║")
                + term.cyan("           pi5servo Interactive Tool")
                + " " * 20
                + term.bold("║")
            )
            click.echo(term.bold("╠" + "═" * 58 + "╣"))
            click.echo(
                term.bold("║")
                + "  1. Quick Move    - Enter commands like 'gpio12:30/hat_pwm1:M' "
                + term.bold("║")
            )
            click.echo(
                term.bold("║")
                + "  2. Single Move   - Move one servo to angle             "
                + term.bold("║")
            )
            click.echo(
                term.bold("║")
                + "  3. Calibrate     - Launch calibration TUI              "
                + term.bold("║")
            )
            click.echo(
                term.bold("║")
                + "  4. Set Speed     - Adjust servo speed limit            "
                + term.bold("║")
            )
            click.echo(
                term.bold("║")
                + "  5. Status        - Show backend and servo configs      "
                + term.bold("║")
            )
            click.echo(
                term.bold("║")
                + "  6. Config        - Show/export/import config           "
                + term.bold("║")
            )
            click.echo(
                term.bold("║")
                + "  q. Exit                                                "
                + term.bold("║")
            )
            click.echo(term.bold("╚" + "═" * 58 + "╝"))
            click.echo()

        def quick_move() -> None:
            click.echo("\n" + term.cyan("=== Quick Move Mode ==="))
            click.echo("Enter commands like 'F_gpio12:45/hat_pwm1:-30'. Type 'q' to return.\n")

            from ..parser import parse_command

            while True:
                cmd_str = input("> ").strip()
                if cmd_str.lower() in ("q", "b", "quit", "back"):
                    break
                if not cmd_str:
                    continue

                try:
                    parsed = parse_command(cmd_str)
                    pins = sort_endpoint_keys(list({target.pin for target in parsed.targets}))
                    group, temp_runtime = build_temp_group(pins)
                    owns_group = group is not persistent_group

                    # Quick-move commands are direct operator actions. Force the
                    # final PWM write so center/offline recovery commands are not
                    # skipped when a prior transient servo object left stale state.
                    success = group.execute_command(cmd_str, force=True)
                    click.echo(term.green("✓ Done") if success else term.red("✗ Aborted"))

                    if owns_group:
                        group.close()
                        close_runtime_handle(temp_runtime)
                except Exception as exc:
                    click.echo(term.red(f"✗ Error: {exc}"))

        def single_move() -> None:
            click.echo("\n" + term.cyan("=== Single Move Mode ==="))
            click.echo("Enter servo endpoint (for example 12, gpio12, or hat_pwm1):")
            try:
                pin = parse_endpoint_value(input("> ").strip())
            except ValueError:
                click.echo(term.red("Invalid endpoint"))
                input("\nPress Enter to continue...")
                return

            click.echo(
                f"Moving {format_endpoint_label(pin)}. "
                "Enter angle or 'min'/'center'/'max'. Type 'q' to return.\n"
            )
            try:

                def move_session(servo: Servo) -> None:
                    while True:
                        angle_str = input("> ").strip().lower()
                        if angle_str in ("q", "b", "quit", "back"):
                            break
                        if not angle_str:
                            continue

                        cal = manager.get_calibration(pin)
                        if angle_str == "min":
                            angle = cal.angle_min
                        elif angle_str == "center":
                            angle = cal.angle_center
                        elif angle_str == "max":
                            angle = cal.angle_max
                        else:
                            try:
                                angle = float(angle_str)
                            except ValueError:
                                click.echo(term.red("Invalid angle"))
                                continue

                        servo.set_angle(angle)
                        click.echo(term.green(f"✓ {format_endpoint_label(pin)} → {angle}°"))

                borrowed_servo = get_persistent_servo(pin)
                if borrowed_servo is not None:
                    try:
                        move_session(borrowed_servo)
                    finally:
                        borrowed_servo.off()
                else:
                    run_with_isolated_temp_servo(pin, move_session)
            except Exception as exc:
                click.echo(term.red(f"✗ Error: {exc}"))
                input("\nPress Enter to continue...")
                return

        def calibrate_servo() -> None:
            click.echo("\n" + term.yellow("Enter servo endpoint to calibrate:"))
            try:
                pin = parse_endpoint_value(input("> ").strip())
            except ValueError:
                click.echo(term.red("Invalid endpoint"))
                input("\nPress Enter to continue...")
                return

            try:
                borrowed_servo = get_persistent_servo(pin)

                def calibrate_session(servo: Servo, *, owns_servo: bool) -> None:
                    app = CalibApp(
                        servo,
                        pin,
                        config_path,
                        manager,
                        owns_servo=owns_servo,
                    )
                    try:
                        app.main()
                    finally:
                        app.end()

                if borrowed_servo is not None:
                    calibrate_session(borrowed_servo, owns_servo=False)
                    manager.load()
                    if persistent_group is not None:
                        persistent_group.update_calibration(pin, manager.get_calibration(pin))
                else:
                    run_with_isolated_temp_servo(
                        pin,
                        lambda servo: calibrate_session(servo, owns_servo=True),
                    )
            except Exception as exc:
                click.echo(term.red(f"✗ Error: {exc}"))
                input("\nPress Enter to continue...")
                return
            click.echo(term.green("✓ Config reloaded"))

        def set_speed() -> None:
            click.echo("\n" + term.cyan("=== Set Servo Speed Limit ==="))
            configs = manager.get_all_endpoint_calibrations()
            if configs:
                click.echo("\nCurrent speeds:")
                for endpoint_id, cal in sorted(configs.items()):
                    click.echo(f"  {endpoint_id}: {cal.speed}%")

            click.echo("\n" + term.yellow("Enter servo endpoint:"))
            try:
                pin = parse_endpoint_value(input("> ").strip())
            except ValueError:
                click.echo(term.red("Invalid endpoint"))
                input("\nPress Enter to continue...")
                return

            cal = manager.get_calibration(pin)
            click.echo(f"Current speed for {format_endpoint_label(pin)}: {cal.speed}%")
            click.echo(term.yellow("Enter new speed (0-100):"))
            try:
                new_speed = int(input("> ").strip())
            except ValueError:
                click.echo(term.red("Invalid speed"))
                input("\nPress Enter to continue...")
                return

            if not 0 <= new_speed <= 100:
                click.echo(term.red("Speed must be 0-100"))
                input("\nPress Enter to continue...")
                return

            manager.set_calibration(
                pin,
                ServoCalibration(
                    pulse_min=cal.pulse_min,
                    pulse_max=cal.pulse_max,
                    pulse_center=cal.pulse_center,
                    angle_min=cal.angle_min,
                    angle_max=cal.angle_max,
                    angle_center=cal.angle_center,
                    speed=new_speed,
                ),
            )
            manager.save()
            refresh_persistent_group(center_on_load=False)
            click.echo(term.green(f"✓ Speed for {format_endpoint_label(pin)} set to {new_speed}%"))
            input("\nPress Enter to continue...")

        def show_status() -> None:
            click.echo("\n" + term.cyan("=== Servo Status ==="))
            click.echo(f"Backend: {resolved_backend}")
            click.echo(f"Backend kwargs: {backend_kwargs or '{}'}")

            configs = manager.get_all_endpoint_calibrations()
            if not configs:
                click.echo("No servos configured. Run calibration first.")
            else:
                for endpoint_id, cal in sorted(configs.items()):
                    click.echo(
                        f"  {endpoint_id}: pulse=[{cal.pulse_min}, {cal.pulse_center}, {cal.pulse_max}] speed={cal.speed}%"
                    )
            input("\nPress Enter to continue...")

        def config_menu() -> None:
            click.echo("\n" + term.cyan("=== Config Management ==="))
            click.echo("  1. Show current config")
            click.echo("  2. Export to file")
            click.echo("  3. Import from file")
            click.echo("  b. Back")

            choice = input("\nChoice: ").strip().lower()
            if choice == "1":
                click.echo("\n" + json.dumps(manager._to_dict(), indent=2))
            elif choice == "2":
                click.echo(term.yellow("Enter export path:"))
                path = input("> ").strip()
                if path:
                    manager.save_to(path)
                    click.echo(term.green(f"✓ Exported to {path}"))
            elif choice == "3":
                click.echo(term.yellow("Enter import path:"))
                path = input("> ").strip()
                if path:
                    manager.load_from(path)
                    click.echo(term.green(f"✓ Imported from {path}"))
                    refresh_persistent_group(center_on_load=False)
            input("\nPress Enter to continue...")

        running = True
        while running:
            show_menu()
            choice = input("Choice: ").strip().lower()

            if choice == "1":
                quick_move()
            elif choice == "2":
                single_move()
            elif choice == "3":
                calibrate_servo()
            elif choice == "4":
                set_speed()
            elif choice == "5":
                show_status()
            elif choice == "6":
                config_menu()
            elif choice == "q":
                running = False
            else:
                click.echo("Invalid choice")
                input("\nPress Enter to continue...")

    except Exception as exc:
        click.echo(f"❌ Error: {exc}")
        import traceback

        traceback.print_exc()
    finally:
        try:
            if persistent_group is not None and persistent_group.pins:
                persistent_group.move_all_sync(
                    [0.0] * len(persistent_group.pins),
                    speed_mode="M",
                    force=True,
                )
                click.echo(term.green("✓ All servos centered (0°) on exit"))
                persistent_group.off()
                persistent_group.close()
        except Exception:
            pass

        close_runtime_handle(runtime)
        click.echo("\nGoodbye!")
