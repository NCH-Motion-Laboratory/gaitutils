# -*- coding: utf-8 -*-
"""

c3d reader functions


@author: Jussi (jnu@iki.fi)
"""


import btk
import numpy as np
from scipy.signal import medfilt
import os


def is_c3dfile(obj):
    """ Check whether obj is a valid c3d file. Currently just checks
    existence. """
    try:
        return os.path.isfile(obj)
    except TypeError:
        return False


def get_emgdata(c3dfile):
    """ Read EMG data from a c3d file. Returns a dict """
    reader = btk.btkAcquisitionFileReader()
    reader.SetFilename(str(c3dfile))  # check existence?
    reader.Update()
    acq = reader.GetOutput()
    # frame1 = acq.GetFirstFrame()  # start of ROI (1-based)
    # samplesperframe = acq.GetNumberAnalogSamplePerFrame()
    # sfrate = acq.GetAnalogFrequency()
    # read physical EMG channels and cut data to L/R gait cycles
    data = dict()
    elnames = []
    for i in btk.Iterate(acq.GetAnalogs()):
        if i.GetDescription().find('EMG') >= 0 and i.GetUnit() == 'V':
            elname = i.GetLabel()
            elnames.append(elname)
            data[elname] = np.squeeze(i.GetValues())
    if elnames:
        return data
    else:
        raise ValueError('No EMG channels found in data!')


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
    framerate = acq.GetPointFrequency()
    analograte = acq.GetAnalogFrequency()
    #  get events
    rstrikes, lstrikes, rtoeoffs, ltoeoffs = [], [], [], []
    for i in btk.Iterate(acq.GetEvents()):
        if i.GetLabel() == "Foot Strike":
            if i.GetContext() == "Right":
                rstrikes.append(i.GetFrame())
            elif i.GetContext() == "Left":
                lstrikes.append(i.GetFrame())
            else:
                raise Exception("Unknown context on foot strike event")
        elif i.GetLabel() == "Foot Off":
            if i.GetContext() == "Right":
                rtoeoffs.append(i.GetFrame())
            elif i.GetContext() == "Left":
                ltoeoffs.append(i.GetFrame())
            else:
                raise Exception("Unknown context on foot strike event")
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
            'rstrikes': rstrikes, 'ltoeoffs': ltoeoffs, 'rtoeoffs': rtoeoffs}


def get_forceplate_data(c3dfile):
    """ Read forceplate data. Does not support multiple plates.
    Force results differ somewhat from Nexus, not sure why. Calibration? """
    FP_DZ = 41.3  # forceplate thickness in mm
    # CoP calculation uses filter
    FP_FILTFUN = medfilt  # filter function
    FP_FILTW = 3  # median filter width
    reader = btk.btkAcquisitionFileReader()
    reader.SetFilename(str(c3dfile))  # btk does not tolerate unicode
    reader.Update()
    acq = reader.GetOutput()
    frame1 = acq.GetFirstFrame()  # start of ROI (1-based)
    samplesperframe = acq.GetNumberAnalogSamplePerFrame()
    sfrate = acq.GetAnalogFrequency()
    # TODO: raise DeviceNotFound if needed
    fx, fy, fz, mx, my, mz = (None,) * 6
    for i in btk.Iterate(acq.GetAnalogs()):
        desc = i.GetLabel()
        if desc.find('Force.') >= 0 and i.GetUnit() == 'N':
            if desc.find('Fx') > 0:
                fx = np.squeeze(i.GetValues())  # rm singleton dimension
            elif desc.find('Fy') > 0:
                fy = np.squeeze(i.GetValues())
            elif desc.find('Fz') > 0:
                fz = np.squeeze(i.GetValues())
        elif desc.find('Moment.') >= 0 and i.GetUnit() == 'Nmm':
            if desc.find('Mx') > 0:
                mx = np.squeeze(i.GetValues())  # rm singleton dimension
            elif desc.find('My') > 0:
                my = np.squeeze(i.GetValues())
            elif desc.find('Mz') > 0:
                mz = np.squeeze(i.GetValues())
    if any([var is None for var in (fx, fy, fz, mx, my, mz)]):
        raise ValueError('Cannot read force/moment variable')
    """ Compute CoP according to AMTI instructions. The results differ
    slightly (few mm) from Nexus, for unknown reasons (different filter?)
    See http://health.uottawa.ca/biomech/courses/apa6903/amticalc.pdf """
    # suppress noise by medfilt; not sure what Nexus uses
    fz = FP_FILTFUN(fz, FP_FILTW)
    fz_0_ind = np.where(fz == 0)
    copx = (my + fx * FP_DZ)/fz
    copy = (mx - fy * FP_DZ)/fz
    copx[fz_0_ind] = 0
    copy[fz_0_ind] = 0
    copz = np.zeros(copx.shape)
    cop = np.array([copx, copy, copz]).transpose()
    fall = np.array([fx, fy, fz]).transpose()
    ftot = np.sqrt(np.sum(fall**2, axis=1))
    return {'fall': fall, 'ftot': ftot, 'cop': cop,
            'samplesperframe': samplesperframe, 'sfrate': sfrate}
