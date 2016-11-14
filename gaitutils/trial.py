# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Read gait trials.

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division, print_function
import copy
from gaitutils import nexus, eclipse
from fileutils import is_c3dfile
from envutils import debug_print
import numpy as np
import os
import btk  # biomechanical toolkit for c3d reading
import models
from emg import EMG


class GaitDataError(Exception):
    """ Custom exception class. Stores a message. """

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class GaitCycle:
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
    -gait cycles (beginning and end frames)
    -analog data (EMG, forceplate, etc.)
    -model output variables (Plug-in Gait, muscle length, etc.)
    """

    def __init__(self, source, emg_mapping=None, emg_auto_off=None):
        """ Open trial, read subject info, events etc. """
        self.lfstrikes = []
        self.rfstrikes = []
        self.ltoeoffs = []
        self.rtoeoffs = []
        self.subject = {}

        if is_c3dfile(source):
            debug_print('trial: reading from ', source)
            c3dfile = source
            self.trialname = os.path.basename(os.path.splitext(c3dfile)[0])
            self.sessionpath = os.path.dirname(c3dfile)
            reader = btk.btkAcquisitionFileReader()
            reader.SetFilename(str(c3dfile))  # check existence?
            reader.Update()
            acq = reader.GetOutput()
            # frame offset (start of trial data in frames)
            self.offset = acq.GetFirstFrame()
            self.framerate = acq.GetPointFrequency()
            self.analograte = acq.GetAnalogFrequency()
            #  get events
            for i in btk.Iterate(acq.GetEvents()):
                if i.GetLabel() == "Foot Strike":
                    if i.GetContext() == "Right":
                        self.rfstrikes.append(i.GetFrame())
                    elif i.GetContext() == "Left":
                        self.lfstrikes.append(i.GetFrame())
                    else:
                        raise Exception("Unknown context on foot strike event")
                elif i.GetLabel() == "Foot Off":
                    if i.GetContext() == "Right":
                        self.rtoeoffs.append(i.GetFrame())
                    elif i.GetContext() == "Left":
                        self.ltoeoffs.append(i.GetFrame())
                    else:
                        raise Exception("Unknown context on foot strike event")
            # get subject info
            metadata = acq.GetMetaData()
            # don't ask
            self.subject['Name'] = (metadata.FindChild("SUBJECTS").value().
                                    FindChild("NAMES").value().GetInfo().
                                    ToString()[0].strip())
            self.subject['Bodymass'] = (metadata.FindChild("PROCESSING").
                                        value().FindChild("Bodymass").value().
                                        GetInfo().ToDouble()[0])
            debug_print('Subject info read:\n', self.subject)

        elif nexus.is_vicon_instance(source):
            debug_print('trial: reading from Vicon Nexus')
            vicon = source
            subjectnames = vicon.GetSubjectNames()
            debug_print('subject:', subjectnames)
            if len(subjectnames) > 1:
                raise GaitDataError('Nexus returns multiple subjects')
            if not subjectnames:
                raise GaitDataError('No subject defined')
            self.subjectname = subjectnames[0]
            self.subject['Name'] = self.subjectname
            Bodymass = vicon.GetSubjectParam(self.subjectname, 'Bodymass')
            # for unknown reasons, above method may return tuple or float
            # depending on whether script is run from Nexus or outside
            if type(Bodymass) == tuple:
                self.subject['Bodymass'] = vicon.GetSubjectParam(
                                            self.subjectname, 'Bodymass')[0]
            else:  # hopefully float
                self.subject['Bodymass'] = (vicon.GetSubjectParam(
                                            self.subjectname, 'Bodymass'))
            trialname_ = vicon.GetTrialName()
            self.sessionpath = trialname_[0]
            self.trialname = trialname_[1]
            if not self.trialname:
                raise GaitDataError('No trial loaded')
            # get events
            self.lfstrikes = vicon.GetEvents(self.subjectname,
                                             "Left", "Foot Strike")[0]
            self.rfstrikes = vicon.GetEvents(self.subjectname,
                                             "Right", "Foot Strike")[0]
            self.ltoeoffs = vicon.GetEvents(self.subjectname,
                                            "Left", "Foot Off")[0]
            self.rtoeoffs = vicon.GetEvents(self.subjectname,
                                            "Right", "Foot Off")[0]
            # frame offset (start of trial data in frames)
            self.offset = 1
            self.framerate = vicon.GetFrameRate()
            # Get analog rate. This may not be mandatory if analog devices
            # are not used, but currently it needs to succeed.
            devids = vicon.GetDeviceIDs()
            if not devids:
                raise GaitDataError('No analog devices configured in Nexus, '
                                    'cannot determine analog rate')
            else:
                devid = devids[0]
                _, _, self.analograte, _, _, _ = vicon.GetDeviceDetails(devid)
        else:
            raise GaitDataError('Invalid data source specified')
        debug_print('Foot strikes right:', self.rfstrikes, 'left:',
                    self.lfstrikes)
        debug_print('Toeoffs right:', self.rtoeoffs, 'left:', self.ltoeoffs)
        if len(self.lfstrikes) < 2 or len(self.rfstrikes) < 2:
            raise GaitDataError('Too few foot strike events detected, check '
                                'that data has been processed')
        # sort events (may be in wrong temporal order, at least in c3d files)
        for li in [self.lfstrikes, self.rfstrikes, self.ltoeoffs,
                   self.rtoeoffs]:
            li.sort()
        # get description and notes from Eclipse database
        if not self.sessionpath[-1] == '\\':
            self.sessionpath = self.sessionpath+('\\')
        self.trialdirname = self.sessionpath.split('\\')[-2]
        trialpath = self.sessionpath + self.trialname
        self.eclipse_description = eclipse.get_eclipse_key(trialpath,
                                                           'DESCRIPTION')
        self.eclipse_notes = eclipse.get_eclipse_key(trialpath, 'NOTES')
        self.source = source
        # init emg
        self.emg = EMG(source, emg_auto_off=emg_auto_off,
                       emg_mapping=emg_mapping)
        self.model = model_outputs(self.source)
        self.kinetics_side = nexus.kinetics_available()['context']
        # normalized x-axis of 0,1,2..100%
        self.tn = np.linspace(0, 100, 101)
        self.smp_per_frame = self.analograte/self.framerate
        # figure out gait cycles
        self.cycles = list(self.scan_cycles())
        self.ncycles = len(self.cycles)
        # video files associated with trial
        self.video_files = get_video_filenames(self.sessionpath+self.trialname)

    def scan_cycles(self):
        """ Scan for foot strike events and create gait cycle objects. """
        for strikes in [self.lfstrikes, self.rfstrikes]:
            len_s = len(strikes)
            if len_s < 2:
                raise GaitDataError('Insufficient number of foot strike events'
                                    'detected. Check that the trial has been '
                                    'processed.')
            if strikes == self.lfstrikes:
                toeoffs = self.ltoeoffs
                context = 'L'
            else:
                toeoffs = self.rtoeoffs
                context = 'R'
            for k in range(0, len_s-1):
                start = strikes[k]
                end = strikes[k+1]
                toeoff = [x for x in toeoffs if x > start and x < end]
                if len(toeoff) != 1:
                    raise GaitDataError('Expected a single toe-off event '
                                        'during gait cycle')
                yield gaitcycle(start, end, self.offset, toeoff[0], context,
                                self.smp_per_frame)

    def get_cycle(self, context, ncycle):
        """ e.g. ncycle=2 and context='L' returns 2nd left gait cycle. """
        cycles = [cycle for cycle in self.cycles if cycle.context == context]
        if len(cycles) < ncycle:
            return None
        else:
            return cycles[ncycle-1]


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

    def read_model(self, model):
        """ Read variables of given model (instance of models.model) and normal data
        into self.modeldata. """
        if not model:
            raise GaitDataError('Cannot read empty model')
        debug_print('Reading model:', model.desc)
        source = self.source
        if is_vicon_instance(source):
            # read from Nexus
            vicon = source
            SubjectName = vicon.GetSubjectNames()[0]
            for Var in model.read_vars:
                debug_print('Getting:', Var)
                NumVals,BoolVals = vicon.GetModelOutput(SubjectName, Var)
                if not NumVals:
                    raise GaitDataError('Cannot read model variable: '+Var+
                    '. \nMake sure that the appropriate model has been executed in Nexus.')
                # remove singleton dimensions
                self.modeldata[Var] = np.squeeze(np.array(NumVals))
        elif is_c3dfile(source):
            # read from c3d            
            c3dfile = source
            reader = btk.btkAcquisitionFileReader()
            reader.SetFilename(str(c3dfile))
            reader.Update()
            acq = reader.GetOutput()
            for Var in model.read_vars:
                try:
                    self.modeldata[Var] = np.transpose(np.squeeze(acq.GetPoint(Var).GetValues()))
                except RuntimeError:
                    raise GaitDataError('Cannot find model variable in c3d file: '+Var)
                # c3d stores scalars as first dim of 3-d array
                if model.read_strategy == 'last':
                    debug_print(Var,'has shape:', self.modeldata[Var].shape)
                    self.modeldata[Var] = self.modeldata[Var][2,:]
        else:
            raise GaitDataError('Invalid data source')
        # postprocessing for certain variables
        for Var in model.read_vars:
                if Var.find('Moment') > 0:
                    # moment variables have to be divided by 1000 -
                    # apparently stored in Newton-millimeters
                    debug_print('Normalizing:', Var)                    
                    self.modeldata[Var] /= 1000.
                #debug_print('read_raw:', Var, 'has shape', self.modeldata[Var].shape)
                components = model.read_strategy
                if components == 'split_xyz':
                    if self.modeldata[Var].shape[0] == 3:
                        # split 3-d arrays into x,y,z variables
                        self.modeldata[Var+'X'] = self.modeldata[Var][0,:]
                        self.modeldata[Var+'Y'] = self.modeldata[Var][1,:]
                        self.modeldata[Var+'Z'] = self.modeldata[Var][2,:]
                    else:
                        raise GaitDataError('XYZ split requested but array is not 3-d')
        # read normal data if it exists. only gcd files supported for now
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

