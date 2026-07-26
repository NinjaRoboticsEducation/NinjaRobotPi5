"""Scalable animated Pillow faces embedded in NinjaRobotPi5."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

from PIL import Image, ImageColor, ImageDraw, ImageFont

from .behavior_models import Color, FaceName, normalize_face_name

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class _FaceGeometry:
    width: int
    height: int
    center_x: int
    eye_y: int
    mouth_y: int
    eye_offset: int
    eye_radius: int
    pupil_radius: int
    stroke: int

    @classmethod
    def build(cls, width: int, height: int) -> _FaceGeometry:
        scale = min(width, height)
        return cls(
            width=width,
            height=height,
            center_x=width // 2,
            eye_y=int(height * 0.36),
            mouth_y=int(height * 0.68),
            eye_offset=int(width * 0.19),
            eye_radius=max(18, int(scale * 0.15)),
            pupil_radius=max(8, int(scale * 0.065)),
            stroke=max(5, int(scale * 0.038)),
        )

    @property
    def eye_centers(self) -> tuple[int, int]:
        return self.center_x - self.eye_offset, self.center_x + self.eye_offset


def render_face(
    expression: FaceName | str,
    *,
    width: int,
    height: int,
    background: Color,
    foreground: Color,
    accent: Color,
    elapsed_seconds: float = 0.0,
) -> Image.Image:
    """Render one deterministic frame of an embedded animated face."""
    if width < 120 or height < 120:
        raise ValueError("face rendering requires at least 120 by 120 pixels")
    if elapsed_seconds < 0 or not math.isfinite(elapsed_seconds):
        raise ValueError("elapsed_seconds must be a finite non-negative number")

    name = normalize_face_name(expression)
    bg = cast(RGB, ImageColor.getrgb(background))
    fg = cast(RGB, ImageColor.getrgb(foreground))
    highlight = cast(RGB, ImageColor.getrgb(accent))
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    geometry = _FaceGeometry.build(width, height)
    renderers = {
        "idle": _idle,
        "happy": _happy,
        "laughing": _laughing,
        "sad": _sad,
        "cry": _cry,
        "angry": _angry,
        "surprising": _surprising,
        "sleepy": _sleepy,
        "speaking": _speaking,
        "shy": _shy,
        "scary": _scary,
        "exciting": _exciting,
        "confusing": _confusing,
        "greeting": _greeting,
        "listening": _listening,
        "thinking": _thinking,
        "curious": _curious,
        "success": _success,
        "warning": _warning,
        "error": _error,
    }
    renderers[name](draw, geometry, elapsed_seconds, bg, fg, highlight)
    return image


def render_emergency_stop(*, width: int, height: int) -> Image.Image:
    """Render the persistent Level 2 stop screen without external assets."""
    if width < 120 or height < 120:
        raise ValueError("emergency-stop rendering requires at least 120 by 120 pixels")

    image = Image.new("RGB", (width, height), "#240000")
    draw = ImageDraw.Draw(image)
    scale = min(width, height)
    sign_center = (int(width * 0.27), int(height * 0.43))
    radius = int(scale * 0.27)
    octagon = [
        (
            sign_center[0] + radius * math.cos(math.pi / 8 + index * math.pi / 4),
            sign_center[1] + radius * math.sin(math.pi / 8 + index * math.pi / 4),
        )
        for index in range(8)
    ]
    border_width = max(4, int(scale * 0.025))
    draw.polygon(octagon, fill="#D00000", outline="#FFFFFF", width=border_width)
    _centered_text(
        draw,
        position=sign_center,
        text="STOP",
        size=max(18, int(scale * 0.12)),
        fill="#FFFFFF",
    )
    _centered_text(
        draw,
        position=(int(width * 0.70), int(height * 0.39)),
        text="SYSTEM\nSTOPPED",
        size=max(16, int(scale * 0.075)),
        fill="#FFFFFF",
        spacing=max(2, int(scale * 0.015)),
    )
    _centered_text(
        draw,
        position=(width // 2, int(height * 0.84)),
        text="Select Resume Robot Movement",
        size=max(10, int(scale * 0.043)),
        fill="#FFD54F",
    )
    return image


def _centered_text(
    draw: ImageDraw.ImageDraw,
    *,
    position: tuple[int, int],
    text: str,
    size: int,
    fill: RGB | str,
    spacing: int = 4,
) -> None:
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - compatibility with older Pillow
        font = ImageFont.load_default()
    draw.multiline_text(
        position,
        text,
        font=font,
        fill=fill,
        anchor="mm",
        align="center",
        spacing=spacing,
    )


def _eyes(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    bg: RGB,
    fg: RGB,
    *,
    left_shift: tuple[float, float] = (0, 0),
    right_shift: tuple[float, float] = (0, 0),
    pupil_scale: float = 1.0,
) -> None:
    for center_x, shift in zip(g.eye_centers, (left_shift, right_shift), strict=True):
        draw.ellipse(_box(center_x, g.eye_y, g.eye_radius), fill=fg)
        radius = max(3, int(g.pupil_radius * pupil_scale))
        draw.ellipse(
            _box(
                int(center_x + shift[0]),
                int(g.eye_y + shift[1]),
                radius,
            ),
            fill=bg,
        )


def _closed_eyes(draw: ImageDraw.ImageDraw, g: _FaceGeometry, fg: RGB) -> None:
    for center_x in g.eye_centers:
        draw.arc(
            _box(center_x, g.eye_y, g.eye_radius),
            190,
            350,
            fill=fg,
            width=g.stroke,
        )


def _smile(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    color: RGB,
    *,
    y_offset: float = 0,
) -> None:
    draw.arc(
        (
            int(g.width * 0.32),
            int(g.mouth_y - g.height * 0.12 + y_offset),
            int(g.width * 0.68),
            int(g.mouth_y + g.height * 0.12 + y_offset),
        ),
        5,
        175,
        fill=color,
        width=g.stroke,
    )


def _frown(draw: ImageDraw.ImageDraw, g: _FaceGeometry, color: RGB) -> None:
    draw.arc(
        (
            int(g.width * 0.35),
            int(g.mouth_y - g.height * 0.02),
            int(g.width * 0.65),
            int(g.mouth_y + g.height * 0.18),
        ),
        185,
        355,
        fill=color,
        width=g.stroke,
    )


def _symbol(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    text: str,
    color: RGB,
    *,
    x: float = 0.82,
    y: float = 0.16,
) -> None:
    size = max(20, min(g.width, g.height) // 5)
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - Pillow before scalable default fonts
        font = ImageFont.load_default()
    draw.text(
        (int(g.width * x), int(g.height * y)),
        text,
        fill=color,
        font=font,
        anchor="mm",
    )


def _idle(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del accent
    if t % 3.2 < 0.18:
        for center_x in g.eye_centers:
            draw.line(
                (center_x - g.eye_radius, g.eye_y, center_x + g.eye_radius, g.eye_y),
                fill=fg,
                width=g.stroke,
            )
    else:
        _eyes(draw, g, bg, fg)
    _smile(draw, g, fg, y_offset=math.sin(t * 2.2) * 2)


def _happy(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del bg
    _closed_eyes(draw, g, fg)
    _smile(draw, g, accent, y_offset=math.sin(t * 5.5) * 3)


def _laughing(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del bg
    _closed_eyes(draw, g, fg)
    height = int(g.height * (0.08 + 0.08 * abs(math.sin(t * 8))))
    draw.rounded_rectangle(
        (
            int(g.width * 0.32),
            g.mouth_y - height // 2,
            int(g.width * 0.68),
            g.mouth_y + height,
        ),
        radius=max(4, height // 3),
        fill=accent,
    )


def _sad(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del accent
    lowered = g.pupil_radius * (0.55 + 0.12 * math.sin(t * 2))
    _eyes(
        draw,
        g,
        bg,
        fg,
        left_shift=(0, lowered),
        right_shift=(0, lowered),
    )
    left_x, right_x = g.eye_centers
    draw.line(
        (left_x - g.eye_radius, g.eye_y - g.eye_radius, left_x, g.eye_y - g.eye_radius // 2),
        fill=fg,
        width=g.stroke,
    )
    draw.line(
        (
            right_x + g.eye_radius,
            g.eye_y - g.eye_radius,
            right_x,
            g.eye_y - g.eye_radius // 2,
        ),
        fill=fg,
        width=g.stroke,
    )
    _frown(draw, g, fg)


def _cry(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    _sad(draw, g, t, bg, fg, accent)
    tear_color = cast(RGB, ImageColor.getrgb("#00BFFF"))
    travel = max(20, g.height - g.eye_y)
    for index, center_x in enumerate(g.eye_centers):
        y = int(g.eye_y + g.eye_radius + (t * 110 + index * 37) % travel)
        draw.line((center_x, y, center_x, y + g.stroke * 3), fill=tear_color, width=g.stroke)


def _angry(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del accent
    shake = int(math.sin(t * 18) * 3)
    _eyes(draw, g, bg, fg)
    left_x, right_x = g.eye_centers
    draw.line(
        (
            left_x - g.eye_radius,
            g.eye_y - g.eye_radius + shake,
            left_x + g.eye_radius,
            g.eye_y - g.eye_radius // 3 + shake,
        ),
        fill=fg,
        width=g.stroke,
    )
    draw.line(
        (
            right_x + g.eye_radius,
            g.eye_y - g.eye_radius + shake,
            right_x - g.eye_radius,
            g.eye_y - g.eye_radius // 3 + shake,
        ),
        fill=fg,
        width=g.stroke,
    )
    _frown(draw, g, fg)


def _surprising(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del accent
    openness = min(1.0, t * 4 + 0.15)
    _eyes(draw, g, bg, fg, pupil_scale=1.0 - openness * 0.45)
    radius = max(g.stroke, int(g.eye_radius * (0.3 + openness * 0.55)))
    draw.ellipse(_box(g.center_x, g.mouth_y, radius), outline=fg, width=g.stroke)


def _sleepy(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del bg
    for center_x in g.eye_centers:
        draw.arc(
            _box(center_x, g.eye_y, g.eye_radius),
            5,
            175,
            fill=fg,
            width=g.stroke,
        )
    radius = max(g.stroke, int(g.eye_radius * (0.25 + 0.08 * math.sin(t * 2))))
    draw.ellipse(_box(g.center_x, g.mouth_y, radius), outline=fg, width=g.stroke)
    _symbol(draw, g, "z", accent)


def _speaking(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del accent
    _eyes(draw, g, bg, fg)
    height = int(g.eye_radius * (0.5 + 0.7 * ((math.sin(t * 12) + 1) / 2)))
    draw.ellipse(
        (
            g.center_x - g.eye_radius,
            g.mouth_y - height // 2,
            g.center_x + g.eye_radius,
            g.mouth_y + height // 2,
        ),
        fill=fg,
    )


def _shy(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del accent
    _eyes(
        draw,
        g,
        bg,
        fg,
        left_shift=(-g.pupil_radius, g.pupil_radius // 2),
        right_shift=(-g.pupil_radius, g.pupil_radius // 2),
    )
    blush = cast(RGB, ImageColor.getrgb("#FF69B4"))
    blush_offset = int(2 + abs(math.sin(t * 3)) * g.stroke)
    for center_x in g.eye_centers:
        draw.ellipse(
            (
                center_x - g.eye_radius,
                g.eye_y + g.eye_radius // 2 + blush_offset,
                center_x + g.eye_radius,
                g.eye_y + g.eye_radius + blush_offset,
            ),
            fill=blush,
        )
    _wavy_mouth(draw, g, fg)


def _scary(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del accent
    shake = math.sin(t * 40) * 4
    _eyes(
        draw,
        g,
        bg,
        fg,
        left_shift=(0, shake),
        right_shift=(0, -shake),
        pupil_scale=0.45,
    )
    _frown(draw, g, fg)


def _exciting(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del bg
    for center_x in g.eye_centers:
        draw.polygon(_star(center_x, g.eye_y, g.eye_radius, t * 4), fill=fg)
    _smile(draw, g, accent)


def _confusing(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    _eyes(
        draw,
        g,
        bg,
        fg,
        left_shift=(-g.pupil_radius, 0),
        right_shift=(g.pupil_radius, 0),
    )
    _wavy_mouth(draw, g, fg)
    if t > 0.35:
        _symbol(draw, g, "?", accent)


def _greeting(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    _happy(draw, g, t, bg, fg, accent)
    _symbol(draw, g, "!", accent)


def _listening(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    del accent
    shift = math.sin(t * 2) * (g.pupil_radius // 2)
    _eyes(
        draw,
        g,
        bg,
        fg,
        left_shift=(shift, -g.pupil_radius // 2),
        right_shift=(shift, -g.pupil_radius // 2),
    )
    _smile(draw, g, fg)


def _thinking(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    shift = math.sin(t * 2.5) * g.pupil_radius
    _eyes(
        draw,
        g,
        bg,
        fg,
        left_shift=(shift, g.pupil_radius // 2),
        right_shift=(shift, -g.pupil_radius // 3),
    )
    _frown(draw, g, fg)
    if int(t * 2) % 3 == 0:
        _symbol(draw, g, "...", accent)


def _curious(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    _eyes(
        draw,
        g,
        bg,
        fg,
        left_shift=(g.pupil_radius // 2, -g.pupil_radius // 2),
        right_shift=(g.pupil_radius // 2, -g.pupil_radius // 2),
    )
    radius = max(g.stroke, g.eye_radius // 3)
    draw.ellipse(_box(g.center_x, g.mouth_y, radius), outline=fg, width=g.stroke)
    if t > 0.25:
        _symbol(draw, g, "?", accent)


def _success(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    _happy(draw, g, t, bg, fg, accent)
    points = (
        int(g.width * 0.73),
        int(g.height * 0.34),
        int(g.width * 0.79),
        int(g.height * 0.41),
        int(g.width * 0.91),
        int(g.height * 0.23),
    )
    draw.line(points, fill=accent, width=g.stroke, joint="curve")


def _warning(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    _surprising(draw, g, t, bg, fg, accent)
    warning = cast(RGB, ImageColor.getrgb("#FFD54F"))
    _symbol(draw, g, "!", warning)


def _error(
    draw: ImageDraw.ImageDraw,
    g: _FaceGeometry,
    t: float,
    bg: RGB,
    fg: RGB,
    accent: RGB,
) -> None:
    _sad(draw, g, t, bg, fg, accent)
    red = cast(RGB, ImageColor.getrgb("#EF5350"))
    radius = max(12, g.eye_radius // 2)
    center_y = g.mouth_y + int(math.sin(t * 8) * 3)
    draw.line(
        (g.center_x - radius, center_y - radius, g.center_x + radius, center_y + radius),
        fill=red,
        width=g.stroke,
    )
    draw.line(
        (g.center_x + radius, center_y - radius, g.center_x - radius, center_y + radius),
        fill=red,
        width=g.stroke,
    )


def _wavy_mouth(draw: ImageDraw.ImageDraw, g: _FaceGeometry, color: RGB) -> None:
    points: list[tuple[int, int]] = []
    for index in range(5):
        points.append(
            (
                int(g.width * (0.37 + index * 0.065)),
                g.mouth_y + (g.stroke if index % 2 == 0 else -g.stroke),
            )
        )
    draw.line(points, fill=color, width=max(3, g.stroke - 2), joint="curve")


def _star(center_x: int, center_y: int, radius: int, rotation: float) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(10):
        angle = rotation + index * math.pi / 5
        point_radius = radius if index % 2 == 0 else radius * 0.45
        points.append(
            (
                center_x + point_radius * math.cos(angle),
                center_y + point_radius * math.sin(angle),
            )
        )
    return points


def _box(center_x: int, center_y: int, radius: int) -> tuple[int, int, int, int]:
    return (
        center_x - radius,
        center_y - radius,
        center_x + radius,
        center_y + radius,
    )
