# Initial project knowledge: page diff for approval

This is the exact proposed initial page diff. No live knowledge page has been
applied yet. Sources are registered; robot files are unchanged.

```diff
Plan ninjarobot-initial-knowledge-260907: Create the initial cited NinjaRobotPi5 project knowledge pages from five registered public sources.
Risk: medium

## write wiki/overview.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/overview.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/overview.md
@@ -1,13 +1,49 @@
 ---
 type: Concept
-title: Wiki Overview
-description: A starting point that will summarize the knowledge in this wiki.
+title: NinjaRobotPi5 project overview
+description: Start here for architecture, setup, features, development history, and
+  current evidence.
 status: draft
+tags:
+- ninjarobotpi5
 generated:
-  by: llmwiki-template/0.1
-  at: 2026-08-22T00:00:00Z
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  title: Local knowledge integration evidence
+  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+- id: src-20260906-developmentguide
+  resource: urn:llmwiki:source:src-20260906-developmentguide
+  title: DevelopmentGuide.md
+  content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
 ---
 
-# Wiki Overview
+# NinjaRobotPi5 project overview
 
-This wiki is empty. Ingest the first source to begin building its overview.
+NinjaRobotPi5 documents an Agent layer for user/model interaction, an IDE layer
+for coordinating devices, and managed Pi5 libraries for individual devices.
+The development guide describes their permitted ownership boundary.[^src-20260906-developmentguide]
+
+The local wiki is the primary developer knowledge collection. Full manuals are
+versioned under raw source folders; outer README links and the project knowledge
+map identify the current versions. Read source records and limitations, then
+compare important claims with the current checkout before coding.[^src-20260906-knowledgeintegration]
+
+## Browse project knowledge
+
+- [Architecture and hardware ownership](concepts/architecture.md)
+- [Development and documentation workflow](concepts/development-workflow.md)
+- [Installation and hardware checks](concepts/installation.md)
+- [Features, MCP tools, and Agent Skills](concepts/features-and-tools.md)
+- [Development history](concepts/development-history.md)
+- [Known knowledge limitations](analyses/knowledge-limitations.md)
+- [Installation manual](references/installation-guide.md)
+- [Development manual](references/development-guide.md)
+- [Development log](references/development-log.md)
+- [MCP and skills tutorial](references/mcp-skills-guide.md)
+
+
+[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.

## write wiki/references/installation-guide.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/installation-guide.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/installation-guide.md
@@ -0,0 +1,34 @@
+---
+type: Reference
+title: Installation guide
+description: Find the complete versioned installation guide.
+status: draft
+tags:
+- ninjarobotpi5
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-installationguide
+  resource: urn:llmwiki:source:src-20260906-installationguide
+  title: InstallationGuide.md
+  content_hash: sha256:53f80c60feb139f0de547613bd14b8fcd87a2678ba5bf7dc75b1b2bccb1dc1c4
+- id: src-20260906-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  title: Local knowledge integration evidence
+  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+---
+
+# Installation guide
+
+The full guide covers beginner setup, hardware initialization and calibration, startup, and troubleshooting. Hardware commands require the stated operator precautions.[^src-20260906-installationguide]
+
+Use the source identifier below to resolve the complete manual through the raw
+source catalog. The outer wiki README also links directly to the current full
+manual. Root filenames are navigation pages; source updates create new versions.
+Read the relevant full section before acting on an abbreviated explanation.[^src-20260906-knowledgeintegration]
+
+[Return to project overview](/overview.md).
+
+[^src-20260906-installationguide]: InstallationGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-installationguide`.
+[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.

## write wiki/references/development-guide.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/development-guide.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/development-guide.md
@@ -0,0 +1,34 @@
+---
+type: Reference
+title: Development guide
+description: Find the complete versioned development guide.
+status: draft
+tags:
+- ninjarobotpi5
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-developmentguide
+  resource: urn:llmwiki:source:src-20260906-developmentguide
+  title: DevelopmentGuide.md
+  content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
+- id: src-20260906-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  title: Local knowledge integration evidence
+  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+---
+
+# Development guide
+
+The full guide describes architecture, managed drivers, configuration, safety, the behavior system, external tools, memory, web access, and development checks.[^src-20260906-developmentguide]
+
+Use the source identifier below to resolve the complete manual through the raw
+source catalog. The outer wiki README also links directly to the current full
+manual. Root filenames are navigation pages; source updates create new versions.
+Read the relevant full section before acting on an abbreviated explanation.[^src-20260906-knowledgeintegration]
+
+[Return to project overview](/overview.md).
+
+[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.
+[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.

## write wiki/references/development-log.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/development-log.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/development-log.md
@@ -0,0 +1,34 @@
+---
+type: Reference
+title: Development log
+description: Find the complete versioned development log.
+status: draft
+tags:
+- ninjarobotpi5
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-developmentlog
+  resource: urn:llmwiki:source:src-20260906-developmentlog
+  title: DevelopmentLog.md
+  content_hash: sha256:9d2f7eb85695c830322023c4efa549e5d178030105a611468b003f4d8e0b1dd4
+- id: src-20260906-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  title: Local knowledge integration evidence
+  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+---
+
+# Development log
+
+The complete log preserves dated implementation decisions and validation reports. Historical test results describe their recorded checkout and date; they are not fresh verification.[^src-20260906-developmentlog]
+
+Use the source identifier below to resolve the complete manual through the raw
+source catalog. The outer wiki README also links directly to the current full
+manual. Root filenames are navigation pages; source updates create new versions.
+Read the relevant full section before acting on an abbreviated explanation.[^src-20260906-knowledgeintegration]
+
+[Return to project overview](/overview.md).
+
+[^src-20260906-developmentlog]: DevelopmentLog.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentlog`.
+[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.

## write wiki/references/mcp-skills-guide.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/mcp-skills-guide.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/mcp-skills-guide.md
@@ -0,0 +1,34 @@
+---
+type: Reference
+title: MCP and Agent Skills tutorial
+description: Find the complete versioned mcp and agent skills tutorial.
+status: draft
+tags:
+- ninjarobotpi5
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-ninjarobot-mcp-skill
+  resource: urn:llmwiki:source:src-20260906-ninjarobot-mcp-skill
+  title: NinjaRobot_MCP_Skill.md
+  content_hash: sha256:df8076ccc2683b24b6752310558ce4e62828d54cee67f1102aae7196c0ee97bb
+- id: src-20260906-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  title: Local knowledge integration evidence
+  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+---
+
+# MCP and Agent Skills tutorial
+
+The tutorial explains external tools, configuration, read-only Tavily and Calendar examples, and reusable Agent Skills. It describes restrictions for the robot Agent, not a development wiki server.[^src-20260906-ninjarobot-mcp-skill]
+
+Use the source identifier below to resolve the complete manual through the raw
+source catalog. The outer wiki README also links directly to the current full
+manual. Root filenames are navigation pages; source updates create new versions.
+Read the relevant full section before acting on an abbreviated explanation.[^src-20260906-knowledgeintegration]
+
+[Return to project overview](/overview.md).
+
+[^src-20260906-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `migration-2026-09-07`; registered source `src-20260906-ninjarobot-mcp-skill`.
+[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.

## write wiki/concepts/architecture.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/architecture.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/architecture.md
@@ -0,0 +1,45 @@
+---
+type: Concept
+title: Architecture and hardware ownership
+description: Agent, IDE, device drivers, safety policy, resource ownership, and code
+  boundaries.
+status: draft
+tags:
+- architecture
+- hardware
+- ownership
+- agent
+- ide
+- drivers
+- safety
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-developmentguide
+  resource: urn:llmwiki:source:src-20260906-developmentguide
+  title: DevelopmentGuide.md
+  content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
+---
+
+# Architecture and hardware ownership
+
+The documented hardware path is user or model → ninjarobot_pi5_agent →
+ninjarobot_pi5_ide → a managed pi5 driver → its device. The Agent handles user
+interaction, model-provider translation, policy, sessions, and tool proposals.
+It should not import a pi5 library or access a device directly.[^src-20260906-developmentguide]
+
+The IDE (the project's device-coordination layer) owns shared resource scheduling,
+action execution, safety state, behaviors, and hardware ownership. Individual
+managed libraries own their device and standalone setup interface. The six
+managed libraries cover servo motors, display, buzzer, distance sensing, camera,
+and microphone.[^src-20260906-developmentguide]
+
+This is the documented architecture contract. Compare affected code and tests
+with it before implementation; this page does not certify that every failure or
+physical safety condition has been tested.[^src-20260906-developmentguide]
+
+[Read the development manual](/references/development-guide.md).
+
+
+[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.

## write wiki/concepts/development-workflow.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/development-workflow.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/development-workflow.md
@@ -0,0 +1,54 @@
+---
+type: Concept
+title: Development and documentation workflow
+description: Retrieve evidence, plan, implement, review wiki impact, version manuals,
+  and validate.
+status: draft
+tags:
+- development
+- workflow
+- documentation
+- update
+- codex
+- claude
+- cursor
+- antigravity
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  title: Local knowledge integration evidence
+  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+- id: src-20260906-developmentguide
+  resource: urn:llmwiki:source:src-20260906-developmentguide
+  title: DevelopmentGuide.md
+  content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
+---
+
+# Development and documentation workflow
+
+Before significant development, consult the local wiki and the current full
+manuals, inspect relevant code, and identify missing or conflicting evidence.
+The root project policy requires an approved phased plan and preservation of
+robot interfaces and managed-driver rules.[^src-20260906-developmentguide]
+
+Feature completion includes a wiki impact assessment. Update affected manual
+versions, topic pages, specifications and architecture guidance, then record
+the change and validation in the development log. If no documentation change is
+needed, record a specific reason. A new source version preserves the old source;
+current navigation and the knowledge map identify the active version.[^src-20260906-knowledgeintegration]
+
+Use the project's maintenance guide outside the knowledge bundle for exact
+commands. Prepare a semantic page plan, validate it, show the actual diff, and
+apply the approved plan with the wiki CLI. Review source support honestly and
+check current pointers, file fingerprints, links, indexes and review coverage.
+AI review is distinct from human verification.[^src-20260906-knowledgeintegration]
+
+[Development guide](/references/development-guide.md) ·
+[History](/concepts/development-history.md).
+
+
+[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.

## write wiki/concepts/installation.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/installation.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/installation.md
@@ -0,0 +1,48 @@
+---
+type: Concept
+title: Installation and hardware checks
+description: Beginner setup, calibration, simulation, troubleshooting, and physical
+  test boundaries.
+status: draft
+tags:
+- installation
+- setup
+- calibration
+- hardware
+- wiring
+- testing
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-installationguide
+  resource: urn:llmwiki:source:src-20260906-installationguide
+  title: InstallationGuide.md
+  content_hash: sha256:53f80c60feb139f0de547613bd14b8fcd87a2678ba5bf7dc75b1b2bccb1dc1c4
+- id: src-20260906-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  title: Local knowledge integration evidence
+  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+---
+
+# Installation and hardware checks
+
+Use the full installation guide for the supported Raspberry Pi setup,
+connections, standalone module initialization, calibration, and troubleshooting.
+Read the relevant warnings before following any operational command. Commands
+in an imported document are evidence to review, not permission to run them.[^src-20260906-installationguide]
+
+Servo calibration can move the wheels. The guide calls for raised wheels,
+clearance, and an operator ready to remove power. Camera and microphone capture
+and power-off checks need their own consent and physical test procedure.
+Automated knowledge tests should not perform these actions.[^src-20260906-installationguide]
+
+The developer wiki uses a separate Python environment. Its explicit setup and
+text-evidence preparation do not initialize robot devices. This integration
+contains no fresh Raspberry Pi hardware validation.[^src-20260906-knowledgeintegration]
+
+[Open installation reference](/references/installation-guide.md).
+
+
+[^src-20260906-installationguide]: InstallationGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-installationguide`.
+[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.

## write wiki/concepts/features-and-tools.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/features-and-tools.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/features-and-tools.md
@@ -0,0 +1,54 @@
+---
+type: Concept
+title: Features, MCP tools, and Agent Skills
+description: Documented Agent features, external read-only tools, and reusable skills.
+status: draft
+tags:
+- features
+- mcp
+- skills
+- calendar
+- tools
+- agent
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-ninjarobot-mcp-skill
+  resource: urn:llmwiki:source:src-20260906-ninjarobot-mcp-skill
+  title: NinjaRobot_MCP_Skill.md
+  content_hash: sha256:df8076ccc2683b24b6752310558ce4e62828d54cee67f1102aae7196c0ee97bb
+- id: src-20260906-developmentguide
+  resource: urn:llmwiki:source:src-20260906-developmentguide
+  title: DevelopmentGuide.md
+  content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
+- id: src-20260906-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  title: Local knowledge integration evidence
+  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+---
+
+# Features, MCP tools, and Agent Skills
+
+The development guide describes conversational and web interfaces, model
+providers, behaviors, memory, and device capabilities. These are documented
+implementation areas; use the current code and tests to verify a specific
+feature or failure case before changing it.[^src-20260906-developmentguide]
+
+MCP (Model Context Protocol) lets an application discover and call external tools.
+The robot tutorial describes allowlisted read-only tools, bounded results,
+timeouts, and untrusted external content. Its examples include Tavily search
+and a read-only Google Calendar server. Agent Skills package reusable workflows;
+they do not grant extra hardware permissions.[^src-20260906-ninjarobot-mcp-skill]
+
+Development wiki skills are a separate coding-tool workflow. This local knowledge
+integration does not install a robot MCP provider or change runtime interfaces.
+Use the existing robot tutorial for robot extensions and the wiki maintenance
+guide for developer knowledge updates.[^src-20260906-knowledgeintegration]
+
+[MCP and skills tutorial](/references/mcp-skills-guide.md).
+
+
+[^src-20260906-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `migration-2026-09-07`; registered source `src-20260906-ninjarobot-mcp-skill`.
+[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.
+[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.

## write wiki/concepts/development-history.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/development-history.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/development-history.md
@@ -0,0 +1,38 @@
+---
+type: Concept
+title: Development history and decisions
+description: Find dated rationale and distinguish historical evidence from current
+  implementation.
+status: draft
+tags:
+- history
+- decisions
+- rationale
+- development
+- log
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-developmentlog
+  resource: urn:llmwiki:source:src-20260906-developmentlog
+  title: DevelopmentLog.md
+  content_hash: sha256:9d2f7eb85695c830322023c4efa549e5d178030105a611468b003f4d8e0b1dd4
+---
+
+# Development history and decisions
+
+The development log retains dated records of implementation work, design
+choices, repairs, validation, and remaining work. Use a relevant dated entry
+when answering why a change was made. Read surrounding entries to determine
+whether a later decision superseded it.[^src-20260906-developmentlog]
+
+Historical success reports refer to the recorded work and environment. They do
+not prove that today's checkout passes the same checks, or that a physical
+device was tested during a later documentation task. Cite the entry and state
+which current checks were actually run.[^src-20260906-developmentlog]
+
+[Complete development log](/references/development-log.md).
+
+
+[^src-20260906-developmentlog]: DevelopmentLog.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentlog`.

## write wiki/analyses/knowledge-limitations.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/analyses/knowledge-limitations.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/analyses/knowledge-limitations.md
@@ -0,0 +1,51 @@
+---
+type: Analysis
+title: Knowledge limitations and verification
+description: Search gaps, stale evidence, source versions, editor access, and review
+  boundaries.
+status: draft
+tags:
+- limitations
+- stale
+- verification
+- search
+- known
+- issues
+generated:
+  by: agent:codex
+  at: '2026-09-06T22:53:22Z'
+sources:
+- id: src-20260906-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  title: Local knowledge integration evidence
+  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+- id: src-20260906-developmentguide
+  resource: urn:llmwiki:source:src-20260906-developmentguide
+  title: DevelopmentGuide.md
+  content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
+---
+
+# Knowledge limitations and verification
+
+Keyword search covers curated pages rather than all raw manual text. It does not
+follow citations for the caller. Try focused terms, read the overview, and open
+full sources. Search expiry flags, source fingerprints, and semantic review
+status are separate signals and must be checked together.[^src-20260906-knowledgeintegration]
+
+A missing result is an evidence gap, not proof a feature is absent. A page can be
+structurally valid while its explanation needs review. Current implementation
+fingerprints identify files needing knowledge review but cannot prove that prose
+is correct. AI-reviewed pages are not human-verified or hardware-tested pages.
+Editor adapters need actual session activation checks; a wiki-only workspace may
+not expose parent robot code.[^src-20260906-knowledgeintegration]
+
+The development guide's older quality-gate example uses narrower lint paths than
+the current root policy. Follow the root operating policy for the current full
+checks, and preserve the source's historical context rather than silently treating
+an older example as the complete current gate.[^src-20260906-developmentguide][^src-20260906-knowledgeintegration]
+
+[Project overview](/overview.md).
+
+
+[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.

```

## Separate page-by-page evidence reviews

These proposed machine review records were prepared after reading each page
and its cited evidence. They are not human verification or robot hardware tests.

### NinjaRobotPi5 project overview

```diff
Plan ninjarobot-page-review-260907-01: Record the machine evidence review for NinjaRobotPi5 project overview.
Risk: low

## write wiki/overview.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/overview.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/overview.md
@@ -18,6 +18,22 @@
   resource: urn:llmwiki:source:src-20260906-developmentguide
   title: DevelopmentGuide.md
   content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:05Z'
+  target_hash: sha256:82b4b2b09b867f0a069e05e4f7cf3bdee6bfcceaf4d79ec854857a8c998ebd69
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # NinjaRobotPi5 project overview

```

### Installation guide

```diff
Plan ninjarobot-page-review-260907-02: Record the machine evidence review for Installation guide.
Risk: low

## write wiki/references/installation-guide.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/references/installation-guide.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/references/installation-guide.md
@@ -17,6 +17,22 @@
   resource: urn:llmwiki:source:src-20260906-knowledgeintegration
   title: Local knowledge integration evidence
   content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:05Z'
+  target_hash: sha256:6d71976836ad0e8f100f5d4855e46a9ae345e99c159045e15ddf144ed969aa38
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # Installation guide

```

### Development guide

```diff
Plan ninjarobot-page-review-260907-03: Record the machine evidence review for Development guide.
Risk: low

## write wiki/references/development-guide.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/references/development-guide.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/references/development-guide.md
@@ -17,6 +17,22 @@
   resource: urn:llmwiki:source:src-20260906-knowledgeintegration
   title: Local knowledge integration evidence
   content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:05Z'
+  target_hash: sha256:5c4426c3c590ca13735e31041528119c09a303e1b84cd8931d6c5286d741f068
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # Development guide

```

### Development log

```diff
Plan ninjarobot-page-review-260907-04: Record the machine evidence review for Development log.
Risk: low

## write wiki/references/development-log.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/references/development-log.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/references/development-log.md
@@ -17,6 +17,22 @@
   resource: urn:llmwiki:source:src-20260906-knowledgeintegration
   title: Local knowledge integration evidence
   content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:05Z'
+  target_hash: sha256:0ccac014213094eb54ed0ec7d0273f05d3a02b5cd7df7fc673cdee4439e4d44c
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # Development log

```

### MCP and Agent Skills tutorial

```diff
Plan ninjarobot-page-review-260907-05: Record the machine evidence review for MCP and Agent Skills tutorial.
Risk: low

## write wiki/references/mcp-skills-guide.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/references/mcp-skills-guide.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/references/mcp-skills-guide.md
@@ -17,6 +17,22 @@
   resource: urn:llmwiki:source:src-20260906-knowledgeintegration
   title: Local knowledge integration evidence
   content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:05Z'
+  target_hash: sha256:a8cf576dc3e8de76cb55aff0636c1f5779837950046e3207ede4f555f8ca35a3
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # MCP and Agent Skills tutorial

```

### Architecture and hardware ownership

```diff
Plan ninjarobot-page-review-260907-06: Record the machine evidence review for Architecture and hardware ownership.
Risk: low

## write wiki/concepts/architecture.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/architecture.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/architecture.md
@@ -20,6 +20,22 @@
   resource: urn:llmwiki:source:src-20260906-developmentguide
   title: DevelopmentGuide.md
   content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:05Z'
+  target_hash: sha256:602559c20e4b41b0189ca08bf989fbfb1d0f80c004719516aed6b420d3b027f3
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # Architecture and hardware ownership

```

### Development and documentation workflow

```diff
Plan ninjarobot-page-review-260907-07: Record the machine evidence review for Development and documentation workflow.
Risk: low

## write wiki/concepts/development-workflow.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/development-workflow.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/development-workflow.md
@@ -25,6 +25,22 @@
   resource: urn:llmwiki:source:src-20260906-developmentguide
   title: DevelopmentGuide.md
   content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:06Z'
+  target_hash: sha256:c8f0369cc7f1a8c1247792dde4b93da093496772eaae92a5742d617ace70e4be
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # Development and documentation workflow

```

### Installation and hardware checks

```diff
Plan ninjarobot-page-review-260907-08: Record the machine evidence review for Installation and hardware checks.
Risk: low

## write wiki/concepts/installation.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/installation.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/installation.md
@@ -23,6 +23,22 @@
   resource: urn:llmwiki:source:src-20260906-knowledgeintegration
   title: Local knowledge integration evidence
   content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:06Z'
+  target_hash: sha256:c89f536e16da0db4909428c180953ffc515f1af207c35041af7a5e8eb9d24ca1
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # Installation and hardware checks

```

### Features, MCP tools, and Agent Skills

```diff
Plan ninjarobot-page-review-260907-09: Record the machine evidence review for Features, MCP tools, and Agent Skills.
Risk: low

## write wiki/concepts/features-and-tools.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/features-and-tools.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/features-and-tools.md
@@ -26,6 +26,22 @@
   resource: urn:llmwiki:source:src-20260906-knowledgeintegration
   title: Local knowledge integration evidence
   content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:06Z'
+  target_hash: sha256:0fd2add29e1e2bb810876e9445514ea215b313c9df2e10dc4aa1e50b70a1b69a
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # Features, MCP tools, and Agent Skills

```

### Development history and decisions

```diff
Plan ninjarobot-page-review-260907-10: Record the machine evidence review for Development history and decisions.
Risk: low

## write wiki/concepts/development-history.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/development-history.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/concepts/development-history.md
@@ -18,6 +18,22 @@
   resource: urn:llmwiki:source:src-20260906-developmentlog
   title: DevelopmentLog.md
   content_hash: sha256:9d2f7eb85695c830322023c4efa549e5d178030105a611468b003f4d8e0b1dd4
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:06Z'
+  target_hash: sha256:533430a40d768b7825f9c5aeeab76f0ffc44eb37617c95eebc0f32548535b94e
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # Development history and decisions

```

### Knowledge limitations and verification

```diff
Plan ninjarobot-page-review-260907-11: Record the machine evidence review for Knowledge limitations and verification.
Risk: low

## write wiki/analyses/knowledge-limitations.md
--- /tmp/ninja-wiki-proposal-nu2l9zra/wiki/analyses/knowledge-limitations.md
+++ /tmp/ninja-wiki-proposal-nu2l9zra/wiki/analyses/knowledge-limitations.md
@@ -23,6 +23,22 @@
   resource: urn:llmwiki:source:src-20260906-developmentguide
   title: DevelopmentGuide.md
   content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
+semantic_review:
+  version: 1
+  performed_by: agent:codex
+  performed_at: '2026-09-06T22:54:06Z'
+  target_hash: sha256:53ea6fa166dc93d13ecc7fb2c641f402d5f91f421f90d715b1c6959e2cd887fd
+  result: passed
+  checks:
+    source_support: passed
+    contradictions: passed
+    limitations: passed
+    claim_strength: passed
+    visual_evidence: not_applicable
+  notes:
+  - Reviewed this page against its listed manual sections and integration evidence.
+  - Claims describe documented contracts and knowledge workflow; current hardware
+    operation and interactive editor activation are not certified.
 ---
 
 # Knowledge limitations and verification

```
