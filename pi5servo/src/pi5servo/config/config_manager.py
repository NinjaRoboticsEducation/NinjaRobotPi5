"""Configuration manager for servo calibration data and backend settings."""

import json
from pathlib import Path
from typing import Any

from ..core.endpoint import ServoEndpoint, parse_servo_endpoint
from ..core.servo import ServoCalibration

# Default config filename (relative to library)
DEFAULT_CONFIG_FILE = "servo.json"
BACKEND_CONFIG_KEY = "__backend__"
DEFAULT_BACKEND_CONFIG = {
    "name": "auto",
    "kwargs": {},
}


def get_default_config_path() -> Path:
    """Get the default config file path (relative to this package).

    Returns:
        Path to default servo.json location
    """
    # Look for config in the package's parent (library root) first
    package_dir = Path(__file__).parent.parent
    return package_dir / DEFAULT_CONFIG_FILE


class ConfigManager:
    """Manages servo calibration configuration persistence.

    Loads and saves ServoCalibration data to/from JSON files.
    Supports the new 'speed' field for per-servo speed limits.
    """

    def __init__(self, config_path: str | Path | None = None):
        """Initialize ConfigManager.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path is None:
            self._config_path = get_default_config_path()
        else:
            self._config_path = Path(config_path)

        self._data: dict[str, dict[str, Any]] = {}
        self._backend_config: dict[str, Any] = dict(DEFAULT_BACKEND_CONFIG)

    @property
    def config_path(self) -> Path:
        """Current config file path."""
        return self._config_path

    @config_path.setter
    def config_path(self, value: str | Path):
        """Set config file path."""
        self._config_path = Path(value)

    def exists(self) -> bool:
        """Check if config file exists."""
        return self._config_path.exists()

    def load(self) -> bool:
        """Load configuration from file.

        Returns:
            True if loaded successfully, False if file doesn't exist or error
        """
        if not self._config_path.exists():
            return False

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            self._data = {}
            raw_backend = raw_data.get(BACKEND_CONFIG_KEY, DEFAULT_BACKEND_CONFIG)
            if not isinstance(raw_backend, dict):
                raw_backend = DEFAULT_BACKEND_CONFIG
            self._backend_config = {
                "name": str(raw_backend.get("name", DEFAULT_BACKEND_CONFIG["name"])),
                "kwargs": dict(raw_backend.get("kwargs", {})),
            }
            for key, value in raw_data.items():
                if key == BACKEND_CONFIG_KEY:
                    continue
                try:
                    endpoint = parse_servo_endpoint(key)
                    if isinstance(value, dict):
                        self._data[endpoint.identifier] = value
                except ValueError:
                    pass

            return True
        except (json.JSONDecodeError, OSError):
            return False

    def save(self) -> bool:
        """Save configuration to file.

        Returns:
            True if saved successfully, False on error
        """
        try:
            # Ensure parent directory exists
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            json_data = self._to_dict()

            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2)

            return True
        except OSError:
            return False

    def get_calibration(self, pin: int | str | ServoEndpoint) -> ServoCalibration:
        """Get calibration for a specific endpoint.

        Args:
            pin: GPIO pin number or explicit endpoint identifier

        Returns:
            ServoCalibration for the endpoint (defaults if not configured)
        """
        endpoint = parse_servo_endpoint(pin)
        if endpoint.identifier not in self._data:
            return ServoCalibration()

        data = self._data[endpoint.identifier]
        return ServoCalibration(
            pulse_min=data.get("pulse_min", 500),
            pulse_max=data.get("pulse_max", 2500),
            pulse_center=data.get("pulse_center", 1500),
            angle_min=data.get("angle_min", -90.0),
            angle_max=data.get("angle_max", 90.0),
            angle_center=data.get("angle_center", 0.0),
            speed=data.get("speed", 80),  # New V5 field
        )

    def set_calibration(self, pin: int | str | ServoEndpoint, calibration: ServoCalibration):
        """Set calibration for a specific endpoint.

        Args:
            pin: GPIO pin number or explicit endpoint identifier
            calibration: ServoCalibration to store
        """
        endpoint = parse_servo_endpoint(pin)
        self._data[endpoint.identifier] = {
            "pulse_min": calibration.pulse_min,
            "pulse_max": calibration.pulse_max,
            "pulse_center": calibration.pulse_center,
            "angle_min": calibration.angle_min,
            "angle_max": calibration.angle_max,
            "angle_center": calibration.angle_center,
            "speed": calibration.speed,
        }

    def get_all_calibrations(self) -> dict[int, ServoCalibration]:
        """Get stored native GPIO calibrations using the legacy int-key view.

        Returns:
            Dict mapping native GPIO pin numbers to ServoCalibration objects
        """
        calibrations: dict[int, ServoCalibration] = {}
        for endpoint_id in self._data:
            endpoint = parse_servo_endpoint(endpoint_id)
            if endpoint.kind == "gpio":
                calibrations[endpoint.legacy_pin] = self.get_calibration(endpoint)
        return calibrations

    def get_all_endpoint_calibrations(self) -> dict[str, ServoCalibration]:
        """Get all stored calibrations using explicit endpoint identifiers."""
        return {
            endpoint_id: self.get_calibration(endpoint_id)
            for endpoint_id in sorted(self._data.keys())
        }

    def get_known_endpoints(self) -> list[ServoEndpoint]:
        """Return all configured endpoints in normalized form."""
        return [parse_servo_endpoint(endpoint_id) for endpoint_id in sorted(self._data)]

    def remove_calibration(self, pin: int | str | ServoEndpoint) -> bool:
        """Remove calibration for a specific endpoint.

        Args:
            pin: GPIO pin number or explicit endpoint identifier

        Returns:
            True if removed, False if not found
        """
        endpoint = parse_servo_endpoint(pin)
        if endpoint.identifier in self._data:
            del self._data[endpoint.identifier]
            return True
        return False

    def clear(self):
        """Clear all calibrations (does not save automatically)."""
        self._data = {}

    def get_backend_config(self) -> dict[str, Any]:
        """Return backend metadata for the standalone runtime."""
        return {
            "name": str(self._backend_config.get("name", DEFAULT_BACKEND_CONFIG["name"])),
            "kwargs": dict(self._backend_config.get("kwargs", {})),
        }

    def set_backend_config(self, name: str, kwargs: dict[str, Any] | None = None) -> None:
        """Store backend metadata for standalone runtime selection."""
        self._backend_config = {
            "name": str(name),
            "kwargs": dict(kwargs or {}),
        }

    def _to_dict(self) -> dict[str, Any]:
        """Convert internal data to JSON-serializable dict.

        Returns:
            Dict with string keys (for JSON compatibility)
        """
        json_data = dict(self._data)
        json_data[BACKEND_CONFIG_KEY] = self.get_backend_config()
        return json_data

    def save_to(self, path: str | Path) -> bool:
        """Save configuration to a different file.

        Args:
            path: Target file path

        Returns:
            True if saved successfully, False on error
        """
        original = self._config_path
        self._config_path = Path(path)
        result = self.save()
        self._config_path = original
        return result

    def load_from(self, path: str | Path) -> bool:
        """Load configuration from a different file.

        Args:
            path: Source file path

        Returns:
            True if loaded successfully, False if file doesn't exist or error
        """
        original = self._config_path
        self._config_path = Path(path)
        result = self.load()
        self._config_path = original
        return result
