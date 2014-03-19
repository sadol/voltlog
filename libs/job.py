#!/usr/bin/env python
import libs.condition as condition


class WrongConditionSet(Exception):
    pass


class Job():
    """
    Voltcraft`s PSU basic work unit.
    """
    def __init__(self, psu, what, how_long=0, stop_cond=[]):
        """Arguments:
            psu  -> (VoltcraftPSU object) power supply object
            what -> (tuple : (func alias, float)) VoltdraftPSU method
                     func aliases : `setv', `maxv', `maxi'
                                    for example : ...('setv', 5.59)...
            how_long  -> (float) jobs time constraint, maximium amount of sec
                        scheduled for this job to complete.
            stop_cond-> (list of condition.Condition objects , optional)
                         alternative to `how_long' stopping conditions list

        Returns:

        WARNING: job is stpped by scheduler only if ALL conditions
                 on the stop list of conditions are satisfied or `how_long' is
                 exceeded."""
        self.psu = psu  # PSU device
        self.what = what  # action
        self.how_long = how_long
        self.stop_cond = stop_cond
        #psu function aliases defined here (not in modelDicts module)
        aliases = ('setv', 'maxv', 'maxi')
        self.funcs = dict(zip(aliases, (self.psu.setVoltage,
                                        self.psu.setMaxVoltage,
                                        self.psu.setMaxCurrent)))
        #internal job conditions` dictionary of subsets:
        self.subs = {'V': [], 'I': [], 'P': []}
        #populates subsets according to stop conds lists
        self._pop_subs(self.stop_cond)

    def getHowLong(self):
        return self.__dict__['how_long']

    def setHowLong(self, length):
        """This variable must be properly set because it acts as a safety'fuse'
        in case of incorectly set stop conditions list."""
        if length < 0:
            msg = 'how_long :{} , this variable must be set as positive int.'
            msg = msg.format(length)
            raise WrongConditionSet(msg)
        self.__dict__['how_long'] = int(length)
    how_long = property(getHowLong, setHowLong)

    def run(self):
        """runs the job and updates.
        WARNING: self.psu device must prepared earlier by scheduler to proper
                 use this function"""
        if(self.what[1] is not None):
            self.funcs[self.what[0]](self.what[1])  # setter

    def _pop_subs(self, cond_list):
        """Internal initialization method.
        Populates subsets of ranges and performs simple checks on them.

        Arguments:
            cond_list -> list of condition objects

        Returns:"""
        V, I, P = [], [], []
        for cond in cond_list:  # divide list on local sublists:
            if cond.left == 'V':
                V.append(cond)
            elif cond.left == 'I':
                I.append(cond)
            elif cond.left == 'P':
                P.append(cond)

        temp_dict = {'V': V, 'I': I, 'P': P}
        for ranges in self.subs.items():  # calculate ranges
            if len(temp_dict[ranges[0]]) > 0:  # for nonempty local sublist
                temp_range = condition.get_list_range(temp_dict[ranges[0]])
                ranges[1].append(temp_range[0])  # minimum
                ranges[1].append(temp_range[1])  # maximum
            else:  # for empty local sublist
                temp_range = condition.get_raw_range(ranges[0], self.psu.model)
                ranges[1].append(temp_range[0])  # minimum
                ranges[1].append(temp_range[1])  # maximum

        #and now check calculated P self.subs ranges:
        power_min = self.subs['V'][0] * self.subs['I'][0]
        power_max = self.subs['V'][1] * self.subs['I'][1]
        if ((self.subs['P'][0] < power_min) or (self.subs['P'][1] > power_max)):
            #correct P range silently (I and V take precedence over P):
            self.subs['P'] = power_min, power_max

    def getInfo(self):
        """gets info about a job in the form of tuple of strings

        Arguments:

        Rreturns:
            tuple (psu, what, how_long, cond_list)
        """
        conds = [cond for cond in self.subs.items()]
        return self.psu.model, self.what, self.how_long, conds

if __name__ == '__main__':
    import time
    import voltcraftPSU
    import sys
    my_model = '12010'
    my_port = '/dev/ttyUSB0'
    psu = voltcraftPSU.VoltcraftPSU(my_port)
    psu.getID()
    my_length = 2
    try:
        psu.remoteMode()
        #first simple:
        job1 = Job(psu=psu, what=('setv', 10), how_long=my_length)
        job1.run()
        time.sleep(my_length + 2)  # instead of thread blocade
        #next jobs can`t be run because of lack of scheduler in the import list
        #only scheduler can manage conds correctly and run jobs accordingly
        v1 = condition.Condition(my_model, 'V', '>=', 5)
        c1 = condition.Condition(my_model, 'I', '>=', 0.25)
        c2 = condition.Condition(my_model, 'I', '<=', 0.50)
        p1 = condition.Condition(my_model, 'P', '<=', 10)
        p2 = condition.Condition(my_model, 'P', '>=', 4)
        my_stop = [v1, c1, c2, p1, p2]
        job2 = Job(psu=psu,
                   what=('maxi', 1.00),
                   how_long=my_length,
                   stop_cond=my_stop)
        print('job2 internal ranges {}: '.format(job2.subs))
    except:
        print('Exception {} trapped.'.format(sys.exc_info()))
    finally:
        psu.manualMode()
