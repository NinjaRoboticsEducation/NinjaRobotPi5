# Version-2 Agent skill templates

These are runtime instruction packages, not developer skills from .agents/skills.
Use [the working project-help package](../../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/project-help/skill.json)
as the fourth template. Calendar, research and briefing directories intentionally
require capabilities not implemented in narrowed Phase 4. Their format validates
offline; they cannot be enabled as working features without those providers.

Keep exactly skill.json, instructions.md and optional examples.json. Version 2
declares minimum Agent/tool versions, required capabilities, optional fallbacks
and effect categories. These grant no permission. Version-1 files need no edits.
Examples are simulation-only instructions, not executable code or proof of model
behavior.

## Make a custom project-help package

From the project root, make a temporary copy:

~~~bash
phase4_skill_dir=$(mktemp -d)
mkdir "$phase4_skill_dir/my-project-help"
cp ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/project-help/skill.json   ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/project-help/instructions.md   ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/bundled_skills/project-help/examples.json   "$phase4_skill_dir/my-project-help/"
python - "$phase4_skill_dir/my-project-help/skill.json" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
value = json.loads(path.read_text())
value["id"] = "my-project-help"
value["name"] = "My project help"
path.write_text(json.dumps(value, indent=2) + "\n")
PY
~~~

Expected: a separate package with matching directory and ID. Edit instructions
as needed; do not overwrite the bundled package or add executable files.

Review, simulate and check current compatibility:

~~~bash
uv run --frozen --no-sync ninjarobot-agent skill inspect-path "$phase4_skill_dir/my-project-help"
uv run --frozen --no-sync ninjarobot-agent skill simulate-path "$phase4_skill_dir/my-project-help"   --input '{"prompt":"success"}' --check-live
~~~

Expected: public read tools, bounded limits and explicit fallbacks. Simulation
describes expected steps without calling tools. Resolve missing requirements
before installing.

After reviewing the package, install it. AI-proposed packages require both
explicit confirmation and simulation input:

~~~bash
uv run --frozen --no-sync ninjarobot-agent skill install "$phase4_skill_dir/my-project-help"   --ai-proposed --confirm --simulation-input '{"prompt":"success"}'
uv run --frozen --no-sync ninjarobot-agent skill enable my-project-help
uv run --frozen --no-sync ninjarobot-agent chat --skill my-project-help   "Explain the robot architecture, with sources and limitations."
~~~

Expected: existing packages are preserved. Conversation uses the configured model
and its normal privacy/cost settings. Installation, enabling and every run check
the current catalog. Nothing is installed or started automatically to satisfy a
missing requirement.

Disable or remove only the custom installed package:

~~~bash
uv run --frozen --no-sync ninjarobot-agent skill disable my-project-help
uv run --frozen --no-sync ninjarobot-agent skill remove my-project-help --confirm
~~~

This leaves conversations and bundled packages intact.
See the [Phase 4 walkthrough](../validation/refinement_phase4_walkthrough_260913.md)
for validation and troubleshooting.
