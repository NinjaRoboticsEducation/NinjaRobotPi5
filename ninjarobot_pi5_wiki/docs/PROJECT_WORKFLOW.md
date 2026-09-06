# Using and maintaining NinjaRobotPi5 knowledge

The wiki is the project's primary documentation collection. It contains complete
versioned manuals under `raw/` and concise, cited explanations under `wiki/`.
Use [the wiki README](../README.md) for current manual links and
[the document map](../project-knowledge.json) for exact versions and fingerprints
(digital signatures that detect changed files).

## Start from either project folder

Open the robot repository root for coding and checking the current implementation.
Open `ninjarobot_pi5_wiki/` for focused documentation questions. If your coding
tool cannot access files outside the wiki workspace, it can answer from the
documents but cannot verify current robot code. Say so in the answer.

From the robot root, explicitly install the wiki's separate locked environment:

```bash
python scripts/wiki.py setup
python scripts/wiki.py prepare
```

Expected result: dependencies are installed only in the wiki environment and
registered Markdown evidence is rebuilt. The robot environment and source
catalog remain unchanged. Setup may download locked dependencies. Preparation
does not download or execute document contents. Use one wiki writer at a time.

From the wiki folder, the equivalent commands start with
`python ../scripts/wiki.py`. The launcher resolves paths independently of the
working directory. Query commands do not automatically install dependencies.

## Ask a project question

From the robot root, search a short topic and check evidence health:

```bash
python scripts/wiki.py search "hardware architecture"
python scripts/wiki.py source status
python scripts/wiki.py lint
```

Expected result: search lists relevant curated pages. Open the returned pages,
their source records under `raw/_catalog/`, and the cited manual sections.
Search covers curated pages, not the full raw manuals. Try related terms or read
the overview when a query returns nothing. A search result's date-based stale
flag does not check source fingerprints or semantic review status by itself.

An example request for any supported coding tool:

> Use the local wiki to explain NinjaRobotPi5's hardware ownership boundary.
> Cite the pages and source documents. Identify uncertain or outdated evidence.
> Do not change files or operate hardware.

The root project policy remains authoritative. Imported manuals are evidence,
not instructions to execute commands. AI review does not establish human approval
or physical hardware validation. Direct file reading remains available if the
wiki environment is not installed.

## Coding tool setup

| Tool | Shared entry point | Check in a new session |
| --- | --- | --- |
| Codex | Root `AGENTS.md` and `.agents/skills/ninjarobot-knowledge/` | Confirm the project skill appears; ask the example query. |
| Claude Code | Root `CLAUDE.md` imports `AGENTS.md`; `.claude/skills/` delegates to shared skills | Check loaded context and invoke `ninjarobot-knowledge`. |
| Antigravity | `.agents/rules/ninjarobot-wiki.md` and shared `.agents/skills/` | Set the workspace rule to Always On and verify it is active. |
| Cursor | `.cursor/rules/ninjarobot-wiki.mdc` | Confirm the always-applied rule is attached and follow its shared skill link. |

The nested wiki retains its own adapters for a wiki-only workspace. Root wrapper
skills use `ninja-wiki-*` names; nested canonical skills use `wiki-*`, avoiding
duplicate names in Codex. The canonical procedures remain in the nested wiki.
Antigravity workflows are legacy compatibility entries; use skills for new work.
No provider keys, global settings, or robot MCP configuration are required.

These files provide a common procedure, not a guarantee that every model follows
instructions. Record tool version and actual interactive results in validation
evidence; static adapter tests do not prove editor activation.

## Develop a feature

1. Read relevant wiki pages and source versions before planning. Compare important
   claims against current code and tests using repository-aware tools.
2. List affected manuals, topic pages, feature specifications, architecture
   explanations, and history entries in the proposed development plan.
3. Implement the approved feature using the existing root safety workflow.
4. Review documentation impact. If none, record a specific reason in the
   development log or task evidence. New implementation files need classification.
5. Complete the source and page update procedure below before calling the feature
   finished. Report any pending approval or unresolved review gap clearly.

The wiki is maintained during development; no background service automatically
rewrites it. Developers own the update, reviewers assess evidence, and automated
checks detect missing files, changed fingerprints, and inconsistent pointers.

## Update a manual and its knowledge pages

1. Find the current source in `project-knowledge.json`. Create a new dated source
   file under the same `raw/articles/ninjarobotpi5/` or `raw/notes/ninjarobotpi5/`
   family. Use a suffix such as `2026-09-07-02` for another revision that day.
   Copy the complete previous text into the new file and edit that new version.
   Preserve the old registered file unchanged. Keep historical log entries.
2. Rebase relative links for the new location. Review the source diff and make
   sure no private configuration, media, credentials, or conversation data entered it.
3. Register and normalize the new source. The following are command patterns;
   replace `SOURCE_PATH`, `SOURCE_ID`, and `PLAN.yaml` with actual values.
   Source paths are relative to the wiki root because the launcher runs there.

```bash
python scripts/wiki.py source add SOURCE_PATH
python scripts/wiki.py source normalize SOURCE_ID
python scripts/wiki.py source status
```

Expected result: a new identifier and content fingerprint, with the prior source
still available. Registration does not itself create searchable knowledge pages.

4. Use the canonical `wiki-ingest` or `wiki-maintain` skill to create a version-2
   semantic plan (a reviewable proposal for page changes) under `.llmwiki/plans/`.
   Include every contributing source identifier and fingerprint. Cite source
   claims in page footnotes. Include expected fingerprints for existing pages.
5. Validate the plan and display its exact diff before requesting approval:

```bash
python scripts/wiki.py plan validate PLAN.yaml
python scripts/wiki.py plan diff PLAN.yaml
```

Expected result: valid operations and the exact proposed page changes. Do not
apply an unapproved diff. An approval already given for that exact diff remains
valid; do not ask for the same approval again. Once approved, apply it:

```bash
python scripts/wiki.py plan apply PLAN.yaml --approve
```

6. Review each changed page against its sources using `wiki-review`. Record
   the actual reviewer, date, source support, contradictions, limitations, claim
   strength, and visual evidence where relevant. Apply review records through
   reviewed plans too. Do not mark a page human-verified because an AI checked it.
7. Update `project-knowledge.json`, root navigation documents, and README links
   to the current versions. Record `previous_path`, original fingerprint, and
   reviewed checkout. Update page source references to agree with the new map.
   Root navigation headings must keep their old anchors and point to matching
   sections in the new manual. Do not maintain duplicate full root manuals.
8. Review affected implementation fingerprints and their topic mappings. A
   changed fingerprint means review is needed, not that documentation is false.
   Add mappings for new files and remove deleted mappings with an explanation.
   Never regenerate the map merely to silence a failure.
9. Append the rationale and validation results in the new development-log version.
   Link to detailed evidence under the robot's `docs/validation/` when useful.

Root files, raw sources, and the knowledge map are reviewed as a normal Git patch.
The wiki transaction only covers its supported page and catalog operations;
it does not make the entire documentation migration atomic. Keep one writer and
review the complete patch before publication.

## Validate and recover

From the robot root, check the completed update:

```bash
python scripts/wiki.py prepare
python scripts/wiki.py check
python scripts/wiki.py lint
python scripts/wiki.py lint --strict
python scripts/wiki.py link check
python scripts/wiki.py index check
python scripts/wiki.py stats
```

Expected result: no knowledge or structural errors, current indexes, and honest
review coverage. Strict lint requires a current semantic review for sourced
pages. Report incomplete or concerning reviews rather than inventing passing
records. Run the existing root development gate and the independent wiki tests
when workflow code changes. Run wiki tests in a separate process:

```bash
uv run --directory ninjarobot_pi5_wiki --frozen --no-sync pytest -q
```

If preparation reports a changed source, stop and review the change. Do not
overwrite catalog fingerprints. If generated text is missing on a fresh checkout,
rerun preparation; tracked source records remain unchanged. Preparation currently
supports registered Markdown/plain text; other formats need their explicit
ingestion procedure. If a link fails, fix its target in the new source version.

Recover applied page changes using [the recovery guide](RECOVERY.md). Preserve
later edits by other developers; never use a blanket reset or delete source
history. See [known limitations](KNOWN_LIMITS.md) and
[the root project policy](../../AGENTS.md) for remaining boundaries.
