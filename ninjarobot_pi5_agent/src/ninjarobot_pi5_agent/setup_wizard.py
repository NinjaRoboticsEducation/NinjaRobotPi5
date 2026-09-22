"""Guided, resumable setup orchestration for non-technical robot owners."""

from __future__ import annotations

import asyncio
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
from typing import IO, Awaitable, Callable, Literal, Protocol

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
from .secrets import SecretStore, _validate_name

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
        print(message, flush=True)

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
        records = raw.get("steps", {})
        selections = raw.get("selections", {})
        if not isinstance(records, dict) or not isinstance(selections, dict):
            raise ValueError("invalid setup progress structure; file was not changed")
        steps = {}
        for name, record in records.items():
            if name not in {
                *MANDATORY_HARDWARE,
                *OPTIONAL_HARDWARE,
                "provider",
                "mcp",
                "web_access",
            } or not isinstance(record, dict):
                raise ValueError("invalid setup progress step; file was not changed")
            if record.get("status") not in {
                "pending",
                "complete",
                "skipped",
                "failed",
                "needs_attention",
            } or record.get("verification") not in {
                "unverified",
                "configured",
                "software_verified",
                "operator_verified",
                "simulated",
            }:
                raise ValueError("invalid setup progress status; file was not changed")
            if any(not isinstance(value, str) for value in record.values()):
                raise ValueError("invalid setup progress value; file was not changed")
            try:
                steps[name] = StepRecord(**record)
            except TypeError as exc:
                raise ValueError("invalid setup progress record; file was not changed") from exc
        if any(not isinstance(value, str) for value in selections.values()):
            raise ValueError("invalid setup selections; file was not changed")
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
            rehearsal = SetupProgress()
            _simulate(rehearsal)
            ui.write(json.dumps(asdict(rehearsal), indent=2))
            ui.write("Simulation rehearsal complete. No hardware, account, or service was changed.")
            return SetupOutcome()

        try:
            _welcome(ui)
            ui.write("Required hardware comes first. You can save and exit after any step.")
            config_path = Path(getattr(arguments, "config")).expanduser()
            requested_step = getattr(arguments, "onboard_step", None)

            reused: set[str] = set()
            if not requested_step:
                saved = {
                    name: hardware_setup_status(name)
                    for name in (*MANDATORY_HARDWARE, "microphone")
                }
                if any(item["configuration_saved"] for item in saved.values()):
                    choice = _choice(
                        ui,
                        "1) Open setup tools step by step\n2) Apply existing settings for "
                        "all modules\nQ) Save and exit\nChoose: ",
                        {"1", "2", "q"},
                    )
                    if choice == "q":
                        store.save(progress)
                        return SetupOutcome()
                    if choice == "2":
                        for name, status in saved.items():
                            if status.get("configuration_valid"):
                                _show_hardware(ui, name, status)
                                _record(
                                    progress,
                                    name,
                                    "complete",
                                    "software_verified",
                                    "settings_checked",
                                )
                                reused.add(name)
                            else:
                                ui.write(f"{name}: setup still needed.")
                        store.save(progress)

            for index, component in enumerate(MANDATORY_HARDWARE, 1):
                if requested_step and requested_step != component:
                    continue
                if component in reused:
                    continue
                prior = progress.steps.get(component)
                current_status = hardware_setup_status(component)
                if (
                    getattr(arguments, "resume", False)
                    and prior is not None
                    and prior.status == "complete"
                    and prior.verification != "simulated"
                    and current_status.get("configuration_valid") is True
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

            if requested_step in MANDATORY_HARDWARE:
                _import_hardware_configuration(config_path, ui)
            if requested_step in OPTIONAL_HARDWARE:
                await _optional_hardware(progress, store, ui, config_path, selected=requested_step)
                if requested_step == "microphone":
                    _import_hardware_configuration(
                        config_path,
                        ui,
                        include_microphone=progress.steps.get("microphone", StepRecord()).status
                        == "complete",
                    )
            elif requested_step == "provider":
                await _recover_step(_provider_setup, progress, store, ui, arguments)
            elif requested_step == "mcp":
                await _mcp_setup(progress, store, ui, arguments)
            elif requested_step == "web-access":
                await _recover_step(_remote_setup, progress, store, ui, arguments)
            elif not requested_step:
                await _optional_hardware(
                    progress, store, ui, config_path, reuse_microphone="microphone" in reused
                )
                _import_hardware_configuration(
                    config_path,
                    ui,
                    include_microphone=progress.steps.get("microphone", StepRecord()).status
                    == "complete",
                )
                await _recover_step(_provider_setup, progress, store, ui, arguments)
                await _mcp_setup(progress, store, ui, arguments)
                await _recover_step(_remote_setup, progress, store, ui, arguments)

            incomplete = [
                component
                for component in MANDATORY_HARDWARE
                if progress.steps.get(component, StepRecord()).status != "complete"
                or progress.steps[component].verification == "simulated"
                or not hardware_setup_status(component).get("configuration_valid")
            ]
            progress.completed = not incomplete
            store.save(progress)
            _summary(ui, progress)
            if requested_step:
                return SetupOutcome()
            choice = _choice(
                ui, "Choose 1) Start NinjaRobot Agent or 2) Exit onboarding [2]: ", {"1", "2"}, "2"
            )
            if choice != "1":
                ui.write("Setup progress saved. Run `ninjarobot onboard --resume` to continue.")
                return SetupOutcome()
            mode = _choice(ui, "Start 1) simulation or 2) real hardware? [1]: ", {"1", "2"}, "1")
            if mode == "2" and incomplete:
                ui.write(
                    "Real-hardware launch is blocked until required steps pass: "
                    + ", ".join(incomplete)
                )
                return SetupOutcome()
            return SetupOutcome("real" if mode == "2" else "simulation")
        except (EOFError, KeyboardInterrupt, asyncio.CancelledError):
            store.save(progress)
            ui.write("\nProgress saved. Run `ninjarobot onboard --resume` to continue.")
            return SetupOutcome()


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
            "Setup checks camera settings. Photo tests are optional.",
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
    while True:
        choice = _choice(ui, "1) Open setup tool\nQ) Save and exit\nChoose: ", {"1", "q"})
        if choice == "q":
            return "needs_attention", "unverified", "saved_for_later"
        if component == "servo" and ui.ask("Type WHEELS RAISED to continue: ") != "WHEELS RAISED":
            continue
        try:
            result = run_hardware_setup(component)
            refreshed = hardware_setup_status(component)
            if result == 0 and refreshed.get("configuration_valid"):
                _show_hardware(ui, component, refreshed)
                ui.ask("Press ENTER to continue: ")
                return "complete", "software_verified", "settings_checked"
            ui.write(
                "Setup needs attention: "
                + str(refreshed.get("message", "tool did not finish successfully"))
            )
        except (OSError, RuntimeError, ValueError):
            ui.write("Could not open setup. Check installation and ensure the Agent is stopped.")
        ui.write("Retry the setup tool or save and exit to fix the problem.")


def _import_hardware_configuration(
    path: Path, ui: SetupConsole, *, include_microphone: bool = False
) -> None:
    base = load_effective_config(path if path.exists() else None)
    valid_libraries = {
        str(hardware_setup_status(name)["component"])
        for name in (*MANDATORY_HARDWARE, *(("microphone",) if include_microphone else ()))
        if hardware_setup_status(name).get("configuration_valid")
    }
    updated, imported = import_pi5_configs(
        base, [item for item in discover_pi5_configs() if item.library in valid_libraries]
    )
    ui.write("\nIntegrated configuration preview:")
    for item in imported:
        ui.write(f"  - {item}")
    if not imported:
        ui.write("  No standalone hardware configuration was found.")
        return
    ui.write(json.dumps(updated.hardware.model_dump(mode="json"), indent=2))
    ui.ask("Press ENTER to save these settings and continue: ")
    save_robot_config(updated, path, overwrite=path.exists())
    ui.write(f"Saved private robot configuration to {path}.")


async def _optional_hardware(
    progress: SetupProgress,
    store: ProgressStore,
    ui: SetupConsole,
    config_path: Path,
    *,
    selected: str | None = None,
    reuse_microphone: bool = False,
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
                current = load_effective_config(config_path)
                if current.bluetooth_speaker.address:
                    _record(progress, "bluetooth", "complete", "configured", "speaker_selected")
                else:
                    _record(progress, "bluetooth", "skipped", "unverified", "setup_cancelled")
        else:
            _record(progress, "bluetooth", "skipped", "unverified", "user_skipped")
        store.save(progress)

    if reuse_microphone or selected not in {None, "microphone"}:
        return
    if _yes(ui.ask("Configure the optional USB microphone and Hey Ninja wake word? [y/N]: ")):
        ui.write("The default speech-to-text engine is local whisper.cpp.")
        ui.write("The setup tool uses the bundled hey_Ninja.onnx wake model.")
        ui.write(
            "In mic-tool choose Run setup wizard, select the standalone profile and "
            "whisper_cpp backend, then enable always-on input with the bundled "
            "hey_Ninja.onnx model. Run Doctor before exiting."
        )
        ui.write(
            "Privacy: obtain consent before selecting a recording test in the microphone tool."
        )
        while True:
            try:
                result = run_hardware_setup("microphone")
                status = hardware_setup_status("microphone")
                if result == 0 and status.get("configuration_valid"):
                    _show_hardware(ui, "microphone", status)
                    ui.ask("Press ENTER to continue: ")
                    _record(
                        progress, "microphone", "complete", "software_verified", "settings_checked"
                    )
                    break
            except (OSError, RuntimeError, ValueError):
                pass
            if _choice(ui, "Microphone setup incomplete. R) Retry or S) Skip: ", {"r", "s"}) == "s":
                _record(progress, "microphone", "failed", "unverified", "setup_incomplete")
                break
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
    raw = _choice(ui, "Choose a provider [1]: ", {"1", "2", "3", "4"}, "1")
    try:
        provider_id = PROVIDERS[int(raw) - 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("choose provider 1 through 4") from exc
    config_path = Path(getattr(arguments, "config")).expanduser()
    if not config_path.exists():
        save_robot_config(load_effective_config(None), config_path, overwrite=False)
    secret_store = _CandidateSecrets(Path(getattr(arguments, "secret_file")))
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
        raise RuntimeError("no models available")
    benchmarks = BenchmarkRegistry(Path(getattr(arguments, "benchmark_dir")))
    for number, entry in enumerate(catalog, 1):
        benchmark = ""
        if provider_id == "ollama":
            benchmark = (
                " — accepted benchmark" if benchmarks.accepted(entry.name) else " — not benchmarked"
            )
        ui.write(f"  {number}) {entry.name}{benchmark}")
    selected_raw = _choice(
        ui, "Choose a model [1]: ", {str(n) for n in range(1, len(catalog) + 1)}, "1"
    )
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
        _record(progress, "provider", "failed", "configured", "health_failed")
        store.save(progress)
        ui.write("Provider validation failed. The previous model selection was preserved.")
        raise RuntimeError("provider validation failed")
    secret_store.commit_configuration(
        lambda: persist_model_selection(config_path, provider_id, selected.name)
    )
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
            "ngrok creates an authenticated outbound tunnel. Create an account "
            "at https://ngrok.com/"
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
    while True:
        raw = ui.ask("Enter one or more numbers separated by commas, or press Enter to skip: ")
        if not raw.strip():
            _record(progress, "mcp", "skipped", "unverified", "user_skipped")
            store.save(progress)
            return
        try:
            selected = _parse_multiple_choices(raw, maximum=3)
            break
        except ValueError:
            ui.write("Choose 1, 2, or 3 separated by commas, or Enter to skip.")
    mcp_path = Path(getattr(arguments, "mcp_config")).expanduser()
    results: list[str] = []
    failures: list[str] = []
    for number in selected:
        name = {1: "Tavily Search", 2: "Google Calendar", 3: "Notion"}[number]
        while True:
            server_id = name.lower().replace(" ", "-")
            ui.write(f"\nOptional tool — {name}")
            ui.write(_mcp_explanation(number))
            secret_store = _CandidateSecrets(Path(getattr(arguments, "secret_file")))
            candidate_path: Path | None = None
            committed = False
            try:
                if number == 2:
                    candidate_path = Path(
                        "~/.config/ninjarobot_pi5/mcp-google-calendar"
                    ).expanduser() / ("credential-" + secrets.token_hex(12) + ".json")
                server = await _prepare_mcp_server(
                    number, ui, secret_store, credential_path=candidate_path
                )
                server_id = server.id
                await _validate_mcp_server(server, secret_store)
                secret_store.commit_configuration(lambda: _save_mcp_server(mcp_path, server))
                committed = True
            except Exception as exc:
                ui.write(
                    f"{name} validation failed ({type(exc).__name__}). "
                    "Setup did not complete. Previously validated credentials are preserved."
                )
                if number == 2:
                    ui.write(
                        "Calendar troubleshooting: confirm Desktop client type, enabled API"
                        " and test user. For a browser timeout, keep the Mac SSH tunnel "
                        "open and retry with a fresh link. Check port 8765 is available on "
                        "the Pi."
                    )
                choice = _choice(ui, "Choose R) retry this tool or S) skip it: ", {"r", "s"})
                if choice == "r":
                    continue
                failures.append(server_id)
            else:
                ui.write(f"Success: {name} connected and its reviewed tools were found.")
                results.append(server.id)
            finally:
                if candidate_path is not None and not committed:
                    candidate_path.unlink(missing_ok=True)
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
    number: int, ui: SetupConsole, secret_store: SecretStore, *, credential_path: Path | None = None
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
        ui.write("Google Calendar - connect your account (read-only)")
        ui.write("1. Open https://console.cloud.google.com/ and select or create a project.")
        ui.write("2. APIs & Services > Library: enable Google Calendar API.")
        ui.write(
            "3. Google Auth Platform: configure Branding and Audience. For an "
            "External app in Testing, add your Google account as a test user."
        )
        ui.write(
            "4. Clients > Create client > Desktop app. Download its JSON file "
            "and copy it privately to the Pi."
        )
        ui.write("Guide: https://developers.google.com/workspace/calendar/api/quickstart/python")
        client_file = Path(ui.ask("5. Path to the Google OAuth client JSON file: ")).expanduser()
        browser = _choice(
            ui,
            "6. Browser location: 1) Mac/another computer via SSH  2) Pi desktop [1]: ",
            {"1", "2"},
            "1",
        )
        if browser == "1":
            ui.write(
                "On your Mac, open a SECOND Terminal and run (replace USER and "
                "PI_HOST with your Pi SSH login):"
            )
            ui.write(
                "ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765 USER@PI_HOST"
            )
            ui.write(
                "Keep that terminal open. Silence after login is normal. If the "
                "port is busy, close the old tunnel first."
            )
            ui.write(
                "The browser's 127.0.0.1 is your Mac; this tunnel forwards approval to the Pi."
            )
        ui.ask("Press ENTER when ready to open a NEW authorization link: ")
        ui.write(
            "7. Open the link below, sign in with the test-user account, and "
            "grant read-only access. Do not share the link or redirected URL."
        )
        credential = await authorize_google_calendar(
            client_file, write=False, discover_primary=True, output=ui.write
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
        credential_path = (
            credential_path
            or Path("~/.config/ninjarobot_pi5/mcp-google-calendar/credential.json").expanduser()
        )
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
    connection = SDKMCPConnection(server, secrets_store, allow_oauth_login=True)
    provider = MCPToolProvider(
        server,
        secrets_store,
        connection_factory=lambda config, secrets: connection,
    )
    try:
        async with asyncio.timeout(360):
            await connection.start()
        await provider.start()
        tools = await provider.list_tools()
        if not tools:
            raise RuntimeError("the server exposed no reviewed tools")
        if server.preset == "google-calendar-readonly":
            async with asyncio.timeout(server.timeout_seconds):
                result = await connection.call_tool(
                    "list_today_events", {"timezone": "UTC", "max_results": 1}
                )
            if result.get("isError") or len(json.dumps(result).encode()) > server.max_result_bytes:
                raise RuntimeError("Calendar read-only API validation failed")
            structured = result.get("structuredContent")
            if not isinstance(structured, dict) or not isinstance(structured.get("events"), list):
                raise RuntimeError("Calendar returned an invalid response")
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


def _choice(ui: SetupConsole, prompt: str, allowed: set[str], default: str = "") -> str:
    while True:
        answer = ui.ask(prompt).strip().lower() or default
        if answer in allowed:
            return answer
        ui.write("Please choose one of the displayed options.")


def _show_hardware(ui: SetupConsole, name: str, status: dict[str, object]) -> None:
    ui.write(f"[OK] {name.title()} settings checked")
    ui.write("  " + str(status.get("configuration", "")))
    ui.write(json.dumps(status.get("summary", {}), indent=2, ensure_ascii=True))
    ui.write("  Configuration checked; physical operation is not automatically tested.")


def _welcome(ui: SetupConsole) -> None:
    ui.write(r"""
 _   _ ___ _   _     _   _    ____   ___  ____   ___ _____
| \ | |_ _| \ | |   | | / \  |  _ \ / _ \| __ ) / _ \_   _|
|  \| || ||  \| |_  | |/ _ \ | |_) | | | |  _ \| | | || |
| |\  || || |\  | |_| / ___ \|  _ <| |_| | |_) | |_| || |
|_| \_|___|_| \_|\___/_/   \_\_| \_\___/|____/ \___/ |_|
""")
    ui.write("Welcome to NinjaRobotPi5 - your Raspberry Pi robot assistant.")
    ui.write("We will set up hardware, AI, optional tools, and secure web access.")
    ui.write("Hardware > AI provider > Optional tools > Web access > Ready")


class _CandidateSecrets(SecretStore):
    """Validate new keys in memory before replacing existing private credentials."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.pending: dict[str, str] = {}

    def set(self, name: str, value: str) -> None:
        _validate_name(name)
        if not value or any(character in value for character in "\n\r\x00"):
            raise ValueError("invalid credential")
        if os.environ.get(name) and os.environ[name] != value:
            raise ValueError(
                "An environment credential overrides this key. Update it outside onboarding first."
            )
        self.pending[name] = value

    def get(self, name: str) -> str | None:
        return self.pending.get(name) or super().get(name)

    def commit(self) -> None:
        if self.pending:
            stored = self._read_file()
            stored.update(self.pending)
            self._write_file(stored)
            self.pending.clear()

    def commit_configuration(self, save: Callable[[], object]) -> None:
        original = self._read_file()
        existed = self.path.exists()
        changed = bool(self.pending)
        self.commit()
        try:
            save()
        except BaseException:
            if changed:
                if existed:
                    self._write_file(original)
                else:
                    self.path.unlink(missing_ok=True)
            raise


async def _recover_step(
    action: Callable[[SetupProgress, ProgressStore, SetupConsole, object], Awaitable[None]],
    progress: SetupProgress,
    store: ProgressStore,
    ui: SetupConsole,
    arguments: object,
) -> None:
    while True:
        try:
            await action(progress, store, ui, arguments)
            return
        except Exception:
            name = "provider" if action is _provider_setup else "web_access"
            _record(progress, name, "needs_attention", "unverified", "setup_failed")
            ui.write(
                "This step could not finish. Check connectivity, credentials and prerequisites. "
                "An existing environment API key must be changed in that environment."
            )
            store.save(progress)
            choice = _choice(ui, "R) Retry or C) Continue or Q) Save and exit: ", {"r", "c", "q"})
            if choice == "q":
                raise EOFError
            if choice == "c":
                return
