#!/usr/bin/env python
from threading import RLock
from modelsDict import models
import time
from collections import deque
import logging


logger = logging.getLogger(__name__)


class VoltcraftScheduler():
    """Voltcraft PSU job`s scheduler, interface is based on the sched.py.

    Arguments:
        device    -> Voltcraft PSU device
        start     -> absolute start time of the first job on the list
        frequency -> frequency of PSU call ups: 1 - 1 Hz
                                                2 - 2 Hz ...
    INFO: `device' must be properly set AND checked (see VoltcraftPSU docs)"""
    def __init__(self, device, start, frequency=1):
        self.device = device
        self.jobs = deque()
        self.period = round(1 / frequency, 4)
        self.start = start
        #local buffer of current VIP values:
        self._lock = RLock()  # for psu and self.values dict
        self.values = {'V': models[self.device.model]['Vmin'],
                       'I': models[self.device.model]['Imin'],
                       'P': models[self.device.model]['Pmin']}
        self.debug_info = 'jobs:{}\nvalues:{}'

    def _update(self):
        """updates internal dictionary of temporary values."""
        with self._lock:
            V = self.device.getVoltage()
            I = self.device.getCurrent()
            P = round(V * I, 2)  # not need to use getPower() here
            self.values = V, I, P

    def add(self, job):
        """adds job to the list.

        Arguments:
            job -> job object

        Returns:"""
        with self._lock:
            self.jobs.append(job)

    def _check_condition(self, job):
        """checks if VIP conditions of the particular `job' is satisfied.

        Arguments:
            job -> job ID

        Returns:
            Boolean -> True if conditions are satisfied, False if not."""
        with self._lock:
            self._update()  # fresh values only
            for cond in job.stop_cond:
                if not self.values[cond] in range(*job.stop_cond[cond]):
                    return False
            return True

    def run(self):
        """based on the sched.run() method."""
        period = self.period
        with self._lock:  # turn on PSU in online mode
            self.device.setVoltage(models[self.device.model]['Vmin'])
            self.device.switch('keyb_off')

        while True:  # wait for the start signal
            now = time.time()
            if self.start > now:
                time.sleep(period)
                now = time.time()
            else:
                self.device.switch('power_on')
                break

        logger.debug(self.debug_info.format(self.jobs, self.values))
        while True:  # process job list
            with self._lock:
                if not self.jobs:  # turn off PSU
                    self.device.setVoltage(models[self.device.model]['Vmin'])
                    self.device.switch('keyb_on')
                    self.device.switch('power_off')
                    break
                else:  # start of queue processing
                    j = self.jobs.popleft()
                    j.run()
                    logger.debug(self.debug_info.format(self.jobs, self.values))
                    t = time.time()
                    stop = t + j.how_long
                    while t < stop:
                        if self._check_condition(j):  # check stop conditions
                            time.sleep(period)
                        else:
                            break
                        t += period

if __name__ == '__main__':
    import voltcraftPSU
    import job

    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    FORMAT = '...{funcName} .. {levelname} :.....{asctime}......{name}......\n'
    FORMAT += '{message} \n'
    FORMAT += '-------------------------------------------------------------\n'
    formater = logging.Formatter(FORMAT, style='{')
    handler.setFormatter(formater)
    logger.addHandler(handler)

    port = '/dev/ttyUSB0'
    device = voltcraftPSU.VoltcraftPSU(port)
    device.getID()
    scheduler = VoltcraftScheduler(device=device,
                                   start=time.time() + 3,
                                   frequency=0.5)
    #couple of simple jobs:
    job1 = job.Job(psu=device, what=('setv', 5), how_long=5)
    job2 = job.Job(psu=device, what=('setv', 10), how_long=5)
    job3 = job.Job(psu=device, what=('setv', 14), how_long=5)
    scheduler.add(job1)
    scheduler.add(job2)
    scheduler.add(job3)
    scheduler.run()
