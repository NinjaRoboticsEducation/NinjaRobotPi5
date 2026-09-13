# Movable head evaluation

Decision: defer. A physical head is a separate mechanism, power and driver
project. This Phase 5 evaluation authorizes none of those changes. Read the
[shared inventory and gates](HardwareOptions_260912.md).

## Purpose and alternatives

A small head turn could make attention easier to understand. The current silent
faces and optional expression variations already convey attention without moving
parts; retaining them is the do-nothing option. Do not repurpose wheel endpoints
or introduce automatic idle head motion.

A controller candidate for later study is the
[Pololu Micro Maestro six-channel USB controller](https://www.pololu.com/product/1350).
Its [power guide](https://www.pololu.com/docs/0J40/7.a) distinguishes controller
power from servo power. This does not specify a suitable motor or mechanism for
NinjaRobotPi5. Both sources were checked on 12 September 2026.

## Proposed mechanical, electrical and software boundary

Proposed only: Pi USB → dedicated controller → separately powered head actuator,
with a purpose-designed mount, strain relief, travel limits and protected pinch
points. The supply voltage must match the eventual motor. Motor stall current
(the current when it cannot turn), payload mass, lever arm, torque, peak power,
travel angle and emergency power removal are unknown. No wiring drawing is ready
for construction. Do not power an unspecified servo from the Pi's 3.3 V rail.

USB avoids selecting an existing I2C address, but does not solve power reserve,
port availability, cable snagging or the backup-power path. CSI camera clearance
and any moving camera cable require a separate mechanical review. No wheel GPIO
or existing servo endpoint is available to borrow merely because it exists.

A future dedicated driver would own this device only. The IDE would coordinate
its motion with system stop, admission and bounded speed/travel. Agent policy
would authorize a typed `head` action. This is an additive hardware subsystem,
not a replacement of the current Agent → IDE → driver architecture. Loss of
communication must have a defined mechanical safe state; simply stopping command
messages is not proof that a servo has released force.

## Compatibility, licenses and budget

The vendor's controller documentation does not establish the project's current
Pi OS Lite/Python combination. Choose and verify a command interface, permission
model, timeout, firmware version and exact software license before copying or
installing any code. None is selected here.

A parts list needs one controller, a selected actuator, mount/bearings, stops,
guards, power supply, wiring protection and enclosure changes. All prices and
regional availability are unconfirmed; there is no costed complete mechanism or
approved budget. Unknown mechanical and power values block a prototype recommendation.

## Proposed tests and rollback

Begin with fake travel bounds, stale commands, disconnect, command flooding,
cancellation and system stop. After a separately approved mechanical build, use a
secured test fixture with no person in the movement envelope. Measure full-load
current, temperature, travel, stopping time and safe behavior after loss of power
or control. Any real power interruption requires a specific operator test plan.
Pass criteria must be calculated from the chosen mechanism before testing, not
invented afterward. No physical results exist yet.

Rollback: disable the new capability, isolate its separately approved supply and
remove the mechanism while powered down. Keep wheel calibration, endpoint names,
existing managed-driver files and system power controls unchanged.
