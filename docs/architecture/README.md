# Architecture records

The approved architecture is defined in
`../../NinjaRobotPi5V4_ImplementationPlan.md`. Architecture decision records
capture later choices without silently changing that plan.

The V4 dependency direction is:

```text
user -> ninjarobot_pi5_agent -> ninjarobot_pi5_ide -> immutable pi5 drivers
```

Reverse imports are prohibited. The agent may use only IDE capability
descriptors and execution results; it may not import any `pi5*` package.

Phase 4 cross-device integration remains inside `ninjarobot_pi5_ide`:

```text
validated behavior asset
  -> BehaviorRunner
  -> RobotAssembly
  -> MotionController / SystemSafetyController
  -> shared IDE device boundaries
  -> managed pi5 drivers
```

Behavior assets contain logical roles such as `left_motor`, never GPIO or I2C
driver construction. `RobotAssembly` resolves those roles from private V4
configuration and shares one instance of each device. `ninjarobot-ide-tool`
calls this assembly; it does not invoke standalone Pi5 CLI processes for normal
behavior execution.

The agent phase may list or propose these IDE behaviors later, but any
AI-proposed private action must pass the same strict schema, simulation
preview, user save confirmation, and real-motion confirmation used by the
manual IDE tool.
