#!/usr/bin/env python
import tkinter as tk
from tkinter import ttk
import Pyro4
import libs.stylesDict as st
from tkinter import messagebox
import logging
import time
import datetime
import threading
from tkinter import filedialog as fdi
import os
import pickle
from tkinter import TclError
from collections import deque
import libs.plotFrame as plot


class TimeError(Exception):
    pass

logger = logging.getLogger(__name__)

class MainPanel(ttk.Frame):
    """main GUI panel for the Power Supply Unit(PSU) server (Pyro4 type)"""
    def __init__(self, root, **confs):
        ttk.Frame.__init__(self, root, **confs)
        #-------------connect panel variables----------------------------------
        self.psuServer = None  # server object
        self.server = tk.StringVar()  # sever name in the local network
        self.frequency = tk.StringVar()
        self.frequencies = (1, 0.5, 0.25, 0.1)  # Hz
        self.root = root
        self.neutral = self.root.cget('background')  # neutral color of widgets
        self.butNorm = {'relief': 'raised', 'background': self.neutral,
                        'state': 'normal'}
        self.butPress = {'relief': 'sunken', 'background': 'green',
                         'state': 'disabled'}
        #-------------subframes------------------------------------------------
        #---------------CONNECTION PANEL---------------------------------------
        connectionLabel = ttk.Label(self, text='Connection control',
                                    **st.subFr)
        connectFrame = ttk.LabelFrame(self, padding='3 3 12 12',
                                      labelwidget=connectionLabel)
        self.server_entry = ttk.Entry(connectFrame, width=10,
                                      textvariable=self.server)
        self.server_entry.grid(column=1, row=0, sticky=(tk.W))
        self.frequency.set(self.frequencies[0])  # default value
        self.frequency_list = ttk.Combobox(connectFrame, width=4,
                                           textvariable=self.frequency,
                                           values=self.frequencies)
        self.frequency_list.grid(column=1, row=1, sticky=(tk.W))
        ttk.Label(connectFrame, text='Server').grid(column=0, row=0, sticky=tk.E)
        ttk.Label(connectFrame, text='Frequency').grid(column=0, row=1, sticky=tk.E)
        ttk.Label(connectFrame, text='[Hz]').grid(column=2, row=1, sticky=tk.W)
        self.status = ttk.Label(connectFrame, text='offline',
                                foreground='red')
        self.status.grid(column=2, row=0, sticky=tk.E)
        self.connectBut = tk.Button(connectFrame, text='Connect',
                                    cursor='exchange',
                                    command=self._connect, **st.but)
        self.connectBut.grid(column=0, row=2, sticky=tk.EW, padx=5)
        self.disconnectBut = tk.Button(connectFrame, text='Disonnect',
                                       cursor='exchange',
                                       command=self._disconnect, **st.but)
        self.disconnectBut.grid(row=2, column=1, sticky=tk.EW, padx=5)
        for child in connectFrame.winfo_children():
            child.grid_configure(padx=5, pady=5)
        connectFrame.grid(row=0, column=0, padx=5, pady=5, sticky=(tk.NSEW))

        #------------------SCHEDULER PANEL-------------------------------------
        self.minmax = None
        self.vValue = tk.StringVar()
        self.sValue = tk.StringVar()
        self.vMaxValue = tk.StringVar()
        self.iMaxValue = tk.StringVar()
        self.initMaxV = tk.StringVar()
        self.initMaxI = tk.StringVar()
        self.initHour = tk.StringVar()
        self.initMinute = tk.StringVar()
        self.initSecond = tk.StringVar()
        self.vExitLeftValue = tk.StringVar()
        self.vExitRightValue = tk.StringVar()
        self.iExitLeftValue = tk.StringVar()
        self.iExitRightValue = tk.StringVar()
        self.batch = []  # all job`s list
        self.firstBatch = []  # first part of the batch cont. maxV and maxI
        schedulerLabel = ttk.Label(self, text='Scheduler control', **st.subFr)
        schedulerFrame = ttk.LabelFrame(self, padding='3 3 12 12',
                                        labelwidget=schedulerLabel)
        #---------initial PSU settings subframe--------------------------------
        initialLabel = ttk.Label(self, text='Set initial values',
                                 **st.subSubFr)
        initialSubFrame = ttk.LabelFrame(schedulerFrame, padding='3 3 12 12',
                                         labelwidget=initialLabel)
        initialSubFrame.grid(row=0, column=0, sticky=tk.EW)
        self.vMaxVal = tk.Spinbox(initialSubFrame, from_=0.00, to=20.00,
                                  width=5, increment=0.1, format='%4.2f',
                                  textvariable=self.initMaxV,
                                  command=self._initiateSchedSpins)
        self.vMaxVal.grid(row=0, column=0)
        tk.Label(initialSubFrame, text='MAX voltage [V]').grid(row=0, column=1)
        self.iMaxVal = tk.Spinbox(initialSubFrame, from_=0.00, to=20.00,
                                  width=5, increment=0.1, format='%4.2f',
                                  textvariable=self.initMaxI,
                                  command=self._initiateSchedSpins)
        self.iMaxVal.grid(row=1, column=0)
        tk.Label(initialSubFrame, text='MAX curent [A]').grid(row=1, column=1)
        tk.Frame(initialSubFrame, heigh=10).grid(row=2, column=0, sticky=tk.W)
        tk.Label(initialSubFrame, text='Batch starts at:').grid(row=3,
                                                                column=0,
                                                                sticky=tk.E)
        self.initHourSpin = tk.Spinbox(initialSubFrame, from_=0, to=23,
                                       increment=1, format='%2.0f', width=2,
                                       textvariable=self.initHour)
        self.initHourSpin.grid(row=3, column=1, sticky=tk.E)
        tk.Label(initialSubFrame, text=':').grid(row=3, column=2, sticky=tk.E)
        self.initMinuteSpin = tk.Spinbox(initialSubFrame, from_=0, to=59,
                                         increment=1, format='%2.0f', width=2,
                                         textvariable=self.initMinute)
        self.initMinuteSpin.grid(row=3, column=3, sticky=tk.E)
        tk.Label(initialSubFrame, text=':').grid(row=3, column=4, sticky=tk.E)
        self.initSecondSpin = tk.Spinbox(initialSubFrame, from_=0, to=59,
                                         increment=1, format='%2.0f', width=2,
                                         textvariable=self.initSecond)
        self.initSecondSpin.grid(row=3, column=5, sticky=tk.E)
        #---------job creation subframe----------------------------------------
        jobLabel = ttk.Label(self, text='Job creation', **st.subSubFr)
        jobSubFrame = ttk.LabelFrame(schedulerFrame, padding='3 3 12 12',
                                     labelwidget=jobLabel)
        jobSubFrame.grid(row=1, column=0)
        jobSubSubFrame = tk.Frame(jobSubFrame)
        jobSubSubFrame.grid(row=0, column=0, sticky=tk.W)
        tk.Label(jobSubSubFrame, text='Set').grid(row=0, column=0)
        self.vVal = tk.Spinbox(jobSubSubFrame, from_=0.00, to=20.00,
                               increment=0.1, format='%4.2f', width=5,
                               textvariable=self.vValue)
        self.vVal.grid(row=0, column=1)
        tk.Label(jobSubSubFrame, text='[V] for').grid(row=0, column=2)
        #  device is too slow to set from_ < 10s !!!
        self.sVal = tk.Spinbox(jobSubSubFrame, from_=10, to=9999, increment=1,
                               format='%4.0f', width=4,
                               textvariable=self.sValue)
        self.sVal.grid(row=0, column=3)
        tk.Label(jobSubSubFrame, text='[s]').grid(row=0, column=4)
        tk.Frame(jobSubFrame, heigh=10).grid(row=1, column=0, sticky=tk.W)
        #---exit conditions subframe-------------------------------------------
        altLabel = ttk.Label(self, text='Alternative exit conditions',
                             **st.subSubFr)
        altSubFrame = ttk.LabelFrame(jobSubFrame, padding='3 3 12 12',
                                     labelwidget=altLabel)
        altSubFrame.grid(row=2, column=0)
        tk.Label(altSubFrame, text='Vexit <=').grid(row=0, column=0)
        self.vExitLeftVal = tk.Spinbox(altSubFrame, from_=0.1, to=20.00,
                                       increment=0.1, format='%4.2f', width=5,
                                       textvariable=self.vExitLeftValue)
        self.vExitLeftVal.grid(row=0, column=1)
        tk.Label(altSubFrame, text='[V] or Vexit >=').grid(row=0, column=2)
        self.vExitRightVal = tk.Spinbox(altSubFrame, from_=0.1, to=20.00,
                                        increment=0.1, format='%4.2f', width=5,
                                        textvariable=self.vExitRightValue)
        self.vExitRightVal.grid(row=0, column=3)
        tk.Label(altSubFrame, text='[V]').grid(row=0, column=4)

        tk.Label(altSubFrame, text='Iexit <=').grid(row=1, column=0)
        self.iExitLeftVal = tk.Spinbox(altSubFrame, from_=0.1, to=20.00,
                                       increment=0.1, format='%4.2f', width=5,
                                       textvariable=self.iExitLeftValue)
        self.iExitLeftVal.grid(row=1, column=1)
        tk.Label(altSubFrame, text='[A] or Iexit >=').grid(row=1, column=2)
        self.iExitRightVal = tk.Spinbox(altSubFrame, from_=0.1, to=20.00,
                                        increment=0.1, format='%4.2f', width=5,
                                        textvariable=self.iExitRightValue)
        self.iExitRightVal.grid(row=1, column=3)
        tk.Label(altSubFrame, text='[A]').grid(row=1, column=4)
        #------button section--------------------------------------------------
        jobButtonFrame = tk.Frame(schedulerFrame)
        jobButtonFrame.grid(row=1, column=1)
        self.addBut = tk.Button(jobButtonFrame, text='Add job',
                                command=self._addJob, **st.but)
        self.addBut.grid(row=0, column=0, padx=5, sticky=tk.EW)
        self.delBut = tk.Button(jobButtonFrame, text='Delete job',
                                command=self._delJob, **st.but)
        self.delBut.grid(row=1, column=0, padx=5, sticky=tk.EW)
        #-------job queue section----------------------------------------------
        queueLabel = ttk.Label(self, text='Job queue', **st.subSubFr)
        queueSubFrame = ttk.LabelFrame(schedulerFrame,
                                       padding='3 3 12 12',
                                       labelwidget=queueLabel)
        queueSubFrame.grid(row=0, column=2, rowspan=2, sticky=(tk.NSEW))
        #  4 LOGICAL columns (#0 + self.dataCols) , #0 is a main tree root
        self.dataCols = ('activity', 'value', 'how long', 'vExitLeft',
                         'vExitRight', 'iExitLeft', 'iExitRight')
        self.jobTree = ttk.Treeview(columns=self.dataCols,
                                    displaycolumns=self.dataCols[:3])
        ysb = ttk.Scrollbar(orient=tk.VERTICAL, command=self.jobTree.yview)
        xsb = ttk.Scrollbar(orient=tk.HORIZONTAL, command=self.jobTree.xview)
        self.jobTree['yscroll'] = ysb.set
        self.jobTree['xscroll'] = xsb.set
        for col in self.dataCols:
            self.jobTree.heading(col, text=col, anchor='center')
            self.jobTree.column(col, stretch=100, width=100, anchor=tk.W)
        self.jobTree.column('#0', stretch=20, width=20)
        self.jobTree.grid(in_=queueSubFrame, row=0, column=0, sticky=tk.NSEW)
        ysb.grid(in_=queueSubFrame, row=0, column=1, sticky=tk.NS)
        xsb.grid(in_=queueSubFrame, row=1, column=0, sticky=tk.EW)
        queueSubFrame.columnconfigure(0, weight=999)
        queueSubFrame.columnconfigure(1, weight=1)
        queueSubFrame.rowconfigure(0, weight=999)
        self.delCandidate = None  # candidate node to delete
        self.jobTree.bind('<<TreeviewSelect>>', self._delPrepare)
        self.rootTree = self.jobTree.insert('', tk.END, open=True)
        self.firsts = [None, None]  # list of special first nodes
        #-------button section-------------------------------------------------
        schedulerButtonFrame = tk.Frame(schedulerFrame)
        schedulerButtonFrame.grid(row=1, column=3)
        self.startBut = tk.Button(schedulerButtonFrame, text='Start',
                                  cursor='shuttle', command=self._start,
                                  **st.but)
        self.startBut.grid(row=0, column=0, padx=5, sticky=tk.EW)
        self.stopBut = tk.Button(schedulerButtonFrame, text='Stop',
                                 cursor='X_cursor', command=self._stop,
                                 **st.but)
        self.stopBut.grid(row=1, column=0, padx=5, sticky=tk.EW)
        self.loadBut = tk.Button(schedulerButtonFrame, text='Load',
                                 command=self._load, **st.but)
        self.loadBut.grid(row=2, column=0, padx=5, sticky=tk.EW)
        self.saveBut = tk.Button(schedulerButtonFrame, text='Save',
                                 command=self._save, **st.but)
        self.saveBut.grid(row=3, column=0, padx=5, sticky=tk.EW)

        schedulerFrame.grid(row=1, column=0, padx=5, pady=5, columnspan=4,
                            sticky=(tk.NSEW))
        self.saveDir = os.path.join(os.getcwd(), 'save')
        #--------------PLOT PANEL----------------------------------------------
        plotLabel = ttk.Label(self, text='Plot window', **st.subFr)
        self.plotFrame = ttk.LabelFrame(self, padding='3 3 12 12',
                                        labelwidget=plotLabel)
        self.plotFrame.grid(row=0, column=1, columnspan=3, padx=5, pady=5,
                            sticky=(tk.NSEW))
        self.VQueue = deque([0] * 50, maxlen=50)  # last V values from server
        self.IQueue = deque([0] * 50, maxlen=50)  # last I values from server
        self.matFrame = plot.PlotFrame(self.plotFrame, self.VQueue,
                                       self.IQueue, 2000, self.neutral)
        #--------------THE REST------------------------------------------------
        self.queueWidgets = {self.vVal, self.sVal, self.vExitLeftVal,
                             self.vExitRightVal, self.stopBut, self.loadBut,
                             self.iExitLeftVal, self.iExitRightVal,
                             self.addBut, self.delBut, self.startBut,
                             self.saveBut}
        self.initWidgets = {self.vMaxVal, self.iMaxVal}
        topw = self.root.winfo_toplevel()
        topw.columnconfigure(0, weight=1)
        topw.rowconfigure(0, weight=1)
        self.root.geometry('{}x{}+{}+{}'.format(880, 500, 0, 0))
        self._blockWidgets(self.initWidgets | self.queueWidgets)

    def _connect(self):
        """connects with local Pyro4 server"""
        try:
            if not self.server.get():
                raise ValueError
            uri = ''.join(('PYRO:psuServer@', self.server.get(), ':50000'))
            self.psuServer = Pyro4.Proxy(uri)
            self.psuServer._pyroBind()
            self.status.configure(text='online', foreground='green')
            i = '#---Connection with : {} established.'.format(self.psuServer)
            logger.debug(i)
            self.psuServer.keybOff()  # from now on PSU is blocked !!!
            self.minmax = list(self.psuServer.getMinMax())
            self._setDefaultStartTime()
            self._setDefaultMinMaxSpins()
            self._initiateSchedSpins()
            self._pressed(self.connectBut)
            self._blockWidgets(self.queueWidgets | self.initWidgets, False)
            self._createFirstBatch()  # initiate first part of the batch
            self.matFrame.plot()
        except Exception as err:
            warn = 'Can`t connect to {}:\n{}'.format(self.psuServer, err)
            self.psuServer = None
            self.status.configure(text='offline', foreground='red')
            self._blockWidgets(self.initWidgets | self.queueWidgets)
            logger.debug('#---{}.'.format(warn))
            messagebox.showwarning('Connection Error', warn,
                                   parent=self.root)

    def _disconnect(self):
        """disconnects Pyro4 Proxy with the Server,
           this works also as panic button"""
        try:
            if not self.psuServer:
                raise ValueError
            info = '#---Connection with : {} closed.'.format(self.psuServer)
            self.psuServer.stopScheduler()
            self.psuServer.psuManualMode()  # turn off PSU and turn on keyboard
            self.psuServer._pyroRelease()
            self.psuServer = None
            self.status.configure(text='offline', foreground='red')
            logger.debug(info)
            self._blockWidgets(self.queueWidgets | self.initWidgets)
            self._pressed(self.connectBut, False)
            self._clearTree()
        except Exception as err:
            warn = 'Can`t disconnect {}:\n{}'.format(self.psuServer, err)
            logger.debug('#{}.'.format(warn))
            messagebox.showwarning('Disconnection Error', warn,
                                   parent=self.root)

    def _pressed(self, button, press=True):
        """changes button apperance from normal to pressed and vice versa

        Arguments:
            button -> tkinter button object
            press  -> (boolean) provides pressed apperance if True

        Returns:"""
        if press:
            button.configure(**self.butPress)
        else:
            button.configure(**self.butNorm)

    #-------------------scheduler panel---------------------------------------
    def _updateFirstJobs(self):
        """updates first two jobs in the treeview(set Max V and set Max I)"""
        for i in (0, 1):
            volamp = 'A' if i else 'V'
            if self.firsts[i]:  # at first remove old job from the treeview
                self.jobTree.delete(self.firsts[i])
            self.firsts[i] = self.jobTree.insert(parent=self.rootTree, index=i,
                             values=(self.firstBatch[i][0][0],
                             '{} {}'.format(self.firstBatch[i][0][1], volamp),
                             'always'))

    def _createFirstBatch(self):
        """adds first two jobs to the batch, use this function at the end of
           processing"""
        self.firstBatch.clear()
        self.firstBatch.append([('maxv', float(self.initMaxV.get())), 0.05])
        self.firstBatch.append([('maxi', float(self.initMaxI.get())), 0.05])
        self._updateFirstJobs()

    def _createBatch(self):
        """creates batch for server`s scheduler from ttk treeview objects"""
        self.batch.clear()
        self.batch = self.firstBatch + self.batch  # add obligatory jobs
        for record in self._createRecords():
            self.batch.append(record)

    def _createRecords(self):
        """yields job records ready to process by outer function

        Arguments:

        Yields:
            list -> [what(tuple), how_long(float), ...(tuples)]"""
        for job in self.jobTree.get_children(item=self.rootTree):
            if job in self.firsts:
                continue  # ignore obligatory jobs (added previously)
            what = (self.jobTree.item(item=job)['values'][0],
                    float(self.jobTree.item(item=job)['values'][1].split()[0]))
            leng = float(self.jobTree.item(item=job)['values'][2].split()[0])
            subjob = self.jobTree.get_children(item=job)
            exitVL = ('V', '>=', float(self.jobTree.item(item=subjob)['values'][3]))
            exitVR = ('V', '<=', float(self.jobTree.item(item=subjob)['values'][4]))
            exitIL = ('I', '>=', float(self.jobTree.item(item=subjob)['values'][5]))
            exitIR = ('I', '<=', float(self.jobTree.item(item=subjob)['values'][6]))
            yield [what, leng, exitVL, exitVR, exitIL, exitIR]

    def _createNode(self, record):
        """creates ttk treeview nodes to process by outer function

        Arguments:
            record -> [what(tuple), how_long(float), ...(tuples)]

        Returns:"""
        what, leng, exitVL, exitVR, exitIL, exitIR = record
        cid = self.jobTree.insert(parent=self.rootTree, index=tk.END,
                                  values=('setv', '{} V'.format(what[1]),
                                          '{} s'.format(leng)), open=False)
        strV = '{}>V>{}'.format(exitVL[2], exitVR[2])
        strI = '{}>I>{}'.format(exitIL[2], exitIR[2])
        self.jobTree.insert(parent=cid, index=tk.END,
                            values=('', strV, strI, exitVL[2], exitVR[2],
                                    exitIL[2], exitIR[2]))

    def _addJob(self):
        """adds job to the treeview(button handler)"""
        record = [('setv', self.vValue.get()), self.sValue.get(),
                  ('V', '>=', self.vExitLeftValue.get()),
                  ('V', '<=', self.vExitRightValue.get()),
                  ('I', '>=', self.iExitLeftValue.get()),
                  ('I', '<=', self.iExitRightValue.get())]
        self._createNode(record)

    def _clearTree(self):
        """clears ttk treeview object from old inputs"""
        for job in self.jobTree.get_children(item=self.rootTree):
            self.jobTree.delete(job)
        self.firstBatch.clear()
        self.batch.clear()
        self.firsts = [None, None]

    def _delPrepare(self, *event):
        """returns nodes` ids ready to delete (ttk.treeview event handler)

        Arguments:
           event -> tkinter Event object (ignored)

        Returns:"""
        self.delCandidate = self.jobTree.selection()

    def _delJob(self):
        """removes job from the scheduler list(button handler)"""
        try:
            if not self.delCandidate[0] in self.firsts:
                self.jobTree.delete(self.delCandidate)
            else:
                warn = 'Can`t remove obligatory jobs!'
                logger.debug('#{}.'.format(warn))
                messagebox.showwarning('Deletion Error', warn, parent=self.root)
        except (TclError, TypeError):  # no job chosen
            pass

    def _initiateSchedSpins(self):
        """prepares scheduler spinboxes"""
        self._setSpin(self.vExitRightVal, self.vExitRightValue,  # V max
                      self.minmax[0], self.initMaxV.get(), self.initMaxV.get())
        self._setSpin(self.vExitLeftVal, self.vExitLeftValue,  # V min
                      self.minmax[0], self.minmax[1], self.minmax[0])
        self._setSpin(self.iExitRightVal, self.iExitRightValue,  # I max
                      self.minmax[2], self.initMaxI.get(), self.initMaxI.get())
        self._setSpin(self.iExitLeftVal, self.iExitLeftValue,  # I min
                      self.minmax[2], self.minmax[3], self.minmax[2])
        self._setSpin(self.vVal, self.vValue,  # V min
                      self.minmax[0], self.initMaxV.get(), self.initMaxV.get())
        self._createFirstBatch()  # always refresh first part of the batch

    #--------client-server time handling methods-------------------------------
    def _setDefaultStartTime(self):
        """sets default values for start scheduler time"""
        string = self.psuServer.getServerTimeNow()  # from server host
        dt = self._decodeSrvTime(string)
        dt += datetime.timedelta(seconds=20)  # add arbitrary amount of time
        self.initHour.set(dt.hour)
        self.initMinute.set(dt.minute)
        self.initSecond.set(dt.second)

    def _checkStartTime(self):
        """checks if scheduler start time is properly set"""
        dtCheck = self._getStartTime()
        delta = datetime.timedelta(seconds=5)
        string = self.psuServer.getServerTimeNow()  # from server host
        dtNow = self._decodeSrvTime(string)
        if dtCheck - dtNow < delta:  # time incorrectly set
            raise TimeError('Start time must be now() + 5 s (at least)')

    def _getStartTime(self):
        """gets start time in the form of datetime.datetime object

        Arguments:

        Returns:
            datetime.datetime object"""
        hour = int(self.initHour.get())
        minute = int(self.initMinute.get())
        second = int(self.initSecond.get())
        string = self.psuServer.getServerTimeNow()  # from server host
        dtStart = self._decodeSrvTime(string)
        #!!!! replace RETURNS (NOT changes in place!!!!!!!!!!!!!!!!!!!)
        dtStart = dtStart.replace(hour=hour, minute=minute, second=second)
        return dtStart

    def _decodeSrvTime(self, timeString):
        """decodes time string from server

        Arguments:
            timeString -> (string) formated string

        Returns:
            datetime.datetime object"""
        dt = datetime.datetime.strptime(timeString, st.dtFormat)
        return dt

    def _getStartTimeString(self):
        """returns start time in the form of seconds since epoch

        Arguments:

        Returns:
            formated string"""
        dt = self._getStartTime()
        return dt.strftime(st.dtFormat)

    def _setDefaultMinMaxSpins(self):
        """sets default values for Max V and Max I
           spinboxes after succesfull connection"""
        self._setSpin(self.vMaxVal, self.initMaxV, self.minmax[0],
                      self.minmax[1], self.minmax[1])  # default V max
        self._setSpin(self.iMaxVal, self.initMaxI, self.minmax[2],
                      self.minmax[3], self.minmax[3])  # default I max

    def _setSpin(self, spin, textvariable, from_, to, value):
        """updates internal tkinter`s spinbox values

        Arguments:
            spin           -> tkinter spinbox object
            textvariable   -> spinbox` textvariable
            from_ (double) -> min value
            to (double)    -> max value
            value (double) -> actual value of the spinbox

        Returns:"""
        textvariable.set(value)
        spin['from_'] = from_
        spin['to'] = to

    def _start(self):
        """starts scheduler"""
        off = (self.initWidgets | self.queueWidgets)  # turn off all widgets
        off -= set((self.startBut, self.stopBut))     # except Stop button
        try:
            self._checkStartTime()
            self._blockWidgets(off)  # block almost all widgets
            self._createBatch()  # creates batch for server
            self.psuServer.setQueue(self.batch)  # send the batch to server
            #  fire batch processing: NOT in the form of independent thread
            #  because this operation must be performed on the server side,
            #  fireing new thread here would block client completly!!!
            self.psuServer.startScheduler(self._getStartTimeString(),
                                          float(self.frequency.get()))
            #  fire start button apperance service : this operation could be
            #  performed in client thread
            self.thrBut = threading.Thread(target=self._buttonThread, args=(),
                                        name='buttons', daemon=True)
            self.thrBut.start()
            #  data producer thread for matplotlib plot
            self.dataThr = threading.Thread(target=self._dataThread, args=(),
                                            name='data producer', daemon=True)
            self.dataThr.start()
        except Exception as er:
            logger.debug('#{}.'.format(er))
            self._blockWidgets(off, False)  # unblock almost all widgets
            messagebox.showwarning('Start Time Error', er, parent=self.root)

    def _buttonThread(self):
        """threaded function to service start button apperance"""
        self._pressed(self.startBut)
        while True:
            flag = self.psuServer.getSchedulerStatus()
            time.sleep(float(self.frequency.get()))
            if not flag:
                self._blockWidgets(self.initWidgets | self.queueWidgets, False)
                self._pressed(self.startBut, False)
                break

    def _stop(self):
        """stops scheduler"""
        self.psuServer.stopScheduler()
        self._pressed(self.startBut, False)

    def _load(self):
        """loads preprepared queue of jobs into scheduler"""
        try:
            lf = fdi.askopenfile(mode='rb', defaultextension='.sav',
                                 initialdir=self.saveDir, parent=self.root,
                                 title='Load saved job queue.',
                                 filetypes=[('saved jobs', '*sav')])
            with lf:
                records = pickle.load(lf)
            self._clearTree()            # \
            self._createFirstBatch()     # /  treeview preparing
            for record in records:
                self._createNode(record)
        except Exception as er:
            msg = '{}\nNo save directory.\nPlease save first.'.format(er)
            messagebox.showerror(message=msg, parent=self.root)

    def _save(self):
        """saves prepared queue of jobs into file"""
        if(not os.path.exists(self.saveDir)):  # create dir if needed
            os.mkdir(path=self.saveDir)
        sfd = fdi.asksaveasfilename(title='Saving job queue', parent=self,
                                    initialdir=self.saveDir,
                                    defaultextension='.sav',
                                    filetypes=[('saved jobs', '*.sav')],
                                    confirmoverwrite=True)
        try:
            records = []  # create ONE object to pickle
            for record in self._createRecords():
                records.append(record)
            with open(sfd, mode='wb') as configFile:
                pickle.dump(records, configFile)  # pickle ONE object(don`t append)
        except FileNotFoundError:
            pass

    def _safeExit(self):
        """cleanly closes connection with PSU server before program exit"""
        if self.psuServer:
            self._disconnect()
        logger.debug('#PSU client program exited.')
        self.root.destroy()

    def _blockWidgets(self, widgets, block=True):
        """unblocks (blocks) tkinter widgets
        Arguments:
            widgets         -> list of tkinter`s widget to block(unblock)
            block (boolean) -> if True block otherwise unblocks

        Returns:"""
        for widget in widgets:
            if block:
                widget['state'] = 'disabled'
            else:
                widget['state'] = 'normal'

    def _dataThread(self):
        """threaded method which populates V an I queues with fresh data"""
        while self.psuServer.getSchedulerStatus():
            time.sleep(2)
            lastVIP = self.psuServer.getVIP()
            self.VQueue.popleft()
            self.IQueue.popleft()
            self.VQueue.append(lastVIP[0])
            self.IQueue.append(lastVIP[1])
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
def main():
    clientLog = open(file='logs/PSUclient.log', mode='a+')
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream=clientLog)
    FORMAT = '{message}\t\t{asctime} {levelname}'
    formater = logging.Formatter(FORMAT, style='{')
    handler.setFormatter(formater)
    logger.addHandler(handler)
    root = tk.Tk()
    mainPanel = MainPanel(root)
    mainPanel.grid(row=0, column=0)
    root.iconbitmap('@' + 'libs/plug.xbm')
    root.title('Voltcraft Power Supply Unit remote scheduler')
    root.protocol('WM_DELETE_WINDOW', mainPanel._safeExit)
    root.mainloop()
#-----------------------------------------------------------------------------
if __name__ == '__main__':
    main()
