"""Selected-speaker BlueZ access, independent of robot assembly and device drivers."""

from __future__ import annotations

import asyncio
import importlib
import json
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from .audio_process import run_audio_process

BLUEZ = "org.bluez"
DEVICE = "org.bluez.Device1"
ADAPTER = "org.bluez.Adapter1"
AGENT_PATH = "/org/ninjarobot/SpeakerPairing"
AUDIO_UUIDS = {"0000110b-0000-1000-8000-00805f9b34fb", "0000110d-0000-1000-8000-00805f9b34fb"}
Prompt = Callable[[str], Awaitable[str]]


class BluetoothError(RuntimeError):
    """A recoverable setup problem with an operator-readable explanation."""


def safe_label(value: str) -> str:
    return "".join(c for c in value if c.isprintable())[:100]


@dataclass(frozen=True)
class SpeakerDevice:
    path: str
    address: str
    name: str
    paired: bool
    trusted: bool
    connected: bool


class BlueZSpeaker:
    def __init__(self, adapter: str = "hci0", *, prompt: Prompt | None = None) -> None:
        if not re.fullmatch(r"hci[0-9]{1,3}", adapter):
            raise ValueError("invalid Bluetooth adapter")
        self.adapter = "/org/bluez/" + adapter
        self.prompt = prompt
        self.bus: Any = None
        self.api: Any = None
        self.selected = ""
        self._bluez_owner = ""
        self._registered = False
        self._discovering = False
        self._callbacks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        try:
            self.api = importlib.import_module("dbus_fast")
            aio = importlib.import_module("dbus_fast.aio")
        except ImportError as error:
            raise BluetoothError(
                "Bluetooth support is not installed. From the project root run: "
                "uv sync --frozen --inexact --package ninjarobot-pi5-ide --extra bluetooth"
            ) from error
        try:
            self.bus = aio.MessageBus(bus_type=self.api.BusType.SYSTEM)
            await asyncio.wait_for(self.bus.connect(), 5)
            owner = await asyncio.wait_for(
                self.bus.call(
                    self.api.Message(
                        destination="org.freedesktop.DBus",
                        path="/org/freedesktop/DBus",
                        interface="org.freedesktop.DBus",
                        member="GetNameOwner",
                        signature="s",
                        body=[BLUEZ],
                    )
                ),
                5,
            )
            if owner is None or owner.message_type == self.api.MessageType.ERROR:
                raise BluetoothError("The system Bluetooth service is not running.")
            self._bluez_owner = owner.body[0]
            self.bus.add_message_handler(self._agent_message)
        except (OSError, TimeoutError) as error:
            raise BluetoothError(
                "Cannot reach system Bluetooth. Check systemctl status bluetooth."
            ) from error

    async def call(
        self,
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: list[Any] | None = None,
        *,
        timeout: float = 10,
    ) -> list[Any]:
        try:
            reply = await asyncio.wait_for(
                self.bus.call(
                    self.api.Message(
                        destination=BLUEZ,
                        path=path,
                        interface=interface,
                        member=member,
                        signature=signature,
                        body=body or [],
                    )
                ),
                timeout,
            )
        except TimeoutError as error:
            raise BluetoothError(
                f"Bluetooth {member} timed out. Check speaker power/pairing mode and retry."
            ) from error
        if reply is None or reply.message_type == self.api.MessageType.ERROR:
            name = getattr(reply, "error_name", "NoReply")
            raise BluetoothError(
                f"Bluetooth {member} failed ({name}). "
                "Turn on pairing mode, disconnect other hosts, then retry. "
                "For NotReady, check rfkill and the Bluetooth service."
            )
        return list(reply.body)

    async def objects(self) -> dict[str, Any]:
        return dict(
            (await self.call("/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects"))[0]
        )

    async def devices(self) -> tuple[SpeakerDevice, ...]:
        objects = await self.objects()
        result = []
        for path, interfaces in objects.items():
            if not path.startswith(self.adapter + "/dev_") or DEVICE not in interfaces:
                continue
            props = {key: value.value for key, value in interfaces[DEVICE].items()}
            address = str(props.get("Address", "")).upper()
            if not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address):
                continue
            result.append(
                SpeakerDevice(
                    path,
                    address,
                    safe_label(str(props.get("Alias", address))),
                    bool(props.get("Paired")),
                    bool(props.get("Trusted")),
                    bool(props.get("Connected")),
                )
            )
        return tuple(sorted(result, key=lambda item: (item.name.casefold(), item.address)))

    async def scan(self, seconds: float = 10) -> tuple[SpeakerDevice, ...]:
        if not 1 <= seconds <= 30:
            raise ValueError("scan duration must be 1 through 30 seconds")
        objects = await self.objects()
        if ADAPTER not in objects.get(self.adapter, {}):
            raise BluetoothError("No Bluetooth adapter found. Check bluetoothctl list and rfkill.")
        powered = objects[self.adapter][ADAPTER].get("Powered")
        if not powered or not powered.value:
            await self.call(
                self.adapter,
                "org.freedesktop.DBus.Properties",
                "Set",
                "ssv",
                [ADAPTER, "Powered", self.api.Variant("b", True)],
            )
        await self.call(self.adapter, ADAPTER, "StartDiscovery")
        self._discovering = True
        try:
            await asyncio.sleep(seconds)
            return await self.devices()
        finally:
            await self.stop_scan()

    async def stop_scan(self) -> None:
        if self._discovering:
            self._discovering = False
            with suppress(Exception):
                await self.call(self.adapter, ADAPTER, "StopDiscovery", timeout=3)

    def _agent_message(self, message: Any) -> bool | None:
        if (
            message.path != AGENT_PATH
            or message.interface != "org.bluez.Agent1"
            or message.sender != self._bluez_owner
            or message.message_type != self.api.MessageType.METHOD_CALL
        ):
            return None
        task = asyncio.create_task(self._answer_pairing(message))
        self._callbacks.add(task)
        task.add_done_callback(self._callbacks.discard)
        return True

    async def _answer_pairing(self, message: Any) -> None:
        try:
            signature = ""
            body: list[Any] = []
            if message.member not in {"Release", "Cancel"}:
                if not self.selected or not message.body or message.body[0] != self.selected:
                    raise BluetoothError("Pairing request is not for the selected speaker.")
                if message.member == "AuthorizeService":
                    if len(message.body) != 2 or message.body[1].lower() not in AUDIO_UUIDS:
                        raise BluetoothError("Only audio service authorization is supported.")
                elif message.member == "RequestAuthorization":
                    pass  # Explicit selection authorizes pairing of this device only.
                elif message.member in {"DisplayPinCode", "DisplayPasskey"}:
                    if self.prompt:
                        await asyncio.wait_for(
                            self.prompt(
                                f"Speaker pairing code: {safe_label(str(message.body[1]))}. "
                                "Press Enter."
                            ),
                            45,
                        )
                elif message.member in {"RequestConfirmation", "RequestPinCode", "RequestPasskey"}:
                    if not self.prompt:
                        raise BluetoothError("Pairing requires an interactive terminal.")
                    code = str(message.body[1]) if len(message.body) > 1 else ""
                    answer = await asyncio.wait_for(
                        self.prompt(
                            f"{message.member} {safe_label(code)}: enter yes to confirm, "
                            "or the requested PIN/passkey"
                        ),
                        45,
                    )
                    if message.member == "RequestConfirmation":
                        if answer.lower().strip() not in {"y", "yes"}:
                            raise BluetoothError("Pairing rejected.")
                    elif message.member == "RequestPinCode":
                        if not 1 <= len(answer) <= 16 or not answer.isprintable():
                            raise BluetoothError("PIN must be 1 through 16 printable characters.")
                        signature, body = "s", [answer]
                    else:
                        if not re.fullmatch(r"[0-9]{1,6}", answer):
                            raise BluetoothError("Passkey must be six digits or fewer.")
                        signature, body = "u", [int(answer)]
                else:
                    raise BluetoothError("Unsupported pairing request.")
            await self.bus.send(self.api.Message.new_method_return(message, signature, body))
        except (Exception, asyncio.CancelledError):
            with suppress(Exception):
                await self.bus.send(
                    self.api.Message.new_error(
                        message, "org.bluez.Error.Rejected", "Speaker pairing was not approved."
                    )
                )

    async def connect(self, address: str, *, pair: bool = False) -> SpeakerDevice:
        selected = next((item for item in await self.devices() if item.address == address), None)
        if selected is None:
            raise BluetoothError(
                "Saved speaker is unknown to this adapter. Run speaker setup again."
            )
        self.selected = selected.path
        if pair:
            if not selected.paired:
                await self.call(
                    "/org/bluez",
                    "org.bluez.AgentManager1",
                    "RegisterAgent",
                    "os",
                    [AGENT_PATH, "KeyboardDisplay"],
                )
                self._registered = True
                try:
                    await self.call(selected.path, DEVICE, "Pair", timeout=60)
                except BaseException:
                    with suppress(Exception):
                        await self.call(selected.path, DEVICE, "CancelPairing", timeout=3)
                    raise
            await self.call(
                selected.path,
                "org.freedesktop.DBus.Properties",
                "Set",
                "ssv",
                [DEVICE, "Trusted", self.api.Variant("b", True)],
            )
        elif not selected.paired or not selected.trusted:
            raise BluetoothError(
                "Automatic reconnect requires an already paired and trusted speaker."
            )
        if not selected.connected:
            await self.call(selected.path, DEVICE, "Connect", timeout=20)
        result = next((item for item in await self.devices() if item.address == address), None)
        if result is None or not result.connected or not result.paired or not result.trusted:
            raise BluetoothError("Speaker did not report connected; retry with the speaker nearby.")
        return result

    async def close(self) -> None:
        if self.bus is None:
            return
        await self.stop_scan()
        if self._registered:
            with suppress(Exception):
                await self.call(
                    "/org/bluez",
                    "org.bluez.AgentManager1",
                    "UnregisterAgent",
                    "o",
                    [AGENT_PATH],
                    timeout=3,
                )
            self._registered = False
        for task in tuple(self._callbacks):
            task.cancel()
        await asyncio.gather(*self._callbacks, return_exceptions=True)
        with suppress(Exception):
            self.bus.remove_message_handler(self._agent_message)
        self.bus.disconnect()
        with suppress(Exception):
            await asyncio.wait_for(self.bus.wait_for_disconnect(), 3)
        self.bus = None


async def speaker_output(address: str, *, runner: Any = run_audio_process) -> str:
    """Resolve only the selected Bluetooth identity, never a default speaker."""
    if not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address):
        raise ValueError("invalid speaker address")
    rows = json.loads(await runner(["pw-dump"], timeout=3, output_limit=2_000_000))
    if not isinstance(rows, list):
        raise BluetoothError("PipeWire returned an invalid device list.")
    prefix = "bluez_output." + address.replace(":", "_") + "."
    matches = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("info"), dict):
            continue
        props = row["info"].get("props", {})
        if not isinstance(props, dict):
            continue
        name = props.get("node.name", "")
        if (
            props.get("media.class") == "Audio/Sink"
            and isinstance(name, str)
            and name.startswith(prefix)
            and re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", name)
        ):
            matches.append(name)
    if len(matches) != 1:
        raise BluetoothError(
            "No unique speaker output is ready. Check PipeWire, WirePlumber "
            "and libspa-0.2-bluetooth. Pairing alone is not audio readiness."
        )
    return matches[0]
