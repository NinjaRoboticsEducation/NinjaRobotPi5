"""CLI exports for pi5mic."""

from pi5mic.cli.config_cmd import config_cmd
from pi5mic.cli.doctor import doctor
from pi5mic.cli.install_cmd import install_cmd
from pi5mic.cli.mic_tool import mic_tool
from pi5mic.cli.run_cmd import run_cmd
from pi5mic.cli.setup_cmd import setup_cmd
from pi5mic.cli.status import status
from pi5mic.cli.voiceinput_tool import voiceinput_tool

__all__ = [
    "config_cmd",
    "doctor",
    "install_cmd",
    "mic_tool",
    "run_cmd",
    "setup_cmd",
    "status",
    "voiceinput_tool",
]
