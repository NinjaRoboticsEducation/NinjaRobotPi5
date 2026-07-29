# Robot Behavior Generation

1. Decide whether the request needs an expression or physical movement.
2. Use `robot.behavior.execute_expression` when no servo movement is needed.
3. Use `robot.behavior.execute_movement` only when trusted runtime state says motion is armed.
4. Build a compact draft with `name`, `description`, and ordered `stages`.
5. In each stage, use direct fields such as `face`, `text`, `melody`, `tone`, `movement`, `drive_targets`, `duration_seconds`, and `wait_seconds`.
6. Use at most one of `face` or `text` in a stage because they share the display.
7. Use at most one of `melody` or `tone` in a stage because they share the buzzer.
8. Prefer `movement` with `move_forward`, `move_backward`, `turn_left`, `turn_right`, or `stop`. Use `drive_targets` only for a deliberate custom movement and only with logical roles listed by the tool.
9. Give every generated movement a finite `duration_seconds`. End a multi-stage movement with `movement: stop` when that makes the stop explicit.
10. If validation rejects a draft before execution, correct the named field and submit one new tool call. Do not repeat an action whose physical outcome is unknown.
11. Treat generated behavior as transient. Use `robot.behavior.save_user` only when the user explicitly requests saving and the current request is confirmed.

Expression example:

```json
{
  "name": "happy_hello",
  "description": "Show a happy greeting in two stages.",
  "stages": [
    {
      "face": "happy",
      "tone": {
        "frequency_hz": 880,
        "duration_seconds": 0.2,
        "volume": 64
      },
      "duration_seconds": 2
    },
    {
      "text": "Hello Ninja",
      "melody": "happy",
      "duration_seconds": 2
    }
  ]
}
```

Movement example:

```json
{
  "name": "exciting_forward",
  "description": "Move forward briefly with an exciting face and melody.",
  "stages": [
    {
      "face": "exciting",
      "melody": "exciting",
      "movement": "move_forward",
      "duration_seconds": 1
    },
    {
      "movement": "stop",
      "duration_seconds": 0.1
    }
  ]
}
```
