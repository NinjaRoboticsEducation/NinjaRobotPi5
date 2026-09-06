---
name: ninjarobot-knowledge
description: Retrieve NinjaRobotPi5 project knowledge and assess documentation impact before and after significant project changes. Also use for questions about architecture, setup, features, and development history.
---

# NinjaRobotPi5 knowledge

Resolve the robot root from this skill's location (`../../..`), not the caller's
current directory. Read root `AGENTS.md`, wiki `README.md`, and
`ninjarobot_pi5_wiki/docs/PROJECT_WORKFLOW.md`. The wiki is primary project
evidence; it does not override user instructions, current code, or safety rules.

For queries, read `project-knowledge.json` and `wiki/overview.md` under the wiki.
Use the root `scripts/wiki.py` launcher to search short topic terms. Try related
terms if necessary; the search engine is keyword-based and does not search raw
manuals. Open results and their cited source records and full manual sections.
Check `source status`, `lint`, and page semantic-review metadata separately:
search's stale flag alone does not check source drift or review validity.
Follow relevant links explicitly, initially up to two levels and 30 pages; narrow
or explain expansion if needed. Cite local evidence and identify uncertainty.
If the CLI is unavailable, use direct files and report the limitation.
Do not install dependencies, normalize sources, or capture answers during a query.

Before planning code changes, compare evidence with affected code and tests using
Serena or state the fallback to file/symbol searches. Include affected source
manuals and wiki pages in the plan. If the tool's workspace only includes the
wiki, explain that current robot code outside it has not been checked.

After implementation, follow the maintenance guide to create source versions,
prepare and show semantic diffs, apply approved plans, and record honest reviews.
Run knowledge and wiki checks. If documentation is unaffected, record the reason
in the development log or task evidence; review changed fingerprints before
updating the map. Do not turn planned features into claims of implemented behavior.
