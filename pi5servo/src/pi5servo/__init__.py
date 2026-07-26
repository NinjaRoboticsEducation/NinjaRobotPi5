"""pi5servo - Servo control library for Raspberry Pi 5.

A unified API for controlling one or more servos with:
- velocity-based movement control
- abort support for safe interruption
- movement-tool command parsing
- per-servo calibration with speed limits
- standalone Pi 5 backends plus legacy pigpio compatibility

Usage:
    from pi5servo import ConfigManager, ServoGroup

    manager = ConfigManager()
    manager.load()
    calibrations = {12: manager.get_calibration(12)}

    # Standalone Pi 5 mode (auto-selects the configured backend)
    group = ServoGroup(None, pins=[12], calibrations=calibrations)
    group.move_all_sync(targets=[45], speed_mode="M")
    group.close()
"""

__version__ = "0.1.0"

# Core classes
# Configuration
from .config import (
    ConfigManager,
    get_default_config_path,
)
from .core import (
    PULSE_CENTER,
    PULSE_MAX,
    PULSE_MIN,
    Servo,
    ServoCalibration,
    ServoGroup,
)

# Motion utilities
from .motion import (
    EASING_FUNCTIONS,
    FMS_MULTIPLIERS,
    calculate_duration,
    calculate_step_count,
    ease_in,
    ease_in_out,
    ease_out,
    linear,
)

# Parser
from .parser import (
    ParsedCommand,
    ServoTarget,
    parse_command,
    resolve_special_angle,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "Servo",
    "ServoCalibration",
    "ServoGroup",
    "MultiServo",  # Backward compatibility alias
    "PULSE_MIN",
    "PULSE_MAX",
    "PULSE_CENTER",
    # Config
    "ConfigManager",
    "get_default_config_path",
    # Motion
    "linear",
    "ease_out",
    "ease_in",
    "ease_in_out",
    "EASING_FUNCTIONS",
    "calculate_duration",
    "calculate_step_count",
    "FMS_MULTIPLIERS",
    # Parser
    "parse_command",
    "resolve_special_angle",
    "ParsedCommand",
    "ServoTarget",
]

# Backward compatibility alias for ninja_core
MultiServo = ServoGroup
