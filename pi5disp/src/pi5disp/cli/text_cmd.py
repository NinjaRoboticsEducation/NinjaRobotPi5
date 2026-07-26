"""Text command — Display or scroll text on the screen."""

from __future__ import annotations

import time

import click
from PIL import Image, ImageDraw

from pi5disp.effects.text_ticker import TextTicker, load_font

from ._common import create_display


@click.command()
@click.argument("text_content")
@click.option("--scroll", is_flag=True, help="Enable scrolling marquee.")
@click.option("--lang", default="en", help="Font language: en, ja, zh-tw.")
@click.option("--size", default=32, type=int, help="Font size in pixels.")
@click.option("--color", default="255,255,255", help="Text color R,G,B.")
@click.option("--bg", default="0,0,0", help="Background color R,G,B.")
@click.option("--speed", default=2.0, type=float, help="Scroll speed (pixels/frame).")
@click.option("--duration", default=10.0, type=float, help="Scroll duration (seconds).")
def text(
    text_content: str,
    scroll: bool,
    lang: str,
    size: int,
    color: str,
    bg: str,
    speed: float,
    duration: float,
) -> None:
    """Display text on the ST7789V display."""
    try:
        lcd = create_display()
        text_color = tuple(int(component) for component in color.split(","))
        bg_color = tuple(int(component) for component in bg.split(","))

        if scroll:
            ticker = TextTicker(
                lcd,
                text_content,
                font_size=size,
                color=text_color,
                bg_color=bg_color,
                speed=speed,
                language=lang,
            )
            click.echo(f'Scrolling: "{text_content}" (Ctrl+C to stop)')
            ticker.start()
            try:
                time.sleep(duration)
            except KeyboardInterrupt:
                pass
            ticker.stop()
        else:
            font = load_font(lang, size)
            image = Image.new("RGB", (lcd.width, lcd.height), bg_color)
            draw = ImageDraw.Draw(image)
            bbox = draw.textbbox((0, 0), text_content, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x_pos = (lcd.width - text_w) // 2
            y_pos = (lcd.height - text_h) // 2

            draw.text((x_pos, y_pos), text_content, font=font, fill=text_color)
            lcd.display(image)
            click.echo(f'Displayed: "{text_content}"')

        lcd.close()
    except Exception as exc:
        click.echo(f"Error: {exc}")
