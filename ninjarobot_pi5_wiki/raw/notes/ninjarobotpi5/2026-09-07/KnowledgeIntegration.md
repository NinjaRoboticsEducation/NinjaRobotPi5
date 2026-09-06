# Local knowledge integration evidence

Recorded by Codex on 7 September 2026 during the owner-approved integration.
This is public development evidence, not an instruction to operate the robot.

## Project workflow

The canonical project operating policy is root AGENTS.md; AGENT.md is a
compatibility pointer. The wiki is separate from the robot application and has
its own locked Python environment. The root scripts/wiki.py launcher provides
explicit setup, text-evidence preparation, knowledge checking, and existing
llmwiki commands. Queries use the existing environment without dependency sync.
Root and nested adapters support shared instructions for Codex, Claude Code,
Antigravity and Cursor. Static file checks do not prove activation in every editor.

The current full manuals are versioned sources under raw/articles/ninjarobotpi5
and raw/notes/ninjarobotpi5. Root manual files are navigation pages. The current
source pointers and reviewed implementation fingerprints are in
project-knowledge.json. That map detects local file changes requiring review;
it does not prove every explanation remains correct. New features require a
wiki impact assessment, affected source/page updates, a history entry, and checks.
Registered source originals remain unchanged; an update creates a new version.
Semantic page changes require a validated plan, displayed diff, and approval.

## Retrieval limitations

The reviewed search.py implementation searches ordinary curated wiki Markdown
pages with keywords. It does not search complete raw manuals or follow citations
on the caller's behalf. The search stale flag uses page expiry metadata; source
status and lint are separate checks. The reviewed semantic.py implementation
checks review fingerprints separately. Agents need to read citations and compare
important claims with current implementation files. A workspace limited to this
wiki may not permit verification of robot files in the parent directory.

Normalization creates ignored derived evidence. A fresh checkout needs explicit
preparation to restore it; the project launcher prepares registered text in a
temporary copy and installs generated files without changing tracked catalogs.
This preparation currently supports Markdown and plain text only.

## Safety and evidence status

The integration does not authorize robot behavior changes, hardware operation,
network publication, private-source ingestion, or modifications to managed drivers.
The development guide describes the Agent to IDE to driver hardware boundary;
actual hardware behavior still requires the project's manual validation process.
No Raspberry Pi hardware was operated during this integration.
Historical development-log entries are evidence of past work, not fresh results.
AI semantic review is not human verification. Missing or contradictory evidence
must remain visible in answers.
