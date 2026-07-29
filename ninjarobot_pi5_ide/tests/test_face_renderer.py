"""Tests for the embedded animated face catalog."""

from __future__ import annotations

import hashlib

import pytest
from ninjarobot_pi5_ide.behavior_models import (
    FACE_ALIASES,
    FACE_EXPRESSIONS,
    FaceOperation,
    normalize_face_name,
)
from ninjarobot_pi5_ide.face_renderer import render_emergency_stop, render_face
from PIL import Image


def frame(expression: str, elapsed_seconds: float = 0.0) -> Image.Image:
    return render_face(
        expression,
        width=320,
        height=240,
        background="#000000",
        foreground="#FFFFFF",
        accent="#00BFFF",
        elapsed_seconds=elapsed_seconds,
    )


def digest(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


@pytest.mark.parametrize("expression", FACE_EXPRESSIONS)
def test_every_canonical_face_renders_a_nonempty_rgb_frame(expression: str) -> None:
    image = frame(expression)

    assert image.mode == "RGB"
    assert image.size == (320, 240)
    assert image.getbbox() is not None
    assert len(image.getcolors(maxcolors=320 * 240) or []) >= 2


@pytest.mark.parametrize(("alias", "canonical"), FACE_ALIASES.items())
def test_aliases_normalize_and_render_identically(alias: str, canonical: str) -> None:
    assert normalize_face_name(alias) == canonical
    assert digest(frame(alias, 0.7)) == digest(frame(canonical, 0.7))
    operation = FaceOperation.model_validate(
        {
            "kind": "face",
            "expression": alias,
        }
    )
    assert operation.expression == canonical


@pytest.mark.parametrize("expression", FACE_EXPRESSIONS)
def test_every_face_loop_has_time_varying_frames(expression: str) -> None:
    assert digest(frame(expression, 0.1)) != digest(frame(expression, 0.85))


def test_private_camera_indicator_is_animated_but_not_in_the_emotion_catalog() -> None:
    assert "camera" not in FACE_EXPRESSIONS
    assert normalize_face_name("camera") == "camera"
    assert digest(frame("camera", 0.1)) != digest(frame("camera", 0.85))


def test_invalid_face_and_frame_arguments_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown face"):
        frame("not-a-face")
    with pytest.raises(ValueError, match="at least 120"):
        render_face(
            "happy",
            width=100,
            height=100,
            background="#000000",
            foreground="#FFFFFF",
            accent="#00BFFF",
        )
    with pytest.raises(ValueError, match="finite non-negative"):
        frame("happy", -0.1)


def test_emergency_stop_screen_is_distinct_and_scalable() -> None:
    landscape = render_emergency_stop(width=320, height=240)
    portrait = render_emergency_stop(width=240, height=320)

    assert landscape.mode == "RGB"
    assert landscape.size == (320, 240)
    assert portrait.size == (240, 320)
    assert len(landscape.getcolors(maxcolors=320 * 240) or []) >= 4
    with pytest.raises(ValueError, match="at least 120"):
        render_emergency_stop(width=100, height=240)
