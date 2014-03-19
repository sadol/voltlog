#/usr/lib/env python
import matplotlib as mpl
mpl.use('TkAgg')
#from matplotlib import pyplot as plt  # DONT USE IT WITH TKINTER!!!!!!!!!!!!!!
from matplotlib.figure import Figure  # USE THIS INSTEAD!!!!!!!!!!!!!
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as tkCanvas


class PlotFrame():
    """tkinter frame with embeded matplotlib real-time suplot object"""
    def __init__(self, root, VQueue, IQueue, delay, color):
        """PlotFrame constructor

        Arguments:
            root      -> tkinter root frame
            VQueue    -> deque object with 50 samples of fresh V data from PSU
            IQueue    -> deque object with 50 samples of fresh I data from PSU
            delay     -> int(miliseconds) refresh delay
            color     -> background color"""
        self.root = root
        self.delay = delay
        self.color = color
        self.tData = range(50)             # x axis for both V and I
        self.VQueue = VQueue               # internal queue of V values to plot
        self.IQueue = IQueue               # internal queue of I values to plot
        #  DONT USE PYPLOT WITK TKAGG CANVAS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        #self.fig = plt.figure(figsize=(5, 1.7))
        #  USE NATIVE matplotlib.figure.Figure() INSTEAD!!!!!!!!!!!!!!!!!!!!!!!
        self.fig = Figure(figsize=(5, 1.2), facecolor=self.color,
                          edgecolor=self.color, frameon=False, linewidth=0.00)
        self.fig.subplots_adjust(left=0.15, right=0.85)  # important
        self.canvas = tkCanvas(self.fig, master=self.root)
        self.axesV = self.fig.add_subplot(1, 1, 1)        # left y ax is V
        self.axesI = self.axesV.twinx()                   # right y ax is I
        self.labelsV = self.axesV.set_ylim([0, 20])
        self.labelsI = self.axesI.set_ylim([0, 10])
        self.axesV.set_ylabel('voltage [V]', color='g', size='small')
        self.axesI.set_ylabel('current [A]', color='r', size='small')
        self.axesV.tick_params(axis='y', colors='g')
        self.axesI.tick_params(axis='y', colors='r')
        self.axesV.spines['left'].set_color('g')
        self.axesV.spines['right'].set_color('r')
        self.lineV, = self.axesV.plot(self.tData, self.VQueue, 'g-',
                                      label='V', linewidth=2)
        self.lineI, = self.axesI.plot(self.tData, self.IQueue, 'r-',
                                      label='I', linewidth=2)
        lines = self.lineV, self.lineI
        labels = [line.get_label() for line in lines]
        self.axesV.legend(lines, labels, loc=2, fontsize='small',
                          frameon=False, framealpha=0.5)  # stackoverflow trick
        self.canvas.get_tk_widget().grid()

    def plot(self):
        """draws V and I plot on the tkinter canvas

        Arguments:

        Rreturns:
            "after" job ID which can be intercept for cancel thread"""
        self.axesV.set_ylim(self._setLimits(self.VQueue))
        self.axesI.set_ylim(self._setLimits(self.IQueue))
        self.lineV.set_ydata(self.VQueue)
        self.lineI.set_ydata(self.IQueue)
        self.canvas.draw()
        self.root.after(self.delay, self.plot)

    def _setLimits(self, dequeObj):
        """sets y range limits for self.plotObj

        Arguments:
            dequeObj -> collection.deque object populated with values

        Returns:
            list [min, max] values (with offsets) of the argument"""
        mi = min(dequeObj)
        ma = max(dequeObj) + 0.1  # prevents overlaping min and max boundiaries
        return [mi - (0.1 * mi), ma + (0.1 * ma)]
