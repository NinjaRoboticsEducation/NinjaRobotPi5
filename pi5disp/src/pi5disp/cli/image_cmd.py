"""Image command — Display an image file on the screen."""

from __future__ import annotations

import click
from PIL import Image as PILImage

from ._common import create_display


@click.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--rotation", "-r", type=int, default=None, help="Override rotation.")
def image(path: str, rotation: int | None) -> None:
    """Display an image file on the ST7789V display."""
    try:
        lcd = create_display(rotation=rotation)
        img = PILImage.open(path).convert("RGB")
        lcd.display(img)
        click.echo(f"Displayed: {path} ({img.size[0]}×{img.size[1]})")
        lcd.close()
    except Exception as exc:
        click.echo(f"Error: {exc}")
