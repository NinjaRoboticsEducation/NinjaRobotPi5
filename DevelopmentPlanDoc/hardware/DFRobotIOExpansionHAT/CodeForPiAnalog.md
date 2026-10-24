---
title: "IO Expansion HAT Example Code: Master Raspberry Pi ADC ?"
source: "https://wiki.dfrobot.com/dfr0566/docs/20751"
author:
published:
created: 2026-10-23
description: "Download and run Python example code for the DFR0566 IO Expansion HAT. This example code shows you how to use the Raspberry Pi's analog port ADC effectively."
tags:
  - "clippings"
---
## Hardware Preparation

- [Raspberry Pi 4B](https://www.dfrobot.com/product-1875.html) x1
- [IO Expansion HAT for Raspberry Pi](https://www.dfrobot.com/product-1930.html) x1
- HDMI Cable x1
- Display x1
- Keyboard and Mouse x1
- Analog sensor x1 (e.g., potentiometer)

## Software Preparation

- Enable Raspberry Pi I2C interface. (Way to enable SPI is the same with IIC). Skip this step if it is already enabled.
- Install Phython demo library and git, and make sure the network connection of Raspberry Pi is fine. Skip this step if these have been installed.

command: `cd ~`

command: `git clone https://github.com/DFRobot/DFRobot_RaspberryPi_Expansion_Board.git`

command:`sudo unzip DFRobot_RaspberryPi_Expansion_Board.zip`

command: `cd DFRobot_RaspberryPi_Expansion_Board-master/examples`

## Wiring Diagram

![DFR0566 IO Expansion HAT for Raspberry Pi 4B/3B+ Tutorial](https://dfimg.dfrobot.com/nobody/wiki/b1b0068baf0a83679a07b506fad8c26e.png)
- Connect analog sensor to one of the analog ports (A0-A3).

## Sample Code

```arduino
# -*- coding:utf-8 -*-

'''
  # demo_adc.py
  #
  # Connect board with raspberryPi.
  # Run this demo.
  #
  # All or part adc channels value will print on terminal
  #
  # Copyright   [DFRobot](https://www.dfrobot.com), 2016
  # Copyright   GNU Lesser General Public License
  #
  # version  V1.0
  # date  2019-3-28
'''

import time

from DFRobot_RaspberryPi_Expansion_Board import DFRobot_Expansion_Board_IIC as Board

board = Board(1, 0x10)    # Select i2c bus 1, set address to 0x10

def board_detect():
  l = board.detecte()
  print("Board list conform:")
  print(l)

''' print last operate status, users can use this variable to determine the result of a function call. '''
def print_board_status():
  if board.last_operate_status == board.STA_OK:
    print("board status: everything ok")
  elif board.last_operate_status == board.STA_ERR:
    print("board status: unexpected error")
  elif board.last_operate_status == board.STA_ERR_DEVICE_NOT_DETECTED:
    print("board status: device not detected")
  elif board.last_operate_status == board.STA_ERR_PARAMETER:
    print("board status: parameter error")
  elif board.last_operate_status == board.STA_ERR_SOFT_VERSION:
    print("board status: unsupport board framware version")

if __name__ == "__main__":

  board_detect()    # If you forget address you had set, use this to detected them, must have class instance

  # Set board controler address, use it carefully, reboot module to make it effective
  '''
  board.set_addr(0x10)
  if board.last_operate_status != board.STA_OK:
    print("set board address faild")
  else:
    print("set board address success")
  '''

  while board.begin() != board.STA_OK:    # Board begin and check board status
    print_board_status()
    print("board begin faild")
    time.sleep(2)
  print("board begin success")

  board.set_adc_enable()
  # board.set_adc_disable()

  while True:
    val = board.get_adc_value(board.A0)   # A0 channels read
    #val = board.get_adc_value(board.A1)   # A1 channels read
    #val = board.get_adc_value(board.A2)   # A2 channels read
    #val = board.get_adc_value(board.A3)   # A3 channels read
    print("channel: A0, value: %d" %val)
    print("")

    time.sleep(2)
```

command: `python demo_adc.py`

## Result

All or part adc channels value will print on terminal.