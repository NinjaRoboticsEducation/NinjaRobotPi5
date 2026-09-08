# F02 emergency-stop dispatch — 7 September 2026

The first feature from the approved refinement plan is implemented and software
validated. F02 gives trusted stop commands a route around ordinary queued work.
The corresponding curated-wiki update is prepared but not applied. This is an
intermediate feature record, not completion of phase 0A or the whole refinement.

Baseline checkout: `b4812e06bdbcaf5ce6176cff14e79d5de1c817ee`. The checkout was clean
before implementation. There are no new dependencies, managed-driver changes,
configuration migrations, account changes or deployment actions.

## What changed and why

- IDE `scheduler.py`: trusted interrupt dispatch cancels competing queued/running
  work and rejects new overlapping work while stop is active. Stop dispatch does
  not wait for ordinary queue capacity, workers, resource locks or cancellation
  cleanup. Partially acquired locks are released if their task is cancelled.
- IDE `engine.py`: only registered `behavior.stop`, `servo.stop`, and `buzzer.stop`
  with emergency classification and empty arguments use the interrupt path. Existing
  result recording, deadlines and duplicate-request handling remain. Ordinary
  conflicting requests can return `ACTION_STOP_IN_PROGRESS`, meaning they did not
  execute and need a deliberate new request after recovery.
- Agent `web_control.py`: revoke direct-control, chat and voice motion permissions
  and camera permission before Emergency Stop dispatch. Signal the movement's
  cancellation token without joining an earlier movement command's queue.
- IDE `robot.py`: start system device cleanup alongside idle/expression cleanup,
  so those presentation tasks cannot delay dispatch to motors. Cleanup exceptions
  remain reported. IDE `behavior_runtime.py` and idle cleanup avoid cancelling an
  already-cancelling task again, which could interrupt its cleanup.

The five added tests cover full queues with running and waiting actions, duplicate
and concurrent stops, admission during stop, partially acquired locks, blocked
ordinary cleanup, browser dispatch behind an occupied movement-command lock, and
motor-stop dispatch while expression cleanup remains blocked. They use events,
fake devices and temporary state; they do not operate robot hardware.

## Compatibility and limits

Stop names, inputs and successful result formats remain compatible. Independent
resources remain available. Stop is not a normal retry of the interrupted action.
The scheduler requests cancellation; a misbehaving driver can still delay cleanup
or leave an uncertain physical outcome. No physical stopping-time guarantee is
claimed. Existing IDE adapter timeouts remain unchanged.

F01 raw-servo safety, F03 legacy hardware ownership, F04 disabled-device/pin checks,
and all later phases remain unfinished. Do not treat F02 as approval for expanded
live autonomy or proof that every movement entry is safe. No existing driver hash
or authorization record was changed.

## Executed validation

Run these from the robot repository root. `--no-sync` uses the existing locked
environment without installing or removing packages.

```bash
uv run --frozen --no-sync python scripts/verify_immutable_drivers.py
uv run --frozen --no-sync python scripts/verify_workspace_driver_sources.py
uv run --frozen --no-sync python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
uv run --frozen --no-sync pytest -q -m 'not hardware and not provider_live'
```

Results: both driver verifiers passed (222 managed files, six checkout-sourced
libraries, 55 previously authorized repairs); compilation, lint, formatting and
type checks passed. Baseline: 588 tests passed. After F02: **593 tests passed**.
The existing Starlette warning about its HTTP test-client dependency remained;
this change neither introduced it nor changes that dependency. Tests with hardware
or live-provider markers were explicitly excluded; this checkout's collected
suite had no such marked tests. Managed-driver suites were not rerun because no
managed driver changed.

Final documentation checks passed: `git diff --check`, local file/heading links
in the current proposed manuals and changed documentation, semantic-plan validation,
and `git apply --check` for the proposed pointer patch. The combined proposed wiki
pages, source pointers and code fingerprints passed the project knowledge verifier
using in-memory proposed content; no wiki page or pointer was applied for that check.
Current applied-page strict lint reports zero errors, warnings or suggestions.
The live project knowledge check still reports the five pending implementation
fingerprints listed below; this is not reported as a completed publication gate.

## Documentation and wiki gate

New complete source versions preserve registered originals:

- [Development guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07-03/DevelopmentGuide.md)
- [Installation guide](../../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-09-07-02/InstallationGuide.md)
- [Development log](../../ninjarobot_pi5_wiki/raw/notes/ninjarobotpi5/2026-09-07-03/DevelopmentLog.md)

They add only F02's behavior, operational feedback, limitations and validation.
The MCP tutorial and third-party notices were reviewed: external-tool interfaces,
dependencies, licenses and service setup are unchanged, so no new versions are
needed for F02. README and the main refinement plan point to this progress record.

The [exact proposed wiki diff](refinement_f02_wiki_260907.diff) updates ten pages:
four add short F02 explanations; the others update source versions and AI review
records. The [semantic plan](refinement_f02_wiki_260907.yaml)
has expected page hashes and validates successfully. No page is marked human
verified or physically tested. Current source material outside the added F02
sections is preserved; old source records are retained.

Link validation found two sibling tutorial links in the first proposed development
guide that needed rebasing. Because that proposal was already registered, its
original was preserved and a corrected `2026-09-07-03` guide was registered instead.
The superseded `2026-09-07-02/DevelopmentGuide.md` is not selected by this plan or
the proposed current-document map. The durable plan above also has a working copy
under the wiki's ignored `.llmwiki/plans/`; the durable copy is included for review
and future checkout recovery.

The [prepared pointer/map patch](refinement_f02_pointers_260907.patch) makes the
three new manuals current and updates the five reviewed implementation hashes.
It is prepared alongside the semantic diff, not applied prematurely. Until the
wiki approval step is complete, the existing READMEs retain current manual links,
and `python scripts/wiki.py check` correctly reports five implementation files
needing knowledge review. Do not blindly refresh those fingerprints to hide this
pending gate. The current curated pages remain the previously applied versions.

After the owner approves this exact diff: revalidate expected hashes, apply the
semantic plan with the wiki launcher, review/apply the prepared pointer patch,
run wiki checks/search, and record the real results here. No further code approval
is being requested for the already-approved refinement scope.

## Safe smoke checks — no movement

- [ ] Repeat the software commands above in the intended environment. Expected:
  passing checks with no hardware access. Rollback: stop validation on a failure
  and retain its output; do not install packages or change a driver to hide it.
- [ ] After wiki publication, run `python scripts/wiki.py check` and
  `python scripts/wiki.py lint --strict`. Expected: current pointers, matching
  evidence and no wiki errors. Rollback: retain source history and repair the
  exact failed mapping/page through the normal reviewed workflow.

## Device communication checks — manual, not performed

- [ ] With wheels raised and no motion command issued, an operator can inspect
  existing service health and send Emergency Stop through the connected controller.
  Expected: stop feedback or an honest device/cleanup error. Stop may change
  display, buzzer, sensor and media state; no new media capture is requested.
  Rollback: leave the robot stopped if any device is unavailable; inspect the
  reported error before a deliberate confirmed resume.

## Actuator-moving checks — manual, not performed

- [ ] Only after the remaining applicable foundation repairs and operator approval,
  raise wheels, clear the area and keep power removal within reach. Start one
  existing bounded movement, then press Emergency Stop. Expected: outputs stop,
  motion permissions revoke, and interrupted work does not restart on its own.
- [ ] Repeat through the existing controller during an ordinary expression and
  through the approved voice/chat route when already enabled. Expected: the same
  stop boundary. Measure actual stopping time; software event deadlines are not
  a physical measurement. Do not deliberately hang a live hardware driver.
- [ ] Recovery remains deliberate: correct the cause, confirm resume, re-arm only
  if appropriate, and issue a new command. Rollback on unexpected motion: remove
  power, stop the service, and preserve the evidence before further diagnosis.

## Power-risk checks — not required and not performed

No shutdown, UPS, boot, sudoers or power-control code changed. Do not run a power-off
command for this feature's automated or manual validation.

## Code rollback

Before any later deployment, preserve private configuration and data. If the feature
needs rollback, stop the robot/service under operator control and revert only this
reviewed patch using version control. Preserve unrelated changes, original manuals
and source records. Re-run software validation before restarting an earlier build;
that build still has the audited queue issue. No rollback or live restart was run
in this task.
