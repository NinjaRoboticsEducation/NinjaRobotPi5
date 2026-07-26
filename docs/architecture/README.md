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
