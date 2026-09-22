"""Guided, resumable setup orchestration for non-technical robot owners."""

from __future__ import annotations

import fcntl
import getpass
import json
import os
import secrets
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Literal, Protocol

from ninjarobot_pi5_ide.bluetooth_setup import connect_wizard
from ninjarobot_pi5_ide.config_import import (
    discover_pi5_configs,
    import_pi5_configs,
    load_effective_config,
    save_robot_config,
)

from ninjarobot_pi5_ide import hardware_setup_status, load_robot_config, run_hardware_setup

from .calendar_oauth import authorize as authorize_google_calendar
from .cloud_registry import ConfiguredProviderRegistry
from .mcp_client import MCPToolProvider, SDKMCPConnection
from .mcp_config import (
    MCPConfiguration,
    MCPServerConfig,
    google_calendar_server_config,
    load_mcp_configuration,
    notion_server_config,
    save_mcp_configuration,
    tavily_server_config,
)
from .model_selection import BenchmarkRegistry, persist_model_selection
from .models import ProviderHealthStatus
from .remote_access import install_ngrok_binary, persist_remote_access_enabled
from .secrets import SecretStore

DEFAULT_PROGRESS = Path("~/.local/state/ninjarobot_pi5/setup-progress.json")
SCHEMA_VERSION = 1
MANDATORY_HARDWARE = ("buzzer", "display", "distance", "servo", "camera")
OPTIONAL_HARDWARE = ("bluetooth", "microphone")
PROVIDERS = ("ollama", "gemini", "openai", "anthropic")
StepStatus = Literal["pending", "complete", "skipped", "failed", "needs_attention"]
Verification = Literal[
    "unverified", "configured", "software_verified", "operator_verified", "simulated"
]


class SetupConsole(Protocol):
    def write(self, message: str = "") -> None: ...

    def ask(self, prompt: str) -> str: ...

    def secret(self, prompt: str) -> str: ...


class TerminalSetupConsole:
    def write(self, message: str = "") -> None:
        print(message)

    def ask(self, prompt: str) -> str:
        return input(prompt).strip()

    def secret(self, prompt: str) -> str:
        return getpass.getpass(prompt).strip()


@dataclass
class StepRecord:
    status: StepStatus = "pending"
    verification: Verification = "unverified"
    detail: str = ""
    updated_at: str = ""


@dataclass
class SetupProgress:
    schema_version: int = SCHEMA_VERSION
    steps: dict[str, StepRecord] = field(default_factory=dict)
    selections: dict[str, str] = field(default_factory=dict)
    completed: bool = False
    updated_at: str = ""


@dataclass(frozen=True)
class SetupOutcome:
    launch_mode: Literal["simulation", "real"] | None = None


class ProgressStore:
    def __init__(self, path: Path = DEFAULT_PROGRESS) -> None:
        self.path = path.expanduser().absolute()
        self._lock_handle: IO[str] | None = None

    def __enter__(self) -> ProgressStore:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.parent.resolve() != self.path.parent or self.path.is_symlink():
            raise ValueError("setup progress must use a real private path")
        self.path.parent.chmod(0o700)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.fchmod(descriptor, 0o600)
        handle = os.fdopen(descriptor, "r+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise ValueError("another onboarding process is already running") from exc
        self._lock_handle = handle
        return self

    def __exit__(self, *_args: object) -> None:
        handle = self._lock_handle
        if handle is not None:
            handle.close()
        self._lock_handle = None

    def load(self) -> SetupProgress:
        if not self.path.exists():
            return SetupProgress()
        if self.path.is_symlink() or self.path.parent.resolve() != self.path.parent:
            raise ValueError("setup progress must use a real private path")
        if self.path.stat().st_size > 1_048_576:
            raise ValueError("setup progress file is oversized")
        if self.path.stat().st_mode & 0o077:
            raise PermissionError("setup progress must be owner-only (mode 0600)")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("setup progress must contain a JSON object")
        if raw.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported setup progress version; file was not changed")
        steps = {name: StepRecord(**record) for name, record in raw.get("steps", {}).items()}
        return SetupProgress(
            schema_version=SCHEMA_VERSION,
            steps=steps,
            selections=dict(raw.get("selections", {})),
            completed=bool(raw.get("completed", False)),
            updated_at=str(raw.get("updated_at", "")),
        )

    def save(self, progress: SetupProgress) -> None:
        progress.updated_at = _now()
        self.path.parent.chmod(0o700)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{self.path.name}-", suffix=".tmp", dir=self.path.parent, text=True
        )
        temporary = Path(name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(asdict(progress), stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
            raise


async def run_setup_wizard(
    arguments: object,
    *,
    console: SetupConsole | None = None,
    progress_path: Path = DEFAULT_PROGRESS,
) -> SetupOutcome:
    """Run onboarding and return an optional requested Agent launch mode."""
    ui = console or TerminalSetupConsole()
    store = ProgressStore(progress_path)
    if getattr(arguments, "onboard_status", False):
        ui.write(json.dumps(asdict(store.load()), indent=2, sort_keys=True))
        return SetupOutcome()
    if getattr(arguments, "onboard_dry_run", False):
        _show_preview(ui)
        return SetupOutcome()
    with store:
        progress = store.load()
        if getattr(arguments, "onboard_simulation", False):
            _simulate(progress)
            store.save(progress)
            ui.write("Simulation rehearsal complete. No hardware, account, or service was changed.")
            return SetupOutcome()

        ui.write("NinjaRobot guided setup")
        ui.write("Required hardware comes first. You can save and exit after any step.")
        config_path = Path(getattr(arguments, "config")).expanduser()
        requested_step = getattr(arguments, "onboard_step", None)

        for index, component in enumerate(MANDATORY_HARDWARE, 1):
            if requested_step and requested_step != component:
                continue
            prior = progress.steps.get(component)
            current_status = hardware_setup_status(component)
            if (
                getattr(arguments, "resume", False)
                and prior is not None
                and prior.status == "complete"
                and current_status["configuration_saved"] is True
            ):
                ui.write(
                    f"\nStep {index} of {len(MANDATORY_HARDWARE)} — "
                    f"{component.title()} [Required]: saved verification still present."
                )
                continue
            outcome = _hardware_step(ui, component, index=index, total=len(MANDATORY_HARDWARE))
            _record(progress, component, *outcome)
            store.save(progress)
            if outcome[0] == "needs_attention" and outcome[2] == "saved_for_later":
                return SetupOutcome()

        if requested_step in OPTIONAL_HARDWARE:
            await _optional_hardware(progress, store, ui, config_path, selected=requested_step)
            if requested_step == "microphone":
                _import_hardware_configuration(config_path, ui)
        elif requested_step == "provider":
            await _provider_setup(progress, store, ui, arguments)
        elif requested_step == "mcp":
            await _mcp_setup(progress, store, ui, arguments)
        elif requested_step == "web-access":
            await _remote_setup(progress, store, ui, arguments)
        elif not requested_step:
            _import_hardware_configuration(config_path, ui)
            await _optional_hardware(progress, store, ui, config_path)
            _import_hardware_configuration(config_path, ui)
            await _provider_setup(progress, store, ui, arguments)
            await _mcp_setup(progress, store, ui, arguments)
            await _remote_setup(progress, store, ui, arguments)

        incomplete = [
            component
            for component in MANDATORY_HARDWARE
            if progress.steps.get(component, StepRecord()).status != "complete"
        ]
        progress.completed = not incomplete
        store.save(progress)
        _summary(ui, progress)
        if requested_step:
            return SetupOutcome()
        choice = ui.ask("Choose 1) Start NinjaRobot Agent or 2) Exit onboarding [2]: ") or "2"
        if choice != "1":
            ui.write("Setup progress saved. Run `ninjarobot onboard --resume` to continue.")
            return SetupOutcome()
        mode = ui.ask("Start 1) simulation or 2) real hardware? [1]: ") or "1"
        if mode == "2" and incomplete:
            ui.write(
                "Real-hardware launch is blocked until required steps pass: "
                + ", ".join(incomplete)
            )
            return SetupOutcome()
        return SetupOutcome("real" if mode == "2" else "simulation")


def _hardware_step(
    ui: SetupConsole, component: str, *, index: int, total: int
) -> tuple[StepStatus, Verification, str]:
    explanations = {
        "buzzer": (
            "The buzzer is the robot's sound output.",
            "Its GPIO and silence must be checked.",
        ),
        "display": (
            "The display shows the robot face and status.",
            "Wiring, rotation, and brightness must match.",
        ),
        "distance": (
            "The distance sensor measures objects ahead.",
            "Readings must work before calibration.",
        ),
        "servo": (
            "Two continuous servos turn the wheels.",
            "Each wheel needs its own exact stop point.",
        ),
        "camera": (
            "The CSI camera provides temporary vision.",
            "Setup verifies the camera without retaining media.",
        ),
    }
    actions = {
        "buzzer": (
            "Choose Init, listen for the short test beep, confirm it becomes silent, then Exit."
        ),
        "display": (
            "Choose Init, then Show Text and Clear. Confirm the text is readable and correctly "
            "oriented, then Exit."
        ),
        "distance": (
            "Choose Health Check, Single Read, then Calibrate with a target at a measured "
            "distance. A no-target value such as 8191 is not a calibration success."
        ),
        "servo": (
            "With both wheels raised, choose Calibrate for GPIO12 and GPIO13. Verify each "
            "wheel stops at neutral before leaving the tool."
        ),
        "camera": (
            "Choose Run setup wizard, then Doctor. Capture a temporary test photo only after "
            "everyone nearby has consented; delete test media when finished."
        ),
    }
    what, why = explanations[component]
    ui.write(f"\nStep {index} of {total} — {component.title()} [Required]")
    ui.write(f"What is this? {what}")
    ui.write(f"Why is this needed? {why}")
    ui.write(f"What to do: {actions[component]}")
    status = hardware_setup_status(component)
    ui.write(
        "Status: "
        + ("saved configuration found" if status["configuration_saved"] else "not configured")
    )
    if component == "servo":
        ui.write(
            "CAUTION: This step can move motors. Raise both wheels and stay ready to remove power."
        )
    elif component == "camera":
        ui.write("Privacy: tell nearby people and obtain consent before taking any test photo.")
    elif component == "buzzer":
        ui.write("Notice: the initialization check plays a short audible tone.")
    choice = ui.ask(
        "Choose O) Open setup tool, V) verify existing setup, or Q) save and exit: "
    ).lower()
    if choice == "q":
        return "needs_attention", "unverified", "saved_for_later"
    if choice == "o":
        if component in {"servo", "camera"}:
            phrase = "WHEELS RAISED" if component == "servo" else "CONSENT OBTAINED"
            if ui.ask(f"Type {phrase} to continue: ") != phrase:
                return "needs_attention", "unverified", "confirmation_not_given"
        result = run_hardware_setup(component)
        if result != 0:
            if ui.ask("Setup tool failed. Choose R) retry or C) continue later: ").lower() == "r":
                return _hardware_step(ui, component, index=index, total=total)
            return "failed", "unverified", f"setup_tool_exit_{result}"
    refreshed = hardware_setup_status(component)
    if not refreshed["configuration_saved"]:
        ui.write(
            "No saved configuration was found. Retry this step after correcting the tool error."
        )
        if ui.ask("Choose R) retry or C) continue later: ").lower() == "r":
            return _hardware_step(ui, component, index=index, total=total)
        return "failed", "unverified", "configuration_missing"
    verified = ui.ask("Did the component check succeed exactly as described? Type YES: ")
    if verified != "YES":
        return "needs_attention", "configured", "operator_verification_pending"
    return "complete", "operator_verified", "operator_confirmed"


def _import_hardware_configuration(path: Path, ui: SetupConsole) -> None:
    base = load_effective_config(path if path.exists() else None)
    updated, imported = import_pi5_configs(base, discover_pi5_configs())
    ui.write("\nIntegrated configuration preview:")
    for item in imported:
        ui.write(f"  - {item}")
    if not imported:
        ui.write("  No standalone hardware configuration was found.")
        return
    if ui.ask("Type APPLY to save this integrated configuration: ") == "APPLY":
        save_robot_config(updated, path, overwrite=path.exists())
        ui.write(f"Saved private robot configuration to {path}.")


async def _optional_hardware(
    progress: SetupProgress,
    store: ProgressStore,
    ui: SetupConsole,
    config_path: Path,
    *,
    selected: str | None = None,
) -> None:
    ui.write("\nOptional hardware")
    if selected in {None, "bluetooth"}:
        if _yes(ui.ask("Configure a Bluetooth speaker? [y/N]: ")):
            try:
                await connect_wizard(config_path)
            except Exception as exc:
                ui.write(
                    f"Bluetooth setup failed: {type(exc).__name__}. Review the audio prerequisites."
                )
                _record(progress, "bluetooth", "failed", "unverified", type(exc).__name__)
            else:
                _record(progress, "bluetooth", "complete", "operator_verified", "speaker_selected")
        else:
            _record(progress, "bluetooth", "skipped", "unverified", "user_skipped")
        store.save(progress)

    if selected not in {None, "microphone"}:
        return
    if _yes(ui.ask("Configure the optional USB microphone and Hey Ninja wake word? [y/N]: ")):
        ui.write("The default speech-to-text engine is local whisper.cpp.")
        ui.write("The setup tool uses the bundled hey_Ninja.onnx wake model.")
        ui.write(
            "In mic-tool choose Run setup wizard, select the standalone profile and "
            "whisper_cpp backend, then enable always-on input with the bundled "
            "hey_Ninja.onnx model. Run Doctor before exiting."
        )
        if (
            ui.ask("Type CONSENT to allow microphone setup and optional test recording: ")
            == "CONSENT"
        ):
            result = run_hardware_setup("microphone")
            status = hardware_setup_status("microphone")
            if result == 0 and status["configuration_saved"]:
                _record(progress, "microphone", "complete", "operator_verified", "whisper_and_wake")
            else:
                _record(progress, "microphone", "failed", "unverified", f"setup_tool_exit_{result}")
        else:
            _record(progress, "microphone", "skipped", "unverified", "consent_not_given")
    else:
        _record(progress, "microphone", "skipped", "unverified", "user_skipped")
    store.save(progress)


async def _provider_setup(
    progress: SetupProgress, store: ProgressStore, ui: SetupConsole, arguments: object
) -> None:
    ui.write("\nAI model provider")
    for number, provider_name in enumerate(PROVIDERS, 1):
        label = "Google" if provider_name == "gemini" else provider_name.title()
        ui.write(f"  {number}) {label}")
    raw = ui.ask("Choose a provider [1]: ") or "1"
    try:
        provider_id = PROVIDERS[int(raw) - 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("choose provider 1 through 4") from exc
    config_path = Path(getattr(arguments, "config")).expanduser()
    if not config_path.exists():
        save_robot_config(load_effective_config(None), config_path, overwrite=False)
    secret_store = SecretStore(Path(getattr(arguments, "secret_file")))
    config = load_robot_config(config_path)
    provider = config.providers[provider_id]
    if provider_id != "ollama":
        assert provider.api_key_env is not None
        ui.write("Create the provider API key in its official account console.")
        keep_existing = secret_store.contains(provider.api_key_env) and _yes(
            ui.ask("A private key is already configured. Keep and validate it? [Y/n]: ") or "y"
        )
        if not keep_existing:
            value = ui.secret(f"Enter {provider.api_key_env}: ")
            confirmation = ui.secret(f"Enter {provider.api_key_env} again: ")
            if not value or value != confirmation:
                raise ValueError("API key values were empty or did not match")
            secret_store.set(provider.api_key_env, value)
    else:
        ui.write(
            "Ollama runs locally. Install a model with `ollama pull MODEL` if the list is empty."
        )
    registry = ConfiguredProviderRegistry(config_path, secret_store)
    catalog = await registry.catalog(provider_id)
    if not catalog:
        _record(progress, "provider", "failed", "configured", "no_models_available")
        store.save(progress)
        ui.write("No selectable models were returned. Install or enable a model, then retry.")
        return
    benchmarks = BenchmarkRegistry(Path(getattr(arguments, "benchmark_dir")))
    for number, entry in enumerate(catalog, 1):
        benchmark = ""
        if provider_id == "ollama":
            benchmark = (
                " — accepted benchmark" if benchmarks.accepted(entry.name) else " — not benchmarked"
            )
        ui.write(f"  {number}) {entry.name}{benchmark}")
    selected_raw = ui.ask("Choose a model [1]: ") or "1"
    try:
        selected = catalog[int(selected_raw) - 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("choose one of the listed models") from exc
    adapter = registry.create(provider_id, selected.name)
    try:
        health = await adapter.health()
    finally:
        await adapter.close()
    if health.status is not ProviderHealthStatus.READY:
        _record(progress, "provider", "failed", "configured", health.detail or "health_failed")
        store.save(progress)
        ui.write("Provider validation failed. The previous model selection was preserved.")
        return
    persist_model_selection(config_path, provider_id, selected.name)
    if provider_id == "ollama" and not benchmarks.accepted(selected.name):
        ui.write(
            "This local model has no accepted Raspberry Pi benchmark report. "
            "Run `ninjarobot benchmark ollama` before relying on it for Agent work."
        )
    progress.selections.update(provider=provider_id, model=selected.name)
    _record(progress, "provider", "complete", "software_verified", "health_ready")
    store.save(progress)


async def _remote_setup(
    progress: SetupProgress, store: ProgressStore, ui: SetupConsole, arguments: object
) -> None:
    config_path = Path(getattr(arguments, "config")).expanduser()
    config = load_robot_config(config_path)
    if _yes(ui.ask("Enable optional ngrok remote web control? [y/N]: ")):
        ui.write(
            "ngrok creates an authenticated outbound tunnel. Create an account at https://ngrok.com/"
        )
        token = ui.secret("Enter the ngrok authtoken: ")
        confirmation = ui.secret("Enter the ngrok authtoken again: ")
        if not token or token != confirmation:
            raise ValueError("ngrok authtoken values were empty or did not match")
        install_ngrok_binary(config.remote_access.executable)
        secret_store = SecretStore(Path(getattr(arguments, "secret_file")))
        secret_store.set(config.remote_access.authtoken_env, token)
        for name in (
            config.remote_access.pairing_secret_env,
            config.remote_access.session_secret_env,
            config.remote_access.remote_header_secret_env,
        ):
            if not secret_store.contains(name):
                secret_store.set(name, secrets.token_urlsafe(48))
        await persist_remote_access_enabled(config_path, True)
        _record(progress, "web_access", "complete", "configured", "ngrok_selected")
        progress.selections["web_access"] = "ngrok"
        ui.write("ngrok is configured. The running Agent will validate the public endpoint.")
    else:
        await persist_remote_access_enabled(config_path, False)
        current = load_robot_config(config_path)
        updated = current.model_copy(
            update={"onboarding": current.onboarding.model_copy(update={"enabled": True})}
        )
        save_robot_config(updated, config_path, overwrite=True)
        _record(progress, "web_access", "complete", "configured", "authenticated_lan_https")
        progress.selections["web_access"] = "local_network"
        ui.write("Authenticated HTTPS will start for devices on the same Wi-Fi.")
    store.save(progress)


async def _mcp_setup(
    progress: SetupProgress, store: ProgressStore, ui: SetupConsole, arguments: object
) -> None:
    ui.write("\nOptional external MCP tools")
    ui.write("These services can give the Agent read-only access to selected outside data.")
    ui.write("  1) Tavily Search   2) Google Calendar   3) Notion")
    raw = ui.ask("Enter one or more numbers separated by commas, or press Enter to skip: ")
    if not raw.strip():
        _record(progress, "mcp", "skipped", "unverified", "user_skipped")
        store.save(progress)
        return
    selected = _parse_multiple_choices(raw, maximum=3)
    mcp_path = Path(getattr(arguments, "mcp_config")).expanduser()
    secret_store = SecretStore(Path(getattr(arguments, "secret_file")))
    results: list[str] = []
    failures: list[str] = []
    for number in selected:
        name = {1: "Tavily Search", 2: "Google Calendar", 3: "Notion"}[number]
        while True:
            server_id = name.lower().replace(" ", "-")
            ui.write(f"\nOptional tool — {name}")
            ui.write(_mcp_explanation(number))
            try:
                server = await _prepare_mcp_server(number, ui, secret_store)
                server_id = server.id
                await _validate_mcp_server(server, secret_store)
                _save_mcp_server(mcp_path, server)
            except Exception as exc:
                ui.write(
                    f"{name} validation failed ({type(exc).__name__}). "
                    "No MCP server configuration was replaced. Any credential you entered "
                    "remains in private storage for a retry."
                )
                choice = ui.ask("Choose R) retry this tool or S) skip it: ").lower()
                if choice == "r":
                    continue
                failures.append(server_id)
            else:
                ui.write(f"Success: {name} connected and its reviewed tools were found.")
                results.append(server.id)
            break
    progress.selections["mcp_tools"] = ",".join(results)
    if failures:
        _record(progress, "mcp", "needs_attention", "configured", "failed:" + ",".join(failures))
    else:
        _record(progress, "mcp", "complete", "software_verified", "selected:" + ",".join(results))
    store.save(progress)


def _parse_multiple_choices(value: str, *, maximum: int) -> tuple[int, ...]:
    try:
        choices = tuple(dict.fromkeys(int(part.strip()) for part in value.split(",")))
    except ValueError as exc:
        raise ValueError("enter comma-separated option numbers") from exc
    if not choices or any(choice < 1 or choice > maximum for choice in choices):
        raise ValueError(f"choose numbers from 1 through {maximum}")
    return choices


def _mcp_explanation(number: int) -> str:
    return {
        1: (
            "What is this? Tavily searches the public web. Why is it needed? "
            "It lets the Agent answer current-information questions."
        ),
        2: (
            "What is this? A separate read-only Google Calendar MCP server. Why is it needed? "
            "It lets the Agent list today's events without changing them."
        ),
        3: (
            "What is this? Notion's hosted MCP server. Why is it needed? "
            "It lets the Agent search and fetch pages you authorize."
        ),
    }[number]


async def _prepare_mcp_server(
    number: int, ui: SetupConsole, secret_store: SecretStore
) -> MCPServerConfig:
    if number == 1:
        ui.write("Create a Tavily API key in the Tavily dashboard. It will be stored privately.")
        value = ui.secret("Enter TAVILY_API_KEY: ")
        confirmation = ui.secret("Enter TAVILY_API_KEY again: ")
        if not value or value != confirmation:
            raise ValueError("Tavily API key values were empty or did not match")
        secret_store.set("TAVILY_API_KEY", value)
        return tavily_server_config()
    if number == 2:
        ui.write("Create a Google Desktop OAuth client and copy its JSON file to the Pi.")
        client_file = Path(ui.ask("Path to the Google OAuth client JSON file: ")).expanduser()
        ui.write("The next step grants read-only event access in your browser.")
        credential = await authorize_google_calendar(
            client_file, write=False, discover_primary=True
        )
        credential = {
            key: credential[key]
            for key in (
                "client_id",
                "client_secret",
                "refresh_token",
                "scope",
                "calendar_id",
            )
        }
        credential_path = Path(
            "~/.config/ninjarobot_pi5/mcp-google-calendar/credential.json"
        ).expanduser()
        _save_private_json(credential_path, credential)
        return google_calendar_server_config(sys.executable, str(credential_path))
    if number == 3:
        ui.write(
            "A browser will ask you to authorize Notion. Over SSH, run the displayed "
            "port-forward command on your Mac first."
        )
        return notion_server_config()
    raise AssertionError("unknown MCP selection")


async def _validate_mcp_server(server: MCPServerConfig, secrets_store: SecretStore) -> None:
    provider = MCPToolProvider(
        server,
        secrets_store,
        connection_factory=lambda config, secrets: SDKMCPConnection(
            config, secrets, allow_oauth_login=True
        ),
    )
    try:
        await provider.start()
        tools = await provider.list_tools()
        if not tools:
            raise RuntimeError("the server exposed no reviewed tools")
    finally:
        await provider.close()


def _save_mcp_server(path: Path, server: MCPServerConfig) -> None:
    configuration = load_mcp_configuration(path)
    existing = next((item for item in configuration.servers if item.id == server.id), None)
    if existing is not None and existing.preset != server.preset:
        raise ValueError(f"MCP server ID '{server.id}' is already used by another configuration")
    servers = tuple(item for item in configuration.servers if item.id != server.id) + (server,)
    save_mcp_configuration(MCPConfiguration(servers=servers), path)


def _save_private_json(path: Path, payload: dict[str, object]) -> None:
    path = path.expanduser().absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.resolve() != path.parent or path.is_symlink():
        raise ValueError("credential storage must use a real private path")
    path.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}-", suffix=".tmp", dir=path.parent, text=True
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def _show_preview(ui: SetupConsole) -> None:
    ui.write("NinjaRobot onboarding preview — no changes will be made")
    for index, name in enumerate((*MANDATORY_HARDWARE, *OPTIONAL_HARDWARE), 1):
        required = "required" if name in MANDATORY_HARDWARE else "optional"
        ui.write(f"  {index}. {name} ({required})")
    ui.write("  AI provider; external MCP tools; ngrok or same-Wi-Fi HTTPS; launch or exit")


def _simulate(progress: SetupProgress) -> None:
    for name in (*MANDATORY_HARDWARE, *OPTIONAL_HARDWARE, "provider", "mcp", "web_access"):
        _record(progress, name, "complete", "simulated", "offline_rehearsal")
    progress.selections["mode"] = "simulation_rehearsal"


def _summary(ui: SetupConsole, progress: SetupProgress) -> None:
    ui.write("\nSetup summary")
    for name in (*MANDATORY_HARDWARE, *OPTIONAL_HARDWARE, "provider", "mcp", "web_access"):
        record = progress.steps.get(name, StepRecord())
        ui.write(f"  {name}: {record.status} ({record.verification})")


def _record(
    progress: SetupProgress,
    name: str,
    status: StepStatus,
    verification: Verification,
    detail: str,
) -> None:
    progress.steps[name] = StepRecord(
        status=status,
        verification=verification,
        detail=detail[:500],
        updated_at=_now(),
    )


def _yes(value: str) -> bool:
    return value.strip().lower() in {"y", "yes"}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
