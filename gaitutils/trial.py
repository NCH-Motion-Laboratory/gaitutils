# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Read gait trials.

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division, print_function
import copy
from gaitutils import read_data, utils, eclipse, nexus
#from fileutils import is_c3dfile
from envutils import debug_print
import numpy as np
import os
import os.path as op
import btk  # biomechanical toolkit for c3d reading
import models
from emg import EMG


class GaitDataError(Exception):
    """ Custom exception class. Stores a message. """

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class Gaitcycle:
    """" Holds information about one gait cycle. Offset is the frame where
    the data begins; 1 for Vicon Nexus (which always returns whole trial) and
    start of the ROI for c3d files, which contain data only for the ROI. """

    def __init__(self, start, end, offset, toeoff, context, smp_per_frame):
        self.offset = offset
        self.len = end - start
        self.start = start - offset
        self.end = end - offset
        self.toeoff = toeoff - offset
        # which foot begins and ends the cycle
        self.context = context
        # start and end on the analog samples axis; round to whole samples
        self.start_smp = int(round(self.start * smp_per_frame))
        self.end_smp = int(round(self.end * smp_per_frame))
        self.len_smp = self.end_smp - self.start_smp
        # normalized x-axis (% of gait cycle) of same length as cycle
        self.t = np.linspace(0, 100, self.len)
        # normalized x-axis of 0,1,2..100%
        self.tn = np.linspace(0, 100, 101)
        # normalize toe-off event to the cycle
        self.toeoffn = round(100*((self.toeoff - self.start) / self.len))

    def __repr__(self):
        s = '<Gaitcycle |'
        s += ' offset: %d' % self.offset
        s += ' start: %d' % self.start
        s += ' end: %d' % self.end
        s += ' context: %s' % self.context
        s += ' toeoff: %d' % self.toeoff
        s += '>'
        return s

    def normalize(self, var):
        """ Normalize frames-based variable var to the cycle.
        New interpolated x axis is 0..100% of the cycle. """
        return np.interp(self.tn, self.t, var[self.start:self.end])

    def cut_analog_to_cycle(self, var):
        """ Crop analog variable (EMG, forceplate, etc. ) to the
        cycle; no interpolation. """
        return var[self.start_smp:self.end_smp]


class Trial:
    """ A gait trial. Contains:
    -subject and trial info
    -gait cycles
    -analog data (EMG, forceplate, etc.)
    -model output variables (Plug-in Gait, muscle length, etc.)
    """

    def __repr__(self):
        s = '<Trial |'
        s += '>'
        return s

    def __init__(self, source):
        # read metadata into instance attributes
        self.source = source
        meta = read_data.get_metadata(source)
        self.__dict__.update(meta)
        # events may be in wrong temporal order, at least in c3d files
        for li in [self.lstrikes, self.rstrikes, self.ltoeoffs,
                   self.rtoeoffs]:
            li.sort()
        # get description and notes from Eclipse database
        if not self.sessionpath[-1] == '\\':
            self.sessionpath = self.sessionpath+('\\')
        self.trialdirname = self.sessionpath.split('\\')[-2]
        enfpath = self.sessionpath + self.trialname + '.Trial.enf'
        if op.isfile(enfpath):
            self.eclipse_data = eclipse.get_eclipse_keys(enfpath)
        self.kinetics = utils.kinetics_available(source)
        # analog and model data are only read if requested
        self._emg = None
        self._forceplate = None
        self._models_data = dict()
        # normalized x-axis of 0, 1, 2 .. 100%
        self.tn = np.linspace(0, 100, 101)
        self.samplesperframe = self.analograte/self.framerate
        self.cycles = list(self._scan_cycles())
        self.ncycles = len(self.cycles)
        self.video_files = nexus.get_video_filenames(self.sessionpath +
                                                     self.trialname)

    @property
    def emg(self):
        if not self._emg:
            self._emg = EMG(self.source)
            self._emg.read()
        return self._emg

    @property
    def forceplate(self):
        if not self._forceplate:
            self._forceplate = read_data.get_forceplate_data(self.source)
        return self._forceplate

    def get_modelvar(self, var):
        """ Return variable, load and cache data for model if needed """
        model_ = models.model_from_var(var)
        if not model_:
            raise ValueError('No model found for %s' % var)
        if model_.desc not in self._models_data:
            # read and cache model data
            print('loading model')
            modeldata = read_data.get_model_data(self.source, model_)
            self.models_data[model_.desc] = modeldata
        return self.models_data[model_.desc][var]

    def get_cycle(self, context, ncycle):
        """ e.g. ncycle=2 and context='L' returns 2nd left gait cycle. """
        cycles = [cycle for cycle in self.cycles if cycle.context == context]
        if len(cycles) < ncycle:
            return None
        else:
            return cycles[ncycle-1]

    def _scan_cycles(self):
        """ Create gait cycle instances based on strike/toeoff markers. """
        for strikes in [self.lstrikes, self.rstrikes]:
            len_s = len(strikes)
            if len_s < 2:
                return
            if strikes == self.lstrikes:
                toeoffs = self.ltoeoffs
                context = 'L'
            else:
                toeoffs = self.rtoeoffs
                context = 'R'
            for k in range(0, len_s-1):
                start = strikes[k]
                end = strikes[k+1]
                toeoff = [x for x in toeoffs if x > start and x < end]
                toeoff = toeoff[0] if len(toeoff) > 0 else None
                yield Gaitcycle(start, end, self.offset, toeoff, context,
                                self.samplesperframe)



class ModelData:
    """ Handles model output data, e.g. Plug-in Gait, muscle length etc. """

    def __init__(self, source):
        self.source = source
        # local copy of models is mutable, so need a new copy
        # instead of a binding
        self.models = copy.deepcopy(models.models_all)
        self.varnames = []
        self.varlabels = {}
        self.normaldata_map = {}
        self.ylabels = {}
        self.modeldata = {}  # read by read_model as necessary
        self.normaldata = {}  # ditto
        # update varnames etc. for this class
        for model in self.models:
            self.varnames += model.varnames
            self.varlabels.update(model.varlabels)
            self.normaldata_map.update(model.normaldata_map)
            self.ylabels.update(model.ylabels)

    def get_model(self, varname):
        """ Returns model corresponding to varname. """
        for model in self.models:
            if varname in model.varnames:
                return model

    def read_normaldata(self):
        gcdfile = model.normaldata_path
        if gcdfile:
            if not os.path.isfile(gcdfile):
                raise Exception('Cannot find specified normal data file')
            f = open(gcdfile, 'r')
            lines = f.readlines()
            f.close()
            # normaldata variables are named as in the file. the model should have a corresponding map.
            normaldata = {}
            for li in lines:
                if li[0] == '!':  # it's a variable name
                    thisvar = li[1:li.find(' ')]  # set dict key
                    normaldata[thisvar] = list()
                # it's a number, so read into list
                elif li[0].isdigit() or li[0] == '-':
                    normaldata[thisvar].append([float(x) for x in li.split()])
            self.normaldata.update(normaldata)

    def is_kinetic_var(self, varname):
        """ Tell whether a variable represents kinetics. Works at least for
        PiG variables... """
        return varname.find('Power') > -1 or varname.find('Moment') > -1

    def get_normaldata(self, varname):
        """ Return the normal data for variable varname, if available. """
        model = self.get_model(varname)
        if model and varname in model.normaldata_map:
            normalkey = model.normaldata_map[varname]
            return self.normaldata[normalkey]
        else:
            return None

