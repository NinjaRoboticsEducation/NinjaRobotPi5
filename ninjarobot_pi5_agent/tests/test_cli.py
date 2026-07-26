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
    assert payload[0]["name"] == "distance.read"
    assert payload[0]["risk"] == "read_only"


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
