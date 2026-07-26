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
