# Confirmed hardware profile

This is the V4-owned hardware record. It was confirmed by the project owner on
2026-07-26. The implementation plan remains authoritative.

| Capability | Connection |
| --- | --- |
| Passive buzzer | BCM GPIO27 |
| Direct servo endpoints | BCM GPIO12 and GPIO13 using RP1 hardware PWM |
| Optional DFR0566 servo endpoints | Physical PWM0 through PWM3 over I2C bus 1 at `0x10`; not in the default Phase 4 robot |
| VL53L0X | I2C bus 1 at `0x29` |
| ST7789V data | SPI0 CE0, MOSI GPIO10, SCLK GPIO11, CE0 GPIO8 |
| ST7789V control | DC GPIO4, RST GPIO5, BL GPIO6 |
| ST7789V presentation | 240×320, rotation 90°, brightness 75% |
| Camera | OV5647 Raspberry Pi CSI camera, fixed-focus, 1280×720 capture |
| Microphone | USB PnP Sound Device, ALSA card 0/device 0, mono; 16 kHz requested and 44.1 kHz selected by hardware fallback |

The default Phase 4 robot uses two TowerPro MG90D 360-degree
continuous-rotation servos. GPIO12 is the logical left motor and GPIO13 is the
logical right motor. Their DFR0566 digital D12/D13 connections use native Pi
hardware PWM, not the HAT's dedicated PWM0–PWM3 controller.

The two servo red wires connect to the D12/D13 `+` terminals. The
owner-confirmed power chain is:

```text
official Raspberry Pi 27 W supply
  -> Geekworm X1208
  -> Raspberry Pi and DFR0566
  -> D12/D13 servo power
```

The owner measured the servo connection within the MG90D 4.8–6.6 V range.
There is no accessible physical emergency power disconnect. The owner
explicitly approved proceeding with software safety controls despite that
residual risk. A physical cutoff remains strongly recommended and is required
before this hardware profile can be described as production-certified.

The optional DFR0566 PWM0–PWM3 endpoints remain supported for future
user-customized configurations. Any added servo needs its own model, voltage,
stall-current, supply-capacity, protection, grounding, and disconnect review.

The live-Pi audit identifies the camera as OV5647. Confirm its CSI connector
orientation and visual image quality during Phase 3.4 validation. Also record
the buzzer circuit and display board revision before certifying those
capabilities. The USB microphone ALSA identity is now recorded above. ALSA is
the Linux audio device layer.
