---
title: "Unleash Sensor Power with DFR0566 & Raspberry Pi! ?"
source: "https://wiki.dfrobot.com/dfr0566/docs/20752"
author:
published:
created: 2026-10-23
description: "Download and run Python example code for DFR0566 IO Expansion HAT. This example code shows you how to use Raspberry Pi with SEN0285 Gesture&Touch Sensor."
tags:
  - "clippings"
---
## Hardware Preparation

- [Raspberry Pi 4B](https://www.dfrobot.com/product-1875.html) x1
- [IO Expansion HAT for Raspberry Pi](https://www.dfrobot.com/product-1930.html) x1
- HDMI Cable x1
- Display x1
- Keyboard and Mouse x1
- [SEN0285 Gesture&Touch Sensor](https://www.dfrobot.com/product-1898.html) x1

## Software Preparation

- Enable Raspberry Pi I2C interface. (Way to enable SPI is the same with IIC). Skip this step if it is already enabled.
- Install Phython demo library and git, and make sure the network connection of Raspberry Pi is fine. Skip this step if these have been installed.

command: `cd ~`

command: `git clone https://github.com/DFRobot/DFRobot_Gesture_Touch.git`

command:`sudo unzip DFRobot_Gesture_Touch-main.zip`

command: `cd DFRobot_Gesture_Touch-main/raspberry/python/examples/demo_gesture_touch`

## Other Preparation Work

- Connect SEN0285 Gesture&Touch Sensor to UART port.

## Sample Code

command: `python demo_gesture_touch.py`

## Result

Read gesture and touch data via UART.