# Touch input evaluation

Decision: defer a prototype until placement, wiring and electrical measurements
are reviewed. See the [shared inventory](HardwareOptions_260912.md). This is a
proposal checked on 12 September 2026, not a supported new input device.

## Problem and behavior

A discoverable touch target could request a harmless acknowledgement without
opening a terminal. The do-nothing option is to retain web and terminal buttons.
Do not use touch as approval for motion, recording, account changes or shutdown.
A stuck touch must not queue repeated actions.

Candidate: [Adafruit AT42QT1010 momentary touch board](https://www.adafruit.com/product/1374),
with its [manufacturer's breakout guide](https://learn.adafruit.com/adafruit-capacitive-touch-sensor-breakouts?view=all).
Its momentary output is a better match for press/release events than a toggle
that stays on. Proposed only: an insulated upper-shell touch target → touch
board → an available 3.3 V-compatible input on the Pi, with shared ground.
Do not choose a pin from appearance alone. The [inventory](HardwareOptions_260912.md)
reserves the existing buses, display, wheels and buzzer.

## Electrical and software conditions

Power the candidate only according to the exact board revision's documentation;
verify that its output stays within Pi input limits. A nominal 3.3 V design is
proposed. Maximum board current, startup transient, cable length, placement near
motor wiring and final free GPIO are unmeasured. These unknowns block wiring.
No I2C address is needed for this candidate.

A future single-device adapter should read edge events through a selected,
pinned GPIO library; the IDE should own debounce (ignoring rapid contact chatter)
and the bounded acknowledgement. The Agent receives a typed event, not direct
GPIO access. The [Linux GPIO character-device interface](https://docs.kernel.org/userspace-api/gpio/chardev.html)
is a reference for the OS boundary, not a chosen Python package. Resolve the
actual Pi 5 chip/line names and permissions; do not rely on historical chip indexes.

Proposed logic: ignore input until one clean release after startup; require
50 ms stable contact; emit one event per press; require release before another.
Long contact means held, never repeating approval. Sensor loss reports unavailable
and emits no synthetic press. No personal-data retention is needed.

## Compatibility, license, parts and validation

Pi OS Lite 64-bit/Python 3.11–3.13 compatibility is not yet verified for a chosen
GPIO package. Its version and license remain a prerequisite; no dependency or
board design has been copied. Required parts are one touch board, an insulated
pad/enclosure, suitable leads and mounting. Prices, regional supply, shipping,
tax and assembly costs are unknown; there is no approved spending amount.

After prototype approval, test fake chatter, held input, disconnect, restart and
lost events. Then require 100 intentional touches to produce one event each,
no duplicate action while held, and no false action during supervised nearby
motor/electrical-noise trials. Try dry/wet hands and gloves; document limitations.
No movement should be triggered by touch. Test captures only if separately approved.

Rollback: disable the optional input, stop its reader, power down through the
normal operator process and remove the approved board. Restore the original
configuration. Do not edit existing wheel or display drivers for this option.
