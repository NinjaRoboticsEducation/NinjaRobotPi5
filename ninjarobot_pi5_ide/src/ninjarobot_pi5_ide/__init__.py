"""Public Phase 1 contracts for deterministic robot middleware."""

from .api import IDEClient
from .config import RobotConfig, load_robot_config
from .errors import IDEError
from .models import (
    ActionRequest,
    ActionResult,
    ActionStatus,
    CapabilityDescriptor,
    ErrorDetails,
    HealthReport,
    ResourceHealth,
    RetrySafety,
    RiskLevel,
)

__all__ = [
    "ActionRequest",
    "ActionResult",
    "ActionStatus",
    "CapabilityDescriptor",
    "ErrorDetails",
    "HealthReport",
    "IDEClient",
    "IDEError",
    "ResourceHealth",
    "RetrySafety",
    "RiskLevel",
    "RobotConfig",
    "load_robot_config",
]

__version__ = "0.1.0"
