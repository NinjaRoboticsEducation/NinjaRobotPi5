# Wiki application and root manual cleanup

The owner-applied initial wiki was checked before cleanup: 11 sourced pages,
11 current passing AI semantic reviews, five ingested sources, and passing strict
lint, knowledge, link and index checks. Pages remain draft and not human-verified.

At the owner's request, the four root navigation files were removed. Root README,
docs/README, and the prior audit's incoming links now lead to full wiki sources.
The source catalog and current-document map remain the source of current versions.
Documentation checks now require direct links from both READMEs and full source
files instead of root stubs. The maintenance instructions use the same contract.

A new integration evidence version and development-log version preserve the
registered originals. Ten affected wiki pages received navigation/citation
corrections and refreshed AI review fingerprints through the existing plan tool.
The architecture page did not require changes. The owner-authorized change is
recorded in [the cleanup plan](../../DevelopmentPlanDoc/LLMWiki_Root_Manual_Cleanup_260907.md).

No robot functionality, managed driver, runtime dependency, or hardware operation
was changed. Existing external bookmarks to deleted root paths no longer resolve;
use the direct source links in [README](../../README.md).

## Final validation

- Both driver integrity/source verifiers passed; 222 tracked driver files match
  their baseline plus 55 previously authorized repairs.
- Syntax compilation passed for Agent, IDE, scripts and tests.
- Root Ruff lint and format checks passed (380 Python files).
- Mypy passed for 81 Agent/IDE source files.
- Full project suite: 588 passed. One existing Starlette/httpx deprecation warning
  remains; robot dependencies were not changed.
- Separate wiki suite: 66 passed.
- Focused documentation and knowledge tests: 17 passed, included in the root total.
- Strict wiki lint: zero errors, warnings or suggestions.
- Project knowledge, link and index checks passed.
- Final wiki status: 11 sourced draft pages, 11 current passing AI reviews,
  seven ingested sources including preserved previous versions.
- Four retrieval topics returned identical results from project root and wiki
  root: architecture, installation/calibration, MCP/skills, development history.
- Repeated queries preserved source, catalog and page fingerprints.
- Protected robot packages, managed drivers and runtime dependency files have
  no diff. Existing registered raw sources were not edited.
- `git diff --check` passed.

The first test pass exposed a fixture still using a section-only README link
while the updated contract requires a direct full-manual link. The fixture was
updated, focused tests passed, and the full 588-test suite was rerun successfully.

To check manually, open the root README and click each of the four manual links.
Each opens the complete wiki source directly. From the project root, run
`python scripts/wiki.py search "hardware architecture"` for a read-only query.
No physical hardware validation is needed for this documentation change.
