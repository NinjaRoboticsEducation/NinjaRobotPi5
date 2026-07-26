"""Info command — Display driver state and configuration."""

from __future__ import annotations

import click

from pi5disp.config.config_manager import DISPLAY_PROFILES

from ._common import create_display, load_config


@click.command()
def info() -> None:
    """Show display driver state and current configuration."""
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
        lcd = create_display()
        health = lcd.health_check()
        status = (
            click.style("✅ Connected", fg="green") if health else click.style("❌ Error", fg="red")
        )
        click.echo(f"  Hardware:    {status}")
        lcd.close()
    except Exception as exc:
        click.echo(f"  Hardware:    {click.style(f'❌ {exc}', fg='red')}")

    click.echo()
