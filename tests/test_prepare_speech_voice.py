"""Voice installation tests use fake download data, never network or audio."""

import hashlib
import io

import pytest

from scripts import prepare_speech_voice as setup


class Response(io.BytesIO):
    def geturl(self):
        return "https://example.com/voice"


def test_preview_is_read_only_and_offline(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("network access in preview")

    monkeypatch.setattr(setup.urllib.request, "urlopen", forbidden)
    destination = tmp_path / "voices"
    setup.prepare(destination)
    assert not destination.exists()


@pytest.mark.parametrize("corrupt", [False, True])
def test_download_hash_cleanup_and_repeatability(tmp_path, monkeypatch, corrupt):
    payload = b"a voice"
    monkeypatch.setattr(
        setup, "FILES", {"test.onnx": (len(payload), hashlib.sha256(payload).hexdigest())}
    )
    calls = []

    def download(*args, **kwargs):
        calls.append(args)
        return Response(b"corrupt" if corrupt else payload)

    monkeypatch.setattr(setup.urllib.request, "urlopen", download)
    if corrupt:
        with pytest.raises(ValueError, match="verification"):
            setup.prepare(tmp_path, apply=True)
        assert list(tmp_path.iterdir()) == []
    else:
        setup.prepare(tmp_path, apply=True)
        setup.prepare(tmp_path, apply=True)
        assert len(calls) == 1
        assert (tmp_path / "test.onnx").read_bytes() == payload
        (tmp_path / "test.onnx").write_bytes(b"my existing model")
        with pytest.raises(ValueError, match="Preserving"):
            setup.prepare(tmp_path, apply=True)
        assert (tmp_path / "test.onnx").read_bytes() == b"my existing model"
