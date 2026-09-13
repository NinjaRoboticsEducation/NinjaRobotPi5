"""Audit diagnostic: synthetic data only; run from the checkout root.

Reports current behavior, including defects; exit zero is not feature acceptance.
Uses the repository test fixture, never a live Agent, hardware or Google account.
"""

# ruff: noqa: E402
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "ninjarobot_pi5_agent/tests"))
from ninjarobot_pi5_agent.models import (
    FinishReason,
    ModelTurn,
    ToolCall,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from ninjarobot_pi5_agent.testing import FakeProvider
from test_information_controls import runtime_for


class Scripted(FakeProvider):
    async def generate(self, request):
        self.requests.append(request)
        if len(self.requests) == 1:
            return ModelTurn(
                request_id=request.request_id,
                finish_reason=FinishReason.TOOL_CALLS,
                tool_calls=(
                    ToolCall(
                        call_id="audit-search",
                        name="research.search",
                        arguments={"queries": ["synthetic audit"]},
                    ),
                ),
            )
        return ModelTurn(
            request_id=request.request_id,
            finish_reason=FinishReason.STOP,
            text="This unsupported claim is proven [S999].",
        )


async def run(path):
    r = await runtime_for(path)
    try:

        async def search(session, query, cancel):
            return ToolExecutionResult(
                call_id="audit-source",
                tool_name="tavily.search",
                status=ToolExecutionStatus.SUCCEEDED,
                data={
                    "external_untrusted_content": {
                        "structuredContent": {
                            "results": [
                                {
                                    "url": "https://example.org/audit",
                                    "title": "Synthetic source",
                                    "content": "This is a synthetic source excerpt.",
                                }
                            ]
                        }
                    }
                },
            )

        r.information.research.search = search
        r.loop._provider = Scripted(())
        reply = await r.loop.chat(
            session_id="research-audit", text="Research a synthetic public example."
        )
        print("tool_calls:", reply.tool_calls)
        print("final_reply:", reply.text)
    finally:
        await r.close()


with tempfile.TemporaryDirectory(prefix="ninja-audit-research-") as d:
    asyncio.run(run(Path(d)))
