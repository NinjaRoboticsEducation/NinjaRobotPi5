---
type: Concept
title: Features, MCP tools, and Agent Skills
description: Documented Agent features, external read-only tools, and reusable skills.
status: draft
tags:
- features
- mcp
- skills
- calendar
- tools
- agent
- reminders
- tasks
- memory
- speech
- command-help
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260912-ninjarobot-mcp-skill
  resource: urn:llmwiki:source:src-20260912-ninjarobot-mcp-skill
  title: NinjaRobot_MCP_Skill.md
  content_hash: sha256:a378ca8b20ecbab88c423690017a12a8a44d3f0e1e591c4538b34432777ba810
- id: src-20260912-developmentguide
  resource: urn:llmwiki:source:src-20260912-developmentguide
  title: DevelopmentGuide.md
  content_hash: sha256:9843060f7eb54f90846eb51f4dac8ab23e1a3d5dae78211a1d2dae4cd198d376
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-12T09:37:00Z'
  target_hash: sha256:4e1795c24ea92f76120423f4ef4134f0b0ba79079185965e77a81cb1c9501bb5
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against registered Phase 3 follow-up evidence; no human verification
    is claimed.
  - Checkpoint claims distinguish software tests from physical hardware acceptance
    and note pending font repair and monetary spending cap.
---

# Features, MCP tools, and Agent Skills

The development guide describes conversational and web interfaces, model
providers, behaviors, memory, device capabilities, and local audio output.
These are documented implementation areas; use current code and tests to verify
a specific feature or failure case before changing it.[^src-20260912-developmentguide]

MCP (Model Context Protocol) lets an application discover and call external tools.
The robot tutorial describes allowlisted read-only tools, bounded results,
timeouts, and untrusted external content. Its examples include Tavily search
and a read-only Google Calendar server. Agent Skills package reusable workflows;
they do not grant extra hardware permissions.[^src-20260912-ninjarobot-mcp-skill]

Development wiki skills are a separate coding-tool workflow. This local knowledge
integration does not install a robot MCP provider or change runtime interfaces.
Use the existing robot tutorial for robot extensions and the wiki maintenance
guide for developer knowledge updates.[^src-20260907-knowledgeintegration]

[MCP and skills tutorial](/references/mcp-skills-guide.md).

## Local tasks, speech, and command guidance

In existing chat, `/remind 120 Practice` creates a silent draft. `/tasks confirm ID`
explicitly schedules the reviewed time and effect. `/tasks`, cancel, and snooze
controls also appear in the browser Local tasks panel. Snooze needs fresh review.
Exact dated reminders support daily/weekly repeat, optional reviewed display
text, buzzer tones, and optional spoken reminder delivery.[^src-20260912-developmentguide]

Local speech synthesis uses English Piper by default (`en_US-lessac-medium`).
Mandarin accepts an operator-supplied ONNX model, and Japanese is not implemented.
Audio output routes through PipeWire to the configured ALSA or Bluetooth speaker sink.
IDE menu 8 provides an interactive Bluetooth setup wizard that writes `[audio.bluetooth]`
configuration to `config/ninjarobot_pi5.toml`. Same-stream lead-in silence buffering
prevents truncated speech from waking Bluetooth speakers.[^src-20260912-developmentguide]

The bundled `robot-command-help` skill uses `command_help.search` to resolve natural
language inquiries into deterministic `/help <topic>` and `/guide 1` through `/guide 5`
instructions. Web interface additions provide Bluetooth speaker status, reconnect
triggers, and command-help shortcuts. Interrupted turns cleanly cancel active audio
and repair context without repeating stale actions.[^src-20260912-ninjarobot-mcp-skill][^src-20260912-developmentguide]

Task progress requires refresh. General requests do not autonomously resume after
restart. Model calls, tool attempts, input size, requested output, and time are
bounded; this is not a currency-denominated spending cap. `/memory review`, confirm,
edit, and forget expose source/confidence and correction. Confirmed structured
preferences resist contradictory inference; arbitrary natural-language contradiction
resolution is not comprehensive.[^src-20260912-developmentguide]


[^src-20260912-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `refinement-phase3-followup-260912`; registered source `src-20260912-ninjarobot-mcp-skill`.
[^src-20260912-developmentguide]: DevelopmentGuide.md, source version `refinement-phase3-followup-260912`; registered source `src-20260912-developmentguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
