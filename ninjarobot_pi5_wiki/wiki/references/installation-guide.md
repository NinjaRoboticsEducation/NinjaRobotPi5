---
type: Reference
title: Installation guide
description: Find the complete versioned installation guide.
status: draft
tags:
- ninjarobotpi5
generated:
  by: agent:codex
  at: '2026-09-06T22:53:22Z'
sources:
- id: src-20260912-installationguide
  resource: urn:llmwiki:source:src-20260912-installationguide
  title: InstallationGuide.md
  content_hash: sha256:63da8891e70986a964d9c1838c4fc9e54023eb617bf19deb3122a27c90eb9250
- id: src-20260907-knowledgeintegration
  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
  title: Local knowledge integration evidence
  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
semantic_review:
  version: 1
  performed_by: agent:antigravity
  performed_at: '2026-09-12T09:37:00Z'
  target_hash: sha256:ee821bbe393d19b20bb692f656d87be398b71ae297e22c0ff1ffcd7c6b860dea
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

# Installation guide

The full guide covers beginner setup, hardware initialization and calibration, startup, and troubleshooting. Hardware commands require stated operator precautions.[^src-20260912-installationguide]

Use the source identifier below to resolve the complete manual through the raw
source catalog. The outer wiki README also links directly to the current full
manual. Both READMEs link directly to full sources; updates create new versions.
Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]

[Return to project overview](/overview.md).

## Current checkpoint

The 12 September source adds Raspberry Pi OS Lite headless setup, PipeWire and
WirePlumber audio prerequisites, session lingering (`loginctl enable-linger`),
systemd audio drop-in configuration, IDE menu option 8 (Bluetooth Speaker Connection
wizard), saved TOML settings (`[audio.bluetooth]`), a standalone reconnect daemon,
and same-stream lead-in silence buffering. Software tests do not substitute for
physical hardware validation.[^src-20260912-installationguide]


[^src-20260912-installationguide]: InstallationGuide.md, source version `refinement-phase3-followup-260912`; registered source `src-20260912-installationguide`.
[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
