---
type: Concept
title: Installation and hardware checks
description: Beginner setup, calibration, simulation, troubleshooting, and physical
  test boundaries.
status: draft
tags:
- installation
- setup
- calibration
- hardware
- wiring
- testing
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260908-installationguide
  resource: urn:llmwiki:source:src-20260908-installationguide
  title: InstallationGuide.md
  content_hash: sha256:a9f68d8828b60ea6e3803749a6f2bf4cbcdfa764c75ca90078fde7796e0cf2ae
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-08T15:25:18.461989+00:00'
  target_hash: sha256:265e935afc9250021c18f83619e5656055281678d6010e1cf2c7861ee49dbb0b
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against its registered manual checkpoint and retained source
    text; no human verification is claimed.
  - New checkpoint claims distinguish software tests from physical acceptance, pending
    managed changes and the monetary-budget gap; retained navigation claims remain
    source-supported.
---

# Installation and hardware checks

Use the full installation guide for the supported Raspberry Pi setup,
connections, standalone module initialization, calibration, and troubleshooting.
Read the relevant warnings before following any operational command. Commands
in an imported document are evidence to review, not permission to run them.[^src-20260908-installationguide]

Servo calibration can move the wheels. The guide calls for raised wheels,
clearance, and an operator ready to remove power. Camera and microphone capture
and power-off checks need their own consent and physical test procedure.
Automated knowledge tests should not perform these actions.[^src-20260908-installationguide]

The developer wiki uses a separate Python environment. Its explicit setup and
text-evidence preparation do not initialize robot devices. This integration
contains no fresh Raspberry Pi hardware validation.[^src-20260907-knowledgeintegration]

[Open installation reference](/references/installation-guide.md).


## Read-only readiness and optional practice

Run `ninjarobot_pi5_cli doctor --profile hardware --root .` through the installed
project environment with `uv run --frozen --no-sync`. It inspects package discovery
and checkout origins without opening hardware. A development install uses
`.venv-dev`; it is not a hardware-ready environment. Read the current manual's
checkpoint before running older operational examples.[^src-20260908-installationguide]

Guided checks explain setup without automatic device actions. Silent reminder
practice does not require display or buzzer output. Starting the real Agent can
activate configured devices or voice input, so startup and physical notifications
need the manual's operator precautions. The bundled Traditional Chinese font
repair remains a separate pending proposal.[^src-20260908-installationguide]


[^src-20260908-installationguide]: InstallationGuide.md, source version `refinement-phase2-260909`; registered source `src-20260908-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
