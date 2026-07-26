from __future__ import annotations

import asyncio

import pytest
from ninjarobot_pi5_agent.testing import FakeProvider

from ninjarobot_pi5_agent import FinishReason, ModelTurn, ProviderHealthStatus

from .test_models import request


def test_fake_provider_is_scripted_and_idempotently_closable() -> None:
    provider = FakeProvider(
        [ModelTurn(request_id="request-1", text="Done", finish_reason=FinishReason.STOP)]
    )

    turn = asyncio.run(provider.generate(request()))
    health = asyncio.run(provider.health())
    asyncio.run(provider.close())
    asyncio.run(provider.close())

    assert turn.text == "Done"
    assert health.status is ProviderHealthStatus.READY
    assert provider.capabilities.native_tools is True
    assert len(provider.requests) == 1


def test_fake_provider_fails_when_script_is_exhausted_or_closed() -> None:
    provider = FakeProvider([])
    with pytest.raises(RuntimeError, match="no scripted turns"):
        asyncio.run(provider.generate(request()))

    asyncio.run(provider.close())
    with pytest.raises(RuntimeError, match="closed"):
        asyncio.run(provider.health())
