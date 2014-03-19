#!/usr/bin/env python
import struct
import serial
import time
from libs.modelsDict import commands, specValues, frame_size, models
from threading import Lock


#error clases
class ValueOutOfRange(Exception):
    pass


class WrongCommand(Exception):
    pass


class ArgumentError(Exception):
    pass


class PsuOfflineError(Exception):
    pass


class VoltcraftPSU():
    _lock = Lock()

    def __init__(self, volt_port):
        """voltcraft psp PSU constructor.

        Arguments:
            volt_port->(string) serial device port ID ,for example:/dev/ttyUSB0"""
        self.device = serial.Serial(port=volt_port, baudrate=2400,
                                    bytesize=serial.EIGHTBITS, timeout=0.5,
                                    parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE)
        self.model = 'Unknown'
        self.myTimeout = 4  # after 4 s of idle state class signaling offline

    def _read(self, *args, **kwargs):
        """thin serial read wrapper"""
        self.device.flushInput()
        self.device.flushOutput()
        return self.device.read(*args, **kwargs)

    def _write(self, *args, **kwargs):
        """thin serial write wrapper"""
        self.device.flushInput()
        self.device.flushOutput()
        return self.device.write(*args, **kwargs)

    def _testDelta(self, testVal, targetVal, delta=0.1):
        """tests if output value fits within error borders -+0.1[V/A]

        Arguments:
            testVal   -> (float) real value obtained from the device
            targetVal -> (float) ideal value send to the device
            delta     -> (float) delta value (for Voltcraft PSU - 0.1)

        Returns:
            boolean   -> True if value is in the borders, False otherwise"""
        if (testVal <= (targetVal - delta)) or (testVal >= (targetVal + delta)):
            return False
        return True

    def setVoltage(self, value):
        """Sets actual voltage for PSUs.

        Arguments:
            value->(float) value to set

        Returns:"""
        if value < models[self.model]['Vmin'] or value > (40 * models[self.model]['Imul']):
            raise ValueOutOfRange('Voltage is out of range: {}'.format(value))
        v = struct.pack('>h', int(round(value * 100 * models[self.model]['Vmul'], 0)))
        with VoltcraftPSU._lock:
            self._write(commands['set_voltage'] + v)
        """
        #  unfortunately voltcraft PSU responsivness is to low to use section
        #  below properly
        #check settings:
        now = time.time()
        stop = now + self.myTimeout  # max delay of the function
        while now < stop:
            time.sleep(0.5)  # delay is crucial in this case, DON'T DECREASE!!!
            test = self.getVoltage()
            if self._testDelta(test, value):
                return
            else:
                now = time.time()
                continue
        raise PsuOfflineError('setVoltage timeout error')
        """

    def setMaxVoltage(self, value):
        """Sets max voltage for PSUs.

        Arguments:
            value->(float) value to set

        Returns:"""
        if value < models[self.model]['Imin'] or value > (40 * models[self.model]['Imul']):
            raise ValueOutOfRange('Voltage is out of range: {}'.format(value))
        v = struct.pack('>h', int(round(value * 10 * models[self.model]['Vmul'], 0)))
        with VoltcraftPSU._lock:
            self._write(commands['set_max_voltage'] + v)

    def setMaxCurrent(self, value):
        """Sets maximum current for PSUs.

        Arguments:
            value->(float) value to set

        Returns:"""
        if value < models[self.model]['Imin'] or value > (5 * models[self.model]['Vmul']):
            raise ValueOutOfRange('Current is out of range: {}'.format(value))
        v = struct.pack('>h', int(round(value * 100 * models[self.model]['Imul'], 0)))
        with VoltcraftPSU._lock:
            self._write(commands['set_max_current'] + v)

    def getVoltage(self):
        """gets voltage of the voltcraft PSU.

        Arguments:

        Returns:
            float, 2 decimal places"""
        now = time.time()
        stop = now + self.myTimeout
        while now < stop:
            with VoltcraftPSU._lock:
                self._write(commands['get_voltage'] + specValues['read'])
            while now < stop:  # wait for response
                with VoltcraftPSU._lock:
                    frame = self._read(frame_size)
                if len(frame) == frame_size and frame[0] == commands['get_voltage'][0]:
                    value = frame[1:]
                    return round((struct.unpack('>h', value)[0]) / 100 / models[self.model]['Vmul'], 2)
                now = time.time()
            now = time.time()
        raise PsuOfflineError('getVoltage timeout error')

    def getCurrent(self):
        """gets current of the voltcraft PSU.

        Arguments:

        Returns:
            float, 2 decimal places"""
        now = time.time()
        stop = now + self.myTimeout
        while now < stop:
            with VoltcraftPSU._lock:
                self._write(commands['get_current'] + specValues['read'])
            while now < stop:  # wait for response
                with VoltcraftPSU._lock:
                    frame = self._read(frame_size)
                if len(frame) == frame_size and frame[0] == commands['get_current'][0]:
                    value = frame[1:]
                    return round((struct.unpack('>h', value)[0]) / 1000 / models[self.model]['Imul'], 2)
                now = time.time()
            now = time.time()
        raise PsuOfflineError('getCurrent timeout error')

    def getID(self):
        """checks PSU model and populates self.model variable.

        Arguments:

        Returns:
            self.model"""
        now = time.time()
        stop = now + self.myTimeout
        while now < stop:  # my timeout
            with VoltcraftPSU._lock:
                frame = self._read(frame_size)
            if len(frame) == frame_size and frame[0] == 178:  # '\xb2'
                break
            now = time.time()

        frame = frame[:2]
        if frame == models['1405']['init']:
            self.model = '1405'
        elif frame == models['12010']['init']:
            self.model = '12010'
        elif frame == models['1803']['init']:
            self.model = '1803'
        if self.model in models:
            return self.model
        msg = 'getID timeout error\ncheck connection with PSU or restart PSU'
        raise PsuOfflineError(msg)

    def getPower(self):
        """gets power of the voltcraft PSU.

        Arguments:

        Returns:
            float, 2 decimal places"""
        I = self.getCurrent()
        V = self.getVoltage()
        return round(I * V, 2)

    def _switch(self, what):
        """_switching function for voltcraft psu, enables turninig on and off
        psu keyboard and soft power _switch.

        Arguments:
            what->(string) [power|keyb]_[on|off] only

        Returns:"""
        if what not in specValues:  # CAVEAT: read is also one of special vals
            com = "Invalid arg:{}, should be `power_on[off]' or `keyb_on[off]' only".format(what)
            raise ArgumentError(com)
        if what.find('power') == 0:
            with VoltcraftPSU._lock:
                self._write(commands['power'] + specValues[what])
        if what.find('keyb') == 0:
            with VoltcraftPSU._lock:
                self._write(commands['keyboard'] + specValues[what])

    def manualMode(self):
        """Turning on PSU device in manual control mode"""
        self.psuOff()
        self.manualKey()

    def remoteMode(self):
        """Turning on PSU device in remote control mode"""
        self.remoteKey()
        self.psuOn()

    def remoteKey(self):
        """sets keyboard in remote mode"""
        self._switch('keyb_off')

    def manualKey(self):
        """sets keyboard in the manual mode"""
        self._switch('keyb_on')

    def psuOn(self):
        """turns on PSU (only if it is possible)"""
        self._switch('power_on')

    def psuOff(self):
        """turns off PSU (only if it is possible)"""
        self._switch('power_off')

if __name__ == '__main__':
    try:
        port = '/dev/ttyUSB0'
        psu = VoltcraftPSU(port)  # | first step of initialization
        psu.getID()               # | second step
        print(psu.model)
        n = 0
        while n < 10:
            n += 1
            psu.remoteMode()          # | third step
            psu.setMaxVoltage(13.00)  # | rotary DC fan specs -> for testing
            psu.setMaxCurrent(0.12)   # | ...
            psu.setVoltage(12.00)     # | ...
            # device has its own intertion!!!!!
            print('Voltage : {} V.'.format(psu.getVoltage()))  # <> 12 V !!!!!!
            print('Current : {} A.'.format(psu.getCurrent()))
            print('Power : {} W.'.format(psu.getPower()))
            time.sleep(2)  # fake scheduler
            psu.setMaxVoltage(10.00)  # | rotary DC fan specs -> for testing
            psu.setMaxCurrent(0.12)   # | ...
            psu.setVoltage(8.00)     # | ...
            print('Voltage : {} V.'.format(psu.getVoltage()))
            print('Current : {} A.'.format(psu.getCurrent()))
            print('Power : {} W.'.format(psu.getPower()))
            time.sleep(2)  # fake scheduler
            psu.setMaxVoltage(8.00)
            psu.setMaxCurrent(1.00)
            psu.setVoltage(5.10)
            print('Voltage : {} V.'.format(psu.getVoltage()))
            print('Current : {} A.'.format(psu.getCurrent()))
            print('Power : {} W.'.format(psu.getPower()))
            time.sleep(2)  # fake scheduler
            psu.manualMode()
    except PsuOfflineError as e:
        print(e)
        psu.manualMode()
    except serial.serialutil.SerialException:
        print('Port : {} does not exist (or you have insuficient priviligies to use it).'.format(port))
