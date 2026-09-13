from __future__ import annotations

import asyncio
import threading

import pytest
from ninjarobot_pi5_ide.behavior_models import FaceOperation
from ninjarobot_pi5_ide.distance import VL53L0XDistanceAdapter
from ninjarobot_pi5_ide.errors import IDEError
from ninjarobot_pi5_ide.expression_variants import vary_face
from ninjarobot_pi5_ide.models import ResourceHealth


def test_optional_variants_preserve_meaning_and_exclude_state_faces() -> None:
    for face in ("happy", "idle", "warning", "error", "camera", "speaking", "greeting"):
        source = FaceOperation(kind="face", expression=face)
        for token in map(str, range(32)):
            assert vary_face(source, enabled=False, request_id=token) == source
            actual = vary_face(source, enabled=True, request_id=token)
            assert actual == vary_face(source, enabled=True, request_id=token)
            assert actual.expression == source.expression
            assert actual.hold_seconds == source.hold_seconds
            if face != "happy":
                assert actual == source
    source = FaceOperation(kind="face", expression="happy", accent="#FF0000")
    assert vary_face(source, enabled=True, request_id="1") == source


def test_cancelled_sensor_read_keeps_ownership_until_explicit_recovery() -> None:
    async def exercise() -> None:
        entered = threading.Event()
        release = threading.Event()
        reads = 0
        closes = 0

        class Sensor:
            def get_data(self):
                nonlocal reads
                reads += 1
                entered.set()
                assert release.wait(5)
                return dict(distance_mm=100, raw_value=100, is_valid=True, timestamp=1.0)

            def health_check(self):
                assert not entered.is_set() or release.is_set()
                return True

            def close(self):
                nonlocal closes
                assert release.is_set()
                closes += 1

        adapter = VL53L0XDistanceAdapter(sensor_factory=lambda *_: Sensor())
        await adapter.start()
        work = asyncio.create_task(adapter.execute({}))
        try:
            while not entered.is_set():
                await asyncio.sleep(0.001)
            work.cancel()
            with pytest.raises(asyncio.CancelledError):
                await work
            assert await adapter.health() is ResourceHealth.UNAVAILABLE
            for call in (adapter.execute({}), adapter.start(), adapter.suspend(), adapter.close()):
                with pytest.raises(IDEError):
                    await call
            assert reads == 1 and closes == 0
        finally:
            release.set()
            while adapter._busy:
                await asyncio.sleep(0.001)
        with pytest.raises(IDEError):
            await adapter.execute({})
        assert await adapter.health() is ResourceHealth.UNAVAILABLE
        await adapter.start(recover=True)
        assert await adapter.health() is ResourceHealth.READY
        assert (await adapter.execute({}))["distance_mm"] == 100
        await adapter.close()
        assert closes == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("stamp", [float("nan"), float("inf"), -float("inf"), True])
def test_nonfinite_sensor_timestamp_rejected(stamp) -> None:
    adapter = VL53L0XDistanceAdapter()
    with pytest.raises(IDEError):
        adapter._validate_reading(
            dict(distance_mm=100, raw_value=100, is_valid=True, timestamp=stamp)
        )


def test_real_bundled_palettes_have_optional_variations(tmp_path):
    from ninjarobot_pi5_ide.behavior_assets import BehaviorAssetRepository

    assets = BehaviorAssetRepository(tmp_path / "assets")
    for name in ("happy", "shy", "laughing", "exciting"):
        original = assets.load(name)
        source = next(
            op
            for stage in original.stages
            for op in stage.operations
            if isinstance(op, FaceOperation)
        )
        changed = [vary_face(source, enabled=True, request_id=str(i)) for i in range(32)]
        assert any(variant != source for variant in changed)
        assert all(variant.expression == source.expression for variant in changed)
        assert assets.load(name) == original
