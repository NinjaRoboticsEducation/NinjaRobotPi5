from __future__ import annotations

import cv2
import numpy as np
import pytest
from ninjarobot_pi5_ide.qr_display import render_pairing_qr, validate_pairing_url

TOKEN = "pairing-token_" + ("a" * 36)


@pytest.mark.parametrize(
    "url",
    (
        "http://robot.example/#pair=" + TOKEN,
        "https://user@robot.example/#pair=" + TOKEN,
        "https://robot.example/path#pair=" + TOKEN,
        "https://robot.example/?query=x#pair=" + TOKEN,
        "https://robot.example/",
        "https://robot.example/#other=" + TOKEN,
        "https://robot.example/#pair=short",
        "https://single-label/#pair=" + TOKEN,
    ),
)
def test_pairing_qr_rejects_unbounded_or_malformed_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_pairing_url(url)


def test_pairing_qr_is_deterministic_centered_and_decodes_exactly() -> None:
    url = f"https://robot.example/#pair={TOKEN}"

    first = render_pairing_qr(url, width=240, height=320)
    second = render_pairing_qr(url, width=240, height=320)

    assert first.mode == "RGB"
    assert first.size == (240, 320)
    assert first.tobytes() == second.tobytes()
    pixels = np.asarray(first)
    assert np.all(pixels[0] == 255)
    assert np.all(pixels[-1] == 255)
    assert np.all(pixels[:, 0] == 255)
    assert np.all(pixels[:, -1] == 255)
    decoded, _points, _straight = cv2.QRCodeDetector().detectAndDecode(pixels)
    assert decoded == url


def test_long_local_pairing_url_fits_physical_display_without_interpolation() -> None:
    url = f"https://ninjarobot-pi5.local:8443/#pair={'z' * 96}"

    image = render_pairing_qr(url, width=240, height=320)
    colors = {tuple(color) for color in np.unique(np.asarray(image).reshape(-1, 3), axis=0)}

    assert colors == {(0, 0, 0), (255, 255, 255)}
    decoded, _points, _straight = cv2.QRCodeDetector().detectAndDecode(np.asarray(image))
    assert decoded == url


def test_pairing_qr_requires_standard_four_module_quiet_zone() -> None:
    with pytest.raises(ValueError, match="four modules"):
        render_pairing_qr(
            f"https://robot.example/#pair={TOKEN}",
            width=240,
            height=320,
            border_modules=2,
        )
