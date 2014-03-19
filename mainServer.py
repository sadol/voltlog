#!/usr/bin/env python
import libs.voltcraftPSU as voltcraftPSU
import libs.scheduler as scheduler
#import libs.modelsDict as modelsDict
import libs.job as job
import libs.condition as condition
import logging
import datetime
from libs.stylesDict import dtFormat
from threading import Thread, Event
from collections import deque


logger = logging.getLogger(__name__)

class MainServer():
    def __init__(self, psu_device, jobs, job_stats, running):
        """creates Pyro4 main server object for RPC of the PSU:)

           device    -> (string) device name (e.x: /dev/ttyUSB0)
           jobs      -> collections.deque object to store batch(input queue)
           job_stats -> collections.deque object to store out
           running   -> threading.Event object for scheduler running flag

        INFO: `device' must be properly set&checked (see VoltcraftPSU docs)"""
        self.jobs = jobs
        self.job_stats = job_stats
        self.values = {'V': 0.00, 'I': 0.00, 'P': 0.00}
        self.running = running
        self.device = voltcraftPSU.VoltcraftPSU(psu_device)
        self.ID = self.device.getID()
        self.scheduler = scheduler.VoltcraftScheduler(device=self.device,
                                                      jobs=self.jobs,
                                                      job_stats=self.job_stats,
                                                      running=self.running)
        logger.debug('#---PSU {} server started.'.format(self.device.model))

    def psuManualMode(self):
        """Set PSU in manual mode"""
        self.device.manualMode()

    def psuRemoteMode(self):
        """Set PSU in remote mode"""
        self.device.remoteMode()

    def getServerTimeNow(self):
        """returns server now() time"""
        dt = datetime.datetime.now()
        return dt.strftime(dtFormat)

    def stopScheduler(self):
        """Stops scheduler"""
        self.running.clear()
        logger.debug('#\tscheduler stopped.')

    def psuOff(self):
        self.device.psuOff()

    def psuOn(self):
        self.device.psuOn()

    def keybOn(self):
        self.device.manualKey()

    def keybOff(self):
        self.device.remoteKey()

    def startScheduler(self, start, frequency):
        """Starts scheduler

        Arguments:
            start     -> (string) absolute start time
                          of the first job in the line
            frequency -> (float) frequency of the PSU callups (1 - 1 Hz ...)

        Returns:"""
        st = datetime.datetime.strptime(start, dtFormat)
        self.scheduler.setStart(st)
        self.scheduler.setFrequency(frequency)
        #initial job list must be passed to the scheduler!!!
        info = '#\tscheduler started.\n\tStart time :{}\tfrequency : {}'
        logger.debug(info.format(start, frequency))
        self.thrSched = Thread(target=self.scheduler.run,
                               name='scheduler', daemon=True)
        self.thrSched.start()

    def getSchedulerStatus(self):
        """checks if scheduler is running

        Arguments:

        Returns:
            boolean -> True if scheduler is running , False otherwise"""
        return self.running.isSet()

    def getVIP(self):
        """Returns actual V,I,P values from scheduler object.
        Arguments:

        Returns:
            V,I,P tuple"""
        if self.running.isSet():
            output = self.scheduler.values['V'], self.scheduler.values['I'], self.scheduler.values['P']
        else:
            output = 0.00, 0.00, 0.00
        return output

    def getMinMax(self):
        """gets minima and maxima for V,I,P values of the PSU.

        Arguments:

        Returns:
            tuple of values: Vmin, Vmax, Imin, Imax, Pmin, Pmax"""
        return self.scheduler.getMinMax()

    def status(self):
        """returns job statuses queue

        Arguments:

        Returns:
            list of lists of strings for easy Pyro4 Proxy handling"""
        return list(self.job_stats)

    def setQueue(self, batch):
        """Pyro4-friendly wrapper for the scheduler`s job queue creator.
        The only way to pass job to the scheduler is to use this function
        which process whole LIST of jobs

        Arguments:
            batch -> [ [what(tuple(string, float)), how_long(float),
                       ( left(string), operator(string), right(float) ), ...],
                       ...]

        Returns:"""
        self.jobs.clear()
        logger.debug('#\t\tload for scheduler started.')
        for rawJob in batch:
            what, how_long, *rawConds = rawJob
            conds = []
            for rawCond in rawConds:
                cond = condition.Condition(str(self.ID), rawCond[0],
                                           rawCond[1], rawCond[2])
                conds.append(cond)
            j = job.Job(self.device, what, how_long, conds)
            self.jobs.append(j)
            logger.debug('#\t\t\t job :{}'.format(j.getInfo()))
        logger.debug('#\t\tload for scheduler completed.')

def main():
    import argparse
    import Pyro4
    import socket

    #------------------logging section----------------------------------------
    serverLog = open(file='logs/PSUserver.log', mode='a+')
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream=serverLog)
    FORMAT = '{message}\t\t{asctime} {levelname}'
    formater = logging.Formatter(FORMAT, style='{')
    handler.setFormatter(formater)
    logger.addHandler(handler)

    #------------------shell commands parser section--------------------------
    parser = argparse.ArgumentParser(description='Power Supply Unit Server')
    parser.add_argument('-d', '--device', required=True,
                        help='name of the PSU device e.x.:/dev/ttyUSB0')
    parser.add_argument('-p', '--port', type=int,
                        help='Pyro4 port for this server (default 50000)',
                        default=50000, choices=range(50000, 50005))
    parser.add_argument('-t', '--host', help='host name (default socket.gethostname())',
                        default=socket.gethostname())
    parser.add_argument('-i', '--psuid', default='psuServer',
                        help='unique Pyro4 id for the PSU server (default psuServer)')
    #not implemented
    parser.add_argument('-n', '--nameserver', dest='nameserver',
                        action='store_true', help='use nameserver (default) - NOT IMPLEMENTED')
    parser.add_argument('-x', '--no-nameserver', dest='nameserver',
                        action='store_false', help='don`t use nameserver - NOT IMPLEMENTED')
    parser.set_defaults(nameserver=True)
    parser.add_argument('-s', '--openssl', dest='openssl', action='store_true',
                        help='use openssl socket wrapper - NOT IMPLEMENTED')
    parser.add_argument('-o', '--no-openssl', dest='openssl', action='store_false',
                        help='don`t use openssl socket wrapper (default) - NOT IMPLEMENTED')
    parser.set_defaults(openssl=False)
    args = parser.parse_args()

    #------------------Pyro 4 section------------------------------------------
    """    multiline Pyro4 :
    MS = MainServer(args.device)                             # 1 create object to serve
    daemon = Pyro4.Daemon(host=args.host, port=args.port)    # 2 create server daemon
    uri = daemon.register(MS)                                # 3 obtain unique id of the server
    nameserver = Pyro4.locateNS()                            # 4 find nameserver (optional)
    nameserver.register(args.psuid, uri)                     # 5 register daemon on the nameserver (optional)
    daemon.requestLoop()                                     # 6 run daemon
    """

    #-----------------global thread-safe objects section-----------------------
    jobs = deque()                 # queue of jobs to serve
    job_stats = deque()            # output queue of statuses of completed jobs
    runningEvent = Event()         # shared flag of scheduler state

    #------------------Pyro 4 section------------------------------------------
    # another way to build and start server (oneliner without NameServer)
    Pyro4.Daemon.serveSimple({MainServer(args.device,
                                         jobs,
                                         job_stats,
                                         runningEvent): args.psuid},
                             host=args.host, port=args.port, ns=False,
                             verbose=True)

if __name__ == '__main__':
    main()
