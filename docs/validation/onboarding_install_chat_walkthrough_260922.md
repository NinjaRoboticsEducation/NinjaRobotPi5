# Guided setup, curl installation, and chat walkthrough

This guide explains the new installation and onboarding flow and provides safe,
step-by-step checks for a Raspberry Pi 5. Run hardware checks only on the robot
and keep the existing manual setup commands available as a recovery path.

## Install from a clean Raspberry Pi

The GitHub page URL ending in `/install.sh` returns a web page, not the script.
Use the raw-file URL. This one-line command downloads the bootstrap and asks it
to install the reviewed public release branch:

```bash
curl -fsSL https://raw.githubusercontent.com/NinjaRoboticsEducation/NinjaRobotPi5/public_v07/install.sh | bash -s -- --ref public_v07
```

For a higher-assurance release, replace both `public_v07` values with the same
published 40-character commit ID. The bootstrap clones into
`~/NinjaRobotPi5`, prints the resolved commit, verifies the required installer
files, and then runs the existing installer. Add `--dry-run` after `--ref
public_v07` to preview without creating the destination.

The previous clone workflow remains supported:

```bash
git clone https://github.com/NinjaRoboticsEducation/NinjaRobotPi5.git
cd NinjaRobotPi5
./install.sh --dry-run
./install.sh
```

The hardware installer creates `~/.local/bin/ninjarobot`. If the command is not
found in the current SSH session, reconnect or run:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

The installer does not start the Agent, pull an Ollama model, move motors, or
capture camera or microphone data.


## Branch selection and custom installation directories — 23 September 2026

The bootstrap resolves the selected branch, tag, or full commit to a commit
before checkout. This fixes the tracking-branch guessing conflict with
`--detach` when installing a non-default branch. If a branch and tag share a
name, use `refs/heads/NAME` or `refs/tags/NAME` in `--ref` to disambiguate.
Use the same published revision in the raw URL and `--ref` when changing releases.
The downloaded bootstrap cannot infer which URL curl used.

The default is `~/NinjaRobotPi5`, regardless of the current directory. To install
inside a custom folder, run these commands in your Pi SSH terminal:

```bash
mkdir -p "$HOME/Ninja"
cd "$HOME/Ninja"
curl -fsSL https://raw.githubusercontent.com/NinjaRoboticsEducation/NinjaRobotPi5/public_v07/install.sh | bash -s -- --ref public_v07 --install-dir "$PWD/NinjaRobotPi5"
```

Add `--dry-run` to preview without writing files. The destination must be an
absolute path that does not exist, and its parent must already exist. Spaces
are supported when the path is quoted. Changing directories alone does not
change the default destination. Existing clone plus `./install.sh` installation
remains supported.

The confirmation prompt reads the controlling terminal, so piping the script
from curl does not consume or hide your answer. Without a terminal, installation
fails with guidance; `--yes` remains an explicit way to accept the previewed OS
changes. An existing `ninjarobot` launcher pointing elsewhere is refused; this
flow does not migrate an existing installation or its services.

## Preview or resume onboarding

Preview the sequence without changing files, hardware, services, or accounts:

```bash
ninjarobot onboard --dry-run
```

Run an offline rehearsal. Simulated results are labelled `simulated` and never
count as physical verification:

```bash
ninjarobot onboard --simulation
```

Start or resume the real guided setup:

```bash
ninjarobot onboard
ninjarobot onboard --resume
```

Progress is stored without credentials at
`~/.local/state/ninjarobot_pi5/setup-progress.json` with owner-only
permissions. Inspect it through the CLI:

```bash
ninjarobot onboard --status
```

To revisit one setup area, use commands such as:

```bash
ninjarobot onboard --step servo
ninjarobot onboard --step microphone
ninjarobot onboard --step provider
ninjarobot onboard --step mcp
ninjarobot onboard --step web-access
```

## Complete required hardware setup

The wizard opens each existing driver tool through the IDE hardware ownership
lock. It does not reimplement the driver setup.

1. **Buzzer:** choose **Init**, listen for the short test beep, confirm it
   becomes silent, and exit.
2. **Display:** choose **Init**, **Show Text**, and **Clear**. Confirm readable
   orientation and brightness.
3. **Distance sensor:** choose **Health Check**, **Single Read**, and
   **Calibrate** with a target at a measured distance. `8191` means no target.
4. **Servos:** raise both wheels and keep power removal within reach. Type the
   exact confirmation, calibrate GPIO12 and GPIO13 separately, and verify both
   wheels stop at neutral.
5. **Camera:** obtain consent from nearby people, run **Setup** and **Doctor**,
   and perform a temporary capture only if everyone agrees. Remove test media.

The wizard requires a saved component configuration and your explicit success
confirmation. A deferred or failed required step prevents a real-hardware
launch. Simulation remains available.

## Configure optional audio

Bluetooth speaker setup uses the existing headless pairing wizard. It can also
offer the existing independent reconnect service. No test sound is played
without your action.

Microphone setup is optional and requires explicit recording consent. In the
opened `pi5mic` tool choose:

1. **Run setup wizard**.
2. Profile **standalone**.
3. STT backend **whisper_cpp**.
4. The installed whisper.cpp executable and model defaults.
5. Always-on input only if wanted, using the bundled `hey_Ninja.onnx` model.
6. **Doctor** before exiting.

## Select an AI provider

Choose Ollama, Google, OpenAI, or Anthropic. Cloud keys are entered twice with
terminal echo disabled and saved through the existing private secret store.
The wizard discovers models, asks you to choose one, checks provider health,
and saves the selection only after validation.

For Ollama, install a local model first if the list is empty, for example:

```bash
ollama pull qwen3:4b
```

The wizard shows whether a local model has an accepted Raspberry Pi benchmark.
Run the existing benchmark before relying on an unbenchmarked model:

```bash
ninjarobot benchmark ollama --model qwen3:4b
```

## Configure optional external MCP tools

The optional-tools screen accepts multiple comma-separated selections and
configures them one at a time. All three are external MCP providers:

- **Tavily Search:** enter a Tavily API key. The reviewed preset exposes only
  `tavily_search`.
- **Google Calendar:** provide a Google Desktop OAuth client JSON file and
  authorize read-only access through the displayed SSH loopback flow. The
  bundled external stdio server exposes only `list_today_events` and omits
  descriptions, attendees, meeting links, and unnecessary identifiers.
- **Notion:** authorize the official hosted Notion MCP server. From a Mac, run
  the displayed `ssh -L` command before opening the browser URL. The reviewed
  preset exposes only Notion search and fetch.

Credentials and OAuth tokens are stored in owner-only files and are never
written to `mcp.toml`, logs, or progress state. Failed validation leaves the
prior MCP configuration active and offers retry or skip. The Agent service will
never open an interactive Notion login; rerun `ninjarobot onboard --step mcp`
to reauthorize.

## Choose web access and launch

ngrok is optional. If selected, create an account at <https://ngrok.com/>, enter
the authtoken twice, and let the existing remote-access service validate the
public endpoint when the Agent starts. Pairing remains required.

If ngrok is skipped, the Agent starts the existing authenticated HTTPS service
for devices on the same Wi-Fi. The default address is:

```text
https://ninjarobotpi5.local:8443/
```

At completion, choose **Start NinjaRobot Agent** and then simulation or real
hardware. Simulation is the default. Real mode remains blocked until all five
required hardware steps pass. The wizard waits for the existing service,
reports verified ngrok or local HTTPS state, and enters chat. Choosing **Exit
Onboarding** saves progress and leaves the Agent stopped.

Leaving chat does not stop an Agent that you started. Stop it explicitly with:

```bash
ninjarobot service stop
```

## Use multiline terminal chat

The chat header displays this guidance:

> Arrow keys: edit your prompt | Enter: send | Shift+Enter or Alt+Enter
> (Mac: Option+Enter): new line | If unsupported: Esc, then Enter | /help:
> commands

Some Mac terminal profiles use the word **Option** instead of **Alt**. If the
terminal sends Option+Enter as an ordinary Enter, press and release `Esc`, then
press `Enter`. Pasted multiline text stays in the editor until ordinary Enter
sends it.

## Curl repair validation — 23 September 2026

The repair passed 1,034 repository tests, including 44 installer tests, and
457 managed-driver tests in separate processes. Ruff lint and formatting,
mypy, compilation, driver integrity/source checks, Bash syntax, documentation
links, and whitespace checks passed. ShellCheck was unavailable. No dependency
or managed driver changed. The earlier validation below records the previous
checkpoint.

After the repair is published to `public_v07`, test on a disposable Raspberry
Pi OS image:

1. Safe smoke: run the custom-folder curl example above with `--dry-run`.
   Expect the chosen revision and absolute destination, with no new checkout.
2. Installation/interface: run without `--dry-run`. Expect a resolved commit,
   the existing installation plan, and a usable `INSTALL` prompt over SSH.
   Enter anything else to cancel before OS changes. The downloaded checkout
   remains available; retry through its `./install.sh`.
3. On the disposable image, rerun the checkout installer and type `INSTALL`.
   Expect the usual installation checks and launcher pointing to this checkout.
   An existing launcher owned by another installation must be refused.
4. Actuator-moving tests: not required for this repair; do not move wheels.
5. Power-risk tests: no power-off test. Follow any existing installer reboot
   guidance only after installation completes and the robot is safely stopped.

Rollback for a completed OS installation is restoration of the disposable image
or your prior OS backup. Keep existing installations, private configuration,
and services intact while testing a new destination. A changed checkout path
alone does not relocate an existing systemd deployment.

## Automated validation completed

The final hardware-free gate passed on 22 September 2026:

- 1,021 repository tests passed. The only warning is the existing Starlette
  `TestClient` deprecation notice.
- The six managed-driver suites passed independently: 68 buzzer, 27 camera,
  65 display, 92 microphone, 134 servo, and 71 distance-sensor tests (457
  total).
- Immutable-driver verification passed for 222 tracked files and the existing
  56 authorized repairs. All six workspace driver-source checks passed.
- Ruff lint and formatting checks passed for 463 files; mypy passed for 120
  source files; compilation, lock validation, shell syntax, and
  `git diff --check` passed.
- Agent and IDE source distributions and wheels built successfully. The Agent
  wheel contains the onboarding, terminal-input, OAuth, and external Calendar
  MCP modules plus both `ninjarobot` and `ninjarobot-agent` entry points.
- Installer tests exercise streamed dry-run, successful staged delegation,
  argument forwarding, exact-commit verification and mismatch refusal,
  destination refusal, launcher idempotence, and staging cleanup.

ShellCheck is not installed in the development environment, so it was not run.
No automated test contacted a provider or MCP account, opened a tunnel, changed
system services, moved hardware, or captured camera/microphone data. Those checks
remain the manual acceptance steps below.

## Manual acceptance tests

### Safe smoke checks

1. Run `ninjarobot onboard --dry-run` from a directory outside the repository.
   Expect a complete preview and no new progress file.
2. Run `ninjarobot onboard --simulation`. Expect every result to say
   `simulated`; expect no hardware, account, or service activity.
3. Run `ninjarobot onboard --status`. Expect no secret values.
4. Start simulation through onboarding, enter text, move left and right through
   characters, use up and down across lines, add a line with Shift+Enter or
   Option+Enter, and press Enter to send. Expect no `^[[A`-style text.
5. Enter `/help`, then `/exit`. Expect help text and a reminder that the Agent
   continues independently.

If any step starts hardware or an account flow, stop the Agent and report the
unexpected action; the dry-run and simulation checks have failed.

### Device communication checks

Run one step at a time. Keep the Agent stopped. Expect the matching saved
configuration and operator confirmation after each successful test:

```bash
ninjarobot onboard --step buzzer
ninjarobot onboard --step display
ninjarobot onboard --step distance
ninjarobot onboard --step camera
ninjarobot onboard --step microphone
```

For camera and microphone checks, obtain consent and remove any test media.
Stop and retry the individual step if the tool reports a device or permission
error.

### Actuator-moving check

> [!CAUTION]
> Raise both wheels, keep hands clear, and stay ready to disconnect power.

Run `ninjarobot onboard --step servo`. Confirm each neutral point and stop. If a
wheel continues moving, exit the tool, disconnect motor power, inspect the
calibration, and do not start real mode.

Expected result: both wheels stop at their saved neutral points and the wizard
records operator verification. The immediate rollback is to exit the tool and
remove motor power.

### Power-risk check

Onboarding has no power-off or reboot step. Choose **Exit Onboarding**, then run
`ninjarobot service status`. Expect no new Agent process and no shutdown or
reboot request. Do not test a real power-off command as part of this acceptance
run.

If the Pi reports undervoltage, throttling, or an unexpected shutdown request,
leave real mode disabled, stop the Agent, inspect the power supply and X1208
wiring, and repeat only the safe smoke checks after the fault is corrected.

### Provider and MCP checks

1. Run `ninjarobot onboard --step provider`. Expect a dynamic model list and a
   successful health result without the key appearing on screen.
2. Run `ninjarobot onboard --step mcp`, select only one tool, and complete its
   account flow. Expect reviewed tools to be discovered before configuration is
   saved.
3. Repeat for the other tools. An empty read result is valid; a missing or
   renamed tool must fail closed.
4. Run `ninjarobot mcp list`. Expect all selected tools to appear as external
   servers without credentials.

### Network-access checks

1. Skip ngrok, start the simulated Agent, and open the reported HTTPS URL from
   a phone on the same Wi-Fi. Expect pairing before controller access.
2. Try a fresh unpaired browser. Expect access to be denied until pairing.
3. Configure ngrok and start simulation. Expect a validated public HTTPS URL or
   a clear failure plus authenticated local fallback.
4. Exit onboarding instead of starting. Expect no new Agent process.

### Installation regression checks

After this change is published to the referenced branch or commit, use a
disposable clean Raspberry Pi OS image to run the curl command with `--dry-run`,
then install. Expect the resolved Git revision, existing installer review
prompt, reboot guidance, and a working `ninjarobot --help`. Also repeat the
clone plus `./install.sh` workflow to confirm backward compatibility.

## Recovery

- Resume a partial setup with `ninjarobot onboard --resume`.
- Retry one area with `ninjarobot onboard --step STEP`.
- Use `./install.sh --check` inside the checkout to inspect installation health.
- Stop the Agent before standalone hardware tools with
  `ninjarobot service stop`.
- Revoke provider, ngrok, Google, Tavily, or Notion credentials in the
  corresponding account if a credential may have been exposed.
- Never forward port 8443 through a router; use authenticated same-Wi-Fi HTTPS
  or the existing ngrok pairing boundary.
