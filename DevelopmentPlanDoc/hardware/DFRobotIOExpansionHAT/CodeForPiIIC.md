---
title: "IO Expansion HAT for Raspberry Pi - Example Code for UV Sensor"
source: "https://wiki.dfrobot.com/dfr0566/docs/20755"
author:
published:
created: 2026-10-23
description: "Download and run Python example code for IO Expansion HAT on Raspberry Pi, showcasing how to read UVA, UVB, and UVI data using VEML6075 sensor."
tags:
  - "clippings"
---
## Hardware Preparation

- [Raspberry Pi 4B](https://www.dfrobot.com/product-1875.html) x1
- [IO Expansion HAT for Raspberry Pi](https://www.dfrobot.com/product-1930.html) x1
- HDMI Cable x1
- Display x1
- Keyboard and Mouse x1
- [SEN0303 VEML6075 UV sensor](https://www.dfrobot.com/product-1906.html) x1

## Software Preparation

- Enable Raspberry Pi I2C interface. (Way to enable SPI is the same with IIC). Skip this step if it is already enabled.
- Install Phython demo library and git, and make sure the network connection of Raspberry Pi is fine. Skip this step if these have been installed.

command: `cd ~`

command: `git clone https://github.com/DFRobot/DFRobot_VEML6075.git`

command: `unzip DFRobot_VEML6075.zip`

command: `cd DFRobot_VEML6075-master/raspberry/example`

## Sample Code

```python
# -*- coding: utf-8 -*-

'''
 *  file DFRobot_VEML6075_demo.py
 *  normal test for VEML6075
 *  UVA index, UVB index and UV index will print on terminal
 *
 *  Copyright    [DFRobot](https://www.dfrobot.com), 2018
 *  Copyright    GNU Lesser General Public License
 *  version  V1.0
 *  date  2018-12-18
'''

import time
import sys
sys.path.append("..")

from DFRobot_VEML6075 import DFRobot_VEML6075

if __name__ == '__main__':

  VEML6075 = DFRobot_VEML6075(1, 0x10)  # use i2c bus 1, module address is 0x10

  while VEML6075.begin() != True:
    print("VEML6075 begin faild")
    time.sleep(2)
  print("VEML6075 begin succeed")

  while True:
    Uva = VEML6075.getUva()          # get UVA
    Uvb = VEML6075.getUvb()          # get UVB
    Uvi = VEML6075.getUvi(Uva, Uvb)  # get UVI
    print("")
    print("======== start print ========")
    print("UVA:     %.2f" %(Uva))
    print("UVB:     %.2f" %(Uvb))
    print("UVA:     %.2f" %(Uvi))
    print("mw/cm^2: %.2f" %(VEML6075.Uvi2mwpcm2(Uvi)))
    print("======== end print =========")
    time.sleep(1)
```

command: `python DFRobot_VEML6075_demo`

## Result

Read UV data on Raspberry Pi

![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Read UV data on Raspberry Pi](https://dfimg.dfrobot.com/nobody/wiki/7233344bbc8facfae5c53865408a1600.png)