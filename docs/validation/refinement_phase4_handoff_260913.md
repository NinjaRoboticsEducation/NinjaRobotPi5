# Narrowed Phase 4 implementation handoff — 13 September 2026

M03, M04, X01 and X05 are implemented. T04 calendar work, T05 new research work
and T06 notes/checklists/briefings remain deferred at the owner's request.
Phase 5 changes already in the working tree were preserved. No new hardware
function, driver change, dependency or external service was introduced.

Start with the [manual walkthrough](refinement_phase4_walkthrough_260913.md).
It is written for Raspberry Pi OS Lite and separates local software checks from
operator-run startup. No physical acceptance is claimed.

## What changed and why

| Feature | Finding and implementation |
| --- | --- |
| M03 memory | Recent behavior anchors could crowd out older search matches. Relevant matches now come first, confirmed preferences are protected in candidate ranking, and private/expired records are excluded before search limits. Queries are bounded to 300 characters and 12 terms, with at most 100 candidates and 20 returned items. Literal substring fallback handles Japanese/Chinese fragments when indexed search finds nothing. SQLite's smaller-is-better relevance order is preserved within ranking tiers. |
| M04 recipes | Behavior-derived memories were not a general, reviewed executor. Recipes now have owned numbered versions, exact-preview hashes, a closed list of local read tools, declared scalar inputs/references, eight-step/60-second ceilings and existing task-budget checks. Every step uses current Agent policy and records a receipt before later work. |
| X01 skills | Version-1 manifests reject extra fields. Version 2 is explicitly parsed without rewriting installed v1 packages. Required minimum contracts and optional fallbacks are checked against the current catalog at install, enable and run time; offline previews are clearly structural. Live preview checking is available with --check-live. |
| X05 help | Developer wiki skills were not runtime tools. The Agent now exposes project_help.search/read through a fixed public manifest, plus /project and a bundled project-help skill. Reads return citations, content fingerprints, version and draft/review limitations. |

Main implementation files are memory_store.py, memory_services.py, recipes.py,
recipe_controls.py, skills.py, project_help.py and project_help_manifest.json
under the Agent package. Existing runtime, prompt, CLI (command-line interface),
IPC (local service messages), registry and task boundaries provide integration.
There is one backward-compatible database migration, revision 6, adding
task_recipes and task_recipe_versions.

## Compatibility, ownership and safety

No Phase 4 edit changes IDE hardware APIs (interfaces used by other software),
Pi5 driver code, Bluetooth setup, service deployment or power commands.
Existing v1 validation output and prompt defaults were retained after a regression
check caught an unintended extra output field.

Recipes support only system.time.get, command_help.search, project_help.search,
project_help.read, tasks.list, memory.search and memory.profile.get.
Tool descriptions and schemas are fingerprinted. A changed contract requires a new
preview and saved version. Dynamic or hardware tools cannot enter the list merely
by claiming a low risk level.

Recipe authoring is explicit structured text through the CLI; there is no
automatic extraction of private tool parameters or autonomous learning.
Optional source_task_ids must refer to owned, completed request receipts whose
steps succeeded. The most recent 100 request records are considered for this
evidence check. Missing evidence requires a fresh review, not a success claim.
Feedback is represented by editing purpose/steps and saving a new reviewed version.

Only top-level scalar input references and declared scalar fields from earlier
steps are accepted. No loops, expressions, shell, arbitrary attributes, retries
or external writes exist. Expected outcomes are review guidance, not automatic
proof of semantic success. Read results are bounded in the terminal response;
full content is not copied into recipe defaults or step receipts.

Recipe save uses the exact preview hash; concurrent changes require another
review. Runs pin a version, verify current scope and contracts between steps,
stop on disable/delete/cancellation, and retain completed receipts. A unique saved
identity prevents deletion/recreation from reviving an old run. Shutdown cancels
owned workers before closing task persistence. Restart marks interrupted requests
uncertain and never resumes them automatically.

Storage limits are 100 recipes per owner and 100 versions per recipe. Profile
deletion removes its recipe versions through database ownership links. An
explicit full memory reset also clears recipes. There is no automatic reverse
migration or deletion of user data during upgrade.

## Public-help trust and limits

The fixed manifest was derived from existing public pages, source records and
the published document map. It pins four curated pages and every cited source.
This task did not perform a new semantic review (checking claims against source
meaning). Existing AI review information is identified as such, and every result
remains labeled draft/historical. No human or current hardware verification is
claimed.

Coverage is pinned to 12 September 2026. Prepared Phase 4/5 manuals are intentionally
excluded while wiki ingestion/review remain deferred. A page or cited source
hash mismatch withholds that result. Unmapped citations are refused.

The provider opens each path component relative to its parent directory and
rejects symlinks, traversal, non-regular files, invalid encoding and oversized
pages. It reads at most 64 KiB per page, 128 KiB per cited source for hash checking,
and 256 KiB total per lookup. The larger source-hash allowance is needed for
existing approximately 99 KiB manuals; their full text is not returned.
Queries allow 300 characters, six excerpts of up to 1,500 characters, and a
three-second local deadline. No link traversal, subprocess, inherited secret
environment, wiki engine installation, network access or maintenance action
exists. A bounded local file read may finish in its worker after cancellation;
its result is discarded and it has no mutation authority.

An editable project checkout supplies the default public wiki location. An
installed wheel without it reports unavailable help rather than searching
arbitrary directories. Command help and ordinary Agent service operation remain
available. Disable the project-help skill to disable its automatic conversational
selection; that does not remove the explicit read-only /project command.

## Validation evidence

The final consolidated gate passed on 13 September 2026:

| Check | Result |
| --- | --- |
| ruff check | Passed for the repository |
| ruff format --check | 432 Python files formatted |
| mypy | Passed for 103 Agent/IDE source files |
| compileall | Agent, IDE, scripts and root tests compiled |
| pytest -q | 868 passed in 35.41 seconds |
| Immutable drivers | 222 files match the baseline plus 56 previously authorized repairs; no new driver repair |
| Workspace driver sources | All six managed libraries load directly from this checkout |
| JavaScript syntax | Existing web app passes node --check |
| git diff --check | Passed |
| Wheel | Built Agent 1.0.0; all seven required new provider/recipe/skill artifacts included |
| Documentation | 263 local links and 58 anchors across 12 documents resolve; 23 Bash blocks pass syntax checking |
| Public examples | Both recipe versions previewed, saved and ran through actual runtime policy in a temporary database |
| Public-help smoke | Bluetooth, architecture, memory and development queries return bounded dated evidence |

The suite reports one pre-existing Starlette/HTTPX deprecation warning. It is not
a test failure. Phase 5's separate managed-driver test results remain recorded
in its handoff; Phase 4 did not change driver code. Tests used temporary data
and fake providers. No live robot service, private configuration or hardware
was exercised.

Reproduce the main gate from the repository root:

~~~bash
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py
uv run --frozen --no-sync python -m compileall -q ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen --no-sync pytest -q
node --check ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app.js
git diff --check
~~~

The synthetic retrieval evaluation used 1,002 records, two users and 50 repeated
queries: zero top-result misses; median 0.436 ms, maximum 0.871 ms, and a
122-character selected context on this host. This is a small keyword-search
measurement, not a broad intelligence or production-load benchmark.

Focused coverage includes owner isolation, corrected/deleted/expired/private
memory, both search modes, multilingual fragments, recipe preview/run separation,
version conflicts, rollback, invalid references, policy denial, outer budgets,
cancellation, disable/delete, contract drift, shutdown and restart, profile
deletion, v1 compatibility, v2 optional fallback, denied tool sequences, future
versions, file confinement, hash drift and broken citations.

## Documentation and remaining acceptance

New full Installation Guide, Development Guide, MCP/Skills Guide and Development
Log versions live under the wiki raw articles/notes directories dated
2026-09-13-02. Root/wiki/documentation READMEs link to them. Master and Phase 4
plans distinguish implemented scope from deferred work. The walkthrough includes
copyable commands and expected results; two public example recipes and a skill
template guide are supplied.

THIRD_PARTY_NOTICES.md was reviewed: no new runtime dependency or external
service requires a notice. Existing packages provide SQLite, data validation
and schema checking.

Wiki ingestion, source review, semantic diffs, publication, fingerprint updates,
wiki lint and knowledge-map changes remain deliberately skipped. Registered
originals and published pointers are preserved. Documentation-link validation
does not publish or review the wiki.

Remaining acceptance is the owner's manual walkthrough and optional regression
checks of existing device functions. No actuator or power test is required for
this Phase 4 scope. Phase 5 physical acceptance remains separate.
Do not start deferred calendar/research/notes work without further authorization.
