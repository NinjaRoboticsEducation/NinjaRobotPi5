"""Deterministic, standards-compatible pairing QR rendering for the IDE display."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import parse_qs, urlsplit

import qrcode  # type: ignore[import-untyped]
from PIL import Image
from qrcode.constants import ERROR_CORRECT_M  # type: ignore[import-untyped]

MAX_PAIRING_URL_LENGTH = 512
MIN_PAIRING_TOKEN_LENGTH = 32
MAX_PAIRING_TOKEN_LENGTH = 128


def validate_pairing_url(url: str) -> str:
    """Accept one HTTPS origin plus one URL-fragment pairing credential."""
    if not isinstance(url, str) or not 1 <= len(url) <= MAX_PAIRING_URL_LENGTH:
        raise ValueError("pairing URL must contain 1 through 512 characters")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("pairing URL must be one plain HTTPS origin and fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("pairing URL port is invalid") from exc
    if port is not None and not 1 <= port <= 65_535:
        raise ValueError("pairing URL port is invalid")
    hostname = parsed.hostname.encode("idna").decode("ascii").lower()
    if not (_is_local_hostname(hostname) or "." in hostname):
        raise ValueError("pairing URL hostname is invalid")
    values = parse_qs(parsed.fragment, strict_parsing=True)
    if set(values) != {"pair"} or len(values["pair"]) != 1:
        raise ValueError("pairing URL must contain one pairing fragment")
    token = values["pair"][0]
    if not (
        MIN_PAIRING_TOKEN_LENGTH <= len(token) <= MAX_PAIRING_TOKEN_LENGTH
        and all(character.isalnum() or character in "-_" for character in token)
    ):
        raise ValueError("pairing URL fragment is invalid")
    return url


def render_pairing_qr(
    url: str,
    *,
    width: int,
    height: int,
    border_modules: int = 4,
) -> Image.Image:
    """Center a black/white QR using integer modules without interpolation."""
    validated = validate_pairing_url(url)
    if width < 64 or height < 64:
        raise ValueError("display dimensions are too small for a pairing QR")
    if border_modules != 4:
        raise ValueError("pairing QR quiet border must be four modules")
    probe = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=1,
        border=border_modules,
    )
    probe.add_data(validated)
    probe.make(fit=True)
    if probe.modules_count is None:
        raise RuntimeError("QR module sizing did not complete")
    total_modules = probe.modules_count + (2 * border_modules)
    box_size = min(width, height) // total_modules
    if box_size < 1:
        raise ValueError("pairing URL does not fit the configured display")

    qr = qrcode.QRCode(
        version=probe.version,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border_modules,
    )
    qr.add_data(validated)
    qr.make(fit=False)
    code = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    canvas = Image.new("RGB", (width, height), "white")
    canvas.paste(code, ((width - code.width) // 2, (height - code.height) // 2))
    return canvas


def _is_local_hostname(hostname: str) -> bool:
    local_names = {
        "localhost",
        socket.gethostname().rstrip(".").lower(),
        f"{socket.gethostname().rstrip('.').lower()}.local",
    }
    if hostname in local_names or hostname.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local
