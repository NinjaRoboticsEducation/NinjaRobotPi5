"""Demo command — Bouncing ball animation demo."""

from __future__ import annotations

import random
import time

import click
from PIL import Image, ImageDraw

from ._common import create_display


@click.command()
@click.option("--num-balls", default=3, type=int, help="Number of balls.")
@click.option("--fps", default=30, type=int, help="Target frames per second.")
@click.option("--duration", default=10.0, type=float, help="Duration in seconds.")
def demo(num_balls: int, fps: int, duration: float) -> None:
    """Run a bouncing ball animation demo."""
    try:
        lcd = create_display()
        click.echo(f"Running demo: {num_balls} balls, {fps} FPS, {duration}s (Ctrl+C to stop)")
        _run_ball_demo(lcd, num_balls, fps, duration)
        lcd.clear()
        lcd.close()
        click.echo("Demo complete.")
    except KeyboardInterrupt:
        click.echo("\nDemo stopped.")
    except Exception as exc:
        click.echo(f"Error: {exc}")


def _run_ball_demo(lcd, num_balls: int, fps: int, duration: float) -> None:
    """Run the bouncing ball animation loop."""
    width, height = lcd.width, lcd.height
    frame_time = 1.0 / fps

    balls = []
    for _ in range(num_balls):
        radius = random.randint(8, 20)
        balls.append(
            {
                "x": random.uniform(radius, width - radius),
                "y": random.uniform(radius, height - radius),
                "vx": random.uniform(-3, 3),
                "vy": random.uniform(-3, 3),
                "radius": radius,
                "color": (
                    random.randint(100, 255),
                    random.randint(100, 255),
                    random.randint(100, 255),
                ),
            }
        )

    gravity = 0.15
    damping = 0.98
    start_time = time.monotonic()
    frame_count = 0

    while time.monotonic() - start_time < duration:
        frame_start = time.monotonic()
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        for ball in balls:
            ball["vy"] += gravity
            ball["vx"] *= damping
            ball["vy"] *= damping
            ball["x"] += ball["vx"]
            ball["y"] += ball["vy"]

            radius = ball["radius"]

            if ball["x"] - radius < 0:
                ball["x"] = radius
                ball["vx"] = abs(ball["vx"])
            elif ball["x"] + radius > width:
                ball["x"] = width - radius
                ball["vx"] = -abs(ball["vx"])

            if ball["y"] - radius < 0:
                ball["y"] = radius
                ball["vy"] = abs(ball["vy"])
            elif ball["y"] + radius > height:
                ball["y"] = height - radius
                ball["vy"] = -abs(ball["vy"]) * 0.85

            x_pos, y_pos = int(ball["x"]), int(ball["y"])
            draw.ellipse(
                [x_pos - radius, y_pos - radius, x_pos + radius, y_pos + radius],
                fill=ball["color"],
            )

        lcd.display(image)
        frame_count += 1

        elapsed = time.monotonic() - frame_start
        sleep_time = frame_time - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    total_time = time.monotonic() - start_time
    actual_fps = frame_count / total_time if total_time > 0 else 0
    click.echo(f"  Rendered {frame_count} frames in {total_time:.1f}s ({actual_fps:.1f} FPS)")
