#!/usr/bin/env python
import struct
import serial
from functools import wraps
import time
from modelsDict import commands, specValues, frame_size, models


#error clases
class ValueOutOfRange(Exception):
    pass


class WrongCommand(Exception):
    pass


class ArgumentError(Exception):
    pass


class PsuOfflineError(Exception):
    pass


def _dec_check(function):
        """Decorator.
        Method checker function for VoltcraftPSU class.
        args[0] is the instance itself (self argument).
        Constantly checks if device is ready to process commands.

        Arguments:
            function -> VoltcraftPSU method

        Returns:
            method wrapper"""
        @wraps(function)
        def check(*args, **kwargs):
            if args[0].read(frame_size) == b'':
                raise PsuOfflineError('Turn on PSU or check connection')
            return function(*args, **kwargs)
        return check


def _dec_voltcraft(Class):
    """class decorator.
    Applies check function on every method in VolcraftPSU class except __init__

    Arguments:
        Class -> VoltcraftPSU class

    Returns:
        Processed class"""
    for name, value in vars(Class).items():  # Beazley trick
        if callable(value) and (name.find('__init__') == -1):
            setattr(Class, name, _dec_check(value))
        return Class


#@_dec_voltcraft
class VoltcraftPSU(serial.Serial):
    """Voltcraft psp Power Supply Unit class.
    PSU input and output data frame is composed of 3 bytes:
    first byte for command, 2nd and 3rd for value.

    WARNING: ordinary way of using this class is this:
            1. create VoltcraftPSU instance
            2. fire getID method on behalf of the instance
            3. use instance(run getters and setters)"""

    def __init__(self, volt_port):
        """voltcraft psp PSU constructor.

        Arguments:
            volt_port->(string) serial device port ID ,for example:/dev/ttyUSB0
            rest of the arguments are initialized:
                baudrate=2400
                bytesize=8
                timeout=1
                parity=0"""
        serial.Serial.__init__(self, port=volt_port, baudrate=2400,
                               bytesize=serial.EIGHTBITS, timeout=1,
                               parity=serial.PARITY_NONE)
        self.model = 'Unknown'

    @_dec_check
    def setVoltage(self, value):
        """Sets actual voltage for PSUs.

        Arguments:
            value->(float) value to set

        Returns:"""
        if value < models[self.model]['Vmin'] or value > (40 * models[self.model]['Imul']):
            raise ValueOutOfRange('Voltage is out of range: {}'.format(value))
        v = struct.pack('>h', int(round(value * 100 * models[self.model]['Vmul'], 0)))
        self.write(commands['set_voltage'] + v)

    @_dec_check
    def setMaxVoltage(self, value):
        """Sets max voltage for PSUs.

        Arguments:
            value->(float) value to set

        Returns:"""
        if value < models[self.model]['Imin'] or value > (40 * models[self.model]['Imul']):
            raise ValueOutOfRange('Voltage is out of range: {}'.format(value))
        v = struct.pack('>h', int(round(value * 10 * models[self.model]['Vmul'], 0)))
        self.write(commands['set_max_voltage'] + v)

    @_dec_check
    def setMaxCurrent(self, value):
        """Sets maximum current for PSUs.

        Arguments:
            value->(float) value to set

        Returns:"""
        if value < models[self.model]['Imin'] or value > (5 * models[self.model]['Vmul']):
            raise ValueOutOfRange('Current is out of range: {}'.format(value))
        v = struct.pack('>h', int(round(value * 100 * models[self.model]['Imul'], 0)))
        self.write(commands['set_max_current'] + v)

    @_dec_check
    def getVoltage(self):
        """gets voltage of the voltcraft PSU.

        Arguments:

        Returns:
            float, 2 decimal places"""
        # stub value for reading from device: b'\x00\x00'
        self.write(commands['get_voltage'] + specValues['read'])
        # response of the device is NOT immediate
        temp = self.read(frame_size)
        while(temp[0] != commands['get_voltage'][0]):
            temp = self.read(frame_size)
        value = temp[1:]
        return round((struct.unpack('>h', value)[0]) / 100 / models[self.model]['Vmul'], 2)

    @_dec_check
    def getCurrent(self):
        """gets current of the voltcraft PSU.

        Arguments:

        Returns:
            float, 2 decimal places"""
        # stub value for reading from device: b'\x00\x00'
        self.write(commands['get_current'] + specValues['read'])
        # response of the device is NOT immediate
        temp = self.read(frame_size)
        while(temp[0] != commands['get_current'][0]):
            temp = self.read(frame_size)
        value = temp[1:]
        return round((struct.unpack('>h', value)[0]) / 1000 / models[self.model]['Imul'], 2)

    @_dec_check
    def getID(self):
        """checks PSU model and populates self.model variable."""
        time.sleep(1)  # time for hand shaking
        #command below is useless because of constant flow of b'\xb1\x02\x02'
        #byte string from 12010 device
        #self.write(commands['device'] + specValues['read'])
        initial_data_frame = self.read(frame_size)
        initial_data_frame = initial_data_frame[1]
        if initial_data_frame == 1:
            self.model = '1405'
        elif initial_data_frame == 2:
            self.model = '12010'
        elif initial_data_frame == 3:
            self.model = '1803'

    @_dec_check
    def getPower(self):
        """gets power of the voltcraft PSU.

        Arguments:

        Returns:
            float, 2 decimal places"""
        I = self.getCurrent()
        V = self.getVoltage()
        return round(I * V, 2)

    @_dec_check
    def switch(self, what):
        """switching function for voltcraft psu, enables turninig on and off
        psu keyboard and soft power switch.

        Arguments:
            what->(string) [power|keyb]_[on|off] only

        Returns:"""
        if what not in specValues:  # CAVEAT: read is also one of special vals
            com = "Invalid arg:{}, should be `power_on[off]' or `keyb_on[off]' only".format(what)
            raise ArgumentError(com)
        if what.find('power') == 0:
            self.write(commands['power'] + specValues[what])
        if what.find('keyb') == 0:
            self.write(commands['keyboard'] + specValues[what])

if __name__ == '__main__':
    try:
        port = '/dev/ttyUSB0'
        psu = VoltcraftPSU(port)  # | first step of initialization
        psu.getID()               # | second step
        print(psu.model)
        psu.switch('keyb_off')
        psu.setMaxVoltage(13.00)  # | rotary DC fan specs -> for testing
        psu.setMaxCurrent(0.12)   # | ...
        psu.setVoltage(12.00)     # | ...
        psu.switch('power_on')
        time.sleep(5)  # fake scheduler
        print('Voltage : {} V.'.format(psu.getVoltage()))
        print('Current : {} A.'.format(psu.getCurrent()))
        print('Power : {} W.'.format(psu.getPower()))
        time.sleep(5)  # fake scheduler
        psu.switch('power_off')
        psu.setMaxVoltage(10.00)
        psu.setMaxCurrent(1.00)
        psu.setVoltage(00.00)
        psu.switch('keyb_on')
    except PsuOfflineError:
        print('PSU not connected or powered off.')
    except serial.serialutil.SerialException:
        print('Port : {} does not exist. Plug serial cable properly.'.format(port))
