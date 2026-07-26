"""Public contracts and core services for deterministic robot middleware."""

from .adapters import CapabilityAdapter
from .api import IDEClient
from .buzzer import BuzzerDevice, BuzzerStopAdapter, BuzzerToneAdapter
from .camera import CameraCaptureAdapter, CameraDevice, CameraStatusAdapter
from .config import RobotConfig, load_robot_config
from .display import (
    DisplayBrightnessAdapter,
    DisplayClearAdapter,
    DisplayDevice,
    DisplayShowTextAdapter,
)
from .distance import VL53L0XDistanceAdapter
from .engine import ExecutionEngine
from .errors import IDEError
from .ledger import ActionLedger
from .models import (
    ActionRecord,
    ActionRequest,
    ActionResult,
    ActionStatus,
    CapabilityDescriptor,
    ErrorDetails,
    HealthReport,
    LifecycleState,
    ResourceHealth,
    RetrySafety,
    RiskLevel,
)
from .registry import CapabilityRegistry
from .scheduler import QueueCapacityError, ResourceScheduler
from .servo import (
    ServoDevice,
    ServoMoveAdapter,
    ServoRuntime,
    ServoStatusAdapter,
    ServoStopAdapter,
)

__all__ = [
    "ActionLedger",
    "ActionRecord",
    "ActionRequest",
    "ActionResult",
    "ActionStatus",
    "CapabilityAdapter",
    "CapabilityDescriptor",
    "CapabilityRegistry",
    "BuzzerDevice",
    "BuzzerStopAdapter",
    "BuzzerToneAdapter",
    "CameraCaptureAdapter",
    "CameraDevice",
    "CameraStatusAdapter",
    "DisplayBrightnessAdapter",
    "DisplayClearAdapter",
    "DisplayDevice",
    "DisplayShowTextAdapter",
    "ErrorDetails",
    "ExecutionEngine",
    "HealthReport",
    "IDEClient",
    "IDEError",
    "LifecycleState",
    "QueueCapacityError",
    "ResourceHealth",
    "ResourceScheduler",
    "RetrySafety",
    "RiskLevel",
    "RobotConfig",
    "ServoDevice",
    "ServoMoveAdapter",
    "ServoRuntime",
    "ServoStatusAdapter",
    "ServoStopAdapter",
    "VL53L0XDistanceAdapter",
    "load_robot_config",
]

__version__ = "0.1.0"
