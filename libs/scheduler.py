#!/usr/bin/env python
from threading import Thread, Event, Timer
from libs.voltcraftPSU import PsuOfflineError
from libs.modelsDict import models, statuses
import time
from collections import deque
import logging
import datetime


logger = logging.getLogger(__name__)


class JobListError(Exception):
    pass


class StartTimeError(Exception):
    pass


class FrequencyError(Exception):
    pass


class VoltcraftScheduler():
    def __init__(self, device, jobs, job_stats, running,
                 start=None, frequency=1):
        """Voltcraft PSU job`s scheduler, interface is based on the sched.py.

        Arguments:
            device    -> Voltcraft PSU device
            jobs      -> collections.deque object to store batch(input queue)
            job_stats -> collections.deque object to store out
            running   -> threading.Event object for scheduler running flag
            start     -> absolute start time of the first job on the list
                        (datetime.datetime object)
            frequency -> (float)frequency of PSU call ups: 1 - 1 Hz
                                                    0.5 - 0.5 Hz ...
        INFO: `device' must be properly set&checked (see VoltcraftPSU docs)"""
        self.device = device
        self.jobs = jobs
        self.job_stats = job_stats
        self.period = self._calcPeriod(frequency)
        self.start = start
        self.values = {'V': 0.00, 'I': 0.00, 'P': 0.00}
        self.running = running
        self.running.clear()  # not running

    def setStart(self, start):
        """Sets start value for the whole scheduler

        Arguments:
            start -> (datetime.datetime,now() + something)

        Returns :"""
        delta = datetime.timedelta(seconds=1)
        now = datetime.datetime.now()
        if start - now < delta:
            raise StartTimeError('Starting point can`t be placed in the past')
        self.start = start

    def setFrequency(self, freq):
        """Sets frequency of the PSU calls .

        Arguments:
            freq -> 0 < float <=1

        Returns:"""
        if not (0 < freq <= 1):
            raise FrequencyError('Frequency is too high for the Voltcraft PSU')
        self._calcPeriod(freq)

    def _calcPeriod(self, freq):
        """calulates period from frequency

        Arguments:
            freq -> 0 < float <=1

        Returns:
            float"""
        if not (0 < freq <= 1):
            raise FrequencyError('Frequency is too high for the Voltcraft PSU')
        return round(1 / freq, 4)

    def _update(self):
        """updates internal dictionary of temporary values."""
        if self.running.isSet():
            try:
                self.values['V'] = self.device.getVoltage()
                self.values['I'] = self.device.getCurrent()
                self.values['P'] = round(self.values['V'] * self.values['I'], 2)
            except PsuOfflineError:
                pass
        else:
            self.values['V'] = 0.00
            self.values['I'] = 0.00
            self.values['P'] = 0.00

    def _check_condition(self, job):
        """checks if VIP conditions of the particular `job' are satisfied.

        Arguments:
            job -> job ID

        Returns:
            Boolean -> True if conditions are satisfied, False if not."""
        for cond in job.subs:
            if not job.subs[cond][0] <= self.values[cond] <= job.subs[cond][1]:
                return False
        return True

    def _checkScheduler(self):
        """Checks if scheduler is ready to run"""
        if len(self.jobs) == 0:
            raise JobListError('Initial job queue is empty!!!')
        if not self.start:
            raise StartTimeError('Schedule start time is unset.')

    def getMinMax(self):
        """gets minima and maxima for V,I,P values of the PSU.

        Arguments:

        Returns:
            tuple of values: Vmin, Vmax, Imin, Imax, Pmin, Pmax"""
        return (models[self.device.model]['Vmin'],
                models[self.device.model]['Vmax'],
                models[self.device.model]['Imin'],
                models[self.device.model]['Imax'],
                models[self.device.model]['Pmin'],
                models[self.device.model]['Pmax'])

    def _updateValues(self):
        """thread method updates values dictionary with V,I.P values"""
        while self.running.isSet():
            time.sleep(2)
            self._update()

    def run(self):
        """based on the sched.run() method."""
        self.running.set()  # sheduler is running
        self._checkScheduler()
        period = self.period

        updateThread = Thread(target=self._updateValues, daemon=True,
                              name='update')
        updateThread.start()

        while self.running.isSet():  # wait for start signal
            now = datetime.datetime.now()
            if self.start > now:
                time.sleep(period)
                now = datetime.datetime.now()
            else:
                break

        self.device.psuOn()  # TODO : add turnon and turnoff job types
        while self.running.isSet():  # start batch processing
            if len(self.jobs) == 0:  # properly completed batch work
                self._stop()
            else:  # start of queue processing
                #logger.debug(self.debug_info.format(self.jobs, self.values))
                j = self.jobs.popleft()
                j.run()
                #logger.debug('current job:{}'.format(j.getInfo()))
                if j.what[0] == 'setv':  # only for set V job !!!
                    t = datetime.datetime.now()
                    stop = t + datetime.timedelta(seconds=j.how_long)
                    while t < stop and self.running.isSet():
                        if not self._check_condition(j):  # check stop condS
                            break  # premature stop the job
                        time.sleep(period)
                        t += datetime.timedelta(seconds=period)
                #  for set max I and set max V there is no need to wait
                #self.job_stats.append([j.getInfo(), statuses['c']])

        if not self.running.isSet():  # emergency stpped batch work
            self._stop()

    def _stop(self):
        """stops scheduler"""
        self.device.setVoltage(0.1)  # direct command to the device(reset PSU)
        self.device.psuOff()
        self.running.clear()  # not running

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
    device.getID()  # initialization stage
    jobs = deque()
     #couple of simple jobs:
    job0 = job.Job(psu=device, what=('maxv', 13))
    job1 = job.Job(psu=device, what=('setv', 5), how_long=15)
    job2 = job.Job(psu=device, what=('setv', 10), how_long=15)
    job3 = job.Job(psu=device, what=('setv', 12), how_long=15)
    jobs.append(job0)
    jobs.append(job1)
    jobs.append(job2)
    jobs.append(job3)

    job_stats = deque()
    values = {'V': models[device.model]['Vmin'],
              'I': models[device.model]['Imin'],
              'P': models[device.model]['Pmin']}
    runningEvent = Event()

    start = datetime.datetime.now() + datetime.timedelta(seconds=3)
    scheduler = VoltcraftScheduler(device=device, start=start,
                                   jobs=jobs, job_stats=job_stats,
                                   values=values, running=runningEvent)
    scheduler.device.remoteMode()
    try:
        panicThr = Timer(interval=35, function=runningEvent.clear, args=())
        scheduThr = Thread(target=scheduler.run, args=(), daemon=False)
        scheduThr.start()
        panicThr.start()
        scheduThr.join()
    finally:
        scheduler.device.manualMode()
