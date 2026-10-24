---
title: "IO Expansion HAT for Raspberry Pi - Quick Start Guide ⚡"
source: "https://wiki.dfrobot.com/dfr0566/docs/22892"
author:
published:
created: 2026-10-23
description: "Step-by-step guide to set up the IO Expansion HAT for Raspberry Pi 5 / 4B / 3B+. This beginner's guide for DFR0566 provides wiring instructions and setup tips."
tags:
  - "clippings"
---
## Overview

![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Board Overview](https://dfimg.dfrobot.com/nobody/wiki/63d442d3455ede2262bdd005cf3a4617.jpg)

| Silkscreen | Label | Description |
| --- | --- | --- |
| + | + | 3.3V Positive |
| \- | \- | Negative |
| ⊕ | ⊕ | Binding post connect to external power positive |
| ㊀ | ㊀ | Binding post connect to external power negative |
| Digital | 0-27 | Raspberry Pi GPIO0-GPIO27 |
| PWM | 0-3 | PWM signal output pin 0-3 |
| Analog | 0-3 | Analog signal input pin 0-3 |
| IIC | C | IIC port clock line |
|  | D | IIC port data line |
| UART | T | UART Transmit port |
|  | R | UART Receive port |
| 5V | 5V | 5V positive |
| GND | GND | Negative |
| IIS | SCK | IIS serial clock line |
|  | DIN | IIS serial data input |
|  | LCK | IIS L/R channel selection line |
|  | BCK | IIS system clock line |
| SPI | MISO | SPI data output line |
|  | SS | SPI enable pin |
|  | SCLK | SPI serial clock line |
|  | MOSI | SPI data input line |

**Note:**

- The GPIO number in this board adopts BCM codes.
- When the VP port is not power by external power, the voltage of PWM ⊕ is 5V.
- When the VP port is powered by external power, the voltage of PWM ⊕ is equal to that of the VP external power (6-12V).

## Port and Learning Guide

- Digital Port: IO expansion board offers 28 groups (D0-D27) of digital ports that are led out via Raspberry Pi ports GPIO0~GPIO27 (BCM codes). [GPIO Learning Guide.](https://www.raspberrypi.org/documentation/usage/gpio/python/README.md?tdsourcetag=s_pctim_aiomsg "GPIO Learning Guide.")
![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Tutorial](https://dfimg.dfrobot.com/nobody/wiki/9e7fed060b2d90060637c71069dd43ce.png)
- Analog Port: IO expansion board has four groups of analog ports A0-A3. The board integrates on-board MCU STM32, and 12-bits ADC. The input voltage of analog sensor is 12-bit ADC. After the analog data is converted into digital data, it will be sent to Raspberry Pi via IIC commnucation. [Download Example Program.](https://github.com/DFRobot/DFRobot_RaspberryPi_Expansion_Board.git "Download Example Program.")
![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Tutorial](https://dfimg.dfrobot.com/nobody/wiki/b1b0068baf0a83679a07b506fad8c26e.png)
- PWM Port: IO expansion board provides four groups of PWM ports. Connect the STM32 to PWM. Raspberry Pi will send data to STM32 via IIC to control. VP port can supply 6-12V external power to PWM port. When not powered, the voltage of PWM ⊕ is 3.3V. [Download Example Program.](https://github.com/DFRobot/DFRobot_RaspberryPi_Expansion_Board.git "Download Example Program.")
![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Tutorial](https://dfimg.dfrobot.com/nobody/wiki/f95e171252517c4c53123b1158bef344.png)
- IIC Port: IO expansion board has 3 groups of IIC ports that are led out via Raspberry Pi GPIO2（SDA.1）and GPIO3（SCL.1）（BCM code). [IIC Learning Guide.](https://pypi.org/project/smbus2/?tdsourcetag=s_pctim_aiomsg "IIC Learning Guide.")
![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Tutorial](https://dfimg.dfrobot.com/nobody/wiki/4327cb5e4148d1c75444b8e174c1f13e.png)
- IIS Port: there is 1 group of IIS port that is led out via Raspberry Pi GPIO ports: GIO21 (SCK), GPIO20(DIN), GPIO19(LCK), GPIO18(BCK).
![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Tutorial](https://dfimg.dfrobot.com/nobody/wiki/ade6c9830afeaa07cde4cf219d75d542.png)
- SPI Port: IO expansion board leads out a group of SPI ports via its GPIO port (BCM code): GPIO10(MOSI)and GPIO9(MISO), GPIO11(SCLK), GPIO8(SS). [SPI Learning Guide.](https://pypi.org/project/spidev/?tdsourcetag=s_pctim_aiomsg "SPI Learning Guide.")
![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Tutorial](https://dfimg.dfrobot.com/nobody/wiki/07f17d0fdabb0c5a71a8878defd32885.png)

## Preparatory work

**IIC Usage Operation and Program Execution Introduction**

- Enable Raspberry Pi I2C interface. (Way to enable SPI is the same with IIC). Skip this step if it is already enabled.

Open Terminal and input the following commands, press "Enter":

command: `sudo raspi-config`

Use the "Enter" key to select: \[Interfacing Options\] or (\[Advanced Options\])->\[I2C\]->\[Yes\]->\[OK\]->\[Finish\]:

![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ IIC Usage Operation and Program Execution Introduction](https://dfimg.dfrobot.com/nobody/wiki/3406c7d875b614db1c7a455b9430848f.png) ![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ IIC Usage Operation and Program Execution Introduction](https://dfimg.dfrobot.com/nobody/wiki/09647f3626bcde7c5ea8ff58ed65fa30.png)
- Install Phython demo library and git, and make sure the network connection of Raspberry Pi is fine. Skip this step if these have been installed.

command: `sudo apt-get update`

command: `sudo apt-get install build-essential python-dev python-smbus git`

- Download the driver library and run.

command: `cd ~`

command: `git clone https://github.com/DFRobot/DFRobot_RaspberryPi_Expansion_Board.git`