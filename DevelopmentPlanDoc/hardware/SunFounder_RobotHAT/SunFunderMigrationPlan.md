# SunFounder Robot HAT Migration Plan

**Document ID:** `DOC-HW-MIGRATION-261024-ROBOTHAT-V1`  
**Companion Document:** [NinjaPi5Compatibility.md](./NinjaPi5Compatibility.md)  
**Target Platform:** Raspberry Pi 5 (8 GB) running NinjaRobotPi5  
**Migration:** DFRobot DFR0566 IO Expansion HAT → SunFounder Robot HAT (v5)  
**Author:** Antigravity AI Pair Programmer  
**Date:** 2026-10-24  

---

## Table of Contents

1. [Migration Overview](#1-migration-overview)
2. [Prerequisites & Safety Checklist](#2-prerequisites--safety-checklist)
3. [Phase 1: Hardware Decommissioning & Physical Installation](#phase-1-hardware-decommissioning--physical-installation)
4. [Phase 2: Operating System & Audio Configuration](#phase-2-operating-system--audio-configuration)
5. [Phase 3: Display & Sensor Adaptation](#phase-3-display--sensor-adaptation)
6. [Phase 4: AT32F413 MCU Servo Backend Development](#phase-4-at32f413-mcu-servo-backend-development)
7. [Phase 5: Battery Telemetry & Power Management](#phase-5-battery-telemetry--power-management)
8. [Phase 6: Motion Control & Servo Calibration](#phase-6-motion-control--servo-calibration)
9. [Phase 7: Integration Testing & Validation](#phase-7-integration-testing--validation)
10. [Phase 8: Documentation & Cleanup](#phase-8-documentation--cleanup)
11. [Risk Register & Mitigation](#risk-register--mitigation)
12. [Complete GPIO Allocation Map](#complete-gpio-allocation-map)
13. [Migration Timeline Summary](#migration-timeline-summary)

---

## 1. Migration Overview

### 1.1 What Are We Doing?

We're replacing the DFRobot DFR0566 IO Expansion HAT (a simple GPIO breakout board) with a SunFounder Robot HAT v5 (a feature-rich robotics controller with an onboard microcontroller, audio system, and power management). This isn't just swapping a board — it's upgrading the entire hardware foundation of NinjaRobotPi5.

```
BEFORE (DFR0566 Architecture)              AFTER (SunFounder Robot HAT Architecture)
                                                    
┌─────────────────────┐                    ┌──────────────────────────┐
│ Geekworm X1208 UPS  │                    │ SunFounder 2S Li-ion     │
│ (External Battery)  │                    │ Battery Pack (7.4V)      │
└────────┬────────────┘                    └──────────┬───────────────┘
         │                                            │
┌────────▼────────────┐                    ┌──────────▼───────────────┐
│ Raspberry Pi 5      │                    │ SunFounder Robot HAT v5  │
│ + DFR0566 HAT       │                    │ ├── AT32F413 MCU (I2C)   │
│ ├── 2 Servos        │                    │ ├── 12 PWM Channels      │
│ │   (GPIO 12 & 13)  │        ═══►        │ ├── 4 Motor Ports        │
│ ├── Buzzer (GPIO 27)│                    │ ├── I2S Speaker + Mic    │
│ ├── Display (SPI)   │                    │ ├── 4-ch ADC + Battery   │
│ └── Sensor (I2C)    │                    │ └── Buttons + LED        │
│                     │                    │                          │
│ BT Speaker (ext.)   │                    │ ┌─ Raspberry Pi 5 ─────┐ │
│ USB Mic (ext.)      │                    │ │ 8 Servos on P0–P7    │ │
└─────────────────────┘                    │ │ Display, Sensor, Cam  │ │
                                           └─┴───────────────────────┘
```

### 1.2 What Changes?

| Aspect | Before (DFR0566) | After (Robot HAT) | Change Type |
|---|---|---|:---:|
| Power source | Geekworm X1208 UPS + 27W USB-C | Robot HAT 7.4V battery | **Replace** |
| Servo count | 2 (GPIO 12, 13) | 8 (P0–P7 via MCU I2C) | **Expand** |
| Servo driver | Pi5 RP1 hardware PWM | AT32F413 MCU at `0x14` | **New Backend** |
| Audio output | External Bluetooth speaker | Onboard I2S 2030 speaker | **Replace** |
| Audio input | USB PnP microphone | USB mic + onboard MEMS mic | **Add Option** |
| Display RST pin | GPIO 5 | GPIO 17 | **Rewire** |
| Battery monitoring | None | ADC Ch4 over I2C | **New Feature** |
| Physical buttons | None | USR (GPIO 25), RST (GPIO 16) | **New Feature** |
| Status LED | None | User LED (GPIO 26) | **New Feature** |

### 1.3 What Stays the Same?

These subsystems require **zero changes** — they connect directly and work as-is:

- ✅ **ST7789V Display** SPI data path (MOSI=GPIO 10, SCLK=GPIO 11, CS=GPIO 8)
- ✅ **VL53L0X Distance Sensor** I2C bus (SDA=GPIO 2, SCL=GPIO 3, address `0x29`)
- ✅ **Passive Buzzer** on GPIO 27 (Digital 27 on Robot HAT)
- ✅ **OV5647 Camera** CSI ribbon to Pi 5
- ✅ **Display DC pin** on GPIO 4 (Digital 4 on Robot HAT)
- ✅ **Display Backlight** on GPIO 6 (BSY pin on SPI header)

### 1.4 Multi-Hardware Profile System & Full Backward Compatibility

The migration does **not** abandon or break previous hardware choices. The codebase maintains full support across three distinct hardware profiles:

1. **SunFounder Robot HAT (v5) [Target Profile]:**
   - 2S 7.4V battery pack (Geekworm X1208 retired), onboard 5V/5A buck regulator.
   - Onboard 2.5W 2030 chamber speaker driven over I2S with GPIO 12 amplifier enable.
   - Up to 12 servos on PWM ports P0–P11 via AT32F413 MCU (`0x14`).
   - ST7789V Display Reset wired to Digital 17 (GPIO 17).
2. **DFRobot DFR0566 IO Expansion HAT + Geekworm X1208 UPS [Legacy Profile]:**
   - Dual-power: X1208 UPS battery + 27W USB-C.
   - 2 servos on GPIO 12 & 13 driven via Pi 5 RP1 hardware PWM.
   - External Bluetooth speaker for voice output.
   - ST7789V Display Reset wired to GPIO 5.
3. **General PCA9685 12/16-Channel PWM Expansion Board [External Controller Profile]:**
   - External UBEC / battery pack to PCA9685 `V+` screw terminal (ideal for 4–16 heavy MG996R servos).
   - Up to 16 servos on channels 0–15 driven via pre-existing `pca9685` backend at I2C address `0x40`.
   - USB or Bluetooth speaker.

All core `pi5servo` driver functions stay untouched; the active profile is selected during onboarding or switched on-demand via the IDE.

---

## 2. Prerequisites & Safety Checklist

### 2.1 Hardware You Will Need

| Item | Quantity | Purpose |
|---|:---:|---|
| SunFounder Robot HAT v5 | 1 | Main expansion board |
| SunFounder 2S 18650 Battery Pack (XH2.54 3-pin) | 1 | Sole power source (7.4V, 2000 mAh) |
| TowerPro MG996R servo | Up to 2 | High-torque joints (arm shoulder/base) |
| TowerPro MG90S / MG90D servo | Up to 8 | Lightweight joints (head, gripper, wheels) |
| Dupont jumper wires (F-F) | ~6 | Display DC, RST, BL signal connections |
| USB Type-C cable | 1 | Battery charging |
| Elevated work platform or block | 1 | Suspend wheels/arms during calibration |

### 2.2 Software Prerequisites

| Requirement | How to Verify | Notes |
|---|---|---|
| NinjaRobotPi5 repo cloned | `ls ~/NinjaRobotPi5` | All code must be at current HEAD |
| `uv` package manager | `uv --version` | Required for running project tools |
| Python 3.11+ | `python3 --version` | Standard Pi 5 Bookworm OS |
| I2C enabled | `sudo raspi-config` → Interfaces → I2C | Must be ON for MCU communication |
| SPI enabled | `sudo raspi-config` → Interfaces → SPI | Must be ON for display |
| SSH access | `ssh user@ninjarobotpi5.local` | Remote work during headless setup |

### 2.3 Pre-Flight Safety Checklist

> [!CAUTION]
> **Complete ALL items before touching any hardware.**

- [ ] Robot is powered off (`sudo poweroff`)
- [ ] USB-C power cable is **physically disconnected**
- [ ] Geekworm X1208 battery is disconnected (if applicable)
- [ ] Robot chassis is elevated on a block — wheels and arms in the air
- [ ] You have a second computer nearby for SSH access
- [ ] You have read and understood the [NinjaPi5Compatibility.md](./NinjaPi5Compatibility.md) report
- [ ] You have a backup of `~/.config/ninjarobot_pi5/config.toml`
- [ ] You have a backup of `~/.config/pi5disp/display.json`
- [ ] You have a backup of `~/.config/pi5servo/servo.json`
- [ ] Git working tree is clean (`git status --short` shows no uncommitted changes)

---

## Phase 1: Hardware Decommissioning & Physical Installation

### Objective
Physically remove the old DFR0566 HAT and Geekworm X1208 UPS, then mount the SunFounder Robot HAT onto the Raspberry Pi 5.

### Hardware Risk Level: 🟡 MODERATE
Incorrect header alignment can short pins. Static discharge can damage ICs.

### Tasks

#### 1.1 Decommission Geekworm X1208 UPS

1. Ensure the X1208 is fully powered off and disconnected.
2. Unscrew the X1208 mounting hardware from the Pi 5 underside.
3. Remove pogo pin connectors or GPIO header connections.
4. Store the X1208 safely — it is no longer needed.

#### 1.2 Remove DFR0566 HAT

1. Disconnect all wires from DFR0566 headers:
   - Servo connectors from D12 and D13
   - Buzzer connector from D27
   - Display wires from the GPIO breakout
   - VL53L0X I2C wires
2. Carefully lift the DFR0566 off the 40-pin header.
3. Inspect the 40-pin header for bent pins. Straighten if needed.

#### 1.3 Mount SunFounder Robot HAT

1. **Ground yourself** — touch a grounded metal surface.
2. Align the Robot HAT's 40-pin socket with the Pi 5's 40-pin header.
3. Press down firmly and evenly until fully seated.
4. Verify alignment: Pin 1 (3V3) on the Pi must mate with the correct corner of the HAT.

#### 1.4 Connect Battery

1. Insert the SunFounder 2S 18650 battery pack's XH2.54 3-pin connector into the Robot HAT's **Power Port**.
2. **Do NOT turn on the power switch yet.**
3. Verify the battery connector is fully seated and oriented correctly (reverse polarity protection exists, but proper orientation is still best practice).

### Validation Gate
- [ ] Robot HAT is firmly seated on the 40-pin header
- [ ] No bent pins visible
- [ ] Battery pack connected but power switch OFF
- [ ] Old X1208 and DFR0566 physically removed and stored

### Rollback
If the Robot HAT does not seat properly or if pins appear damaged, stop and inspect. The Pi 5 can be used without any HAT for basic testing.

---

## Phase 2: Operating System & Audio Configuration

### Objective
Configure the Raspberry Pi 5 operating system to recognize the Robot HAT's I2S audio system (speaker + MEMS microphone) and verify basic I2C communication with the onboard MCU.

### Hardware Risk Level: 🟢 LOW
Software-only changes. No hardware manipulation after initial power-on.

### Prerequisites
- Phase 1 complete
- SSH access available

### Tasks

#### 2.1 Initial Power-On & I2C Verification

1. Slide the Robot HAT power switch **ON**.
2. Wait for the Pi 5 to boot. SSH in:
   ```bash
   ssh YOUR_USERNAME@ninjarobotpi5.local
   ```
3. Verify the AT32F413 MCU is visible on I2C bus 1:
   ```bash
   i2cdetect -y 1
   ```
   **Expected:** Address `0x14` appears in the scan results. If the VL53L0X sensor is also connected, `0x29` should also appear.

4. If `0x14` does not appear:
   - Power cycle the Robot HAT (slide switch OFF, wait 5 seconds, ON).
   - Check that I2C is enabled: `sudo raspi-config` → Interface Options → I2C → Yes.
   - Verify the HAT is fully seated on the header.

#### 2.2 Enable I2S Audio Overlay

1. Edit the boot configuration:
   ```bash
   sudo nano /boot/firmware/config.txt
   ```
2. Add or ensure these lines are present (not duplicated):
   ```ini
   dtparam=i2s=on
   dtoverlay=hifiberry-dac
   ```
3. Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).
4. Reboot:
   ```bash
   sudo reboot
   ```

#### 2.3 Verify Audio Output

1. SSH back in after reboot.
2. Check that the I2S sound card is recognized:
   ```bash
   aplay -l
   ```
   **Expected:** A card named `snd_rpi_hifiberry_dac` (or similar) appears.

3. Enable the speaker amplifier:
   ```bash
   # Set GPIO 12 HIGH to power the amplifier
   pinctrl set 12 op dh
   ```

4. Play a test tone:
   ```bash
   speaker-test -D default -c 1 -t sine -f 440 -l 1
   ```
   **Expected:** A 440 Hz tone plays from the onboard 2030 speaker.

5. Set GPIO 12 LOW to disable the amplifier when done:
   ```bash
   pinctrl set 12 op dl
   ```

#### 2.4 Verify Battery LED Indicators

- Both battery LEDs should be ON if the battery is above 7.6V (freshly charged).
- If only one LED is on, the battery voltage is between 7.15V and 7.6V.
- If both are off, charge the battery immediately via the Type-C port.

### Validation Gate
- [ ] `i2cdetect -y 1` shows address `0x14`
- [ ] `aplay -l` shows the HiFiBerry DAC sound card
- [ ] Test tone plays audibly from the onboard speaker
- [ ] Battery LEDs indicate healthy charge level
- [ ] System boots normally with the new HAT

### Rollback
The I2S overlay can be removed by deleting the added lines from `/boot/firmware/config.txt` and rebooting. No permanent changes are made in this phase.

---

## Phase 3: Display & Sensor Adaptation

### Objective
Reconnect the ST7789V display and VL53L0X distance sensor to the Robot HAT, with the critical change of moving the display Reset pin from GPIO 5 (which is the MCU reset on the Robot HAT!) to GPIO 17.

### Hardware Risk Level: 🟡 MODERATE
Incorrect wiring of the display Reset pin to GPIO 5 would cause the MCU to reset unexpectedly during display initialization.

### Prerequisites
- Phase 2 complete
- Display and sensor hardware available

### Tasks

#### 3.1 Wire the ST7789V Display

Connect the display to the Robot HAT as follows:

| Display Pin | Wire to Robot HAT | GPIO | Notes |
|---|---|:---:|---|
| VCC (3.3V) | SPI Header: `3V3` | — | Display power |
| GND | SPI Header: `GND` | — | Ground |
| MOSI (Data) | SPI Header: `MO` | GPIO 10 | SPI data (**same as before**) |
| SCLK (Clock) | SPI Header: `SCK` | GPIO 11 | SPI clock (**same as before**) |
| CS (Chip Select) | SPI Header: `CS` | GPIO 8 | Active-low select (**same as before**) |
| DC (Data/Command) | Digital `4` header: Signal pin | GPIO 4 | (**same as before**) |
| **RST (Reset)** | **Digital `17` header: Signal pin** | **GPIO 17** | ⚠️ **CHANGED from GPIO 5!** |
| BL (Backlight) | SPI Header: `BSY` | GPIO 6 | Backlight PWM (**same as before**) |

> [!WARNING]
> **DO NOT connect the display Reset wire to GPIO 5!** On the Robot HAT, GPIO 5 is hardwired to the AT32F413 MCU's reset pin. Pulling it low during display initialization would reset the microcontroller, killing all servo PWM signals and I2C communication.

#### 3.2 Update Display Configuration

Run the display interactive tool and update the Reset pin setting:

```bash
cd ~/NinjaRobotPi5
uv run --frozen --no-sync pi5disp display-tool
```

1. Select **`1. Init`** (Set up display module & pin config).
2. Enter the pin values:
   - `dc_pin` = `4` (unchanged)
   - `rst_pin` = **`17`** ← **This is the critical change!**
   - `backlight_pin` = `6` (unchanged)
3. Return to the main menu.
4. Select **`4. Ball Demo`** to verify the display renders correctly.
5. Select **`9. Exit`** to save settings to `~/.config/pi5disp/display.json`.

#### 3.3 Connect the VL53L0X Distance Sensor

Connect the sensor to the Robot HAT's I2C interface:

| Sensor Pin | Wire to Robot HAT | Notes |
|---|---|---|
| VCC | I2C Header: `3V3` or `VCC` | 3.3V power |
| GND | I2C Header: `GND` | Ground |
| SDA | I2C Header: `SDA` | GPIO 2 (**same as before**) |
| SCL | I2C Header: `SCL` | GPIO 3 (**same as before**) |

**Alternative:** Use the SH1.0 QWIIC/STEMMA QT port if your sensor has a compatible cable.

#### 3.4 Verify Sensor Communication

```bash
uv run --frozen --no-sync pi5vl53l0x sensor-tool
```

1. Select **`5. Health Check`** — confirms I2C address `0x29` is responsive.
2. Select **`4. Calibrate`** — place a flat surface 100 mm away, enter `100`.
3. Select **`q. Exit`**.

#### 3.5 Verify Buzzer

Connect the buzzer to Digital 27 header (Signal=GPIO 27, VCC=5V, GND=GND):

```bash
uv run --frozen --no-sync pi5buzzer buzzer-tool
```

Select **`2. Beep`** to confirm GPIO 27 buzzer output works.

### Validation Gate
- [ ] Display renders Ball Demo correctly with RST on GPIO 17
- [ ] `~/.config/pi5disp/display.json` shows `"rst_pin": 17`
- [ ] VL53L0X health check passes at address `0x29`
- [ ] Sensor calibration stores offset successfully
- [ ] Buzzer beeps on GPIO 27
- [ ] No MCU resets observed (check `dmesg` for I2C errors)

### Rollback
If the display does not work with GPIO 17, verify wiring continuity. The `rst_pin` setting can be reverted in `~/.config/pi5disp/display.json` to `5` to restore old behavior (only valid when using the old DFR0566 HAT).

---

## Phase 4: AT32F413 MCU Servo Backend Development

### Objective
Create a new `pi5servo` backend driver that communicates with the SunFounder Robot HAT's AT32F413 MCU over I2C to control PWM channels P0–P7 (expandable to P0–P11) for servo motors.

### Hardware Risk Level: 🟢 LOW (development phase)
Code development and testing. Live hardware testing is deferred to Phase 6.

### Prerequisites
- Phase 3 complete
- Understanding of the MCU I2C protocol (see [OnboardMCU.md](./OnboardMCU.md))

### Tasks

#### 4.1 Create the Backend Module

Create a new file: `pi5servo/src/pi5servo/core/backends/sunfounder_robot_hat.py`

This module must implement the same interface as existing backends (e.g., `dfr0566.py`, `pca9685.py`):

**Core Responsibilities:**
1. Open I2C bus 1 at address `0x14`.
2. Configure Timer 0 (channels P0–P3) and Timer 1 (channels P4–P7) for 50 Hz servo frequency:
   - Set period to `4095` (registers `0x44` for Timer 0, `0x45` for Timer 1).
   - Calculate prescaler: `72,000,000 / (4095 + 1) / 50 - 1 = 350`.
   - Write prescaler to registers `0x40` (Timer 0) and `0x41` (Timer 1).
3. Convert servo pulse width (in microseconds, typically 500–2500 µs) to an "On Value":
   - `on_value = pulse_us / 20000 * (period + 1)` → For period 4095: `on_value = pulse_us * 4096 / 20000`.
   - Example: 1500 µs center → `on_value = 1500 * 4096 / 20000 = 307`.
4. Write the On Value to the appropriate channel register (`0x20` + channel).
5. Implement MCU reset recovery: if an I2C `IOError` occurs, pulse GPIO 5 LOW for 10 ms then HIGH for 10 ms, wait 10 ms, then retry.

**I2C Protocol Reference:**

```python
# Example: Set channel 0 to 1500 µs (center position)
from smbus2 import SMBus

ADDR = 0x14
PERIOD = 4095
FREQ = 50

bus = SMBus(1)

# Step 1: Configure Timer 0
bus.write_word_data(ADDR, 0x44, PERIOD)         # Timer 0 period = 4095
prescaler = int(72_000_000 / (PERIOD + 1) / FREQ) - 1  # = 350
bus.write_word_data(ADDR, 0x40, prescaler)      # Timer 0 prescaler = 350

# Step 2: Set servo pulse
pulse_us = 1500  # Center position
on_value = int(pulse_us * (PERIOD + 1) / 20000)  # = 307
bus.write_word_data(ADDR, 0x20, on_value)       # Channel 0 = 307
```

#### 4.2 Register the Backend

Update `pi5servo/src/pi5servo/core/backends/__init__.py` to register the new backend alongside existing ones:

```python
# Add to the backend registry
"sunfounder_robot_hat": SunFounderRobotHatBackend,
```

#### 4.3 Add MCU Reset Utility

Implement a `reset_mcu()` function that:
1. Sets GPIO 5 as output.
2. Drives GPIO 5 LOW for 10 ms.
3. Drives GPIO 5 HIGH for 10 ms.
4. Waits 10 ms for MCU to reinitialize.

> [!IMPORTANT]
> **Architecture Boundary:** Per AGENTS.md, the `pi5servo` driver owns its device directly. The `reset_mcu()` function belongs in this backend, not in `ninjarobot_pi5_agent` or at a higher abstraction level.

#### 4.4 Simplified Endpoint Aliases & Endpoint Validation

1. **Update `ServoEndpoint` in `pi5servo`:**
   In `pi5servo/src/pi5servo/core/endpoint.py`, expand channel range validation and add intuitive, simplified aliases:
   ```python
   # In ServoEndpoint.__post_init__:
   if self.kind == "hat_pwm" and not 0 <= self.value <= 15:
       raise ValueError("HAT/expansion PWM channels must be in the range 0..15")

   # In parse_servo_endpoint(raw):
   # Accept "pwm0", "pwm1", etc.
   if text.startswith("pwm") and text[3:].isdigit():
       return ServoEndpoint(kind="hat_pwm", value=int(text[3:]))
   # Accept "p0", "p1", etc. (matching physical Robot HAT silkscreen!)
   if text.startswith("p") and text[1:].isdigit():
       return ServoEndpoint(kind="hat_pwm", value=int(text[1:]))
   # Retain "hat_pwm0" for canonical compatibility
   if text.startswith("hat_pwm") and text[7:].isdigit():
       return ServoEndpoint(kind="hat_pwm", value=int(text[7:]))
   ```
   **User Benefit:** When calibrating or moving servos, the user can simply type `pwm0` or `p0` instead of the cumbersome `hat_pwm0`!

2. **Update IDE Supported Endpoints:**
   In `ninjarobot_pi5_ide/src/ninjarobot_pi5_ide/config.py`, update `SUPPORTED_SERVO_ENDPOINTS` to include channels 0 through 11 (up to 15) in both canonical and simplified alias formats:
   ```python
   EXPANSION_PWM_ENDPOINTS = tuple(f"pwm{i}" for i in range(16))
   CANONICAL_PWM_ENDPOINTS = tuple(f"hat_pwm{i}" for i in range(16))
   SUPPORTED_SERVO_ENDPOINTS = (
       *DEFAULT_SERVO_ENDPOINTS,
       *CANONICAL_PWM_ENDPOINTS,
       *EXPANSION_PWM_ENDPOINTS,
   )
   ```

#### 4.5 Add Pin Mapping & Hardware Profile Tool in `ninjarobot_pi5_ide`

Create a dedicated hardware profile switcher in `ninjarobot-ide-tool`:
```bash
uv run ninjarobot-ide-tool hardware set-profile <profile_name> [--apply]
```
Supported profiles:
- `sunfounder_robot_hat`:
  - Sets display `rst_pin = 17`, `dc_pin = 4` in `~/.config/pi5disp/display.json`.
  - Sets servo backend `sunfounder_robot_hat` in `~/.config/pi5servo/servo.json`.
  - Sets `servo_roles`: `left_motor = "pwm0"`, `right_motor = "pwm1"`, `head_pan = "pwm2"`, `head_tilt = "pwm3"` in `~/.config/ninjarobot_pi5/config.toml`.
  - Enables I2S audio with GPIO 12 amplifier enable.
- `dfr0566`:
  - Sets display `rst_pin = 5`, `dc_pin = 4`.
  - Sets servo backend `hardware_pwm` (GPIO 12/13).
  - Sets `servo_roles`: `left_motor = "gpio12"`, `right_motor = "gpio13"`.
  - Routes audio to Bluetooth speaker.
- `pca9685`:
  - Sets servo backend `pca9685` at I2C address `0x40`.
  - Sets `servo_roles`: `left_motor = "pwm0"`, `right_motor = "pwm1"`.

#### 4.6 Authorize Managed Driver Changes (`AGENTS.md` Policy)

Because `pi5servo` is a managed driver package with an immutable baseline, all file additions (`sunfounder_robot_hat.py`) and modifications (`endpoint.py`, `__init__.py`) must be recorded in `docs/validation/authorized_driver_changes.json`:
```bash
uv run python scripts/verify_immutable_drivers.py \
  --record-authorized pi5servo/src/pi5servo/core/endpoint.py \
  --reason "Support SunFounder Robot HAT PWM channels 0-11 and pwm/p aliases" \
  --authorized-by "Project owner" \
  --authorized-on 2026-10-24
```

#### 4.7 Unit Testing (Off-Hardware)

Write unit tests that:
- Mock I2C bus reads/writes for address `0x14`.
- Verify `parse_servo_endpoint("pwm0")` and `parse_servo_endpoint("p0")` return `ServoEndpoint(kind="hat_pwm", value=0)`.
- Verify correct prescaler (350) and period (4095) calculations for 50 Hz.
- Verify pulse-to-On Value conversion is accurate.
- Verify MCU reset sequence timing (GPIO 5 toggling).

### Validation Gate
- [ ] `sunfounder_robot_hat.py` exists and follows existing backend interface
- [ ] Backend registered in `__init__.py`
- [ ] `uv run --frozen python -m compileall -q pi5servo/src` passes
- [ ] `uv run --frozen ruff check pi5servo/` passes
- [ ] `uv run --frozen ruff format --check pi5servo/` passes
- [ ] `uv run --frozen mypy pi5servo/src` passes
- [ ] `uv run --frozen pytest pi5servo/tests/` passes (mocked I2C)
- [ ] Managed driver verifier passes: `uv run --frozen python scripts/verify_immutable_drivers.py`

### Rollback
The new backend file can be removed entirely without affecting existing GPIO-based or DFR0566 servo backends. No existing files are modified beyond adding a registry entry.

---

## Phase 5: Battery Telemetry & Power Management

### Objective
Implement a real-time battery voltage monitoring service that reads the SunFounder Robot HAT's onboard ADC (Channel 4) over I2C and alerts the user before battery voltage drops to dangerous levels.

### Hardware Risk Level: 🟢 LOW
Read-only I2C queries to the MCU's ADC. No actuator movement.

### Prerequisites
- Phase 4 complete (I2C communication established)

### Tasks

#### 5.1 Implement Battery Voltage Reader

Create a module that:
1. Reads ADC Channel 4 (battery level) from the MCU:
   ```python
   # ADC Channel 4 register address: 0x130000 (3-byte format)
   bus.write_word_data(0x14, 0x13, 0)  # Write 0x13 + 0x0000
   msb = bus.read_byte(0x14)
   lsb = bus.read_byte(0x14)
   raw_value = (msb << 8) | lsb  # 12-bit ADC value (0–4095)
   ```
2. Convert raw ADC to battery voltage:
   ```python
   # Voltage divider ratio: 200K / 100K = 3:1
   va4 = raw_value / 4095.0 * 3.3
   battery_voltage = va4 * 3.0
   ```
3. Map voltage to battery state:

   | Battery Voltage | State | LED Indicator | Action |
   |---|---|---|---|
   | ≥ 7.6V | Healthy | 2 LEDs ON | Normal operation |
   | 7.15V – 7.6V | Fair | 1 LED ON | Log warning |
   | 6.9V – 7.15V | Low | 1 LED ON | Alert user, reduce servo activity |
   | < 6.9V | Critical | Both OFF | Safe shutdown sequence |

#### 5.2 Integrate with IDE Health Monitoring

- Create a periodic background probe (polling every 30 seconds).
- Expose battery voltage via the IDE's status reporting.
- Trigger a graceful shutdown warning at 6.9V.
- Never initiate actual shutdown without user confirmation (hardware safety boundary).

#### 5.3 Charging Detection

- Read GPIO 23 (CHG indicator) to detect if the Type-C charger is connected.
- Display charging state in the IDE status.

### Validation Gate
- [ ] Battery voltage reading matches physical LED indicator state
- [ ] Voltage calculation produces values in the 6.0V–8.4V expected range
- [ ] Warning triggers correctly at threshold voltages (testable by draining battery)
- [ ] Charging detection works when Type-C is plugged in

### Rollback
Battery telemetry is an additive feature. Removing it has zero impact on servo or display functionality.

---

## Phase 6: Motion Control & Servo Calibration

### Objective
Connect servos to PWM ports P0–P7, perform hardware zeroing, and calibrate each channel using the `pi5servo servo-tool`.

### Hardware Risk Level: 🔴 HIGH
**Live servo movement.** Motors will spin. Arms will swing. Ensure the robot chassis is elevated with all appendages clear of obstacles and people.

### Prerequisites
- Phase 4 complete (AT32F413 backend functional)
- Phase 5 complete (battery monitoring active — you'll need to know if power sags)
- Physical servos available and servo horns loosely attached

### Tasks

#### 6.1 Servo Power Budget Decision

Before connecting servos, choose your configuration based on the [NinjaPi5Compatibility.md](./NinjaPi5Compatibility.md) power audit:

| Configuration | Max Simultaneous | Internal Power? | Notes |
|---|:---:|:---:|---|
| 8× MG90S only | ✅ All 8 | ✅ Yes | Safest. Recommended starting point. |
| 2× MG996R + 6× MG90S | ✅ All 8 | ✅ Yes | Full capability. Use speed ramping. |
| ≥ 3× MG996R | ⚠️ Sequential only | ❌ Need UBEC | External 5V/10A supply for servo power. |

> [!WARNING]
> **Do NOT connect more than 2× MG996R servos to the Robot HAT's internal 5V rail.** Each MG996R can draw up to 2.5A during stall, which will exceed the 5A regulator capacity and crash the Pi 5. See the Compatibility Report Section 3.4 for full details.

#### 6.2 Physical Servo Connection

1. Plug each servo's 3-pin connector into the PWM port:
   - Orange/Yellow wire → `S` (Signal)
   - Red wire → `+` (5V Power)
   - Brown/Black wire → `−` (Ground)

2. Recommended channel assignment:

   | PWM Port | Servo Role | Recommended Type |
   |:---:|---|---|
   | **P0** | Left Wheel / Drive | MG90S (continuous rotation) |
   | **P1** | Right Wheel / Drive | MG90S (continuous rotation) |
   | **P2** | Head Pan | MG90S |
   | **P3** | Head Tilt | MG90S |
   | **P4** | Arm Base | MG90S or MG996R |
   | **P5** | Arm Shoulder | MG996R |
   | **P6** | Arm Elbow | MG90S |
   | **P7** | Gripper | MG90S |

#### 6.3 Hardware Servo Zeroing

1. Ensure all servos are physically connected to P0–P7.
2. **Double-click** the onboard **Servo Zeroing** button on the Robot HAT.
3. The MCU will output 1500 µs pulses (center position) to ALL channels (P0–P11).
4. While servos are holding center position, attach servo horns at 90° / neutral.
5. **Double-click again** to release all PWM signals (servos go limp).

#### 6.4 Software Servo Calibration & Simplified Aliasing

After the AT32F413 backend is deployed and registered:

1. **Intuitive Channel Selection Using Aliases:**
   Thanks to the endpoint aliasing implemented in Phase 4 (Task 4.4), users no longer need to type the cumbersome canonical string `hat_pwm0`. Both the interactive tools and CLI commands accept simplified aliases:
   - `pwm0`, `pwm1`, ... `pwm7` (or up to `pwm11`)
   - `p0`, `p1`, ... `p7` (matching the exact physical silkscreen printed on the Robot HAT!)

2. **Interactive TUI Calibration (`servo-tool`):**
   ```bash
   cd ~/NinjaRobotPi5
   uv run --frozen --no-sync pi5servo servo-tool
   ```
   - In the tool menu, select **`1. Select / Switch Endpoint`**.
   - Enter your target channel (e.g. `pwm0` or `p0` for Left Wheel; `pwm1` or `p1` for Right Wheel; `pwm2` or `p2` for Head Pan).
   - Use **`w`** and **`s`** keys to nudge pulse width in ±1 µs increments.
   - **For continuous rotation wheel servos:** Nudge until the wheel comes to a complete, dead stop at 1500 µs nominal center. This records the zero-drift trim null point.
   - **For angular / positional servos (pan/tilt/arm):** Use keys to verify smooth motion across 0° (e.g., 500 µs), 90° center (1500 µs), and 180° (2500 µs) travel limits.
   - Press **`Enter`** to save the calibration to `~/.config/pi5servo/servo.json`.

3. **Direct CLI Movement & Verification:**
   Individual channels can also be directly commanded via the CLI using simplified aliases:
   ```bash
   # Move Left Wheel servo (P0) to center position
   uv run --frozen --no-sync pi5servo move pwm0 1500

   # Move Head Pan servo (P2) using silkscreen alias "p2" to 90 degrees
   uv run --frozen --no-sync pi5servo move p2 1500
   ```

#### 6.5 Implement Motion Acceleration Ramping

To prevent current spikes when multiple servos start simultaneously:

1. Implement S-curve or trapezoidal velocity profiling in the backend.
2. When commanding multiple servos at once, stagger their start times by at least 20 ms.
3. This is especially critical if using MG996R servos, which have high inrush current.

### Validation Gate
- [ ] All 8 servo connectors are seated in P0–P7
- [ ] Hardware zeroing (double-click) produces visible centering motion
- [ ] Each channel responds to `servo-tool` pulse width adjustments
- [ ] Continuous rotation servos achieve true zero-drift at calibrated neutral
- [ ] Positional servos reach expected angular limits
- [ ] Battery voltage remains above 7.0V during simultaneous 8-servo motion
- [ ] No MCU communication errors in `dmesg` during operation
- [ ] Servo calibration saved to `~/.config/pi5servo/servo.json`

### Rollback
Servos can be unplugged at any time. The backend can fall back to GPIO-based PWM by changing the servo configuration file. Calibration data is stored per-channel and per-backend.

---

## Phase 7: Integration Testing & Validation

### Objective
Verify that all subsystems work together as a complete robot system under the new SunFounder Robot HAT architecture.

### Hardware Risk Level: 🔴 HIGH
Full-system test with live servos, audio, and AI inference.

### Prerequisites
- All prior phases complete

### Tasks

#### 7.1 Subsystem Interaction Matrix

Test these specific cross-subsystem scenarios:

| Test Case | Subsystems Involved | What to Verify | Pass Criteria |
|---|---|---|---|
| **Speak while moving** | Speaker + Servos + Pi 5 CPU | Audio doesn't clip during servo motion | Clear speech output; no voltage sag |
| **Camera + servos** | Camera + Head Pan/Tilt servos | Camera captures sharp images while head moves | No I2C bus contention between camera and MCU |
| **Distance + stop** | VL53L0X + Drive servos | Robot stops when obstacle detected | Sensor reads accurately during motor vibration |
| **AI inference + servos** | Ollama/Whisper + 8 servos | CPU load doesn't cause servo jitter | Smooth servo motion during LLM generation |
| **Battery drain test** | Battery + All subsystems | Monitor voltage over 20 minutes of mixed use | Voltage stays above 6.9V; LED indicators match |
| **GPIO 5 safety** | Display init + MCU | Display `rst_pin=17` init doesn't reset MCU | `i2cdetect -y 1` shows `0x14` after display init |

#### 7.2 Run the Full Validation Gate Suite

```bash
cd ~/NinjaRobotPi5

# 1. Managed driver integrity
uv run --frozen python scripts/verify_immutable_drivers.py
uv run --frozen python scripts/verify_workspace_driver_sources.py

# 2. Code compilation
uv run --frozen python -m compileall -q \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src scripts tests

# 3. Lint & format
uv run --frozen ruff check .
uv run --frozen ruff format --check .

# 4. Type checking
uv run --frozen mypy \
  ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src

# 5. Automated tests
uv run --frozen pytest -q

# 6. Git hygiene
git diff --check
```

#### 7.3 Guided Onboarding Hardware Profile Selector Flow (`ninjarobot onboard`)

To ensure any student, educator, or developer can set up the robot on either the new SunFounder Robot HAT or legacy hardware without manual configuration file hacking, the setup wizard (`ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/setup_wizard.py`) provides an interactive hardware profile selection step at the start of onboarding:

```text
=============================================================
             NinjaRobotPi5 Setup & Onboarding Wizard         
=============================================================
Please select your active Hardware Platform:

  [1] SunFounder Robot HAT (v5) [Recommended]
      • Single 2S 7.4V battery pack (replaces X1208 UPS)
      • Onboard 2.5W I2S Chamber Speaker (GPIO 12 Amp Enable)
      • AT32F413 MCU PWM channels P0–P7 / P0–P11 (I2C 0x14)
      • ST7789V Display Reset wired to Digital 17

  [2] DFRobot DFR0566 IO Expansion HAT + Geekworm X1208 UPS
      • Dual power: X1208 UPS battery + DFR0566 HAT
      • External Bluetooth speaker for voice output
      • Raspberry Pi RP1 Hardware PWM (GPIO 12 & 13)
      • ST7789V Display Reset wired to GPIO 5

  [3] Raspberry Pi 5 + General PCA9685 16-Channel PWM Board
      • External UBEC 5V power to PCA9685 V+ terminal
      • 16 independent PWM channels over I2C 0x40
      • External USB/Bluetooth speaker

Enter selection [1-3] (Default: 1): 1
```

**What the Wizard Automates Behind the Scenes:**
1. **Display Reset Pin Routing:**
   - Profile 1 (Robot HAT): Automatically sets `"rst_pin": 17` in `~/.config/pi5disp/display.json` (preventing GPIO 5 MCU reset).
   - Profile 2 (DFR0566): Sets `"rst_pin": 5`.
2. **Servo Driver Backend & Endpoints:**
   - Profile 1: Configures `backend = "sunfounder_robot_hat"`, assigns `left_motor = "pwm0"`, `right_motor = "pwm1"`, `head_pan = "pwm2"`, `head_tilt = "pwm3"`.
   - Profile 2: Configures `backend = "hardware_pwm"`, assigns `left_motor = "gpio12"`, `right_motor = "gpio13"`.
   - Profile 3: Configures `backend = "pca9685"`, assigns `left_motor = "pwm0"`, `right_motor = "pwm1"`.
3. **Audio Routing:**
   - Profile 1: Configures ALSA HiFiBerry DAC card and GPIO 12 amplifier enable pin.
   - Profile 2: Prompts for Bluetooth pairing with external speaker.
4. **Interactive Hardware Walkthrough:**
   - Sequentially launches `display-tool`, `servo-tool`, and `sensor-tool`, displaying wiring guidance and instructions tailored specifically to the selected board.

#### 7.4 AI Agent Integration & Verification (`ninjarobot_pi5_agent`)

A critical architectural requirement of NinjaRobotPi5 is that **the AI Agent does NOT require any code modifications, prompt redesigns, or brain refactoring to run on the SunFounder Robot HAT.**

**How the Agent Operates Transparently Across Hardware:**
```text
┌────────────────────────────────────────────────────────┐
│               ninjarobot_pi5_agent                     │
│  (LLM reasoning, speech understanding, goal planning)  │
└───────────────────────────┬────────────────────────────┘
                            │ Proposes typed MCP action:
                            │ robot.behavior.execute_movement(
                            │   target_speeds={"left_motor": 30.0, "right_motor": -30.0}
                            │ )
                            ▼
┌────────────────────────────────────────────────────────┐
│                ninjarobot_pi5_ide                      │
│  • Reads active profile in config.toml                 │
│  • Maps role "left_motor"  ──► "pwm0" (Robot HAT)      │
│  • Maps role "right_motor" ──► "pwm1" (Robot HAT)      │
│  • Distance sensor safety check (VL53L0X at 0x29)      │
└───────────────────────────┬────────────────────────────┘
                            │ Dispatches to driver backend
                            ▼
┌────────────────────────────────────────────────────────┐
│           pi5servo (sunfounder_robot_hat)              │
│  • Converts speeds/angles to pulse widths (µs)         │
│  • Writes to MCU I2C registers 0x20, 0x21 at 0x14      │
└────────────────────────────────────────────────────────┘
```

**Verification Procedure:**
1. Start the complete integrated system:
   ```bash
   ninjarobot start
   ```
2. **Voice Interaction Test:**
   - Speak into the USB microphone: *"Hello Ninja, introduce yourself!"*
   - Verify speech synthesis plays clearly through the onboard 2.5W chamber speaker (confirming GPIO 12 amplifier enable + I2S data stream).
3. **Movement & Vision Test:**
   - Speak: *"Ninja, look up and turn left 45 degrees."*
   - Verify:
     - Head tilt servo on P3 tilts camera upward.
     - Drive servos on P0 (left) and P1 (right) rotate in counter-directions to pivot the robot.
     - VL53L0X distance sensor actively monitors forward clearance during motion.
4. **Multi-DOF Actuation Test (if arm installed):**
   - Command: *"Ninja, wave your gripper."*
   - Verify Agent dispatches behavior targets for `arm_shoulder` (P5) and `gripper` (P7) smoothly without jitter or audio interference.

#### 7.5 Consolidate Robot Configuration

```bash
# Preview configuration changes
uv run --frozen --no-sync ninjarobot-ide-tool config import

# Apply to ~/.config/ninjarobot_pi5/config.toml
uv run --frozen --no-sync ninjarobot-ide-tool config import --apply

# Run guided setup verification
ninjarobot onboard --resume
```

### Validation Gate
- [ ] All subsystem interaction tests pass (Matrix 7.1)
- [ ] Full validation gate suite passes (verify_immutable_drivers, compileall, ruff, mypy, pytest)
- [ ] Onboarding profile selector switches cleanly between `sunfounder_robot_hat`, `dfr0566`, and `pca9685`
- [ ] Configuration import succeeds
- [ ] `ninjarobot onboard --resume` completes without errors
- [ ] AI Agent commands drive servos (P0–P7) via MCP behavioral tools without code changes
- [ ] Robot responds to voice commands with audio output through onboard 2.5W speaker
- [ ] Battery telemetry displays correct voltage and charging state

### Rollback
Individual subsystems can be tested independently. If integration reveals a fundamental issue, each phase has its own rollback procedure.

---

## Phase 8: Documentation & Cleanup

### Objective
Update all project documentation to reflect the new SunFounder Robot HAT architecture while maintaining backward compatibility for DFR0566 and PCA9685 profiles.

### Hardware Risk Level: 🟢 NONE
Documentation-only changes.

### Tasks

#### 8.1 Update Repository Documentation

| Document | Changes Required |
|---|---|
| `README.md` | Update hardware prerequisites, wiring table, power chain description |
| Wiki source for `InstallationGuide.md` | New HAT installation steps, battery charging, I2S audio setup |
| Wiki source for `DevelopmentGuide.md` | AT32F413 backend architecture, MCU I2C protocol reference |
| Wiki source for `DevelopmentLog.md` | Record migration rationale, validation results, servo power audit |
| `docs/hardware/hardware-profile.md` | Replace DFR0566/X1208 entries with Robot HAT pin assignments |
| `THIRD_PARTY_NOTICES.md` | Add SunFounder Robot HAT and AT32F413 MCU attribution |

#### 8.2 Update Wiki Knowledge Base

Follow the [ninjarobot-knowledge skill](.agents/skills/ninjarobot-knowledge/SKILL.md):

1. Run `python scripts/wiki.py check` after documentation updates.
2. Review changed implementation fingerprints.
3. Update affected wiki sources and pages.
4. Run wiki lint to verify consistency.

#### 8.3 Clean Up Configuration & Preserve Hardware Profiles

- **Preserve Backward Compatibility:** Do **NOT** delete DFR0566 or PCA9685 driver code. Maintain all three hardware profile presets in `ninjarobot_pi5_ide` so existing robots can continue operating.
- **Update Default Profile:** Set `sunfounder_robot_hat` as the default hardware profile for all newly generated configurations.
- **Retire Geekworm X1208 Service:** Disable and mask the standalone `x1208-pwr.service` systemd unit on the Pi 5 when the Robot HAT profile is active, as power is now managed entirely by the Robot HAT.
- **Update Template Documentation:** Ensure default examples in `docs/` showcase `pwm0`..`pwm7` for servos and GPIO 17 for display reset.

#### 8.4 Git Commit & Tag

```bash
git add -A
git commit -m "feat: migrate to SunFounder Robot HAT v5

- Replace DFR0566 IO Expansion HAT with SunFounder Robot HAT v5
- Retire Geekworm X1208 UPS; use Robot HAT 7.4V battery as sole power source
- Add AT32F413 MCU I2C backend to pi5servo for 8 PWM channels (P0-P7)
- Remap display RST from GPIO 5 to GPIO 17 (GPIO 5 = MCU reset)
- Enable I2S onboard speaker (GPIO 12 amp enable, GPIO 18/19/21 I2S)
- Add battery telemetry via ADC Channel 4 over I2C"
```

### Validation Gate
- [ ] All documentation accurately reflects the new hardware
- [ ] No stale DFR0566 or X1208 references remain in active documentation
- [ ] Wiki check passes
- [ ] `docs/hardware/hardware-profile.md` fully updated
- [ ] Git commit is clean; `git diff --check` passes

---

## Risk Register & Mitigation

| Risk ID | Risk Description | Likelihood | Impact | Mitigation Strategy |
|:---:|---|:---:|:---:|---|
| R1 | GPIO 5 display reset crashes MCU | 🔴 High (if wired wrong) | 🔴 High | Wire display RST to GPIO 17; verify with I2C scan after display init. |
| R2 | MG996R brownout during stall | 🟡 Medium | 🔴 High | Limit to 2x MG996R max on internal power; use external UBEC for more. |
| R3 | I2C bus contention (MCU + VL53L0X) | 🟢 Low | 🟡 Medium | Addresses `0x14` and `0x29` are distinct. Use bus locking in driver code. |
| R4 | MCU firmware desync after interrupted I2C | 🟡 Medium | 🟡 Medium | Implement `reset_mcu()` with GPIO 5 pulse; auto-retry on `IOError`. |
| R5 | Battery 2000 mAh insufficient for extended use | 🟡 Medium | 🟡 Medium | Monitor via telemetry; consider upgraded 3000+ mAh pack if runtime < 30 min. |
| R6 | WS2812 conflicts with SPI display | 🟢 Low | 🟢 Low | Hardware constraint: WS2812 port shares GPIO 10 (MOSI) with SPI. Cannot use both. Documented; no workaround needed. |
| R7 | HiFiBerry DAC overlay conflicts with other audio | 🟢 Low | 🟡 Medium | Verify PipeWire/ALSA config; test USB mic input separately from I2S output. |
| R8 | Servo jitter during heavy AI inference | 🟡 Medium | 🟢 Low | MCU generates PWM independently; jitter only possible if I2C updates are delayed. Add timeout handling. |

---

## Complete GPIO Allocation Map

This is the definitive GPIO assignment for NinjaRobotPi5 on the SunFounder Robot HAT:

| BCM GPIO | Robot HAT Label | NinjaRobotPi5 Function | Direction | Shared? |
|:---:|---|---|:---:|:---:|
| 2 | SDA | I2C SDA (MCU `0x14` + VL53L0X `0x29`) | Bidir | Bus |
| 3 | SCL | I2C SCL | Bidir | Bus |
| 4 | DIGITAL 4 | ST7789V Display DC (Data/Command) | Output | No |
| 5 | MCU Reset | AT32F413 MCU hardware reset | Output | **Reserved** |
| 6 | (SPI) BSY | ST7789V Display Backlight PWM | Output | No |
| 8 | SPI CE0 | ST7789V Display Chip Select | Output | No |
| 9 | SPI MISO | SPI MISO (unused by display) | — | Available |
| 10 | SPI MOSI / WS2812 | ST7789V Display Data (MOSI) | Output | **SPI/WS2812 conflict** |
| 11 | SPI SCLK | ST7789V Display Clock | Output | No |
| 12 | Speaker Enable | I2S Amplifier Power Enable | Output | No |
| 13 | NC | **Free** (was servo on DFR0566) | — | Available |
| 14 | TXD | UART TX (available) | Output | Available |
| 15 | RXD | UART RX (available) | Input | Available |
| 16 | RST Button | Robot HAT RST button (customizable) | Input | No |
| 17 | DIGITAL 17 | ST7789V Display RST (Reset) | Output | No |
| 18 | I2S BCLK | I2S Bit Clock (Speaker) | Output | I2S Bus |
| 19 | I2S LRCLK | I2S Word Select (Speaker) | Output | I2S Bus |
| 20 | I2S DATAIN | I2S Data In (MEMS Microphone) | Input | I2S Bus |
| 21 | I2S DATAOUT | I2S Data Out (Speaker) | Output | I2S Bus |
| 22 | DIGITAL 22 | **Free** (Digital header available) | — | Available |
| 23 | CHG | Charging indicator (read-only) | Input | No |
| 25 | USR Button | User tactile button (active-low) | Input | No |
| 26 | USER LED | Programmable status LED | Output | No |
| 27 | DIGITAL 27 | Passive Buzzer Signal | Output | No |

---

## Migration Timeline Summary

```
                    MIGRATION PHASES & ESTIMATED EFFORT
                    
Phase  Description                         Effort        Depends On   Risk
────── ───────────────────────────────────── ───────────── ──────────── ──────
  1    Hardware Decommissioning & Mounting   ~1 hour       —            🟡
  2    OS & Audio Configuration             ~1 hour       Phase 1      🟢
  3    Display & Sensor Adaptation          ~1–2 hours    Phase 2      🟡
  4    AT32F413 MCU Backend Development     ~2–4 days     Phase 3      🟢
  5    Battery Telemetry & Power Mgmt       ~1–2 days     Phase 4      🟢
  6    Motion Control & Servo Calibration   ~1–2 days     Phase 4 & 5  🔴
  7    Integration Testing & Validation     ~1–2 days     Phase 6      🔴
  8    Documentation & Cleanup              ~1 day        Phase 7      🟢
       ─────────────────────────────────────
       TOTAL ESTIMATED EFFORT:              ~8–14 days
```

```
 PHASE DEPENDENCY GRAPH
 
 Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──┬──► Phase 5 ──┐
                                                │              │
                                                └──────────────┼──► Phase 6
                                                               │
                                                               └──► Phase 7 ──► Phase 8
```

---

## Sign-Off

- **Plan Status:** Ready for review
- **Code Impact:** No existing code modified in this planning document
- **Guardrail Verification:** PASS — This plan is documentation-only
- **Recommended First Action:** Approve this plan, then proceed with Phase 1 (hardware decommissioning) followed by Phase 2 (OS configuration)
- **Critical Decision Required:** Confirm your target servo configuration (all-MG90S vs. hybrid mix) before entering Phase 6
