"""Procedural Pillow faces for the V4 robot display."""

from __future__ import annotations

from typing import cast

from PIL import Image, ImageColor, ImageDraw

from .behavior_models import Color, FaceName


def render_face(
    expression: FaceName,
    *,
    width: int,
    height: int,
    background: Color,
    foreground: Color,
    accent: Color,
) -> Image.Image:
    """Render a simple scalable robot face without external image assets."""
    if width < 120 or height < 120:
        raise ValueError("face rendering requires at least 120 by 120 pixels")
    image = Image.new("RGB", (width, height), ImageColor.getrgb(background))
    draw = ImageDraw.Draw(image)
    fg = cast(tuple[int, int, int], ImageColor.getrgb(foreground))
    highlight = cast(tuple[int, int, int], ImageColor.getrgb(accent))
    stroke = max(4, min(width, height) // 36)
    eye_y = int(height * 0.38)
    left_x = int(width * 0.32)
    right_x = int(width * 0.68)
    eye_radius = max(7, min(width, height) // 20)

    if expression == "happy":
        _happy_eyes(draw, left_x, right_x, eye_y, eye_radius, fg, stroke)
        draw.arc(_mouth_box(width, height), 10, 170, fill=highlight, width=stroke)
    elif expression == "thinking":
        draw.ellipse(_eye_box(left_x, eye_y, eye_radius), fill=fg)
        draw.ellipse(_eye_box(right_x, eye_y, eye_radius), outline=fg, width=stroke)
        draw.line(
            (int(width * 0.43), int(height * 0.67), int(width * 0.62), int(height * 0.64)),
            fill=highlight,
            width=stroke,
        )
        bubble_radius = max(5, eye_radius // 2)
        draw.ellipse(
            _eye_box(int(width * 0.79), int(height * 0.20), bubble_radius),
            fill=highlight,
        )
    elif expression == "success":
        _happy_eyes(draw, left_x, right_x, eye_y, eye_radius, fg, stroke)
        draw.arc(_mouth_box(width, height), 10, 170, fill=highlight, width=stroke)
        draw.line(
            (
                int(width * 0.76),
                int(height * 0.25),
                int(width * 0.81),
                int(height * 0.31),
                int(width * 0.91),
                int(height * 0.17),
            ),
            fill=highlight,
            width=stroke,
            joint="curve",
        )
    elif expression == "warning":
        draw.polygon(
            (
                (width // 2, int(height * 0.10)),
                (int(width * 0.90), int(height * 0.84)),
                (int(width * 0.10), int(height * 0.84)),
            ),
            outline=highlight,
            width=stroke,
        )
        draw.line(
            (width // 2, int(height * 0.34), width // 2, int(height * 0.62)),
            fill=fg,
            width=stroke,
        )
        draw.ellipse(
            _eye_box(width // 2, int(height * 0.72), max(4, eye_radius // 3)),
            fill=fg,
        )
    elif expression == "error":
        for center_x in (left_x, right_x):
            draw.line(
                (
                    center_x - eye_radius,
                    eye_y - eye_radius,
                    center_x + eye_radius,
                    eye_y + eye_radius,
                ),
                fill=highlight,
                width=stroke,
            )
            draw.line(
                (
                    center_x + eye_radius,
                    eye_y - eye_radius,
                    center_x - eye_radius,
                    eye_y + eye_radius,
                ),
                fill=highlight,
                width=stroke,
            )
        draw.arc(_mouth_box(width, height), 190, 350, fill=fg, width=stroke)
    else:
        draw.ellipse(_eye_box(left_x, eye_y, eye_radius), fill=fg)
        draw.ellipse(_eye_box(right_x, eye_y, eye_radius), fill=fg)
        draw.line(
            (int(width * 0.40), int(height * 0.66), int(width * 0.60), int(height * 0.66)),
            fill=highlight,
            width=stroke,
        )
    return image


def _eye_box(center_x: int, center_y: int, radius: int) -> tuple[int, int, int, int]:
    return (
        center_x - radius,
        center_y - radius,
        center_x + radius,
        center_y + radius,
    )


def _mouth_box(width: int, height: int) -> tuple[int, int, int, int]:
    return (
        int(width * 0.35),
        int(height * 0.48),
        int(width * 0.65),
        int(height * 0.76),
    )


def _happy_eyes(
    draw: ImageDraw.ImageDraw,
    left_x: int,
    right_x: int,
    eye_y: int,
    radius: int,
    color: tuple[int, int, int],
    stroke: int,
) -> None:
    for center_x in (left_x, right_x):
        draw.arc(
            _eye_box(center_x, eye_y, radius),
            start=190,
            end=350,
            fill=color,
            width=stroke,
        )
