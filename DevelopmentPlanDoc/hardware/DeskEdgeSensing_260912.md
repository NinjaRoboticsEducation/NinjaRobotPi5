# Desk-edge sensing evaluation

Decision: defer physical implementation. Keep the robot stationary on a desk;
the current forward sensor and distance game do not provide fall protection.
Read the [connection inventory and decision gates](HardwareOptions_260912.md).

## Problem and candidate

An edge detector would need to stop movement before a wheel loses support in
all permitted travel directions. The do-nothing option is stationary desktop
use or supervised movement on a suitable floor. A partial detector must not be
marketed as a safe autonomous tabletop mode.

Candidate for later testing: downward-facing VL53L1X boards. The
[ST product information](https://www.st.com/en/imaging-and-photonics-solutions/vl53l1x.html)
describes a typical 27-degree field of view (the cone the sensor observes).
That number alone does not establish a safe mounting or stopping distance.
[Adafruit's board pinout](https://learn.adafruit.com/adafruit-vl53l1x/pinouts)
identifies the default address `0x29`, which conflicts with the current forward
sensor. Sources were checked on 12 September 2026.

## Proposed placement and electrical constraints

Proposed only: downward sensors ahead of the wheel contact points in every
allowed travel direction → separately reviewed address-isolation arrangement →
shared IDE-owned sensor coordination. Number of sensors, tilt, mounting height,
connector, regulated supply, total/peak current and isolation method are unknown.
The exact breakout's electrical requirements must be used, not the bare chip's
requirements. Additional shutdown pins or an I2C multiplexer (a bus selector)
would require their own pin/address allocation and driver evaluation.

Do not change the existing sensor's address or managed library merely to attach
another board. Power, display-bus timing, wheel-controller addressing, backup-power
hardware and enclosure clearance remain compatibility checks.

## Failure behavior and validation proposal

A future IDE safety controller would combine readings and stop relevant movement
on invalid, stale or missing coverage. It must not reuse the game's permissive
hand-distance bands. No model may decide whether an edge is safe in real time.
There is no need to retain pictures, recordings or per-frame sensor history.

First simulate stale values, blocked reads, missing sensors, bus contention,
clock changes, simultaneous stops and direction changes. Before any moving test,
measure sensing and stopping latency. Required margin must exceed:

`maximum speed × total sensing/control delay + measured braking distance + uncertainty margin`

Every value is currently unknown. Test stationary fixtures over known drops on
light, dark, reflective, transparent and uneven surfaces and under different
lighting. Then, only after specific approval, use a restrained robot over a
catch platform; never begin with an unrestrained robot near a desk edge. Require
coverage in every permitted direction and deterministic stop on every injected
failure. A failed or ambiguous case blocks normal use. No such test was run here.

## Compatibility, license, costs and rollback

Pi OS Lite 64-bit/Python 3.11–3.13 support for a selected board library, its license,
pinned version and bus isolation remain unverified. ST/vendor examples are
references, not installed runtime support. No code or firmware was copied.

Parts would include an as-yet-unknown number of sensor boards, isolation hardware,
mounts, protected wiring and the test restraint/platform. There is no confirmed
regional quote, shipping/tax estimate or approved budget. The incomplete geometry
and parts list prevent a meaningful total price.

Rollback of any later prototype must first disable its movement mode, stop through
the existing safety path, and remove hardware only while safely powered down.
Return to stationary desktop use; never bypass a new failed safety sensor to make
motion appear available. This document does not authorize a managed-driver,
boot-file or power-system change.
