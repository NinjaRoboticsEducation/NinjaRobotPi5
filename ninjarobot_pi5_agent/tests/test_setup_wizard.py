from __future__ import annotations

import argparse
import asyncio
import json
from collections import deque
from pathlib import Path

import pytest

from ninjarobot_pi5_agent import setup_wizard


class _Console:
    def __init__(self, answers: tuple[str, ...] = ()) -> None:
        self.answers = deque(answers)
        self.messages: list[str] = []

    def write(self, message: str = "") -> None:
        self.messages.append(message)

    def ask(self, _prompt: str) -> str:
        self.messages.append(_prompt)
        return self.answers.popleft()

    def secret(self, _prompt: str) -> str:
        return self.answers.popleft()


def _arguments(tmp_path: Path, **updates: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "onboard_status": False,
        "onboard_dry_run": False,
        "onboard_simulation": False,
        "onboard_step": None,
        "config": tmp_path / "config.toml",
        "secret_file": tmp_path / "secrets.env",
        "mcp_config": tmp_path / "mcp.toml",
    }
    values.update(updates)
    return argparse.Namespace(**values)


def test_dry_run_is_read_only_and_explains_every_setup_area(tmp_path) -> None:
    progress = tmp_path / "missing" / "progress.json"
    console = _Console()

    outcome = asyncio.run(
        setup_wizard.run_setup_wizard(
            _arguments(tmp_path, onboard_dry_run=True), console=console, progress_path=progress
        )
    )

    assert outcome.launch_mode is None
    assert not progress.parent.exists()
    rendered = "\n".join(console.messages)
    assert "buzzer (required)" in rendered
    assert "AI provider; external MCP tools" in rendered


def test_simulation_records_rehearsal_without_real_configuration(tmp_path) -> None:
    progress = tmp_path / "state" / "progress.json"
    console = _Console()

    asyncio.run(
        setup_wizard.run_setup_wizard(
            _arguments(tmp_path, onboard_simulation=True),
            console=console,
            progress_path=progress,
        )
    )

    payload = json.loads(console.messages[0])
    assert payload["steps"]["servo"]["verification"] == "simulated"
    assert payload["steps"]["mcp"]["detail"] == "offline_rehearsal"
    assert not Path(_arguments(tmp_path).config).exists()
    assert not progress.exists()


def test_required_hardware_step_enforces_motion_confirmation(monkeypatch, tmp_path) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        setup_wizard,
        "hardware_setup_status",
        lambda _component: {
            "configuration_saved": True,
            "configuration_valid": True,
            "component": "pi5buzzer",
        },
    )
    monkeypatch.setattr(
        setup_wizard,
        "run_hardware_setup",
        lambda component: opened.append(component) or 0,
    )
    console = _Console(("1", "not ready", "q"))

    result = setup_wizard._hardware_step(console, "servo", index=4, total=5)

    assert result == ("needs_attention", "unverified", "saved_for_later")
    assert opened == []
    assert "raise both wheels" in "\n".join(console.messages).lower()


def test_multiple_mcp_selection_is_ordered_unique_and_validated() -> None:
    assert setup_wizard._parse_multiple_choices("3, 1, 3", maximum=3) == (3, 1)
    with pytest.raises(ValueError, match="1 through 3"):
        setup_wizard._parse_multiple_choices("4", maximum=3)


def test_progress_store_rejects_future_schema_without_overwriting(tmp_path) -> None:
    path = tmp_path / "state" / "progress.json"
    path.parent.mkdir()
    original = '{"schema_version": 999, "future": true}\n'
    path.write_text(original, encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(ValueError, match="unsupported setup progress"):
        with setup_wizard.ProgressStore(path) as store:
            store.load()

    assert path.read_text(encoding="utf-8") == original


def test_progress_store_prevents_two_wizards(tmp_path) -> None:
    path = tmp_path / "state" / "progress.json"

    with setup_wizard.ProgressStore(path):
        with pytest.raises(ValueError, match="another onboarding process"):
            with setup_wizard.ProgressStore(path):
                pass


def test_resume_reuses_only_completed_step_with_existing_configuration(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "state" / "progress.json"
    progress = setup_wizard.SetupProgress(
        steps={
            "buzzer": setup_wizard.StepRecord(
                status="complete",
                verification="operator_verified",
                detail="operator_confirmed",
            )
        }
    )
    with setup_wizard.ProgressStore(path) as store:
        store.save(progress)
    monkeypatch.setattr(
        setup_wizard,
        "hardware_setup_status",
        lambda _component: {
            "configuration_saved": True,
            "configuration_valid": True,
            "component": "pi5buzzer",
        },
    )
    monkeypatch.setattr(
        setup_wizard,
        "_hardware_step",
        lambda *_args, **_kwargs: pytest.fail("completed setup should have been reused"),
    )
    monkeypatch.setattr(
        setup_wizard, "_import_hardware_configuration", lambda *args, **kwargs: None
    )
    console = _Console()

    asyncio.run(
        setup_wizard.run_setup_wizard(
            _arguments(tmp_path, resume=True, onboard_step="buzzer"),
            console=console,
            progress_path=path,
        )
    )

    assert "saved verification still present" in "\n".join(console.messages)


@pytest.mark.parametrize("bad", ["0", "-1", "9", "abc"])
def test_choice_rejects_out_of_range_input(bad):
    ui = _Console((bad, "2"))
    assert setup_wizard._choice(ui, "Choose: ", {"1", "2"}) == "2"
    assert "Please choose" in "\n".join(ui.messages)


def test_hardware_exit_checks_config_without_operator_confirmation(monkeypatch):
    monkeypatch.setattr(
        setup_wizard,
        "hardware_setup_status",
        lambda name: {
            "configuration_saved": True,
            "configuration_valid": True,
            "summary": {"pin": 17},
        },
    )
    opened = []
    monkeypatch.setattr(setup_wizard, "run_hardware_setup", lambda name: opened.append(name) or 0)
    ui = _Console(("1", ""))
    result = setup_wizard._hardware_step(ui, "buzzer", index=1, total=5)
    assert result == ("complete", "software_verified", "settings_checked")
    assert opened == ["buzzer"]
    assert "Type YES" not in "\n".join(ui.messages)


def test_bulk_reuse_only_opens_missing_modules(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock

    def status(name):
        return {
            "configuration_saved": name != "camera",
            "configuration_valid": name != "camera",
            "component": name,
            "summary": {},
        }

    monkeypatch.setattr(setup_wizard, "hardware_setup_status", status)
    opened = []
    monkeypatch.setattr(
        setup_wizard,
        "_hardware_step",
        lambda ui, name, **kw: (
            opened.append(name) or ("complete", "software_verified", "settings_checked")
        ),
    )
    monkeypatch.setattr(setup_wizard, "_optional_hardware", AsyncMock())
    monkeypatch.setattr(setup_wizard, "_provider_setup", AsyncMock())
    monkeypatch.setattr(setup_wizard, "_mcp_setup", AsyncMock())
    monkeypatch.setattr(setup_wizard, "_remote_setup", AsyncMock())
    imports = []
    monkeypatch.setattr(
        setup_wizard, "_import_hardware_configuration", lambda *a, **kw: imports.append(kw)
    )
    ui = _Console(("2", "2"))
    outcome = asyncio.run(
        setup_wizard.run_setup_wizard(
            _arguments(tmp_path), console=ui, progress_path=tmp_path / "state" / "progress.json"
        )
    )
    assert outcome.launch_mode is None
    assert opened == ["camera"]
    assert len(imports) == 1
    assert setup_wizard._optional_hardware.call_args.kwargs["reuse_microphone"] is True


def test_simulated_progress_is_not_reused(monkeypatch, tmp_path):
    path = tmp_path / "state" / "progress.json"
    progress = setup_wizard.SetupProgress()
    setup_wizard._simulate(progress)
    with setup_wizard.ProgressStore(path) as store:
        store.save(progress)
    monkeypatch.setattr(
        setup_wizard,
        "hardware_setup_status",
        lambda name: {"configuration_saved": True, "configuration_valid": True},
    )
    opened = []
    monkeypatch.setattr(
        setup_wizard,
        "_hardware_step",
        lambda ui, name, **kw: (
            opened.append(name) or ("needs_attention", "unverified", "saved_for_later")
        ),
    )
    asyncio.run(
        setup_wizard.run_setup_wizard(
            _arguments(tmp_path, resume=True, onboard_step="buzzer"),
            console=_Console(),
            progress_path=path,
        )
    )
    assert opened == ["buzzer"]


def test_candidate_key_does_not_replace_working_secret_before_commit(tmp_path):
    path = tmp_path / "private" / "secret.env"
    original = setup_wizard.SecretStore(path)
    original.set("TEST_KEY", "old-value")
    candidate = setup_wizard._CandidateSecrets(path)
    candidate.set("TEST_KEY", "new-value")
    assert candidate.require("TEST_KEY") == "new-value"
    assert original.require("TEST_KEY") == "old-value"
    candidate.commit()
    assert original.require("TEST_KEY") == "new-value"


def test_calendar_ssh_instructions_precede_authorization(monkeypatch, tmp_path):
    events = []
    ui = _Console((str(tmp_path / "client.json"), "1", ""))

    async def authorize(*args, **kwargs):
        assert "ssh -N" in "\n".join(ui.messages)
        events.append("authorized")
        return dict(
            client_id="fixture",
            client_secret="fixture",
            refresh_token="fixture",
            scope="fixture",
            calendar_id="fixture@example.org",
        )

    monkeypatch.setattr(setup_wizard, "authorize_google_calendar", authorize)
    path = tmp_path / "private" / "candidate.json"
    server = asyncio.run(
        setup_wizard._prepare_mcp_server(
            2, ui, setup_wizard.SecretStore(tmp_path / "secrets"), credential_path=path
        )
    )
    assert events == ["authorized"]
    assert server.preset == "google-calendar-readonly"
    assert path.stat().st_mode & 0o077 == 0


def test_calendar_probe_calls_read_only_tool_and_closes(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock

    connection = AsyncMock()
    connection.call_tool.return_value = {"structuredContent": {"events": []}}
    provider = AsyncMock()
    provider.list_tools.return_value = [object()]
    monkeypatch.setattr(setup_wizard, "SDKMCPConnection", lambda *a, **kw: connection)
    monkeypatch.setattr(setup_wizard, "MCPToolProvider", lambda *a, **kw: provider)
    server = setup_wizard.google_calendar_server_config("python", str(tmp_path / "credential"))
    asyncio.run(
        setup_wizard._validate_mcp_server(server, setup_wizard.SecretStore(tmp_path / "secrets"))
    )
    connection.call_tool.assert_awaited_once_with(
        "list_today_events", {"timezone": "UTC", "max_results": 1}
    )
    provider.close.assert_awaited_once()


def test_rehearsal_preserves_existing_progress(tmp_path):
    path = tmp_path / "state" / "progress.json"
    with setup_wizard.ProgressStore(path) as store:
        store.save(setup_wizard.SetupProgress())
    previous = path.read_bytes()
    asyncio.run(
        setup_wizard.run_setup_wizard(
            _arguments(tmp_path, onboard_simulation=True), console=_Console(), progress_path=path
        )
    )
    assert path.read_bytes() == previous


def test_fresh_setup_has_no_bulk_reuse_option_and_handles_eof(monkeypatch, tmp_path):
    monkeypatch.setattr(
        setup_wizard,
        "hardware_setup_status",
        lambda name: {"configuration_saved": False, "configuration_valid": False},
    )

    class ClosedConsole(_Console):
        def ask(self, prompt):
            self.messages.append(prompt)
            raise EOFError

    ui = ClosedConsole()
    path = tmp_path / "state" / "progress.json"
    result = asyncio.run(
        setup_wizard.run_setup_wizard(_arguments(tmp_path), console=ui, progress_path=path)
    )
    assert result.launch_mode is None
    assert "Apply existing" not in "\n".join(ui.messages)
    assert path.exists()


def test_calendar_failed_validation_preserves_previous_credential(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock

    monkeypatch.setenv("HOME", str(tmp_path))
    credential = tmp_path / ".config/ninjarobot_pi5/mcp-google-calendar/credential.json"
    credential.parent.mkdir(parents=True)
    credential.write_text("original")
    candidate_paths = []

    async def prepare(number, ui, secrets, *, credential_path):
        setup_wizard._save_private_json(credential_path, {"candidate": "fixture"})
        candidate_paths.append(credential_path)
        return setup_wizard.google_calendar_server_config("python", str(credential_path))

    monkeypatch.setattr(setup_wizard, "_prepare_mcp_server", prepare)
    monkeypatch.setattr(setup_wizard, "_validate_mcp_server", AsyncMock(side_effect=RuntimeError))
    path = tmp_path / "state" / "progress.json"
    with setup_wizard.ProgressStore(path) as store:
        asyncio.run(
            setup_wizard._mcp_setup(
                setup_wizard.SetupProgress(), store, _Console(("2", "s")), _arguments(tmp_path)
            )
        )
    assert credential.read_text() == "original"
    assert candidate_paths and not candidate_paths[0].exists()
    assert not (tmp_path / "mcp.toml").exists()


def test_candidate_secret_rolls_back_when_configuration_cannot_save(tmp_path):
    path = tmp_path / "private" / "secret.env"
    original = setup_wizard.SecretStore(path)
    original.set("TEST_KEY", "working")
    candidate = setup_wizard._CandidateSecrets(path)
    candidate.set("TEST_KEY", "replacement")

    def fail():
        raise OSError("fixture failure")

    with pytest.raises(OSError):
        candidate.commit_configuration(fail)
    assert original.require("TEST_KEY") == "working"


def test_real_calendar_mcp_subprocess_with_mocked_google(tmp_path):
    import sys

    from ninjarobot_pi5_agent.calendar_google import READ_SCOPE

    credential = tmp_path / "private" / "calendar.json"
    setup_wizard._save_private_json(
        credential,
        dict(
            client_id="fixture",
            client_secret="fixture",
            refresh_token="fixture",
            scope=READ_SCOPE,
            calendar_id="fixture@example.org",
        ),
    )
    # Run the real external MCP server, but stub its Google transport in the child.
    code = "\n".join(
        [
            "import asyncio, sys",
            "from pathlib import Path",
            "from ninjarobot_pi5_agent.external_mcp.google_calendar import "
            "create_server, GoogleCalendarBackend",
            "async def request(*args, **kwargs): return {'items': []}",
            "GoogleCalendarBackend.request = request",
            "asyncio.run(create_server(Path(sys.argv[1])).run_stdio_async())",
        ]
    )
    server = setup_wizard.google_calendar_server_config(sys.executable, str(credential))
    server = server.model_copy(update={"args": ("-c", code, str(credential))})

    async def validate():
        async with asyncio.timeout(20):
            await setup_wizard._validate_mcp_server(
                server, setup_wizard.SecretStore(tmp_path / "secret.env")
            )

    asyncio.run(validate())


def test_candidate_secrets_preserve_secret_store_name_validation(tmp_path):
    candidate = setup_wizard._CandidateSecrets(tmp_path / "secret.env")
    with pytest.raises(ValueError, match="secret names"):
        candidate.set("INVALID\nNAME", "fixture")
    assert not candidate.pending
    assert not candidate.path.exists()
