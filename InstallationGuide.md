# NinjaRobotPi5V4 Installation Guide

NinjaRobotPi5V4 is currently in Phase 0 and does not yet provide a runnable
robot agent. These instructions install only the locked developer environment.

## Requirements

- Python 3.11
- `uv`
- Git
- Raspberry Pi 5 hardware is not required for default tests

For live hardware validation, this repository targets the DFRobot DFR0566
expansion HAT. Enable I2C and SPI in `raspi-config`, then reboot. The temporary
servos use the HAT's digital GPIO12/GPIO13 breakouts, so they require this entry
in `/boot/firmware/config.txt` and another reboot:

```ini
dtparam=audio=off
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
```

These digital breakouts are different from the HAT's dedicated PWM0–PWM3
controller at I2C address `0x10`. The VL53L0X uses the pass-through I2C bus and
normally appears at address `0x29`.

Validate the sensor before calibration:

```bash
cd pi5vl53l0x
uv sync --extra dev --frozen
uv run pi5vl53l0x status
uv run pi5vl53l0x test
```

Both commands intentionally return a non-zero exit status for `8191 mm`, the
VL53L0X out-of-range sentinel. Do not run calibration until a flat target
produces valid, repeatable readings. If the device identity is correct but all
readings remain `8191 mm`, power down before checking the sensor window,
target alignment, power, ground, SDA, and SCL; then cold-power-cycle the sensor.

## Developer installation

```bash
git clone <repository-url> NinjaRobotPi5V4
cd NinjaRobotPi5V4
uv sync --dev
uv run python scripts/verify_immutable_drivers.py
uv run pytest -q
```

For the camera library on Raspberry Pi OS, install Picamera2 from `apt` and use
the package bootstrap so the virtual environment can see the matching
system-provided libcamera ABI:

```bash
sudo apt install -y python3-picamera2 python3-libcamera python3-venv
cd pi5camera
./scripts/bootstrap-rpi-standalone.sh --skip-apt
```

For standalone USB microphone capture and local speech-to-text:

```bash
sudo apt install -y libportaudio2 portaudio19-dev cmake build-essential
```

Build whisper.cpp and download its multilingual base model as documented in
`pi5mic/README.md`, then register the executable and model with a user-owned
config such as `~/.config/pi5mic/mic.json`.

Do not install or run hardware extras until the relevant Raspberry Pi checklist
has been approved. Runtime installation, configuration, Ollama setup, provider
credentials, and managed startup will be documented only when those features
are implemented in later phases.
