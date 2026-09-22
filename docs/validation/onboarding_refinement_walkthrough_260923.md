# Onboarding refinement walkthrough and manual tests

Use this guide to test the refined onboarding interface and Google Calendar MCP
connection. Automatic tests do not certify real devices or a live Google account.
Run Pi commands in your Pi terminal; commands marked **Mac** run on your Mac.

## Scope and preparation

This change adds a welcome screen, bulk reuse of saved hardware settings,
automatic configuration checks, simpler continuation prompts, and guided Google
Calendar authorization over SSH. Existing manual commands and managed drivers
remain available. No installation, boot or systemd changes are part of this update.

1. Use the checkout containing these changes. From its root, `uv run --frozen
   ninjarobot ...` runs that checkout; an installed `ninjarobot` launcher might
   point at another checkout. Check `command -v ninjarobot` if behavior differs.
2. Stop your normally managed Agent before opening standalone hardware tools.
   Do not start another instance if a system service already owns the hardware.
3. Keep a private backup of your existing robot configuration and progress before
   testing changes. Do not copy credentials into the repository or share them.
4. For fresh-user testing, use a spare OS/user profile. Do not delete working
   configuration to simulate a first installation.

## Safe smoke tests: no hardware operations

On the Pi, from the checkout root:

```bash
uv run --frozen ninjarobot onboard --help
uv run --frozen ninjarobot onboard --dry-run
uv run --frozen ninjarobot onboard --simulation
uv run --frozen ninjarobot onboard --status
```

Expected results:

- Help lists the existing resume/status/dry-run/simulation/single-step options.
- Dry-run lists the setup areas and changes no settings.
- Simulation prints rehearsal results without replacing existing real progress.
- Status shows recorded steps, not credentials. A fresh profile has no completed
  steps. Simulated progress from an older version cannot qualify as real setup.

Start the interface and choose Q at the first hardware menu:

```bash
uv run --frozen ninjarobot onboard
```

Expect an ASCII NINJAROBOT title, introduction, phase overview, and clear required
hardware explanations. A fresh user sees **1) Open setup tool** and **Q) Save and
exit**. No Agent starts when you exit. Try invalid input such as `0` or `x`:
it should reprompt without launching a tool. Ctrl+C should save checkpoints and exit.

## Reuse existing module settings

1. With saved standalone hardware configuration, run `ninjarobot onboard`.
2. At the hardware entry, select **2) Apply existing settings for all modules**.
3. Expect valid modules to show a settings summary without opening their tools.
4. Missing or malformed mandatory settings lead to that module's normal setup
   tool. Previously simulated verification is not accepted as a physical test.
5. A valid saved microphone setup is included in bulk reuse. Bluetooth pairing
   remains optional and separate because it uses the existing Bluetooth wizard.
6. After selected hardware steps, expect one integrated preview. Press Enter to
   save and continue. Unrelated provider, service and robot settings are preserved.

Settings checks validate saved configuration; they cannot confirm wiring, wheel
neutral behavior, image quality or sound quality. Reuse only settings whose actual
hardware you have already checked. Supported discovery uses XDG/user paths and
existing project-local fallback locations; an invalid preferred file is shown as
needing repair rather than silently replaced with defaults.

Recovery: choose Q, repair through the existing driver tool, then rerun onboarding.
For a malformed-file test, use a private disposable fixture/profile rather than
editing the only copy of working calibration. Missing-module setup remains mandatory.

## Device communication and explicit media tests

Opening these tools can access real hardware. Camera/microphone tests require
consent from nearby people; do not retain test media.

1. Run `ninjarobot onboard --step display`, select 1, and use the existing display
   tool. On exit, expect checked settings and **Press ENTER to continue**.
2. Repeat with `--step distance`. Use a known target distance; no-target readings
   do not prove successful calibration.
3. Run `--step camera`. There is no onboarding CONSENT phrase. Select capture
   only when you intend to take a test photo, then remove the test photo. Onboarding
   itself does not automatically capture media.
4. Run `--step microphone` if desired. Follow the existing standalone wizard:
   select local whisper.cpp, configure its binary/model, enable Hey Ninja voice
   input using `hey_Ninja.onnx`, then run Doctor. Select a recording test only
   with consent. The onboarding asset check only checks files in a child process;
   it does not run inference, record audio or install a model.
5. Exit a tool without saving on a fresh profile. Expect an incomplete-setting
   message and retry/exit choices rather than a false success.

The integrated launch retains its existing whisper.cpp defaults:
`~/whisper.cpp/build/bin/whisper-cli` and `~/whisper.cpp/models/ggml-base.bin`.
If your standalone microphone uses different locations, supply the existing
launch options when starting onboarding so its final Agent launch uses them:

```bash
ninjarobot --whisper-command /absolute/path/to/whisper-cli \
  --whisper-model /absolute/path/to/model.bin onboard
```

The same global options apply to manual Agent startup. Onboarding does not change
existing manual launch defaults or install large models automatically.

## Actuator and audible tests: opt in

Raise both wheels and remain ready to remove power before servo setup.

1. Run `ninjarobot onboard --step servo` and select 1.
2. The **WHEELS RAISED** precaution remains. Without the required response,
   the servo tool must not open.
3. Calibrate both GPIO12 and GPIO13 using the existing tool. Confirm neutral
   wheel stop physically. Onboarding requires saved neutral calibration for both.
4. Exit the tool. Expect a calibration summary and Enter to continue, without
   the old typed YES confirmation.
5. Buzzer initialization can play a short tone. Run `--step buzzer` only when
   ready for that sound, then confirm the buzzer returns to silence.

Recovery: stop the standalone operation, remove power if movement is unexpected,
and correct calibration before trying real mode. Do not test motion unattended.

## Google Calendar MCP: Mac browser over SSH

This configures the external read-only MCP server. It does not require the Agent
or real hardware to be running. The native Calendar integration is separate.

1. In your Mac browser, open [Google Cloud Console](https://console.cloud.google.com/).
   Select or create a project. Enable **Google Calendar API** in APIs & Services.
2. Configure **Google Auth Platform → Branding/Audience**. If using an External
   app in Testing, add the Google account you will use as a test user. Follow
   [Google's Calendar setup guide](https://developers.google.com/workspace/calendar/api/quickstart/python)
   if the console labels differ.
3. Create an OAuth client with application type **Desktop app**. Download its
   JSON file. This is not a service-account key or an API-key text file.
4. Copy the JSON file privately to the Pi. Enter its Pi filesystem path when
   onboarding asks; a Mac filesystem path does not refer to a Pi file.
5. On the Pi, run:

   ```bash
   ninjarobot onboard --step mcp
   ```

   Select `2` for Google Calendar. You can select multiple tools, for example
   `1,2,3`; onboarding handles each in order. Enter alone skips the optional step.
6. Enter the credential-file path and choose browser location **1) Mac/another
   computer via SSH**.
7. **On your Mac**, open a second Terminal window. Replace the login placeholders
   and run:

   ```bash
   ssh -N -o ExitOnForwardFailure=yes \
     -L 127.0.0.1:8765:127.0.0.1:8765 YOUR_PI_USER@YOUR_PI_HOST
   ```

   Enter your SSH password if requested. Keep this window open. A quiet terminal
   after login is normal. If your normal SSH connection uses a custom port or
   identity file, use those same SSH options here.
8. Return to onboarding on the Pi, press Enter, then open its **new** authorization
   link in the Mac browser. Log in as the configured test user and grant read-only
   access. Do not share either the authorization link or the redirected URL.
9. The browser redirects to `127.0.0.1:8765`. The tunnel forwards this Mac-local
   request to the Pi. Expect the browser to say authorization was received and
   the Pi to immediately acknowledge receipt and validate Google access.
10. Expect MCP success after one bounded events request. Zero events is valid.
    No event contents should appear in onboarding. The working preset is saved
    only after validation. Close the forwarding terminal with Ctrl+C afterward.

If your browser runs directly on the Pi, choose **2) Pi desktop** and open the link
there. No SSH tunnel is needed.

### Calendar recovery checks

| Symptom | Action and expected outcome |
| --- | --- |
| Mac redirects to localhost but Pi keeps waiting | Start the forwarding command on the Mac, not the Pi. Keep it open; retry with a new link if the old attempt timed out. |
| Forwarding says address already in use | Close the previous forwarding process using that port. Do not kill an unrelated service blindly. Retry the command. |
| Access denied or unverified/testing app blocked | Check the selected Google account is an allowed test user and the Desktop client belongs to the enabled project. Respect organization restrictions. |
| Wrong JSON/client type | Download a Desktop OAuth client, transfer it to the Pi, and retry with that file. |
| Browser succeeds but API validation fails | Check Calendar API is enabled and read-only permissions were granted. Previously working MCP credentials remain intact. |
| Authorization expires | Onboarding waits up to five minutes with periodic feedback. Choose retry and use the newly generated URL. |
| Reconnect later fails | Run the MCP step again. Existing working entries remain; unsuccessful candidate credentials are removed. |

Test cancellation and denial using a disposable/test Google account if available.
Expect cleanup and retry guidance, not a stuck listener or disclosure of tokens.
A live Google account check remains a manual test; automated tests use mocks.

## Provider, optional tools and launch regression

1. Enter invalid provider/model menu numbers such as `0` or `-1`. Expect a reprompt.
2. Try an invalid replacement API key in a test profile. Expect validation failure;
   the previous stored key must remain. Environment keys override file-backed
   keys and must be updated in their environment rather than silently replaced.
3. Skip all MCP tools. Existing manual/custom MCP configuration must remain.
4. If selected, authorize Notion using its displayed port-8766 forwarding guide.
   Interactive authorization has a longer allowance than normal runtime requests.
5. Skip ngrok. Choose **Exit onboarding**: no Agent/web service should start.
6. Rerun and choose **Start NinjaRobot Agent → simulation**. Expect the existing
   chat interface and authenticated same-Wi-Fi HTTPS startup. Check that remote
   access does not become an unauthenticated HTTP interface.
7. Verify chat still uses arrows to edit, Enter to send, Shift+Enter or Alt+Enter
   (Option+Enter on Mac) to add lines, and Esc then Enter as a compatibility fallback.
   `/help` should still work.
8. Test real mode only after physical checks and with raised wheels. Invalid or
   missing mandatory configuration must block real launch. Existing service-mode
   conflict protections remain authoritative.
9. If ngrok is selected, distinguish **configured** from a running, validated
   public endpoint. Validation happens through the existing final launch reporting.

## Power-risk tests

None are required for this change. Do not run shutdown, UPS power-cut, boot-file,
or sudoers tests as part of onboarding verification. No power helper changed.

## Automated evidence and pass/fail checklist

- [x] Final full repository regression suite: **1,065 passed** in 45.58 seconds.
- [x] Driver suites in separate processes: buzzer 68, camera 27, display 65,
  microphone 92, servo 134, distance sensor 71; total 457.
- [x] Driver baseline: 222 managed files unchanged relative to the authorized baseline.
- [x] Workspace driver-source verification, compileall, Ruff lint/format,
  mypy (121 source files), CLI help and dry-run.
- [x] Real local Calendar MCP subprocess tested with Google transport mocked.
- [x] OAuth state/PKCE regression, callback receipt/denial, settings validation,
  bulk reuse, checkpoint preservation, credential rollback and microphone containment.
- [ ] Fresh and returning-user Pi walkthrough completed by owner.
- [ ] Live Google Calendar connection using Mac SSH forwarding.
- [ ] Optional tools and authenticated web interface manually checked.
- [ ] Physical component checks, with explicit consent and actuator precautions.

The first full run exposed microphone import contamination; the repaired isolated
probe passed the subsequent full suite. Sandbox subprocess restrictions required
running the full hardware-free suite outside the sandbox. Remaining warnings are
existing Starlette/httpx and standalone-driver audioop deprecations.

Wiki ingestion, semantic review and map/fingerprint updates were not performed,
as requested. Existing registered sources are unchanged; the new manual versions
are ready for the owner's review after testing.

## Rollback and troubleshooting

Exit onboarding with Q or Ctrl+C; completed driver settings remain available to
manual commands. Stop an Agent you explicitly launched through its normal service
manager. Close only the SSH forwarding terminal you opened for authorization.
If needed, restore your private configuration backup with the Agent stopped;
do not regenerate calibration or delete credentials blindly. Existing Calendar
credential files are retained when a validated replacement is saved, so review
and revoke obsolete grants deliberately through your Google account rather than
removing working credentials during testing.

See the [current installation guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-23-02/InstallationGuide.md)
and [MCP manual](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-23-02/NinjaRobot_MCP_Skill.md).
