# Confirmed hardware profile

This is the V4-owned hardware record. It was confirmed by the project owner on
2026-07-26. The implementation plan remains authoritative.

| Capability | Connection |
| --- | --- |
| Passive buzzer | BCM GPIO27 |
| Direct servo endpoints | BCM GPIO12 and GPIO13 using RP1 hardware PWM |
| DFR0566 servo endpoints | Physical PWM0 through PWM3 over I2C bus 1 at `0x10` |
| VL53L0X | I2C bus 1 at `0x29` |
| ST7789V data | SPI0 CE0, MOSI GPIO10, SCLK GPIO11, CE0 GPIO8 |
| ST7789V control | DC GPIO4, RST GPIO5, BL GPIO6 |
| ST7789V presentation | 240×320, rotation 90°, brightness 75% |
| Camera | OV5647 Raspberry Pi CSI camera, fixed-focus, 1280×720 capture |
| Microphone | USB PnP Sound Device, ALSA card 0/device 0, mono; 16 kHz requested and 44.1 kHz selected by hardware fallback |

The two MG90D continuous-rotation servos currently available are test hardware
only. They do not replace or reduce the planned six-endpoint V4 topology. Their
DFR0566 digital GPIO12/GPIO13 connections use native Pi hardware PWM, not the
HAT's dedicated PWM0–PWM3 controller.

## Electrical certification blockers

Do not run powered servo tests until the following record is complete and
approved:

- exact model and rated voltage of every production servo
- stall current of every production servo
- supply voltage plus continuous and peak current rating
- fuse or current-limiting arrangement
- common-ground arrangement
- accessible emergency power-disconnect procedure

The live-Pi audit identifies the camera as OV5647. Confirm its CSI connector
orientation and visual image quality during Phase 3.4 validation. Also record
the buzzer circuit and display board revision before certifying those
capabilities. The USB microphone ALSA identity is now recorded above. ALSA is
the Linux audio device layer.
