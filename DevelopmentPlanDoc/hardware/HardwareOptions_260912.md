# Phase 5 hardware evaluation — 12 September 2026

This is an evaluation, not permission to buy, wire or install hardware. Phase 5
adds an optional game using existing devices. It does not add a movable head,
touch sensor or fall-prevention system.

## Decisions

| Option | Decision | Reason and next evidence needed |
| --- | --- | --- |
| [Speaker output](SpeakerOutput_260912.md) | Retain the existing Bluetooth path; defer a wired prototype | Existing software already supports it. Measure reconnect and first-word playback on the owner's speaker before adding another device. |
| [Touch input](TouchInput_260912.md) | Defer; candidate and interface documented | Potentially convenient, but placement, current consumption, accidental activation and Pi 5 permissions need evidence. |
| [Movable head](MovableHead_260912.md) | Defer | No approved mechanism, motor load, power budget or emergency-stop design exists. |
| [Desk-edge sensing](DeskEdgeSensing_260912.md) | Defer physical work; keep wheels stationary on desks | A forward distance reading cannot establish protection against a fall. Geometry and stopping-distance tests are missing. |

These are engineering recommendations for the plan's Gate B (option evaluation).
They are not a claim that the owner has accepted a purchase or prototype. Gate C
requires a specific design, budget and approval; Gate D requires supervised test
results before normal use. B05's documentation deliverable can finish with deferral.

## Current connection inventory

This inventory comes from `config/ninjarobot_pi5.toml.example` and the IDE config
schema. GPIO means the Pi's numbered electrical input/output connections. I2C is
a shared two-wire device bus; SPI is a separate high-speed display bus. Confirm
actual wiring and private configuration before allocating anything new.

| Existing component | Configured connection | Consequence for proposed additions |
| --- | --- | --- |
| Buzzer | GPIO27 | Reserved; do not reuse for touch. |
| Display | SPI0 device 0; control GPIO4/5/6 | Reserve SPI0 signal pins too (GPIO8–11). Avoid extra electrical loads on these connections. |
| Default wheel endpoints | GPIO12/13, using the existing servo library | Never reuse wheel endpoint names for a head. Extra configured endpoints may reserve more pins. |
| Distance sensor | I2C1, address `0x29` | A second default-address distance board would conflict. |
| Optional DFR0566 servo controller | I2C1, configured address `0x10` | Existing addressing and motion meanings stay unchanged. |
| I2C1 signals | GPIO2/3 | Shared bus access must remain coordinated. |
| Camera | CSI (camera ribbon connection) | Preserve privacy indication, connector and enclosure clearance. |
| Microphone | Configured audio device; actual USB topology varies | An added USB audio device must not change the selected microphone. |
| Speaker | Bluetooth through IDE audio output | No new GPIO assignment; preserve the service user's audio session. |
| Backup power / UPS | Exact installed board, bus address and electrical budget are not established by this checkout's config | Inspect board documentation and actual wiring before any build. Do not assume an unused address or spare current. |

Pi 5 USB power availability depends on the supply: the official documentation
explains the 600 mA limit with a 3 A supply and the higher 1.6 A peripheral budget
with a suitable 5 A supply. This is a total budget, not a promise for an extra
speaker or motor. The installed backup-power path must also sustain the load.
[Official Raspberry Pi hardware documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)
was checked on 12 September 2026.

## Evaluation method

The proposed weights remain: user benefit 25%, compatibility 25%, reliability
25%, installation effort 15%, total cost 10%. Scores below are engineering
judgments on a 1–5 scale, where higher is better. They are not measurements.
Unknown values prevent a weighted total and a build recommendation.

| Option | Benefit | Compatibility | Reliability | Installation | Cost | Evidence behind judgment |
| --- | --- | --- | --- | --- | --- | --- |
| Keep Bluetooth | 4 | 5 | Unknown | 4 | 5 for reuse | Spoken replies and the wizard already exist; no new purchase. Owner-specific reconnect remains a physical test. |
| Wired audio candidate | 3 | Unknown | Unknown | 3 | Unknown | Removes radio pairing, but adds cables, an output device and power load. Upstream older Pi support is not this Pi's acceptance. |
| Touch candidate | 3 | Unknown | Unknown | 2 | Unknown | Could shorten a common interaction; placement and accidental triggers remain unresolved. |
| Movable head | 2 | Unknown | Unknown | 1 | Unknown | Expressive benefit is plausible, but a complete mechanism and power design are absent. |
| Edge sensors | 5 if proven | Unknown | Unknown | 1 | Unknown | Preventing falls would be valuable; partial coverage or false confidence overrides that score. |

## Cost, licenses and compatibility

No region or purchase budget has been confirmed. Do not treat a USD catalog price
as a delivered price in Japan or another country. The option pages list required
parts and unknown costs, shipping, tax, power and enclosure needs. No order was
placed. All cited pages were checked on 12 September 2026; future developers must
recheck availability and specifications.

The target is Raspberry Pi OS Lite 64-bit and the project's Python range
`>=3.11,<3.14`. Candidate upstream examples do not certify that combination.
No candidate library or firmware is copied, installed or added to the lock file.
Datasheet copyright remains with its publisher. Any later copied code, library,
firmware or board design needs its exact license and version recorded before use.

## Validation and rollback

Desk research is complete enough to document the choices and blockers. Physical
prototype tests, purchasing, wiring and power measurements were not performed.
The reversible action today is to retain the existing hardware. See each option
for the proposed tests and the [Phase 5 walkthrough](../../docs/validation/refinement_phase5_walkthrough_260912.md)
for the software that actually exists.
