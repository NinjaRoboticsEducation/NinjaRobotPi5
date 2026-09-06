# Wiki integration validation — 7 September 2026

The documentation migration and development-tool integration are implemented.
The initial knowledge pages and their separate AI evidence-review records have
been validated in disposable copies. **Applying those semantic changes to the
live wiki is pending approval of the concrete preview.** Robot functionality
has not been modified.

## Reviewable result

- [Wiki README and full manuals](../../ninjarobot_pi5_wiki/README.md).
- [Shared maintenance procedure](../../ninjarobot_pi5_wiki/docs/PROJECT_WORKFLOW.md).
- [Current document and implementation map](../../ninjarobot_pi5_wiki/project-knowledge.json).
- [Approved refinement plan](../../DevelopmentPlanDoc/LLMWiki_Workflow_Refinement_Plan_260907.md).
- [Exact initial content and review preview](../../DevelopmentPlanDoc/LLMWiki_Initial_Knowledge_Preview_260907.md).
- [Initial page plan](../../DevelopmentPlanDoc/LLMWiki_Initial_Knowledge_260907.yaml).
- [Separate page review plans](../../DevelopmentPlanDoc/LLMWiki_Page_Reviews_260907.json).
- [Migration content fingerprints](wiki_migration_260907.json).

The implementation plan was approved by the owner. The nested wiki-ingest and
wiki-review skills separately require showing and approving the actual semantic
diffs. This approval was requested after the complete preview was prepared.
No live page changes or fabricated human verification records were applied.

## What changed

The four full manuals moved into dated article/note source folders. Root files
remain navigation documents with compatibility anchors. The migration comparison
confirmed the original text survives after mechanical link rebasing, with a
workflow appendix in the development guide and an integration entry in the log.
An existing installation-guide heading mismatch was repaired by adding an
explicit anchor; its original heading and technical text were preserved.

Five sources were registered and normalized: the four manuals and a public
integration evidence note. Catalog identifiers use the CLI's UTC date, which can
be the previous calendar day relative to the project's Asia/Tokyo date. The
identifiers are retained exactly as assigned.

Root AGENTS.md remains the canonical policy. AGENT.md is a compatibility pointer.
Codex, Claude Code, Antigravity and Cursor adapters point to shared procedures.
The existing documentation skill now requires retrieval and wiki-impact review.
The Pi validation skill remains unchanged.

The new launcher supports explicit setup, generated-text preparation, checks,
and existing wiki commands from either working folder. The knowledge validator
checks four current source pointers, catalog agreement, mapped implementation
fingerprints, unmapped files, adapters, and local documentation links. The map
covers 136 files under the Agent and IDE source directories. This is initial
navigation coverage, not a claim that every symbol has been documented.

The existing wiki's Ruff formatting/import findings were repaired without
changing its algorithms. An abstract syntax tree comparison (a comparison of
Python program structure) found the same code apart from imports in all 29
modified existing wiki Python files. The root Ruff policy was not weakened.

## Checks run on the working checkout

Commands were run from the robot root unless specified otherwise.

| Command or check | Result |
| --- | --- |
| `uv run --frozen python scripts/verify_immutable_drivers.py` | PASS: 222 tracked files across six drivers; 55 previously authorized repairs. |
| `uv run --frozen python scripts/verify_workspace_driver_sources.py` | PASS: all six managed libraries resolve to this checkout. |
| `uv run --frozen python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests` | PASS. |
| `uv run --frozen ruff check .` | PASS. |
| `uv run --frozen ruff format --check .` | PASS: 380 Python files formatted. |
| `uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src` | PASS: 81 source files. |
| `uv run --frozen pytest -q` | PASS: 588 tests; one existing Starlette/httpx deprecation warning. |
| `env -u VIRTUAL_ENV uv run --directory ninjarobot_pi5_wiki --frozen pytest -q` | PASS: 66 tests, including five preparation cases. |
| `uv run --frozen pytest -q tests/test_project_knowledge.py` | PASS: seven drift, link, pointer, adapter and read-only regression tests; included in the 588 root tests. |
| Wiki-environment pytest on `../tests/test_project_knowledge.py` | PASS: seven tests without installing the robot environment. |
| Skill creator `quick_validate.py` on eight root and six Claude skill folders | PASS: 14 skills. |
| `python scripts/wiki.py prepare` | PASS: five text sources rebuilt; tracked source/catalog bytes unchanged. |
| `python scripts/wiki.py lint --strict` on live wiki | PASS structurally, but the live wiki still contains only the blank overview; this does not establish project retrieval. |
| `python scripts/wiki.py check` on live wiki | EXPECTED BLOCK: reports pending publication and missing proposed pages. Do not suppress this gate. |
| `git diff --check` | PASS. |
| Protected-file diff and migration comparison | PASS: robot packages, six drivers, robot lock/project files, installer and driver authorization manifests unchanged. |

A new preparation regression initially expected the launcher's error wording,
while configuration validation rejected an unsafe path earlier. The test was
corrected to cover both an outside-project redirect and a redirect inside raw
sources. Both are rejected before writes; the complete 66-test wiki suite passes.

The existing Starlette warning concerns robot dependencies and was not changed
as part of this documentation-only task.

## End-to-end checks in a disposable checkout

A temporary directory was populated from public tracked/current project files,
without Git history, virtual environments, generated evidence, or private runtime
files. A fresh independent wiki environment was installed from its lockfile.
The initial page plan and 11 separate review plans were applied only in that
disposable test copy; the copy was removed after testing.

Results:

- Preparation rebuilt all five source evidence files from a missing cache.
- The full knowledge validator passed with the proposed pages present.
- Strict lint reported zero errors, warnings, or suggestions.
- Knowledge link checks passed and generated indexes were current.
- `hardware architecture` found the architecture page and overview.
- `installation calibration` found installation guidance and its manual reference.
- `MCP skills` found the features/tools page and tutorial reference.
- `development history` found history and workflow guidance.
- `quantum teleportation` returned no results, as expected for absent knowledge.
- The same queries from the robot root and wiki root returned identical results.
- Repeating queries and preparation preserved the fingerprints of public project
  files and source records. Only ignored generated evidence was rewritten.

This validates the proposed integrated content and local tooling. It does not
substitute for applying the approved plans to the live wiki and rerunning the
live knowledge checks.

## Cross-tool and automation evidence

Codex CLI 0.153.4 is installed. The active Codex session's skill catalog exposed
the new six root project/wiki skills after creation. Shared instruction and
wrapper paths were checked, and the local launcher was exercised from both
working folders. A separate fresh model session was not launched.

Claude Code, Antigravity and Cursor executables were not found on this host's
PATH. Their adapter structures and targets were checked; their interactive
activation is **not tested**. Antigravity's rule may need manual Always On
activation. Windows and macOS execution is also not claimed from this Linux run.

The new root GitHub workflow is configured for Linux, macOS and Windows with
read-only repository permissions, a separate locked wiki environment, source
preparation, strict lint, knowledge checks, independent tests and a final clean
tracked-file check. Nothing was pushed and no remote job was run.

Upstream action revisions were checked through their official repositories and
Git tags on this date:

- [actions/checkout](https://github.com/actions/checkout): v7 at
  `3d3c42e5aac5ba805825da76410c181273ba90b1`.
- [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv): v9.0.0 at
  `c771a70e6277c0a99b617c7a806ffedaca235ff9`.
- [uv](https://github.com/astral-sh/uv): executable pinned to 0.12.5, matching
  the local version; upstream tag `210d1f6785e95a8c8c0d53e284408c9be1134700`.

## Remaining completion step

After explicit approval of the linked preview, apply the saved initial plan and
then each saved page-review plan using the existing CLI. Revalidate expected
fingerprints first; if a source or target has changed, stop and prepare a revised
diff. Mark the knowledge map ready only after application, then run live knowledge,
strict lint, source, link, index, statistics, and retrieval checks. Update this
record with the actual results.

No hardware test is necessary for documentation and local retrieval changes.
No motors moved, camera/microphone capture, device communication, deployment,
network publication, or system power action was performed. Future device changes
still require the existing separate hardware validation procedures.
