"""pi0servo.parser - Command string parsing utilities.

Exports:
    - ServoEndpoint: Normalized endpoint model for native GPIO and HAT PWM
    - parse_command: Parse movement-tool format command strings
    - ParsedCommand: Dataclass containing parsed result
    - ServoTarget: Dataclass for individual servo targets
    - parse_servo_endpoint: Parse endpoint identifiers
    - resolve_special_angle: Convert C/M/X to angles
"""

from ..core.endpoint import ServoEndpoint, parse_servo_endpoint
from .command import (
    ParsedCommand,
    ServoTarget,
    parse_command,
    resolve_special_angle,
)

__all__ = [
    "ServoEndpoint",
    "parse_command",
    "ParsedCommand",
    "ServoTarget",
    "parse_servo_endpoint",
    "resolve_special_angle",
]
