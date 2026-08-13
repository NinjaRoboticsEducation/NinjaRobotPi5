"""Remote pairing entropy, replay, expiry, host, and origin tests."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from ninjarobot_pi5_agent.pairing import (
    PairingError,
    PairingSessionManager,
    validate_local_https_origin,
    validate_public_https_origin,
)

REMOTE_MARKER = "r" * 43


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def manager(clock: Clock | None = None) -> PairingSessionManager:
    return PairingSessionManager(
        pairing_secret=b"p" * 32,
        session_secret=b"s" * 32,
        remote_header_secret=REMOTE_MARKER,
        pairing_lifetime_seconds=60,
        session_lifetime_seconds=300,
        clock=clock or Clock(),
    )


def fragment_token(url: str) -> str:
    return parse_qs(urlsplit(url).fragment)["pair"][0]


@pytest.mark.parametrize(
    "url",
    (
        "http://robot.example",
        "https://user@robot.example",
        "https://robot.example/path",
        "https://robot.example?token=x",
        "https://robot.example/#token",
        "https://127.0.0.1",
        "https://localhost",
        "https://robot.example:8443",
        "https://single-label",
    ),
)
def test_public_remote_origin_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_https_origin(url)


def test_pairing_token_is_one_use_origin_bound_and_session_is_revocable() -> None:
    pairing = manager()
    pairing.set_remote_url("https://robot.example/")
    url = pairing.pairing_url()
    token = fragment_token(url)

    assert url.startswith("https://robot.example/#pair=")
    assert len(token) >= 32
    with pytest.raises(PairingError, match="origin"):
        pairing.exchange(
            token,
            origin="https://attacker.example",
            host="robot.example",
            remote_marker=REMOTE_MARKER,
        )

    session = pairing.exchange(
        token,
        origin="https://robot.example",
        host="robot.example",
        remote_marker=REMOTE_MARKER,
    )
    assert pairing.authorize_remote(
        session,
        origin="https://robot.example",
        host="robot.example",
        remote_marker=REMOTE_MARKER,
    )
    with pytest.raises(PairingError, match="expired or unavailable"):
        pairing.exchange(
            token,
            origin="https://robot.example",
            host="robot.example",
            remote_marker=REMOTE_MARKER,
        )

    pairing.rotate(invalidate_sessions=True)
    assert not pairing.authorize_remote(
        session,
        origin="https://robot.example",
        host="robot.example",
        remote_marker=REMOTE_MARKER,
    )


def test_pairing_and_session_expire_without_retaining_raw_credentials() -> None:
    clock = Clock()
    pairing = manager(clock)
    pairing.set_remote_url("https://robot.example")
    first = fragment_token(pairing.pairing_url())
    clock.now += 61
    with pytest.raises(PairingError, match="expired"):
        pairing.exchange(
            first,
            origin="https://robot.example",
            host="robot.example",
            remote_marker=REMOTE_MARKER,
        )

    second = fragment_token(pairing.rotate())
    session = pairing.exchange(
        second,
        origin="https://robot.example",
        host="robot.example",
        remote_marker=REMOTE_MARKER,
    )
    clock.now += 301
    assert not pairing.authorize_remote(
        session,
        origin="https://robot.example",
        host="robot.example",
        remote_marker=REMOTE_MARKER,
    )
    status = pairing.status()
    assert status.active_sessions == 0
    assert "token" not in repr(status).casefold()


def test_host_scope_preserves_private_lan_and_denies_unknown_public_hosts() -> None:
    pairing = manager()
    pairing.set_remote_url("https://robot.example")

    assert pairing.request_scope("127.0.0.1:8443") == "local"
    assert pairing.request_scope("192.168.1.20:8443") == "local"
    assert pairing.request_scope("ninjarobot.local:8443") == "local"
    assert pairing.request_scope("robot.example") == "denied"
    assert pairing.request_scope("robot.example", remote_marker="wrong" * 10) == "denied"
    assert pairing.request_scope("robot.example", remote_marker=REMOTE_MARKER) == "remote"
    assert pairing.request_scope("192.168.1.20", remote_marker=REMOTE_MARKER) == "denied"
    assert pairing.request_scope("attacker.example") == "denied"


@pytest.mark.parametrize(
    "url",
    (
        "http://127.0.0.1:8443",
        "https://user@127.0.0.1:8443",
        "https://127.0.0.1:8443/path",
        "https://127.0.0.1:8443?token=x",
        "https://robot.example",
        "https://single-label",
    ),
)
def test_local_origin_rejects_nonlocal_or_nonorigin_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_local_https_origin(url)


def test_local_pairing_is_origin_bound_and_remote_recovery_revokes_it() -> None:
    pairing = manager()
    pairing.set_local_url("https://127.0.0.1:8443")
    local_token = fragment_token(pairing.pairing_url())
    local_session = pairing.exchange(
        local_token,
        origin="https://127.0.0.1:8443",
        host="127.0.0.1:8443",
        remote_marker=None,
    )
    assert pairing.authorize_controller(
        local_session,
        origin="https://127.0.0.1:8443",
        host="127.0.0.1:8443",
        remote_marker=None,
    )
    assert pairing.status().active_scope == "local"

    pairing.set_remote_url("https://robot.example")
    assert not pairing.authorize_remote(
        local_session,
        origin="https://robot.example",
        host="robot.example",
        remote_marker=REMOTE_MARKER,
    )
    assert pairing.status().active_scope == "remote"
