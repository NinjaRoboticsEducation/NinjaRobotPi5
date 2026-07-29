# Phase 6 Cloud Provider Validation — 2026-07-30

Use this checklist on the Raspberry Pi after installing the Phase 6 source.
Run one provider at a time. OpenAI, Google Gemini, and Anthropic can charge for
requests, so check the account's price and spending limit first.

API means Application Programming Interface, the network service used to talk
to a cloud model. OAuth means a browser-based login that produces a temporary
access token. MCP means Model Context Protocol, the boundary used to add
external tools such as Tavily web search.

Never paste an API key into this document, a chat prompt, a shell command,
Git, a screenshot, an MCP file, or an Agent Skill. The commands below use a
hidden terminal prompt.

## 1. Safe smoke tests — no cloud request and no hardware movement

From the project root:

```bash
cd "$HOME/NinjaRobotPi5"
source .venv/bin/activate

uv sync --frozen --extra hardware --group dev
uv run python scripts/verify_immutable_drivers.py
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest -q
```

Expected result:

- the immutable-driver check says `PASS`
- Ruff, the Python linter and formatter, reports no errors
- mypy, the Python type checker, reports no errors
- pytest reports all tests passed

These commands do not contact a model provider or move a servo.

Set the private configuration path:

```bash
export NINJAROBOT_CONFIG="$HOME/.config/ninjarobot_pi5/config.toml"
test -f "$NINJAROBOT_CONFIG"
```

List the provider capability matrix:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider list
```

Expected result: Ollama, OpenAI, Gemini, and Anthropic appear. Every provider
shows `native_tools: true` and `streaming: true`. Ollama remains current unless
you previously selected a cloud model.

If a cloud provider is missing, copy only its complete provider block from
`config/ninjarobot_pi5.toml.example` into the private configuration. Do not
replace calibrated hardware sections.

## 2. OpenAI communication test

OpenAI API inference supports an API key. A ChatGPT account login or ChatGPT
subscription is not an API credential for NinjaRobotAgent.

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider set-api-key openai
```

Enter the key twice when prompted. Then run:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider status openai

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider health openai

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model list --provider openai
```

Expected result:

- status says `configured: true` but never prints the key
- health says `ready`
- the model list contains only model IDs available to this API account

Choose an exact returned model ID:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  model select OPENAI_MODEL_ID --provider openai
```

## 3. Google Gemini communication test

The recommended Raspberry Pi setup uses a Gemini API key:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider set-api-key gemini

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider health gemini

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model list --provider gemini
```

Expected result: health says `ready`, and the list includes only models whose
official catalog says they support `generateContent`.

Select an exact returned model:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  model select GEMINI_MODEL_ID --provider gemini
```

Optional OAuth test:

1. Install the current Google Cloud CLI by following Google's official Debian
   instructions.
2. Create a Desktop OAuth client and download its JSON file.
3. Put the Google Cloud project ID in the private Gemini provider block:

   ```toml
   project_id = "your-google-cloud-project"
   ```

4. Run:

   ```bash
   uv run --frozen ninjarobot-agent \
     --config "$NINJAROBOT_CONFIG" \
     provider login gemini \
     --client-id-file "$HOME/path/to/client_secret.json"
   ```

Follow the displayed URL and code. The access and refresh credentials are
owned by `gcloud`, not NinjaRobotPi5.

## 4. Anthropic communication test

The recommended Raspberry Pi setup uses an Anthropic API key:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider set-api-key anthropic

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider health anthropic

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" model list --provider anthropic
```

Expected result: health says `ready`, and the list contains the models
available to the selected Anthropic workspace.

Select an exact returned model:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  model select ANTHROPIC_MODEL_ID --provider anthropic
```

Optional OAuth test:

1. Install Anthropic's current official `ant` CLI.
2. Run:

   ```bash
   uv run --frozen ninjarobot-agent \
     --config "$NINJAROBOT_CONFIG" provider login anthropic
   ```

3. Follow the displayed no-browser URL and code.

The adapter asks `ant` for a refreshed bearer token when needed. It does not
copy the profile token into NinjaRobotPi5 configuration.

## 5. Simulation test for each provider

Stop any old service, select the provider/model, and start simulation:

```bash
uv run --frozen ninjarobot-agent service stop

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" service start

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" status

uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" chat \
  "Reply with one short greeting and do not use a tool."
```

Expected result: status names the selected provider/model, and streamed text
appears without a robot tool call. Repeat after selecting each configured
provider.

## 6. Agent Skill and local robot-tool parity

Run the bundled offline Skill:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" chat \
  --skill offline-robot-check \
  "Check the robot's front distance once."
```

Expected result: the model proposes `robot.distance.read`; the local policy
engine and IDE run it in simulation. The Skill remains subordinate to the
same safety prompt and can use only its declared tool.

Repeat this command after selecting Ollama, OpenAI, Gemini, and Anthropic.
Passing all four proves the Skill structure is provider independent.

## 7. MCP web-search parity

Complete the Tavily setup in `InstallationGuide.md` first. Confirm its health:

```bash
uv run --frozen ninjarobot-agent mcp health tavily
uv run --frozen ninjarobot-agent mcp tools tavily
```

Restart the service after an MCP configuration change:

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" service start
```

Run the bundled web Skill:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" chat \
  --skill current-web-answer \
  "Search for the latest official Raspberry Pi 5 news and give me the source links."
```

Expected result: the model proposes the allowlisted
`mcp.tavily.tavily-search` tool, the local registry executes it, and the model
summarizes the untrusted result. Repeat after selecting each provider. A cloud
model does not need a separate Tavily or Skill installation.

## 8. Real read-only device test

Hardware risk: low. This starts real devices but does not authorize servo
movement.

```bash
uv run --frozen ninjarobot-agent service stop
uv run --frozen --extra hardware ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" service start --real

uv run --frozen ninjarobot-agent chat \
  --skill offline-robot-check \
  "Read the front distance sensor once."
```

Expected result: the selected provider requests the same local
`robot.distance.read` tool and returns the measured distance. Repeat once per
provider. If the model only explains the action, mark that model as a
tool-calling failure; do not blame or recalibrate the sensor.

## 9. Confirmed actuator-moving test

Hardware risk: actuator movement. Raise the wheels so they cannot drive the
robot off the table. Keep hands, hair, cables, and loose clothing away from
the wheels. Be ready to press the physical power control or web Emergency Stop.

Start a terminal chat:

```bash
uv run --frozen ninjarobot-agent chat
```

In the chat:

```text
/arm
ARM
Use the robot-behavior-generation workflow to move forward briefly, then stop.
```

Expected result:

- movement starts only after the explicit session arm
- the provider proposes a trusted robot behavior tool
- the IDE applies servo calibration, obstacle monitoring, watchdog, and stop
- the robot returns to Idle after completion

Run this high-risk test only once for each provider that passed simulation and
read-only testing. Use `/disarm` immediately afterward.

## 10. Network loss and recovery

Hardware risk: keep the wheels raised. Begin a short movement, then disconnect
network access or block the selected cloud endpoint.

Expected result: no completed tool is automatically replayed. The software
watchdog stops servo motion if control updates stop. The final robot state and
error remain visible. Restore the network, use `/resume` only if the system is
latched, and use `/arm` again only when you intend to grant new motion.

Optional provider fallback should be tested in simulation first. It is allowed
only before the current request executes a tool and before visible text. It
does not change the saved provider.

## 11. Cleanup and rollback

Stop the service:

```bash
uv run --frozen ninjarobot-agent service stop
```

Remove one provider's selected credentials:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" provider logout PROVIDER_ID
```

To return to local operation:

```bash
uv run --frozen ninjarobot-agent \
  --config "$NINJAROBOT_CONFIG" \
  model select qwen3:4b --provider ollama
```

To disable automatic fallback, keep:

```toml
fallback_providers = []
```

Do not delete servo calibration, module JSON files, or the action ledger to
roll back a model provider. Provider selection is independent of hardware
calibration.

## Pass/fail record

Record the date, Pi model, selected provider/model, authentication method
without any credential value, test step, observed result, and pass/fail.

Phase 6 physical validation passes only when:

- all safe software checks pass
- credentials never appear in output or files other than their approved store
- every selected provider streams text and normalizes a read-only tool call
- the same MCP server and Agent Skills work without provider-specific changes
- no provider repeats a completed action after network failure
- any actuator-moving test stops safely and returns to Idle
