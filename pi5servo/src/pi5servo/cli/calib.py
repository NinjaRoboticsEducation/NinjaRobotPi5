"""Interactive servo calibration command."""

from __future__ import annotations

import sys

import click

from ..config import ConfigManager
from ..core import Servo, ServoCalibration
from ._common import (
    backend_options,
    close_runtime_handle,
    create_servo_from_config,
    format_endpoint_label,
    parse_endpoint_value,
)

# Hardware limits for calibration (NOT the same as default calibration values)
HARDWARE_PULSE_MIN = 500
HARDWARE_PULSE_MAX = 2500


class CalibApp:
    """Interactive servo calibration TUI application."""

    TARGET_CENTER = 0
    TARGET_MIN = -90
    TARGET_MAX = 90
    TARGETS = [TARGET_MIN, TARGET_CENTER, TARGET_MAX]
    TARGET_NAMES = {TARGET_MIN: "Min", TARGET_CENTER: "Center", TARGET_MAX: "Max"}

    STEP_LARGE = 20
    STEP_FINE = 1

    def __init__(
        self,
        servo: Servo,
        pin: int | str,
        config_path: str,
        manager: ConfigManager,
        debug: bool = False,
        owns_servo: bool = True,
    ) -> None:
        self.servo = servo
        self.pin = pin
        self.endpoint_label = format_endpoint_label(pin)
        self.config_path = config_path
        self.debug = debug
        self.owns_servo = owns_servo
        self.manager = manager
        self.calibration = self.manager.get_calibration(pin)

        self.pulse_min = self.calibration.pulse_min
        self.pulse_center = self.calibration.pulse_center
        self.pulse_max = self.calibration.pulse_max
        self.speed = self.calibration.speed

        self.cur_target = self.TARGET_CENTER
        self.running = True
        self.cur_pulse = self.pulse_center

        try:
            import blessed

            self.term = blessed.Terminal()
            self.has_blessed = True
        except ImportError:
            self.has_blessed = False
            click.echo("Warning: 'blessed' not installed. Using simple mode.", err=True)

    def _setup_key_bindings(self):
        return {
            "KEY_TAB": self.inc_target,
            "KEY_BTAB": self.dec_target,
            "v": lambda: self.set_target(self.TARGET_MIN),
            "c": lambda: self.set_target(self.TARGET_CENTER),
            "x": lambda: self.set_target(self.TARGET_MAX),
            "w": lambda: self.move_diff(self.STEP_FINE),
            "s": lambda: self.move_diff(-self.STEP_FINE),
            "KEY_UP": lambda: self.move_diff(self.STEP_LARGE),
            "KEY_DOWN": lambda: self.move_diff(-self.STEP_LARGE),
            "+": lambda: self.adjust_speed(10),
            "=": lambda: self.adjust_speed(10),
            "-": lambda: self.adjust_speed(-10),
            "_": lambda: self.adjust_speed(-10),
            "KEY_ENTER": self.set_calibration,
            " ": self.set_calibration,
            "h": self.display_help,
            "H": self.display_help,
            "?": self.display_help,
            "q": self.quit,
            "Q": self.quit,
        }

    def main(self) -> None:
        """Run the interactive calibration loop."""
        if not self.has_blessed:
            self._simple_mode()
            return

        click.echo("\nServo Calibration Tool: 'h' for help, 'q' to quit")
        self.show()
        self.servo.set_pulse(self.pulse_center)
        self.cur_pulse = self.pulse_center

        key_bindings = self._setup_key_bindings()
        with self.term.cbreak(), self.term.hidden_cursor():
            while self.running:
                self.print_prompt()
                inkey = self.term.inkey()
                if not inkey:
                    continue

                key_name = inkey.name if inkey.is_sequence else str(inkey)
                if key_name:
                    action = key_bindings.get(key_name)
                    if action:
                        action()

    def _simple_mode(self) -> None:
        click.echo("\n=== Simple Calibration Mode ===")
        click.echo(f"Config: {self.config_path}")
        click.echo(f"Servo endpoint: {self.endpoint_label}")
        click.echo("Current calibration:")
        click.echo(f"  Min: {self.pulse_min}, Center: {self.pulse_center}, Max: {self.pulse_max}")
        click.echo("\nInstall 'blessed' for interactive mode: pip install blessed")

    def show(self) -> None:
        click.echo()
        click.echo(f"* Config: {self.config_path}")
        click.echo()
        click.echo(f"* {self.endpoint_label}")
        click.echo(f"   Min ({self.TARGET_MIN}°): pulse = {self.pulse_min}")
        click.echo(f"   Center ({self.TARGET_CENTER}°): pulse = {self.pulse_center}")
        click.echo(f"   Max ({self.TARGET_MAX}°): pulse = {self.pulse_max}")
        click.echo(f"   Speed: {self.speed}%")
        click.echo()

    def print_prompt(self) -> None:
        target_str = self.TARGET_NAMES.get(self.cur_target, "Unknown")
        prompt = f"{self.endpoint_label} | Target: {target_str} | pulse={self.cur_pulse}"
        print(f"\r{self.term.clear_eol()}{prompt}> ", end="", flush=True)

    def inc_target(self) -> None:
        idx = self.TARGETS.index(self.cur_target)
        self.set_target(self.TARGETS[(idx + 1) % len(self.TARGETS)])

    def dec_target(self) -> None:
        idx = self.TARGETS.index(self.cur_target)
        self.set_target(self.TARGETS[(idx - 1 + len(self.TARGETS)) % len(self.TARGETS)])

    def set_target(self, target: int) -> None:
        if target not in self.TARGETS:
            return

        self.cur_target = target
        if target == self.TARGET_MIN:
            self.cur_pulse = self.pulse_min
        elif target == self.TARGET_CENTER:
            self.cur_pulse = self.pulse_center
        else:
            self.cur_pulse = self.pulse_max
        self.servo.set_pulse(self.cur_pulse)

    def move_diff(self, diff_pulse: int) -> None:
        dst_pulse = max(
            min(self.cur_pulse + diff_pulse, HARDWARE_PULSE_MAX),
            HARDWARE_PULSE_MIN,
        )
        self.cur_pulse = dst_pulse
        self.servo.set_pulse(dst_pulse)

    def adjust_speed(self, diff: int) -> None:
        self.speed = max(0, min(100, self.speed + diff))
        if self.has_blessed:
            click.echo(f"\rSpeed: {self.speed}%" + self.term.clear_eol())
        else:
            click.echo(f"Speed: {self.speed}%")

    def set_calibration(self) -> None:
        if self.has_blessed:
            print(f"\r{self.term.clear_eol()}", end="")

        target_str = self.TARGET_NAMES.get(self.cur_target, "Unknown")
        if self.cur_target == self.TARGET_CENTER:
            if self.pulse_min < self.cur_pulse < self.pulse_max:
                self.pulse_center = self.cur_pulse
            else:
                click.echo(
                    f"Error: Center ({self.cur_pulse}) must be between Min ({self.pulse_min}) and Max ({self.pulse_max})."
                )
                return
        elif self.cur_target == self.TARGET_MIN:
            if HARDWARE_PULSE_MIN <= self.cur_pulse < self.pulse_center:
                self.pulse_min = self.cur_pulse
            else:
                click.echo(
                    f"Error: Min ({self.cur_pulse}) must be less than Center ({self.pulse_center})."
                )
                return
        elif self.cur_target == self.TARGET_MAX:
            if self.pulse_center < self.cur_pulse <= HARDWARE_PULSE_MAX:
                self.pulse_max = self.cur_pulse
            else:
                click.echo(
                    f"Error: Max ({self.cur_pulse}) must be greater than Center ({self.pulse_center})."
                )
                return

        new_cal = ServoCalibration(
            pulse_min=self.pulse_min,
            pulse_max=self.pulse_max,
            pulse_center=self.pulse_center,
            speed=self.speed,
        )
        self.manager.set_calibration(self.pin, new_cal)
        self.manager.save()
        click.echo(f"✓ Saved! {target_str} for {self.endpoint_label} = pulse {self.cur_pulse}")

    def display_help(self) -> None:
        click.echo(
            """

=== Servo Calibration Help ===

Select Target:
  [Tab] / [Shift+Tab] : Cycle through Min, Center, Max
  [v] : Select Min (-90°)
  [c] : Select Center (0°)
  [x] : Select Max (90°)

Adjust Pulse:
  [Up] / [Down] : Large step adjustment (±20)
  [w] / [s]     : Fine-tune adjustment (±1)

Speed Control:
  [+] / [-] : Adjust speed limit (±10%)

Save:
  [Enter] / [Space] : Save current pulse AND speed for selected target

Misc:
  [q] : Quit
  [h] : Show this help
"""
        )
        self.show()

    def quit(self) -> None:
        click.echo("\n=== Quit ===")
        self.running = False

    def end(self) -> None:
        """Cleanup on exit."""
        self.servo.off()
        self.show()
        if self.owns_servo:
            self.servo.close()


@click.command("calib")
@click.argument("pin", type=str, required=False)
@click.option(
    "-c",
    "--config",
    type=click.Path(),
    default="servo.json",
    help="Path to configuration file.",
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Enable debug output.",
)
@click.option(
    "--show",
    is_flag=True,
    help="Show calibration without interactive mode.",
)
@backend_options
def calib(
    pin: str | None,
    config: str,
    debug: bool,
    show: bool,
    backend_name: str | None,
    chip: int | None,
    bus_id: int | None,
    frequency_hz: int | None,
    address: str | None,
    pin_channel_map: str | None,
    channel_map: str | None,
) -> None:
    """Interactive servo calibration tool."""
    manager = ConfigManager(config)
    manager.load()
    try:
        pin_value = parse_endpoint_value(pin) if pin is not None else None
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="pin") from exc

    if show or pin_value is None:
        if pin_value is not None:
            _print_calibration(pin_value, manager.get_calibration(pin_value))
        else:
            all_cals = manager.get_all_endpoint_calibrations()
            if not all_cals:
                click.echo("No calibrations stored.")
                click.echo(f"Config file: {config}")
            else:
                click.echo(f"Config: {config}")
                for endpoint_id, cal in sorted(all_cals.items()):
                    _print_calibration(endpoint_id, cal)
        return

    servo = None
    runtime = None
    app = None
    try:
        servo, manager, runtime, resolved_backend, backend_kwargs = create_servo_from_config(
            pin=pin_value,
            config_path=config,
            backend_name=backend_name,
            chip=chip,
            bus_id=bus_id,
            frequency_hz=frequency_hz,
            address=address,
            pin_channel_map=pin_channel_map,
            channel_map=channel_map,
        )
        if debug:
            click.echo(f"Backend: {resolved_backend}")
            click.echo(f"Backend kwargs: {backend_kwargs}")

        app = CalibApp(servo, pin_value, config, manager, debug=debug)
        app.main()
    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
    except click.Abort:
        raise
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)
    finally:
        if app is not None:
            app.end()
        elif servo is not None:
            servo.close()
        close_runtime_handle(runtime)


def _print_calibration(pin: int | str, cal: ServoCalibration) -> None:
    """Print calibration info for an endpoint."""
    click.echo(f"Endpoint {format_endpoint_label(pin)}:")
    click.echo(f"  Pulse: {cal.pulse_min} / {cal.pulse_center} / {cal.pulse_max}")
    click.echo(f"  Angle: {cal.angle_min}° / {cal.angle_center}° / {cal.angle_max}°")
    click.echo(f"  Speed: {cal.speed}%")
