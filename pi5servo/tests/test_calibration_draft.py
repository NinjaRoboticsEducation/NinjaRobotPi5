"""Fusion calibration drafts never persist partially configured pulse limits."""

import itertools
import json
from types import SimpleNamespace

import pytest

from pi5servo.cli.calib import CalibApp
from pi5servo.config import ConfigManager


@pytest.fixture
def session(tmp_path):
    path = tmp_path / "servo.json"
    path.write_text(
        json.dumps(
            {
                "__backend__": {"name": "fusion_hat_plus", "kwargs": {}},
                "hat_pwm0": {
                    "pulse_min": 1500,
                    "pulse_center": 1500,
                    "pulse_max": 1500,
                    "angle_min": -45,
                    "angle_max": 45,
                    "angle_center": 0,
                },
                "gpio12": {"pulse_center": 1500},
            }
        )
    )
    manager = ConfigManager(path)
    assert manager.load()
    pulses = []
    servo = SimpleNamespace(set_pulse=pulses.append, off=lambda: None, close=lambda: None)
    app = CalibApp(servo, "hat_pwm0", str(path), manager)
    app.has_blessed = False
    return app, manager, path


@pytest.mark.parametrize("order", list(itertools.permutations((-90, 0, 90))))
def test_points_can_be_staged_in_any_order_and_written_once(session, monkeypatch, order):
    app, manager, path = session
    before = path.read_bytes()
    original_save = manager.save
    calls = []

    def save():
        calls.append(True)
        return original_save()

    monkeypatch.setattr(manager, "save", save)
    bindings = app._setup_key_bindings()
    for index, target in enumerate(order):
        app.set_target(target)
        app.cur_pulse = {-90: 900, 0: 1500, 90: 2100}[target]
        bindings["KEY_ENTER" if index % 2 else " "]()
        assert app.running
        assert path.read_bytes() == before
        assert manager.get_calibration("hat_pwm0").pulse_max == 1500
    assert calls == []
    bindings["f"]()
    assert not app.running
    assert calls == [True]
    saved = json.loads(path.read_text())
    assert saved["hat_pwm0"]["pulse_min"] == 900
    assert saved["hat_pwm0"]["pulse_max"] == 2100
    assert saved["hat_pwm0"]["angle_min"] == -45
    assert saved["gpio12"] == {"pulse_center": 1500}


def test_incomplete_finish_stays_open_then_can_be_completed(session, capsys):
    app, _, path = session
    before = path.read_bytes()
    app.set_target(90)
    app.cur_pulse = 2100
    app.set_calibration()
    app.finish_calibration()
    assert app.running and path.read_bytes() == before
    assert "Cannot finish" in capsys.readouterr().out
    app.set_target(-90)
    app.cur_pulse = 900
    app.set_calibration()
    app.finish_calibration()
    assert not app.running


def test_quit_discards_draft_without_persistence(session):
    app, manager, path = session
    before = path.read_bytes()
    app.set_target(90)
    app.cur_pulse = 2100
    app.set_calibration()
    app.quit()
    assert not app.running
    assert path.read_bytes() == before
    assert manager.get_calibration("hat_pwm0").pulse_max == 1500


@pytest.mark.parametrize("failure", [False, ValueError("other endpoint invalid")])
def test_save_failure_keeps_draft_and_restores_manager(session, monkeypatch, failure):
    app, manager, path = session
    before = path.read_bytes()
    app.pulse_min, app.pulse_max = 900, 2100
    original_save = manager.save

    def fail():
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(manager, "save", fail)
    app.finish_calibration()
    assert app.running
    assert app.pulse_min == 900 and app.pulse_max == 2100
    assert path.read_bytes() == before
    assert manager.get_calibration("hat_pwm0").pulse_max == 1500
    monkeypatch.setattr(manager, "save", original_save)
    app.finish_calibration()
    assert not app.running


def test_new_channel_cancel_or_failed_save_does_not_create_entry(session, monkeypatch):
    app, manager, path = session
    app.pin = "hat_pwm1"
    app.pulse_min, app.pulse_max = 900, 2100
    before = path.read_bytes()
    monkeypatch.setattr(manager, "save", lambda: False)
    app.finish_calibration()
    assert "hat_pwm1" not in manager.get_all_endpoint_calibrations()
    assert path.read_bytes() == before


def test_original_backend_keeps_existing_point_save_behavior(session):
    app, manager, path = session
    manager.set_backend_config("auto", {})
    app.draft_mode = False
    app.set_target(90)
    app.cur_pulse = 2100
    app.set_calibration()
    assert json.loads(path.read_text())["hat_pwm0"]["pulse_max"] == 2100
    assert app.running
