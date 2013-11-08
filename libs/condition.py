#!/usr/bin/env python
from modelsDict import models, operators, lefts


#error classes for Condition class:
class WrongOperatorError(Exception):
    pass


class OffLimitsError(Exception):
    pass


class WrongVariableError(Exception):
    pass


class WrongModelError(Exception):
    pass


class DiffConditionTypes(Exception):
    pass


class CompactRangeError(Exception):
    pass


def get_raw_range(cond_type='V', model='12010'):
    """returns range of values for particular model

    Arguments:
        cond_type -> (modelsDict.lefts key, optional)type of condition
        model     -> (modelsDict.models key, optional) PSU model

    Returns:
        tuple of floats (min, max)"""
    return models[model][cond_type + 'min'], models[model][cond_type + 'max']


def get_list_range(cond_list):
    """returns common part of all conditions on the list.
    Conditions on the list must be the same type (V, I or P) and for the same
    PSU model (12010, 1405, 1803).

    Arguments:
        cond_list -> list of conditions

    Returns:
        (min range, max range) tuple"""
    cond_type = cond_list[0].left  # first cond on the list determines
    cond_model = cond_list[0].model  # model and operator:no need to have additional arguments
    ranges = []
    for cond in cond_list:
        if cond.model != cond_model:
            raise WrongModelError('Wrong model : {} on the : {} list'.format(cond.model, cond_model))
        if cond.left != cond_type:
            raise WrongOperatorError('Wrong operator :{} on the : {} list'.format(cond.left, cond_type))
        ranges.append(cond.get_range())
    #minimax criterion:
    local_min = max(ranges, key=lambda x: x[0])[0]  # choose max from the min
    local_max = min(ranges, key=lambda x: x[1])[1]  # choose min from the max
    if local_min >= local_max:
        raise CompactRangeError()
    return local_min, local_max


#method decorator with arguments: checks if setters get valid values
def _dec_check_val(dictionary, error_class):
    def _dec_real(function):
        def wrapper(*args, **kwargs):
            if args[1] not in dictionary:
                msg = "Unrecognizable variable value: {}.".format(args[1])
                raise error_class(msg)
            return function(*args, **kwargs)
        return wrapper
    return _dec_real


class Condition():
    def __init__(self, model, left, operator, right):
        """Arguments:
            model    ->    (string) PSU model
            left     ->    (string) variable (I, V)
            operator ->    (string) >=, <=
            right    ->    (float)  parameter"""
        self.model = model
        self.left = left
        self.right = right
        self.operator = operator

    def getModel(self):
        return self.__dict__['model']

    @_dec_check_val(dictionary=models, error_class=WrongModelError)
    def setModel(self, val):
        self.__dict__['model'] = val
    model = property(getModel, setModel)

    def getLeft(self):
        return self.__dict__['left']

    @_dec_check_val(dictionary=lefts, error_class=WrongVariableError)
    def setLeft(self, val):
        self.__dict__['left'] = val
    left = property(getLeft, setLeft)

    def getOperator(self):
        return self.__dict__['operator']

    @_dec_check_val(dictionary=operators, error_class=WrongOperatorError)
    def setOperator(self, val):
        self.__dict__['operator'] = val
    operator = property(getOperator, setOperator)

    def getRight(self):
        return self.__dict__['right']

    def setRight(self, val):
        if self.left == 'V':
            if val < models[self.model]['Vmin'] or val > models[self.model]['Vmax']:
                msg = 'Wrong V value: {}'.format(val)
                raise OffLimitsError(msg)
        elif self.left == 'I':
            if val < models[self.model]['Imin'] or val > models[self.model]['Imax']:
                msg = 'Wrong I value: {}'.format(val)
                raise OffLimitsError(msg)
        elif self.left == 'P':
            if val < models[self.model]['Pmin'] or val > models[self.model]['Pmax']:
                msg = 'Wrong P value: {}'.format(val)
                raise OffLimitsError(msg)
        self.__dict__['right'] = round(val, 2)
    right = property(getRight, setRight)

    def __str__(self):
        msg = 'Model:{} --> {} {} {}'
        return msg.format(self.model, self.left, self.operator, self.right)

    def get_range(self):
        """extracts range from condition

        Arguments:

        Returns:
            tuple (min_range, max_range)"""
        if self.operator == '>=':
            local_min = self.right
            local_max = models[self.model][self.left + 'max']
        else:
            local_min = models[self.model][self.left + 'min']
            local_max = self.right
        return local_min, local_max

if __name__ == '__main__':
    import sys
    my_model = '12010'
    print('Raw V range for {} : {}'.format(my_model,
                                           get_raw_range('V', my_model)))
    print('Raw I range for {} : {}'.format(my_model,
                                           get_raw_range('I', my_model)))
    print('Raw P range for {} : {}'.format(my_model,
                                           get_raw_range('P', my_model)))
    conditions = []
    c1 = Condition(my_model, 'V', '>=', 12.34)
    conditions.append(c1)
    c2 = Condition(my_model, 'I', '<=', 5.05)
    conditions.append(c2)
    c3 = Condition(my_model, 'V', '<=', 5.05)
    conditions.append(c3)
    c4 = Condition(my_model, 'V', '>=', 5.05)
    conditions.append(c4)
    c5 = Condition(my_model, 'V', '<=', 15.05)
    conditions.append(c5)
    k = 1
    for i in conditions:
        print('Condition c{}: {}'.format(k, i))
        k += 1
    k = 2
    for i in conditions[1:]:
        try:
            print('Range between c1 an c{} : {}'.format(k, get_list_range([conditions[0], conditions[k - 1]])))
        except:
            print('get_list_range(c1, c{}): Exception {} trapped.'.format(k, sys.exc_info()[0]))
        finally:
            k += 1
    my_operator = '>='
    my_left = 'I'
    my_right = 4
    my_fake = 666
    tester = Condition(my_model, my_left, my_operator, my_right)
    for name, value in tester.__dict__.items():
        try:
            setattr(tester, name, my_fake)
        except:
            print('Exception {} trapped.'.format(sys.exc_info()[0]))
        finally:
            tester.model = my_model
            tester.left = my_left
            tester.operator = my_operator
            tester.right = my_right
