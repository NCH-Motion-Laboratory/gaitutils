# -*- coding: utf-8 -*-
"""

c3d reader functions


@author: Jussi (jnu@iki.fi)
"""

from __future__ import print_function
import logging
import numpy as np
import os

from .numutils import center_of_pressure, change_coords
from .envutils import GaitDataError


logger = logging.getLogger(__name__)
try:
    import btk
except ImportError:
    print('Cannot find btk module; unable to read .c3d files')


def is_c3dfile(obj):
    """ Check whether obj is a valid c3d file. Currently just checks
    existence. """
    try:
        return os.path.isfile(obj)
    except TypeError:
        return False


def get_emg_data(c3dfile):
    """ Read EMG data from a c3d file. """
    reader = btk.btkAcquisitionFileReader()
    reader.SetFilename(str(c3dfile))
    reader.Update()
    acq = reader.GetOutput()
    data = dict()
    elnames = []
    for i in btk.Iterate(acq.GetAnalogs()):
        if i.GetDescription().find('EMG') >= 0 and i.GetUnit() == 'V':
            elname = i.GetLabel()
            elnames.append(elname)
            data[elname] = np.squeeze(i.GetValues())
    if elnames:
        return {'t': np.arange(len(data[elname])) / acq.GetAnalogFrequency(),
                'data': data}
    else:
        raise GaitDataError('No EMG channels found in data')


def get_marker_data(c3dfile, markers):
    if not isinstance(markers, list):  # listify if not already a list
        markers = [markers]
    reader = btk.btkAcquisitionFileReader()
    reader.SetFilename(str(c3dfile))
    reader.Update()
    acq = reader.GetOutput()
    mdata = dict()
    for marker in markers:
        try:
            mP = np.squeeze(acq.GetPoint(marker).GetValues())
        except RuntimeError:
            raise GaitDataError('Cannot read variable %s from c3d file'
                                % marker)
        mdata[marker + '_P'] = mP
        mdata[marker + '_V'] = np.gradient(mP)[0]
        mdata[marker + '_A'] = np.gradient(mdata[marker+'_V'])[0]
        # find gaps
        allzero = np.logical_and(mP[:, 0] == 0, mP[:, 1] == 0, mP[:, 2] == 0)
        mdata[marker + '_gaps'] = np.where(allzero)[0]
    return mdata


def get_metadata(c3dfile):
    """ Read trial and subject metadata """
    trialname = os.path.basename(os.path.splitext(c3dfile)[0])
    sessionpath = os.path.dirname(c3dfile)
    reader = btk.btkAcquisitionFileReader()
    reader.SetFilename(str(c3dfile))  # check existence?
    reader.Update()
    acq = reader.GetOutput()
    # frame offset (start of trial data in frames)
    offset = acq.GetFirstFrame()
    lastfr = acq.GetLastFrame()
    length = lastfr - offset + 1
    framerate = acq.GetPointFrequency()
    analograte = acq.GetAnalogFrequency()
    samplesperframe = acq.GetNumberAnalogSamplePerFrame()
    # count forceplates
    n_forceplates = 0
    for i in btk.Iterate(acq.GetAnalogs()):
        desc = i.GetLabel()
        if desc.find('Force.') >= 0 and i.GetUnit() == 'N':
            n_forceplates += 1
    #  get events
    rstrikes, lstrikes, rtoeoffs, ltoeoffs = [], [], [], []
    for i in btk.Iterate(acq.GetEvents()):
        if i.GetLabel() == "Foot Strike":
            if i.GetContext() == "Right":
                rstrikes.append(i.GetFrame())
            elif i.GetContext() == "Left":
                lstrikes.append(i.GetFrame())
            else:
                raise GaitDataError("Unknown context on foot strike event")
        elif i.GetLabel() == "Foot Off":
            if i.GetContext() == "Right":
                rtoeoffs.append(i.GetFrame())
            elif i.GetContext() == "Left":
                ltoeoffs.append(i.GetFrame())
            else:
                raise GaitDataError("Unknown context on foot strike event")
    # get subject info
    metadata = acq.GetMetaData()
    # don't ask
    name = (metadata.FindChild("SUBJECTS").value().
            FindChild("NAMES").value().GetInfo().ToString()[0].strip())
    bodymass = (metadata.FindChild("PROCESSING").value().
                FindChild("Bodymass").value().GetInfo().ToDouble()[0])
    # sort events (may be in wrong temporal order, at least in c3d files)
    for li in [lstrikes, rstrikes, ltoeoffs, rtoeoffs]:
        li.sort()
    return {'trialname': trialname, 'sessionpath': sessionpath,
            'offset': offset, 'framerate': framerate, 'analograte': analograte,
            'name': name, 'bodymass': bodymass, 'lstrikes': lstrikes,
            'rstrikes': rstrikes, 'ltoeoffs': ltoeoffs, 'rtoeoffs': rtoeoffs,
            'length': length, 'samplesperframe': samplesperframe,
            'n_forceplates': n_forceplates}


def get_model_data(c3dfile, model):
    modeldata = dict()
    reader = btk.btkAcquisitionFileReader()
    reader.SetFilename(str(c3dfile))
    reader.Update()
    acq = reader.GetOutput()
    for var in model.read_vars:
        try:
            vals = acq.GetPoint(var).GetValues()
            modeldata[var] = np.transpose(np.squeeze(vals))
        except RuntimeError:
            raise GaitDataError('Cannot find model variable %s in c3d file' %
                             var)
        # c3d stores scalars as last dim of 3-d array
        if model.read_strategy == 'last':
            modeldata[var] = modeldata[var][2, :]
    return modeldata


def get_forceplate_data(c3dfile):
    logger.debug('reading forceplate data from %s' % c3dfile)
    read_chs = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz']
    reader = btk.btkAcquisitionFileReader()
    reader.SetFilename(str(c3dfile))  # btk does not tolerate unicode
    reader.Update()
    acq = reader.GetOutput()
    fpe = btk.btkForcePlatformsExtractor()
    fpe.SetInput(acq)
    fpe.Update()
    fpdata = list()
    nplate = 1
    for plate in btk.Iterate(fpe.GetOutput()):
        logger.debug('reading from plate %d' % nplate)
        nplate += 1
        if plate.GetType() != 2:
            # Nexus should always write forceplates as type 2
            raise GaitDataError('Only type 2 forceplates are '
                                'supported for now')
        rawdata = dict()
        data = dict()
        for ch in btk.Iterate(plate.GetChannels()):
            label = ch.GetLabel()[-3:-1]  # strip descriptor and plate number
            rawdata[label] = np.squeeze(ch.GetData().GetValues())
        if not all([ch in rawdata for ch in read_chs]):
            raise GaitDataError('could not read force/moment data')
        F = np.stack([rawdata['Fx'], rawdata['Fy'], rawdata['Fz']], axis=1)
        M = np.stack([rawdata['Mx'], rawdata['My'], rawdata['Mz']], axis=1)
        # this should be the plate thickness (from moment origin to physical
        # origin) needed for center of pressure calculations
        dz = np.abs(plate.GetOrigin()[2])
        cop = center_of_pressure(F, M, dz)  # in plate local coords
        Ftot = np.sqrt(np.sum(F**2, axis=1))
        # locations of +x+y, -x+y, -x-y, +x-y plate corners in world coords
        # (in that order)
        cor = plate.GetCorners()
        wT = np.mean(cor, axis=1)  # translation vector, plate -> world
        # upper and lower bounds of forceplate
        ub = np.max(cor, axis=1)
        lb = np.min(cor, axis=1)
        # plate unit vectors in world system
        px = cor[:, 0] - cor[:, 1]
        py = cor[:, 0] - cor[:, 3]
        pz = np.array([0, 0, -1])
        P = np.stack([px, py, pz], axis=1)
        wR = P / np.linalg.norm(P, axis=0)  # rotation matrix, plate -> world
        # check whether cop stays inside forceplate area and clip if necessary
        cop_w = change_coords(cop, wR, wT)
        cop_wx = np.clip(cop_w[:, 0], lb[0], ub[0])
        cop_wy = np.clip(cop_w[:, 1], lb[1], ub[1])
        if not (cop_wx == cop_w[:, 0]).all() and (cop_wy == cop_w[:, 1]).all():
            logger.warning('center of pressure outside forceplate '
                           'bounds, clipping to plate')
            cop[:, 0] = cop_wx
            cop[:, 1] = cop_wy
        # XXX moment and force transformations may still be wrong
        data['F'] = change_coords(-F, wR, 0)  # not sure why sign flip needed
        data['Ftot'] = Ftot
        data['M'] = change_coords(-M, wR, 0)  # not sure why sign flip needed
        data['CoP'] = cop_w
        data['upperbounds'] = ub
        data['lowerbounds'] = lb
        data['wR'] = wR
        data['wT'] = wT
        fpdata.append(data)
    return fpdata
