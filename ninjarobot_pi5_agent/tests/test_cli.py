from __future__ import annotations

import json
from pathlib import Path

from ninjarobot_pi5_agent.cli import main

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "ninjarobot_pi5.toml.example"


def test_cli_validates_configuration(capsys) -> None:
    result = main(["config", "validate", "--config", str(EXAMPLE)])

    output = capsys.readouterr().out
    assert result == 0
    assert "buzzer=GPIO27" in output
    assert "display=DC4/RST5/BL6" in output


def test_cli_prints_contract_schemas(capsys) -> None:
    result = main(["contracts", "schema"])

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert "action_request" in payload
    assert payload["action_request"]["additionalProperties"] is False


def test_cli_dry_run_is_clearly_simulated(capsys) -> None:
    result = main(["dry-run", "--json", '{"message": "hello"}'])

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["status"] == "succeeded"
    assert payload["data"]["simulated"] is True


def test_cli_rejects_non_object_json(capsys) -> None:
    result = main(["dry-run", "--json", "[]"])

    captured = capsys.readouterr()
    assert result == 2
    assert "must contain a JSON object" in captured.err


def test_phase_two_capabilities_are_hardware_free(capsys) -> None:
    assert main(["capabilities"]) == 0
    payload = json.loads(capsys.readouterr().out)
    capabilities = {item["name"]: item for item in payload}
    assert capabilities["distance.read"]["risk"] == "read_only"
    assert capabilities["buzzer.play_tone"]["risk"] == "low"
    assert capabilities["buzzer.stop"]["risk"] == "emergency"
    assert capabilities["display.show_text"]["risk"] == "low"
    assert capabilities["display.clear"]["resources"] == [
        "display",
        "spi0",
        "gpio4",
        "gpio5",
        "gpio6",
    ]
    assert capabilities["servo.status"]["risk"] == "read_only"
    assert capabilities["servo.move"]["risk"] == "motion"
    assert capabilities["servo.move"]["confirmation_required"] is True
    assert capabilities["servo.stop"]["risk"] == "emergency"
    assert capabilities["camera.status"]["risk"] == "read_only"
    assert capabilities["camera.capture"]["risk"] == "privacy"
    assert capabilities["camera.capture"]["resources"] == ["camera"]
    assert capabilities["camera.capture"]["confirmation_required"] is True


def test_simulated_distance_health_and_read_are_persisted(tmp_path, capsys) -> None:
    ledger = tmp_path / "actions.sqlite3"
    assert main(["health", "--ledger", str(ledger)]) == 0
    health = json.loads(capsys.readouterr().out)
    assert health["status"] == "ready"

    command = [
        "distance",
        "read",
        "--ledger",
        str(ledger),
        "--action-id",
        "manual-distance-1",
        "--idempotency-key",
        "manual-distance-key-1",
    ]
    assert main(command) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "succeeded"
    assert result["data"]["distance_mm"] == 250
    assert set(result) == {
        "action_id",
        "status",
        "data",
        "error",
        "started_at",
        "finished_at",
        "retry_safety",
    }

    assert main(command) == 0
    repeated = json.loads(capsys.readouterr().out)
    assert repeated == result

    assert (
        main(
            [
                "actions",
                "show",
                "--ledger",
                str(ledger),
                "--action-id",
                "manual-distance-1",
            ]
        )
        == 0
    )
    record = json.loads(capsys.readouterr().out)
    assert record["result"] == result


def test_distance_cli_rejects_unsafe_bounds(tmp_path, capsys) -> None:
    assert (
        main(
            [
                "distance",
                "read",
                "--ledger",
                str(tmp_path / "bounds.sqlite3"),
                "--count",
                "101",
            ]
        )
        == 2
    )
    assert "--count must be between 1 and 100" in capsys.readouterr().err


def test_simulated_buzzer_health_play_and_stop(tmp_path, capsys) -> None:
    ledger = tmp_path / "buzzer.sqlite3"
    assert main(["buzzer", "health", "--ledger", str(ledger)]) == 0
    health = json.loads(capsys.readouterr().out)
    assert health["status"] == "ready"

    assert (
        main(
            [
                "buzzer",
                "play",
                "--ledger",
                str(ledger),
                "--frequency",
                "440",
                "--duration",
                "0.05",
                "--volume",
                "16",
                "--action-id",
                "buzzer-test-1",
                "--idempotency-key",
                "buzzer-key-1",
            ]
        )
        == 0
    )
    played = json.loads(capsys.readouterr().out)
    assert played["status"] == "succeeded"
    assert played["retry_safety"] == "unsafe"
    assert played["data"] == {
        "frequency_hz": 440,
        "duration_seconds": 0.05,
        "volume": 16,
        "interrupted": False,
        "simulated": True,
    }

    assert (
        main(
            [
                "buzzer",
                "stop",
                "--ledger",
                str(ledger),
                "--action-id",
                "buzzer-stop-1",
                "--idempotency-key",
                "buzzer-stop-key-1",
            ]
        )
        == 0
    )
    stopped = json.loads(capsys.readouterr().out)
    assert stopped["status"] == "succeeded"
    assert stopped["data"] == {"stopped": True, "simulated": True}


def test_buzzer_cli_rejects_out_of_bounds_tone(tmp_path, capsys) -> None:
    result = main(
        [
            "buzzer",
            "play",
            "--ledger",
            str(tmp_path / "invalid-buzzer.sqlite3"),
            "--frequency",
            "440",
            "--duration",
            "10",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert result == 1
    assert payload["status"] == "failed"
    assert payload["error"]["code"] == "INVALID_CAPABILITY_ARGUMENTS"


def test_simulated_camera_health_status_capture_and_retention(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    ledger = tmp_path / "camera.sqlite3"
    assert main(["camera", "health", "--ledger", str(ledger)]) == 0
    health = json.loads(capsys.readouterr().out)
    assert health["status"] == "ready"

    assert main(["camera", "status", "--ledger", str(ledger)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "succeeded"
    assert status["data"]["retain_media_by_default"] is False
    assert status["data"]["simulated"] is True

    assert main(["camera", "capture", "--ledger", str(ledger)]) == 0
    transient = json.loads(capsys.readouterr().out)
    assert transient["status"] == "succeeded"
    assert transient["retry_safety"] == "unsafe"
    assert transient["data"]["retained"] is False
    assert transient["data"]["path"] is None

    assert (
        main(
            [
                "camera",
                "capture",
                "--ledger",
                str(ledger),
                "--retain",
                "--filename",
                "phase34-simulated.jpg",
            ]
        )
        == 0
    )
    retained = json.loads(capsys.readouterr().out)
    assert retained["data"]["retained"] is True
    retained_path = Path(retained["data"]["path"])
    assert retained_path == tmp_path / "data" / "simulated-camera" / "phase34-simulated.jpg"
    assert retained_path.is_file()


def test_real_camera_capture_requires_explicit_confirmation(tmp_path, capsys) -> None:
    result = main(
        [
            "camera",
            "capture",
            "--real",
            "--config",
            str(EXAMPLE),
            "--ledger",
            str(tmp_path / "camera.sqlite3"),
        ]
    )

    assert result == 2
    assert "real camera capture requires --confirm-camera" in capsys.readouterr().err


def test_simulated_display_health_text_clear_and_brightness(tmp_path, capsys) -> None:
    ledger = tmp_path / "display.sqlite3"
    assert main(["display", "health", "--ledger", str(ledger)]) == 0
    health = json.loads(capsys.readouterr().out)
    assert health["status"] == "ready"

    assert (
        main(
            [
                "display",
                "text",
                "--ledger",
                str(ledger),
                "--text",
                "NinjaRobot",
                "--font-size",
                "24",
                "--foreground",
                "#00ff00",
                "--action-id",
                "display-text-1",
                "--idempotency-key",
                "display-text-key-1",
            ]
        )
        == 0
    )
    shown = json.loads(capsys.readouterr().out)
    assert shown["status"] == "succeeded"
    assert shown["retry_safety"] == "safe"
    assert shown["data"]["simulated"] is True
    assert shown["data"]["width"] == 320
    assert shown["data"]["height"] == 240
    assert shown["data"]["foreground"] == "#00FF00"

    assert (
        main(
            [
                "display",
                "brightness",
                "--ledger",
                str(ledger),
                "--percent",
                "25",
            ]
        )
        == 0
    )
    brightness = json.loads(capsys.readouterr().out)
    assert brightness["data"] == {"brightness": 25, "simulated": True}

    assert (
        main(
            [
                "display",
                "clear",
                "--ledger",
                str(ledger),
                "--color",
                "#102030",
            ]
        )
        == 0
    )
    cleared = json.loads(capsys.readouterr().out)
    assert cleared["data"] == {
        "cleared": True,
        "color": "#102030",
        "simulated": True,
    }


def test_display_cli_rejects_invalid_color_and_hold(tmp_path, capsys) -> None:
    ledger = tmp_path / "invalid-display.sqlite3"
    result = main(
        [
            "display",
            "text",
            "--ledger",
            str(ledger),
            "--text",
            "test",
            "--foreground",
            "white",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert result == 1
    assert payload["error"]["code"] == "INVALID_CAPABILITY_ARGUMENTS"

    assert (
        main(
            [
                "display",
                "clear",
                "--ledger",
                str(ledger),
                "--hold",
                "31",
            ]
        )
        == 2
    )
    assert "--hold must be between 0 and 30 seconds" in capsys.readouterr().err


def test_simulated_servo_health_status_move_and_stop(tmp_path, capsys) -> None:
    ledger = tmp_path / "servo.sqlite3"
    assert main(["servo", "health", "--ledger", str(ledger)]) == 0
    health = json.loads(capsys.readouterr().out)
    assert health["status"] == "ready"

    assert (
        main(
            [
                "servo",
                "status",
                "--ledger",
                str(ledger),
                "--action-id",
                "servo-status-1",
                "--idempotency-key",
                "servo-status-key-1",
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "succeeded"
    assert status["data"]["simulated"] is True
    assert status["data"]["motion_enabled"] is True
    assert status["data"]["group_motion_enabled"] is False
    assert all(status["data"]["calibrated"].values())

    assert (
        main(
            [
                "servo",
                "move",
                "--ledger",
                str(ledger),
                "--endpoint",
                "gpio12",
                "--angle",
                "10",
                "--speed",
                "S",
                "--action-id",
                "servo-move-1",
                "--idempotency-key",
                "servo-move-key-1",
            ]
        )
        == 0
    )
    moved = json.loads(capsys.readouterr().out)
    assert moved["status"] == "succeeded"
    assert moved["retry_safety"] == "unsafe"
    assert moved["data"] == {
        "endpoint": "gpio12",
        "target_angle": 10.0,
        "speed_mode": "S",
        "interrupted": False,
        "simulated": True,
    }

    assert main(["servo", "stop", "--ledger", str(ledger)]) == 0
    stopped = json.loads(capsys.readouterr().out)
    assert stopped["status"] == "succeeded"
    assert stopped["data"] == {
        "stopped": True,
        "driver_available": True,
        "simulated": True,
    }


def test_real_servo_move_requires_cli_confirmation_before_hardware(
    tmp_path,
    capsys,
) -> None:
    result = main(
        [
            "servo",
            "move",
            "--real",
            "--ledger",
            str(tmp_path / "real-servo.sqlite3"),
            "--endpoint",
            "gpio12",
            "--angle",
            "0",
        ]
    )
    assert result == 2
    assert "requires --confirm-motion" in capsys.readouterr().err


def test_servo_cli_rejects_unsafe_hold_bound(tmp_path, capsys) -> None:
    result = main(
        [
            "servo",
            "move",
            "--ledger",
            str(tmp_path / "servo-hold.sqlite3"),
            "--endpoint",
            "gpio12",
            "--angle",
            "0",
            "--hold",
            "6",
        ]
    )
    assert result == 2
    assert "--hold must be between 0 and 5 seconds" in capsys.readouterr().err
