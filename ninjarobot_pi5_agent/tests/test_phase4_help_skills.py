"""Public-document confinement and v2 compatibility without services or hardware."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest
from ninjarobot_pi5_agent.command_help_tool import CommandHelpProvider
from ninjarobot_pi5_agent.models import ToolCall, ToolExecutionStatus, ToolInvocation
from ninjarobot_pi5_agent.project_help import ProjectHelpProvider, checkout_wiki, confined_read
from ninjarobot_pi5_agent.skills import SkillRepository, SkillValidationError, compatible_tools
from ninjarobot_pi5_agent.tools import CancellationToken


def fixture_help(tmp_path):
    root = tmp_path / "wiki-root"
    page = root / "wiki" / "help.md"
    page.parent.mkdir(parents=True)
    text = "# Bluetooth speaker\n\nPair a speaker on Lite. Imported text: sudo is evidence only.\n"
    page.write_text(text)
    manifest = tmp_path / "manifest.json"
    data = {
        "version": 1,
        "documents": [
            {
                "id": "public-help",
                "title": "Bluetooth help",
                "path": "wiki/help.md",
                "content_hash": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
                "source_version": "fixture",
                "page_state": "draft",
                "review_state": "synthetic",
                "sources": [],
            }
        ],
    }
    manifest.write_text(json.dumps(data))
    return ProjectHelpProvider(root, manifest=manifest), page, manifest, data


def test_help_is_bounded_cited_and_invalidation_is_content_based(tmp_path):
    provider, page, manifest, data = fixture_help(tmp_path)
    result = provider.lookup("Bluetooth")
    assert result["results"][0]["source_path"] == "wiki/help.md"
    assert result["results"][0]["page_state"] == "draft"
    assert result["executed"] is False
    before = page.stat()
    page.write_text(page.read_text() + "Altered content")
    os.utime(page, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert provider.lookup("Bluetooth")["results"] == []
    page.write_text("x" * 65537)
    assert provider.lookup("Bluetooth")["results"] == []
    data["documents"][0]["path"] = "../secret"
    manifest.write_text(json.dumps(data))
    assert provider.lookup("Bluetooth")["results"] == []


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "wiki/../secret", "wiki//help.md"])
def test_path_and_symlink_confinement(tmp_path, path):
    provider, page, manifest, data = fixture_help(tmp_path)
    with pytest.raises((ValueError, OSError)):
        confined_read(page.parent.parent, path, 65536)
    external = tmp_path / "secret"
    external.write_text("private")
    page.unlink()
    page.symlink_to(external)
    assert provider.lookup("Bluetooth")["results"] == []
    page.unlink()
    page.parent.rmdir()
    page.parent.symlink_to(tmp_path)
    with pytest.raises(OSError):
        confined_read(page.parent.parent, "wiki/secret", 65536)


def test_broken_citation_is_withheld(tmp_path):
    provider, page, manifest, data = fixture_help(tmp_path)
    page.write_text("# Bluetooth\nUnsupported claim [^src-missing]")
    data["documents"][0]["content_hash"] = "sha256:" + hashlib.sha256(page.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(data))
    assert provider.lookup("Bluetooth")["results"] == []


def test_real_public_checkpoint_and_missing_checkout():
    provider = ProjectHelpProvider(checkout_wiki())
    result = provider.lookup("Bluetooth")
    assert result["results"]
    assert "2026-09-12" in result["warnings"][0]
    assert all(item["page_state"] == "draft" for item in result["results"])
    assert ProjectHelpProvider().lookup("Bluetooth")["results"] == []


def test_cancelled_help_never_reads_files(tmp_path, monkeypatch):
    async def exercise():
        provider, *_ = fixture_help(tmp_path)
        monkeypatch.setattr(provider, "lookup", lambda *args, **kw: pytest.fail("must not read"))
        token = CancellationToken()
        token.cancel()
        invocation = ToolInvocation(
            session_id="help",
            call=ToolCall(
                call_id="help-call", name="project_help.search", arguments={"query": "speaker"}
            ),
        )
        result = await provider.call(invocation, token)
        assert result.status is ToolExecutionStatus.CANCELLED

    asyncio.run(exercise())


def test_v2_required_optional_future_versions_and_offline_install(tmp_path):
    async def exercise():
        repository = SkillRepository(tmp_path / "skills")
        help_skill = repository.get("project-help", available_tools={"command_help.search"})
        definitions = await CommandHelpProvider().list_tools()
        assert compatible_tools(help_skill, definitions) == {"command_help.search"}
        with pytest.raises(SkillValidationError, match="unavailable"):
            compatible_tools(help_skill, ())
        changed = help_skill.manifest.model_copy(
            update={
                "requirements": help_skill.manifest.requirements.model_copy(
                    update={"required_capabilities": {"command_help.search": "9.0.0"}}
                )
            }
        )
        with pytest.raises(SkillValidationError, match="9.0.0"):
            compatible_tools(help_skill.model_copy(update={"manifest": changed}), definitions)
        with pytest.raises(SkillValidationError, match="current service"):
            repository.set_enabled("project-help", enabled=True)
        repository.set_enabled("project-help", enabled=True, definitions=definitions)
        for directory in sorted(Path("docs/skill-templates").iterdir()):
            if not directory.is_dir():
                continue
            template = repository.load_path(directory)
            assert template.manifest.schema_version == 2
            with pytest.raises(SkillValidationError, match="unavailable"):
                compatible_tools(template, definitions)
            with pytest.raises(SkillValidationError, match="current service"):
                repository.install(directory)
            for example in template.examples.examples:
                preview = repository.simulate(template, example.input)
                assert preview["simulation_only"]
                if example.input["prompt"] != "success":
                    assert example.expected_tools == ()
        # Future versions never fall back to v1.
        package = tmp_path / "project-help"
        package.mkdir()
        for path in help_skill.path.iterdir():
            if path.is_file():
                (package / path.name).write_bytes(path.read_bytes())
        manifest = json.loads((package / "skill.json").read_text())
        manifest["schema_version"] = 3
        (package / "skill.json").write_text(json.dumps(manifest))
        with pytest.raises(SkillValidationError, match="unsupported"):
            repository.load_path(package)

    asyncio.run(exercise())


@pytest.mark.parametrize("scenario", ["success", "missing_optional", "denied", "cancel"])
def test_v2_runtime_tool_sequence_and_forbidden_calls(tmp_path, scenario):
    from ninjarobot_pi5_agent.testing import FakeProvider

    from ninjarobot_pi5_agent import (
        AgentLoop,
        ConversationStore,
        FinishReason,
        ModelTurn,
        MotionArmManager,
        PolicyEngine,
        RecoveryPolicy,
        ToolRegistry,
    )

    async def exercise():
        calls = []
        token = CancellationToken()

        class Help(CommandHelpProvider):
            async def call(self, invocation, cancellation):
                calls.append(invocation.call.name)
                return await super().call(invocation, cancellation)

        class Public(ProjectHelpProvider):
            async def call(self, invocation, cancellation):
                calls.append(invocation.call.name)
                return await super().call(invocation, cancellation)

        class Model(FakeProvider):
            async def generate(self, request):
                self.requests.append(request)
                if len(self.requests) == 1:
                    if scenario == "cancel":
                        token.cancel()
                    name = (
                        "robot.servo.move"
                        if scenario == "denied"
                        else "command_help.search"
                        if scenario == "missing_optional"
                        else "project_help.search"
                    )
                    return ModelTurn(
                        request_id=request.request_id,
                        finish_reason=FinishReason.TOOL_CALLS,
                        tool_calls=(
                            ToolCall(call_id="chosen", name=name, arguments={"query": "speech"}),
                        ),
                    )
                return ModelTurn(
                    request_id=request.request_id,
                    text="Bounded answer",
                    finish_reason=FinishReason.STOP,
                )

        providers = [Help()] if scenario == "missing_optional" else [Help(), Public()]
        tools = ToolRegistry(providers)
        store = ConversationStore(tmp_path / "agent.sqlite3")
        await store.start()
        await tools.start()
        model = Model(())
        loop = AgentLoop(
            provider=model,
            tools=tools,
            policy=PolicyEngine(MotionArmManager()),
            recovery=RecoveryPolicy(),
            store=store,
        )
        skill = SkillRepository(tmp_path / "skills").get("project-help")
        try:
            if scenario == "cancel":
                with pytest.raises(asyncio.CancelledError):
                    await loop.chat(
                        session_id="test",
                        text="Explain this feature",
                        skill=skill,
                        cancellation=token,
                    )
                assert calls == []
            else:
                await loop.chat(session_id="test", text="Explain this feature", skill=skill)
                expected = {
                    "success": ["project_help.search"],
                    "missing_optional": ["command_help.search"],
                    "denied": [],
                }
                assert calls == expected[scenario]
            assert "robot.servo.move" not in calls
        finally:
            await tools.close()
            await store.close()

    asyncio.run(exercise())
