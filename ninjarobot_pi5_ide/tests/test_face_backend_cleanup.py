"""Exercise the authorized driver cleanup with no camera or recognition model."""

import pytest
from pi5camera.core import recognition
from pi5camera.errors import RecognitionError
from pi5camera.models import EncodedFace, FaceBoundingBox


@pytest.mark.parametrize(
    "failure", ["none", "missing_image", "capture", "detection", "recognition", "index", "storage"]
)
def test_backend_closes_once_after_success_or_failure(tmp_path, monkeypatch, failure):
    closed = []

    class Backend:
        def detect_and_encode(self, path):
            if failure == "detection":
                raise RuntimeError("injected detection failure")
            if failure == "recognition":
                raise RecognitionError("injected recognition failure")
            if failure == "storage":
                return [
                    EncodedFace(
                        bounding_box=FaceBoundingBox(top=0, right=1, bottom=1, left=0),
                        encoding=[0.1],
                    )
                ]
            return []

        def close(self):
            closed.append(True)

    class Index:
        def __init__(self, config):
            pass

        def load_known_entries(self):
            if failure == "index":
                raise RuntimeError("injected index failure")
            return []

    class Pending:
        def __init__(self, config):
            pass

        def save_pending_recognition(self, **kwargs):
            raise RuntimeError("injected storage failure")

    def capture(*args, **kwargs):
        assert failure == "capture", "unexpected capture attempt"
        raise RuntimeError("injected capture failure")

    monkeypatch.setattr(recognition, "build_recognition_backend", lambda config: Backend())
    monkeypatch.setattr(recognition, "FaceIndex", Index)
    monkeypatch.setattr(recognition, "PendingRecordManager", Pending)
    monkeypatch.setattr(recognition, "capture_photo", capture)
    picture = tmp_path / "fixture.jpg"
    if failure != "missing_image":
        picture.write_bytes(b"fake image, never decoded")
    if failure == "none":
        assert recognition.recognize_faces({}, image_path=picture)["face_count"] == 0
    else:
        with pytest.raises((RecognitionError, RuntimeError)):
            recognition.recognize_faces({}, image_path=None if failure == "capture" else picture)
    assert closed == [True]


def test_repeated_calls_release_each_backend(tmp_path, monkeypatch):
    instances = []

    class Backend:
        def __init__(self):
            self.closed = 0
            instances.append(self)

        def detect_and_encode(self, path):
            return []

        def close(self):
            self.closed += 1

    class Index:
        def __init__(self, config):
            pass

        def load_known_entries(self):
            return []

    monkeypatch.setattr(recognition, "build_recognition_backend", lambda config: Backend())
    monkeypatch.setattr(recognition, "FaceIndex", Index)
    picture = tmp_path / "fixture.jpg"
    picture.write_bytes(b"fake image, never decoded")
    for _ in range(5):
        assert recognition.recognize_faces({}, image_path=picture)["face_count"] == 0
        assert all(item.closed == 1 for item in instances)
    assert len(instances) == 5
