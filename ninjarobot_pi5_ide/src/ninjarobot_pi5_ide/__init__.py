"""Public contracts and core services for deterministic robot middleware."""

from .adapters import CapabilityAdapter
from .api import IDEClient
from .behavior_assets import BehaviorAssetError, BehaviorAssetRepository
from .behavior_models import (
    BehaviorDefinition,
    BehaviorStage,
    DriveOperation,
    FaceOperation,
    MelodyOperation,
    TextOperation,
    ToneOperation,
    WaitOperation,
)
from .behavior_runtime import BehaviorRunner, Melody, StageResult, load_pi5buzzer_melody
from .buzzer import BuzzerDevice, BuzzerStopAdapter, BuzzerToneAdapter
from .camera import (
    CameraCaptureAdapter,
    CameraDevice,
    CameraPreviewAdapter,
    CameraStatusAdapter,
)
from .config import RobotConfig, load_robot_config
from .config_import import save_robot_config
from .display import (
    DisplayBrightnessAdapter,
    DisplayClearAdapter,
    DisplayDevice,
    DisplayShowTextAdapter,
)
from .distance import VL53L0XDistanceAdapter
from .engine import ExecutionEngine
from .errors import IDEError
from .integrated import RobotIDEClient, build_robot_ide_client
from .ledger import ActionLedger
from .microphone import (
    MicrophoneBackend,
    MicrophoneCaptureAdapter,
    MicrophoneDevice,
    MicrophoneStatusAdapter,
    MicrophoneTranscribeAdapter,
    SimulatedSpeechTranscriber,
    SpeechTranscriber,
    WhisperCppTranscriber,
)
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
from .robot import RobotAssembly
from .safety import (
    MotionController,
    MotionSafetyError,
    SafetySnapshot,
    SafetyStateStore,
    SystemSafetyController,
    raspberry_pi_undervoltage_active,
)
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
    "BehaviorAssetError",
    "BehaviorAssetRepository",
    "BehaviorDefinition",
    "BehaviorStage",
    "BehaviorRunner",
    "CameraCaptureAdapter",
    "CameraDevice",
    "CameraPreviewAdapter",
    "CameraStatusAdapter",
    "DisplayBrightnessAdapter",
    "DisplayClearAdapter",
    "DisplayDevice",
    "DisplayShowTextAdapter",
    "DriveOperation",
    "ErrorDetails",
    "ExecutionEngine",
    "FaceOperation",
    "HealthReport",
    "IDEClient",
    "IDEError",
    "LifecycleState",
    "MicrophoneCaptureAdapter",
    "MicrophoneBackend",
    "MicrophoneDevice",
    "MicrophoneStatusAdapter",
    "MicrophoneTranscribeAdapter",
    "Melody",
    "MelodyOperation",
    "MotionController",
    "MotionSafetyError",
    "QueueCapacityError",
    "ResourceHealth",
    "ResourceScheduler",
    "RetrySafety",
    "RiskLevel",
    "RobotAssembly",
    "RobotConfig",
    "RobotIDEClient",
    "SafetySnapshot",
    "SafetyStateStore",
    "ServoDevice",
    "ServoMoveAdapter",
    "ServoRuntime",
    "ServoStatusAdapter",
    "ServoStopAdapter",
    "SimulatedSpeechTranscriber",
    "SpeechTranscriber",
    "SystemSafetyController",
    "TextOperation",
    "ToneOperation",
    "WhisperCppTranscriber",
    "VL53L0XDistanceAdapter",
    "WaitOperation",
    "StageResult",
    "load_pi5buzzer_melody",
    "build_robot_ide_client",
    "raspberry_pi_undervoltage_active",
    "load_robot_config",
    "save_robot_config",
]

__version__ = "0.1.0"
