# Narrowed Phase 4 walkthrough — 13 September 2026

Test M03 memory retrieval, M04 reviewed recipes, X01 compatible skills and X05
public project help on Raspberry Pi OS Lite, without a desktop. Calendar changes,
new research services, notes, checklists and briefings remain deferred. Existing
web search and reminders are preserved.

A recipe is a saved list of steps. A skill is an instruction package for the
conversation model. Neither gives extra permission. The new recipes can only
read approved local information; they cannot move the robot, capture media,
schedule reminders, change accounts or run shell commands.

## 1. Prepare your terminal

Connect to the Pi using your normal SSH (remote terminal) connection. Define a
convenient shortcut that lasts only in this terminal:

~~~bash
cd ~/NinjaRobotPi5
nr() { uv run --frozen --no-sync ninjarobot-agent "$@"; }
nr service status
nr recipe --help
nr skill list
~~~

Expected: the recipe command is recognized and project-help appears in the skill
list. These commands do not install dependencies. If the environment is missing,
follow the [installation guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-13-02/InstallationGuide.md)
first. Do not fix it by changing Pi5 driver paths.

Use an already configured Agent service with an existing local user profile.
The first updated service start adds two recipe tables to the existing private
database and preserves old data. Make your usual private backup before upgrading;
do not upload the database.

If the service is running old code, restart it **when the robot is idle**:

~~~bash
nr service stop
nr service start --real
nr service status
~~~

This operator-run startup can communicate with devices through existing startup
behavior. It is not part of the hardware-free automated tests. Use your usual
startup options if your installation requires them. No new service or boot
configuration is required.

Make the acceptance session silent and unarmed:

~~~bash
nr chat --session local-cli "/speech off"
nr chat --session local-cli "/disarm"
~~~

Expected: speech is off and motion is not armed. Keep the same local-cli session.
With memory enabled, recipes belong to the active local user; with memory
disabled, they belong to the session. Do not switch identity during a run.
If no profile exists, complete existing profile setup separately. Phase 4 itself
does not require camera enrollment.

## 2. Read public project help

This direct query does not call a conversation model:

~~~bash
nr chat --session local-cli "/project Bluetooth speaker"
~~~

Expected: a bounded result containing a document ID such as public-1, title,
source path, hash (a content fingerprint), source date and draft warning.
The published checkpoint is **12 September 2026**. New Phase 4/5 manuals are
prepared separately and deliberately are not treated as published evidence.

For a conversational explanation:

~~~bash
nr chat --session local-cli --skill project-help   "How do I connect a Bluetooth speaker on Raspberry Pi OS Lite?"
~~~

Expected: an explanation with sources and visible coverage limits. This second
command uses your selected conversation provider and its normal privacy/cost
settings. It must not claim documentation proves the speaker is connected or
execute pairing commands.

An installed wheel without the checkout reports public wiki content unavailable;
ordinary command help and the Agent remain available. Queries never install a
wiki engine or run ingestion/review. Read the newest manuals directly for newer
features.

## 3. Check improved memory retrieval

Run the synthetic check, which creates and removes its own temporary database:

~~~bash
uv run --frozen --no-sync python scripts/validate_phase4_memory.py
~~~

Expected: 1,002 synthetic records, two users, 50 queries and zero top-result
misses. Timing varies with system load. No personal memory or hardware is used.
Japanese/Chinese support is literal substring matching, not full meaning-based
search.

For an optional personal check:

~~~bash
nr chat --session local-cli "/memory review"
~~~

Choose a preference you intend to change and copy its memory ID. Replace the
MEMORY_ID placeholder before running:

~~~bash
nr chat --session local-cli "/memory edit MEMORY_ID I prefer green tea."
nr chat --session local-cli --skill memory-retrieval   "What is my tea preference? Include the memory ID and confirmation information."
~~~

Expected: the corrected preference appears with source/confirmation information.
The earlier value of that same preference must not survive in a cache. Restore
the original text with another memory edit if needed; do not delete real
preferences just for testing.

Relevant older memories precede unrelated recent behavior anchors. Private and
expired records are excluded from search. Inspect evidence when judging a model
answer; a model can still phrase an answer incorrectly.

## 4. Preview and save a recipe

The supplied example reads the clock and speech-command help. It does not enable
speech:

~~~bash
nr recipe preview --file docs/examples/refinement_phase4/clock-help.recipe.json
~~~

Expected: ordered steps, expected results, tool fingerprints, simulation_only
true, executed false, and review_hash. A preview checks instructions; it does
not execute or prove their expected results. Read the steps first.

Copy the exact review_hash and replace REVIEW_HASH:

~~~bash
nr recipe save --file docs/examples/refinement_phase4/clock-help.recipe.json   --review-hash REVIEW_HASH
nr recipe list
nr recipe show phase4-clock-help --version 1
~~~

Expected: version 1 saved with executed false. Saving must not run a tool.
Changing the file or tool contracts invalidates the old hash. If this ID already
exists, inspect it first; use a new ID for unrelated work.

## 5. Run the exact saved version

~~~bash
nr recipe run phase4-clock-help --version 1 --confirm
nr chat --session local-cli "/tasks"
~~~

Expected: a task ID and results from system.time.get, then command_help.search.
The task receipt records each tool status. There is no sound, movement or new
reminder. The input-free version also runs from web chat or terminal chat:

~~~text
/recipes show phase4-clock-help 1
/recipes run phase4-clock-help 1
~~~

Entering the run command is an explicit user request. The model has no recipe
execution/save tool that can manufacture this permission.

## 6. Save feedback as a new version and use inputs

The second example lets the user choose a topic:

~~~bash
nr recipe preview --file docs/examples/refinement_phase4/clock-help-parameterized.recipe.json
~~~

Review and copy the new hash. Here version 1 means “I am updating the currently
selected version 1”; it checks for another edit since your review:

~~~bash
nr recipe save --file docs/examples/refinement_phase4/clock-help-parameterized.recipe.json   --version 1 --review-hash NEW_REVIEW_HASH
nr recipe show phase4-clock-help --version 2
nr recipe run phase4-clock-help --version 2 --inputs '{"topic":"memory"}' --confirm
~~~

Expected: version 2 reads memory-command help. Missing/wrongly typed inputs are
refused. No private input values are filled in automatically.

Select version 1 again for future use:

~~~bash
nr recipe rollback phase4-clock-help --version 1 --confirm
nr recipe show phase4-clock-help
~~~

Expected: the selected version is 1, while version 2 remains inspectable.
Runs pin explicit versions, so this does not rewrite an active request.
A later edit creates version 3, preserving both earlier versions.

## 7. Check refusal, cancellation and cleanup

~~~bash
nr recipe disable phase4-clock-help
nr recipe run phase4-clock-help --version 1 --confirm
nr recipe enable phase4-clock-help
~~~

Expected: the disabled run is refused. Enabling does not execute anything.
Current tool contracts are still checked at run time.

These local reads normally finish too fast to cancel by hand. For a genuinely
running recipe, use a second terminal with the same session, read its task ID
from /tasks, then replace TASK_ID:

~~~bash
nr chat --session local-cli "/tasks cancel TASK_ID"
~~~

Expected: later steps stop; completed reads and their receipts remain.
Automated checks use deliberately slow fake providers for cancellation and
shutdown races. Do not add a slow hardware call to test cancellation.
Restart never resumes interrupted recipes automatically.

To remove **only this test recipe**:

~~~bash
nr recipe delete phase4-clock-help --confirm
nr recipe list
~~~

Expected: its saved versions disappear; task receipts retain their normal
retention policy. Other recipes and conversations remain intact. Limits:
100 recipes per owner, 100 versions each, eight steps and at most 60 seconds
per run, further reduced by the Agent's current budget.

## 8. Validate skills

~~~bash
nr skill inspect project-help
nr skill simulate project-help --input '{"prompt":"success"}'
nr skill inspect project-help --check-live
nr skill inspect robot-command-help
~~~

Expected: offline inspection/simulation reads the package only. The live option
checks the already running service's capabilities; it never starts the service.
Missing optional help tools use declared fallbacks; missing required tools or
too-old contracts produce clear errors. Existing version-1 packages still work.

Deferred templates are examples, not new working features:

~~~bash
nr skill validate docs/skill-templates/calendar-preview-template
nr skill validate docs/skill-templates/calendar-preview-template --check-live
~~~

Expected: offline format validation passes; live validation refuses the missing
calendar capability. Research/briefing templates behave the same way.
Version-2 install/enable also require a current service catalog. Version-1
offline installation remains supported.

For packaging, simulation, installation and removal, see the
[skill template guide](../skill-templates/README.md).

## 9. Record acceptance and recover

| Check | Expected result | Your result |
| --- | --- | --- |
| Project help | Cited, bounded answer with older/draft coverage warning | Pending |
| Memory | Corrected relevant evidence; no cross-user content | Pending |
| Recipe save | No tool execution | Pending |
| Recipe run | Clock/help receipts in order; task ID visible | Pending |
| Versions and disable | Old versions preserved; disabled starts refused | Pending |
| Skills | v1 works; v2 requirements and template refusal are clear | Pending |
| Existing functions | Chat, reminders and speech controls remain available | Pending |

Safe smoke checks are the synthetic script and isolated tests. Device
communication is limited to separately chosen existing service startup;
additional Bluetooth tests use the Phase 3 guide. No actuator-moving or
power-risk test is needed here. Do not arm motion, capture media, power off
or change boot settings for Phase 4 acceptance.

Rollback: disable a problematic recipe or project-help skill, preserve the
private database backup, and report the failing command and sanitized error.
Do not reverse the migration or erase user data. Public-help failure leaves
ordinary Agent functions available.

See the [handoff](refinement_phase4_handoff_260913.md) for automated results,
implementation limits and deferred wiki publication.
