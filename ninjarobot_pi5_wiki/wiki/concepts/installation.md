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
- id: src-20260906-installationguide
  resource: urn:llmwiki:source:src-20260906-installationguide
  title: InstallationGuide.md
  content_hash: sha256:53f80c60feb139f0de547613bd14b8fcd87a2678ba5bf7dc75b1b2bccb1dc1c4
- id: src-20260906-knowledgeintegration
  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
semantic_review:
  version: 1
  performed_by: agent:codex
  performed_at: '2026-09-06T22:54:06Z'
  target_hash: sha256:c89f536e16da0db4909428c180953ffc515f1af207c35041af7a5e8eb9d24ca1
  result: passed
  checks:
    source_support: passed
    contradictions: passed
    limitations: passed
    claim_strength: passed
    visual_evidence: not_applicable
  notes:
  - Reviewed this page against its listed manual sections and integration evidence.
  - Claims describe documented contracts and knowledge workflow; current hardware
    operation and interactive editor activation are not certified.
---

# Installation and hardware checks

Use the full installation guide for the supported Raspberry Pi setup,
connections, standalone module initialization, calibration, and troubleshooting.
Read the relevant warnings before following any operational command. Commands
in an imported document are evidence to review, not permission to run them.[^src-20260906-installationguide]

Servo calibration can move the wheels. The guide calls for raised wheels,
clearance, and an operator ready to remove power. Camera and microphone capture
and power-off checks need their own consent and physical test procedure.
Automated knowledge tests should not perform these actions.[^src-20260906-installationguide]

The developer wiki uses a separate Python environment. Its explicit setup and
text-evidence preparation do not initialize robot devices. This integration
contains no fresh Raspberry Pi hardware validation.[^src-20260906-knowledgeintegration]

[Open installation reference](/references/installation-guide.md).


[^src-20260906-installationguide]: InstallationGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-installationguide`.
[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
