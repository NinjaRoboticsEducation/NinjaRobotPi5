"""Tests for the OpenClaw transport and presence helpers."""

from __future__ import annotations

from pi5mic.integration.presence import OpenClawPresenceController
from pi5mic.transport.openclaw_cli import OpenClawAgentTransport


class _CompletedProcess:
    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_openclaw_transport_dispatches_agent_request(monkeypatch, tmp_path) -> None:
    command_path = tmp_path / "openclaw"
    command_path.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _CompletedProcess(stdout='{"final":{"text":"Hello back"}}')

    monkeypatch.setattr("pi5mic.transport.openclaw_cli.subprocess.run", fake_run)

    transport = OpenClawAgentTransport(
        command=command_path,
        gateway_url="ws://127.0.0.1:18789",
        agent_id="main",
        session_key="voice:local-mic",
        delivery_mode="local_only",
    )

    result = transport.dispatch("hello ninja")

    assert result.reply_text == "Hello back"
    assert captured["command"] == [
        str(command_path.resolve()),
        "agent",
        "--agent",
        "main",
        "--session-id",
        "voice-local-mic",
        "--message",
        "hello ninja",
        "--json",
    ]


def test_presence_controller_calls_gateway_method(monkeypatch, tmp_path) -> None:
    command_path = tmp_path / "openclaw"
    command_path.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _CompletedProcess(stdout='{"ok":true,"result":{"mode":"listening"}}')

    monkeypatch.setattr("pi5mic.integration.presence.subprocess.run", fake_run)

    controller = OpenClawPresenceController(
        command=command_path,
        gateway_url="ws://127.0.0.1:18789",
    )
    result = controller.set_mode("listening", reason="pi5mic.listening")

    assert result["result"]["mode"] == "listening"
    assert captured["command"] == [
        str(command_path.resolve()),
        "gateway",
        "call",
        "ninjaclawbot.presence.set",
        "--params",
        '{"mode": "listening", "reason": "pi5mic.listening"}',
    ]


def test_openclaw_transport_omits_session_id_for_agent_main_strategy(
    monkeypatch,
    tmp_path,
) -> None:
    command_path = tmp_path / "openclaw"
    command_path.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _CompletedProcess(stdout='{"final":{"text":"Main session reply"}}')

    monkeypatch.setattr("pi5mic.transport.openclaw_cli.subprocess.run", fake_run)

    transport = OpenClawAgentTransport(
        command=command_path,
        gateway_url="ws://127.0.0.1:18789",
        agent_id="main",
        session_key="voice-local-mic",
        session_strategy="agent_main",
        delivery_mode="local_only",
    )

    result = transport.dispatch("hello again")

    assert result.reply_text == "Main session reply"
    assert captured["command"] == [
        str(command_path.resolve()),
        "agent",
        "--agent",
        "main",
        "--message",
        "hello again",
        "--json",
    ]
