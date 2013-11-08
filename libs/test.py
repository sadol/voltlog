#!/usr/bin/env python
import voltcraftPSU

psu = voltcraftPSU.VoltcraftPSU('/dev/ttyUSB0')
psu.switch('keyb_on')
psu.switch('power_off')
