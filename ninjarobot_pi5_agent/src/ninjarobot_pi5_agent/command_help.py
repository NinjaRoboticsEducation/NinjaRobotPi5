"""Shared, read-only command reference for CLI, chat and the command-help skill."""

from __future__ import annotations

import re

CHAT_HELP_TEXT = """Available chat commands:
/info OPERATION {"arguments":{...},"confirmed":true}
  Read notes.list, notes.read, calendar.connections, calendar.list_events;
  preview notes.create/update/delete or calendar.propose_change, then confirm
  the exact preview in this same session with notes.confirm or calendar.confirm.
  Use research.search, research.answer, research.save_note or briefing.build.
  Calendar setup uses the terminal calendar-connect command; never paste tokens.
/project QUESTION
  Search pinned public documentation; answers include source dates and draft warnings.
/recipes list|show ID [VERSION]|run ID VERSION|disable ID
  Review or explicitly run saved read-only recipes. Use the recipe CLI to preview/save.
/time
  Read the Pi system date, time, UTC offset and timezone without a model call.
/game start [5-60]|stop|status
  Play a bounded hand-distance sound game; wheels stay still. Disabled until configured.
/speech on|off|stop|status|outputs|en|zh
  Control local spoken replies; Stop also cancels queued speech without cancelling chat.

/help [TOPIC]
  Show this command list and explain how to use chat.
/guide [1-5]
  Read an optional setup or safety check; no practice actions run automatically.
/exit
  Exit chat without stopping the Agent service.
/clear
  Clear this interface's conversation transcript.
/status
  Show Agent, model, hardware, memory, and tool status.
/remind SECONDS MESSAGE
  Preview a silent local inbox reminder; then confirm its exact task ID.
/tasks
  List local reminders, progress and delivery evidence without a model call.
/tasks confirm ID
  Schedule the exact reminder preview you reviewed (expires after ten minutes).
/tasks cancel ID
  Cancel further delivery; an in-progress notification may already have happened.
/tasks snooze ID MINUTES
  Preview a new due time; review and confirm it again.
/remind-json JSON
  Preview title, due_at (with UTC offset), timezone, repeat and notification.
/memory review
  Inspect saved information, source, confidence and confirmation for the active user.
/memory confirm ID
  Confirm the reviewed preference.
/memory edit ID NEW TEXT
  Correct and confirm a preference for the active user.
/memory forget ID
  Remove that item and its active preference value.
/resume
  Confirm recovery after an Emergency Stop.
/camera
  Authorize one temporary AI camera preview for this chat session.
/arm
  Confirm and arm physical AI motion for this chat session.
/disarm
  Revoke physical AI motion authorization for this chat session.
/confirm <request>
  Explicitly confirm and send one request that requires confirmation.
/voice input on
  Enable always-on wake-word voice input.
/voice input off
  Disable always-on wake-word voice input.
/voice input status
  Show wake-word and microphone listener status.
/show remote access
  Display a fresh one-use ngrok pairing QR without revoking existing browsers.
/new user
  Register an additional user profile and face.
/switch user
  Verify and switch this interface to another registered user.
/identify
  Identify a registered user with the camera.
/update profile
  Show and update the active user's name or registered face.

Ordinary text is sent to NinjaRobot using this interface's active user and session."""


def help_text(query: str = "") -> str:
    """Return a bounded reference, never a claim that a command was executed."""
    if not query.strip():
        return CHAT_HELP_TEXT
    if "bluetooth" in query.lower() or (
        "speaker" in query.lower()
        and any(word in query.lower() for word in ("connect", "pair", "setup"))
    ):
        return (
            "These are instructions only; no setting has been changed. "
            "In a terminal on the Pi, run ninjarobot-ide-tool bluetooth connect "
            "(or choose menu 8). Put the speaker in pairing mode, select its number, "
            "then follow any pairing prompts. Accept the displayed reconnect service "
            "if you want reconnection while the Agent is stopped. This does not start "
            "the Agent. Use ninjarobot-ide-tool bluetooth status to inspect it, or "
            "ninjarobot-ide-tool bluetooth disconnect to disable reconnect and disconnect. "
            "Lite systems need the audio prerequisites in the installation guide. "
            "In chat, /speech on enables spoken replies once a voice and speaker are configured."
        )
    words = set(re.findall(r"[a-z]+", query.lower()))
    aliases = {
        "audio": "speech",
        "speak": "speech",
        "spoken": "speech",
        "speaker": "speech",
        "voice": "speech voice",
        "distance": "game",
        "play": "game",
        "scheduled": "tasks",
        "schedule": "tasks",
        "reminder": "tasks remind",
        "memory": "memory",
        "microphone": "voice",
        "camera": "camera identify",
        "move": "arm disarm resume",
        "functions": "help",
        "commands": "help",
    }
    expanded = set(words)
    for word in words:
        expanded.update(aliases.get(word, "").split())
    blocks = re.split(r"\n(?=/)", CHAT_HELP_TEXT)[1:]
    matches = [
        block
        for block in blocks
        if expanded.intersection(re.findall(r"[a-z]+", block.split()[0].lower()))
    ]
    if not matches:
        return "No matching command found. Type /help for the command list."
    prefix = "These are instructions only; no setting has been changed.\n"
    if "speech" in expanded:
        prefix += (
            "Spoken replies need a configured local voice and speaker. "
            "Type /speech on to enable them, or /speech off to disable them. "
            "This does not enable the microphone.\n"
        )
    return prefix + "\n".join(matches)[:10_000]


def wants_command_help(text: str) -> bool:
    """Narrow routing; task contents and ordinary action requests stay in the normal loop."""
    lowered = text.lower().strip()
    if lowered.startswith("/"):
        return False
    question = any(
        marker in lowered
        for marker in (
            "how do i",
            "how can i",
            "how to",
            "what commands",
            "what functions",
            "help me use",
            "explain how",
            "turn on the audio and voice out",
        )
    )
    topic = any(
        word in lowered
        for word in (
            "speech",
            "spoken",
            "audio",
            "voice",
            "command",
            "function",
            "remind",
            "task",
            "camera",
            "microphone",
            "memory",
            "robot",
            "speaker",
            "bluetooth",
            "game",
        )
    )
    return question and topic
