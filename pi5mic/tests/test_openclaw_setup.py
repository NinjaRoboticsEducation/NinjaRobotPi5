"""Tests for OpenClaw auto-discovery helpers."""

from __future__ import annotations

import importlib
import json

openclaw_setup_module = importlib.import_module("pi5mic.integration.openclaw_setup")


def test_discover_openclaw_auto_config_reads_local_config(monkeypatch, tmp_path) -> None:
    command_path = tmp_path / "openclaw"
    command_path.write_text("", encoding="utf-8")
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "gateway": {
                    "mode": "local",
                    "bind": "loopback",
                    "port": 18789,
                },
                "agents": {
                    "list": [
                        {"id": "main"},
                    ]
                },
                "plugins": {
                    "allow": ["ninjaclawbot"],
                    "entries": {"ninjaclawbot": {"enabled": True}},
                    "load": {"paths": ["/tmp/ninjaclawbot-plugin"]},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        openclaw_setup_module,
        "DEFAULT_OPENCLAW_CONFIG_PATH",
        config_path,
    )
    monkeypatch.setattr(
        openclaw_setup_module,
        "resolve_openclaw_command",
        lambda command=None: command_path,
    )

    discovery = openclaw_setup_module.discover_openclaw_auto_config(command=None)

    assert discovery.command == command_path
    assert discovery.config_path == config_path
    assert discovery.gateway_url == "ws://127.0.0.1:18789"
    assert discovery.agent_id == "main"
    assert discovery.session_key == "voice-local-mic"
    assert discovery.plugin_ready is True
    assert discovery.telegram_enabled is False
    assert discovery.telegram_reply_target is None
    assert discovery.used_defaults == ("session_key",)


def test_discover_openclaw_auto_config_finds_recent_telegram_route(monkeypatch, tmp_path) -> None:
    command_path = tmp_path / "openclaw"
    command_path.write_text("", encoding="utf-8")
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "gateway": {"mode": "local", "bind": "loopback", "port": 18789},
                "agents": {"list": [{"id": "main"}]},
                "channels": {
                    "telegram": {
                        "enabled": True,
                        "botToken": "secret-token",
                    }
                },
                "plugins": {
                    "allow": ["ninjaclawbot"],
                    "entries": {"ninjaclawbot": {"enabled": True}},
                    "load": {"paths": ["/tmp/ninjaclawbot-plugin"]},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        openclaw_setup_module,
        "DEFAULT_OPENCLAW_CONFIG_PATH",
        config_path,
    )
    monkeypatch.setattr(
        openclaw_setup_module,
        "resolve_openclaw_command",
        lambda command=None: command_path,
    )

    class _Result:
        def __init__(self, stdout: str) -> None:
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    def _fake_run(command, **kwargs):
        assert command[:4] == [str(command_path), "gateway", "call", "sessions.list"]
        return _Result(
            json.dumps(
                {
                    "ok": True,
                    "result": {
                        "sessions": [
                            {
                                "key": "agent:main:telegram:direct:12345",
                                "lastChannel": "telegram",
                                "lastTo": "-1001234567890:topic:42",
                                "lastAccountId": "default",
                                "updatedAt": 1_700_000_000_000,
                            }
                        ]
                    },
                }
            )
        )

    monkeypatch.setattr(openclaw_setup_module.subprocess, "run", _fake_run)

    discovery = openclaw_setup_module.discover_openclaw_auto_config(command=None)

    assert discovery.telegram_enabled is True
    assert discovery.telegram_accounts == ("default",)
    assert discovery.telegram_default_account == "default"
    assert discovery.telegram_reply_target is not None
    assert discovery.telegram_reply_target.channel == "telegram"
    assert discovery.telegram_reply_target.target == "-1001234567890:topic:42"
    assert discovery.telegram_reply_target.account_id == "default"
