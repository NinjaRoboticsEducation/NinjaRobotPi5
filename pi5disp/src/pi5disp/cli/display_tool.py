"""Interactive display tool — Menu-driven display testing and configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import click
from PIL import Image as PILImage
from PIL import Image, ImageDraw

from pi5disp.cli._common import create_display, load_config
from pi5disp.config.config_manager import ConfigManager, DISPLAY_PROFILES
from pi5disp.effects.text_ticker import TextTicker, load_font


@dataclass
class DisplayToolSession:
    """Keeps one live display instance across interactive tool actions."""

    lcd: Any | None = None

    def ensure_display(self):
        """Create the display lazily and reuse it until the session ends."""
        if self.lcd is None or not self.lcd.health_check():
            self.close()
            self.lcd = create_display()
        return self.lcd

    def close(self) -> None:
        """Close the live display instance if one exists."""
        if self.lcd is None:
            return
        try:
            self.lcd.close()
        finally:
            self.lcd = None


@click.command("display-tool")
def display_tool() -> None:
    """Launch the interactive display tool."""
    session = DisplayToolSession()
    click.echo()
    click.echo(
        click.style("╔══════════════════════════════════════════════════════════════╗", fg="cyan")
    )
    click.echo(
        click.style("║               pi5disp Interactive Tool                      ║", fg="cyan")
    )
    click.echo(
        click.style("╠══════════════════════════════════════════════════════════════╣", fg="cyan")
    )
    click.echo(
        click.style("║  1. Init          - Set up display module & pin config      ║", fg="cyan")
    )
    click.echo(
        click.style("║  2. Show Image    - Display an image file                   ║", fg="cyan")
    )
    click.echo(
        click.style("║  3. Show Text     - Display text (with optional scroll)     ║", fg="cyan")
    )
    click.echo(
        click.style("║  4. Ball Demo     - Run bouncing ball animation             ║", fg="cyan")
    )
    click.echo(
        click.style("║  5. Brightness    - Adjust backlight brightness             ║", fg="cyan")
    )
    click.echo(
        click.style("║  6. Info          - Show driver state & config              ║", fg="cyan")
    )
    click.echo(
        click.style("║  7. Clear         - Clear the display                       ║", fg="cyan")
    )
    click.echo(
        click.style("║  8. Config        - Export/import configuration             ║", fg="cyan")
    )
    click.echo(
        click.style("║  9. Exit                                                    ║", fg="cyan")
    )
    click.echo(
        click.style("╚══════════════════════════════════════════════════════════════╝", fg="cyan")
    )

    try:
        while True:
            try:
                choice = click.prompt("\nSelect an option", type=int, default=9)
            except (EOFError, KeyboardInterrupt):
                click.echo("\nExiting.")
                break

            if choice == 1:
                _do_init(session)
            elif choice == 2:
                _do_image(session)
            elif choice == 3:
                _do_text(session)
            elif choice == 4:
                _do_demo(session)
            elif choice == 5:
                _do_brightness(session)
            elif choice == 6:
                _do_info(session)
            elif choice == 7:
                _do_clear(session)
            elif choice == 8:
                _do_config(session)
            elif choice == 9:
                click.echo("Goodbye!")
                break
            else:
                click.echo("Invalid choice. Please enter 1-9.")
    finally:
        session.close()


def _do_init(session: DisplayToolSession) -> None:
    """Run the init wizard."""
    config_manager = ConfigManager()
    config_manager.init_config(interactive=True)
    session.close()


def _do_image(session: DisplayToolSession) -> None:
    """Prompt for path and display image."""
    path = click.prompt("Image path", type=str)
    try:
        lcd = session.ensure_display()
        img = PILImage.open(path).convert("RGB")
        lcd.display(img)
        click.echo(f"Displayed: {path} ({img.size[0]}×{img.size[1]})")
    except Exception as exc:
        click.echo(f"Error: {exc}")


def _do_text(session: DisplayToolSession) -> None:
    """Prompt for text and display it."""
    text_content = click.prompt("Text to display", type=str)
    scroll = click.confirm("Enable scrolling?", default=False)
    lang = click.prompt("Language (en/ja/zh-tw)", type=str, default="en")
    try:
        lcd = session.ensure_display()

        if scroll:
            ticker = TextTicker(
                lcd,
                text_content,
                font_size=32,
                color=(255, 255, 255),
                bg_color=(0, 0, 0),
                speed=2.0,
                language=lang,
            )
            click.echo(f'Scrolling: "{text_content}" (Ctrl+C to stop)')
            ticker.start()
            try:
                ticker._stop_event.wait(15.0)
            except KeyboardInterrupt:
                pass
            ticker.stop()
            return

        font = load_font(lang, 32)
        image = Image.new("RGB", (lcd.width, lcd.height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        bbox = draw.textbbox((0, 0), text_content, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x_pos = (lcd.width - text_w) // 2
        y_pos = (lcd.height - text_h) // 2

        draw.text((x_pos, y_pos), text_content, font=font, fill=(255, 255, 255))
        lcd.display(image)
        click.echo(f'Displayed: "{text_content}"')
    except Exception as exc:
        click.echo(f"Error: {exc}")


def _do_demo(session: DisplayToolSession) -> None:
    """Run ball demo with prompts."""
    from pi5disp.cli.demo_cmd import _run_ball_demo

    num_balls = click.prompt("Number of balls", type=int, default=3)
    duration = click.prompt("Duration (seconds)", type=float, default=10.0)
    try:
        lcd = session.ensure_display()
        click.echo(f"Running demo ({num_balls} balls, {duration}s)...")
        _run_ball_demo(lcd, num_balls, 30, duration)
        lcd.clear()
        click.echo("Demo complete.")
    except KeyboardInterrupt:
        click.echo("\nDemo stopped.")
    except Exception as exc:
        click.echo(f"Error: {exc}")


def _do_brightness(session: DisplayToolSession) -> None:
    """Prompt for brightness and apply it."""
    percent = click.prompt("Brightness (0-100%)", type=int, default=100)
    clamped = max(0, min(100, percent))
    try:
        config_manager = ConfigManager()
        config_manager.load()
        config_manager.set("brightness", clamped)
        lcd = session.ensure_display()
        lcd.set_brightness(clamped)
        click.echo(f"Brightness set to {clamped}%")
    except Exception as exc:
        click.echo(f"Error: {exc}")


def _do_info(session: DisplayToolSession) -> None:
    """Show display info."""
    config_manager, config = load_config()
    profile_key = config.get("display_profile", "st7789v_2inch8")
    profile = DISPLAY_PROFILES.get(profile_key, {})
    profile_name = profile.get("name", profile_key)

    click.echo()
    click.echo(
        click.style("╔══════════════════════════════════════════════════════════════╗", fg="cyan")
    )
    click.echo(
        click.style("║               pi5disp — Display Information                  ║", fg="cyan")
    )
    click.echo(
        click.style("╚══════════════════════════════════════════════════════════════╝", fg="cyan")
    )
    click.echo()
    click.echo(f"  Display:     {profile_name}")
    click.echo(f"  Resolution:  {config.get('width', 240)} × {config.get('height', 320)}")
    click.echo(f"  Rotation:    {config.get('rotation', 0)}°")
    click.echo(f"  Brightness:  {config.get('brightness', 100)}%")
    click.echo(f"  SPI Speed:   {config.get('spi_speed_mhz', 32)} MHz")
    click.echo()
    click.echo(click.style("  GPIO Pins:", bold=True))
    click.echo(f"    DC:        BCM {config.get('dc_pin', 14)}")
    click.echo(f"    RST:       BCM {config.get('rst_pin', 15)}")
    click.echo(f"    BLK:       BCM {config.get('backlight_pin', 16)}")
    click.echo()
    click.echo(f"  Config:      {config_manager.config_path}")
    click.echo()

    try:
        health = session.ensure_display().health_check()
        status = (
            click.style("✅ Connected", fg="green") if health else click.style("❌ Error", fg="red")
        )
        click.echo(f"  Hardware:    {status}")
    except Exception as exc:
        click.echo(f"  Hardware:    {click.style(f'❌ {exc}', fg='red')}")

    click.echo()


def _do_clear(session: DisplayToolSession) -> None:
    """Clear the display."""
    try:
        session.ensure_display().clear()
        click.echo("Display cleared.")
    except Exception as exc:
        click.echo(f"Error: {exc}")


def _do_config(session: DisplayToolSession) -> None:
    """Config management submenu."""
    click.echo("\n  1. Show config")
    click.echo("  2. Export config")
    click.echo("  3. Import config")
    choice = click.prompt("  Choice", type=int, default=1)

    from pi5disp.__main__ import config_export, config_import, show

    if choice == 1:
        ctx = click.Context(show)
        ctx.invoke(show)
    elif choice == 2:
        path = click.prompt("Export path", type=str)
        ctx = click.Context(config_export)
        ctx.invoke(config_export, path=path)
    elif choice == 3:
        path = click.prompt("Import path", type=str)
        ctx = click.Context(config_import)
        ctx.invoke(config_import, path=path)
        session.close()
