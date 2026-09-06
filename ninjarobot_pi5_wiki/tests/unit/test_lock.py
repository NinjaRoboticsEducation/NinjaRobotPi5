from __future__ import annotations

import pytest

from llmwiki.locks import LockError, ProjectLock


def test_only_one_writer_can_hold_the_lock(tmp_path) -> None:
    first = ProjectLock(tmp_path)
    second = ProjectLock(tmp_path)
    with first:
        with pytest.raises(LockError):
            second.acquire()
    with second:
        assert second.path.exists()
    assert not second.path.exists()
