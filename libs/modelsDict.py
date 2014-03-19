#!/usr/bin/env python
"""
Dictionary of Voltcraft PSU types and their properities
Dictionary items structure:
    key:
        model -> (string) model digital ID

    value: (subdict)
        `Vmul' -> (float) internal voltage multiplier (WARNING: not tested
                                                        for 1405 and 1803)
        `Imul' -> (float) internal current multiplier (WARNING: not tested
                                                          for 1405 and 1803)
        `Vmin' -> (float) min voltage
                         (WARNING : this value could not be ZERO!!! because
                                    of low precision of the Voltcraft`s PSUs!!)
        `Imin' -> (float) min current
        `Vmax' -> (float) max voltage
        `Imax' -> (float) max current
        `init' -> (bytestring) model id transmited by the  PSU
        INFO: multipliers are derived from the formula :
              (element 1)*maxV * (element 2)*maxI = 200W
"""

models = {'1405': {'Vmul': 1.0, 'Imul': 1.0, 'Vmin': 0.1, 'Imin': 0.0,
                   'Vmax': 40.0, 'Imax': 5.0, 'Pmin': 0.0, 'Pmax': 200.0,
                   'init': b'\xb2\x01'},
          '12010': {'Vmul': 2.0, 'Imul': 0.5, 'Vmin': 0.1, 'Imin': 0.0,
                    'Vmax': 20.0, 'Imax': 10.0, 'Pmin': 0.0, 'Pmax': 200.0,
                    'init': b'\xb2\x02'},
          '1803': {'Vmul': 0.5, 'Imul': 2.0, 'Vmin': 0.1, 'Imin': 0.0,
                   'Vmax': 80.0, 'Imax': 2.5, 'Pmin': 0.0, 'Pmax': 200.0,
                   'init': b'\xb2\x03'}}

#commands for voltcraft data frames
commands = {'set_voltage': b'\xaa',
            'get_voltage': b'\xae',
            'get_current': b'\xaf',
            'power': b'\xab',
            'set_max_current': b'\xac',
            'set_max_voltage': b'\xad',
            'keyboard': b'\xb0',
            'device': b'\xb2'}

#special values for voltcraft data frames
specValues = {'power_on': b'\x01\x00',
              'power_off': b'\x00\x00',
              'keyb_on': b'\x00\x00',
              'keyb_off': b'\x01\x00',
              'read': b'\x00\x00'}

frame_size = 3  # raw data frame contains 3 bytes

#voltcraft PSUs job operators set
#INFO: != and == operators not supported due to low PSU precision
operators = {'>=', '<='}

#voltcraft PSUs job variable name set
#variables: left hand operands
lefts = {'V', 'I', 'P'}

#job statuses:
statuses = {'p': 'pending', 'e': 'error', 'w': 'waiting',
            'c': 'completed', 'x': 'canceled'}
