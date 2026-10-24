---
title: "Master LED Blink with DFR0566 IO Expansion HAT ?"
source: "https://wiki.dfrobot.com/dfr0566/docs/20753"
author:
published:
created: 2026-10-23
description: "Download and run Python example code for DFR0566 IO Expansion HAT. This example code shows you how to use the HAT for Raspberry Pi to make an LED blink."
tags:
  - "clippings"
---
## Hardware Preparation

- [Raspberry Pi 4B](https://www.dfrobot.com/product-1875.html) x1
- [IO Expansion HAT for Raspberry Pi](https://www.dfrobot.com/product-1930.html) x1
- HDMI Cable x1
- Display x1
- Keyboard and Mouse x1
- [Gravity: Bright LED Module](https://www.dfrobot.com/product-1511.html) x1

## Software Preparation

- Install RPi.GPIO library:`pip install RPi.GPIO`

## Wiring Diagram

![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Tutorial](https://dfimg.dfrobot.com/nobody/wiki/9e7fed060b2d90060637c71069dd43ce.png)
- Plug a LED on the Pin27 on the expansion board.

## Sample Code

```python
import RPi.GPIO as GPIO
import time
import atexit
blinkPin=27
atexit.register(GPIO.cleanup)
GPIO.setmode(GPIO.BCM)
GPIO.setup(blinkPin,GPIO.OUT)
while True:
    GPIO.output(blinkPin,GPIO.HIGH)
    time.sleep(1)
    GPIO.output(blinkPin,GPIO.LOW)
    time.sleep(1)
```

## Result

The LED will begin to blink on and off.

## Additional Information

IO expansion board offers 28 groups (D0-D27) of digital ports that are led out via Raspberry Pi ports GPIO0~GPIO27 (BCM codes). [GPIO Learning Guide.](https://www.raspberrypi.org/documentation/usage/gpio/python/README.md?tdsourcetag=s_pctim_aiomsg "GPIO Learning Guide.")