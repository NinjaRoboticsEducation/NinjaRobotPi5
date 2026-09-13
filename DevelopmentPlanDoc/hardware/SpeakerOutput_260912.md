# Speaker output evaluation

Decision: retain the existing Bluetooth speaker and defer an optional wired
prototype. Read the [shared inventory and decision gates](HardwareOptions_260912.md)
first. Checked on 12 September 2026; no hardware was installed.

## Problem and benefit

Pairing and user audio-session failures can interrupt spoken replies. A wired
alternative might reduce that friction. Measure the actual Bluetooth reconnect
success rate and whether the first words are audible before spending money.
The do-nothing option is to use the existing wizard and independent reconnect
service. Replacing text-to-speech, adding recording or changing volume policy is
outside this option.

## Candidate and proposed connections

A candidate is [Adafruit USB audio adapter 1475](https://www.adafruit.com/product/1475)
with [powered speakers 1363](https://www.adafruit.com/product/1363).
The adapter's page reports testing with Raspbian, not certification of this
project's Pi 5 Lite/Python versions. The speakers take analog audio; USB is their
power connection, not their audio interface. A USB sound adapter is therefore a
separate part of this proposed combination.

Proposed only: Pi USB → sound adapter → analog audio cable → powered speakers.
Use a separately evaluated speaker supply where needed. No GPIO or I2C address
is required. Check connector clearance, cables near wheels, total USB current,
startup peaks and the backup-power system. Exact candidate peak current and
installed reserve are unknown; this blocks a build recommendation.

Continue using the existing IDE `AudioOutput` and PipeWire (the OS audio service).
Do not add another player or let the Agent access hardware. Missing or unplugged
output should retain text and report unavailable, without selecting the microphone
or silently switching to an unexpected loud speaker.

## Compatibility, license and costs

No new Python dependency is selected. Linux audio-device support and the real
service user's PipeWire output selection need a Pi OS Lite test after separate
approval. Neither vendor page establishes this project's complete configuration.
No vendor code is copied; any future driver addition needs a pinned version and
license review.

| Proposed item | Quantity | Cost status |
| --- | --- | --- |
| USB audio adapter | 1 | Vendor listing showed USD 4.95 when checked; not a delivered regional quote. |
| Powered speakers | 1 pair | Current price/stock not established from the retrieved page. |
| Supply, cables and mounting | As required | Unspecified; confirm power rating, shipping, taxes and placement first. |

## Proposed acceptance and rollback

After Gate C approval, test fake disconnects first. Then, at a modest manually
selected volume, measure 20 connect/play cycles, 10 cold starts and ten short
sentences after silence. Require complete first words, no spontaneous playback,
correct output selection and working speech cancellation. Record failures and
latency; these are proposed tests, not completed results. Confirm reminders and
microphone selection still work. Recording needs separate consent.

Rollback: stop playback, restore the previously selected output, unplug only the
approved new device and retain the Bluetooth configuration. No boot-file change,
new power helper or managed-driver change is authorized by this evaluation.
