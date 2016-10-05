# -*- coding: utf-8 -*-
"""

c3d functions


@author: Jussi (jnu@iki.fi)
"""


import btk
import numpy as np
from scipy.signal import medfilt


def get_forceplate_data(c3dfile):
    """ Read forceplate data. """
    reader = btk.btkAcquisitionFileReader()
    reader.SetFilename(str(c3dfile))  # btk does not tolerate unicode
    reader.Update()
    acq = reader.GetOutput()
    frame1 = acq.GetFirstFrame()  # start of ROI (1-based)
    samplesperframe = acq.GetNumberAnalogSamplePerFrame()
    sfrate = acq.GetAnalogFrequency()
    # TODO: raise DeviceNotFound if needed
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
            print 'moment'
            if desc.find('Mx') > 0:
                mx = np.squeeze(i.GetValues())  # rm singleton dimension
            elif desc.find('My') > 0:
                my = np.squeeze(i.GetValues())
            elif desc.find('Mz') > 0:
                mz = np.squeeze(i.GetValues())
    """ Compute CoP according to AMTI instructions. The results differ
    slightly (about 1 mm max) from Nexus, for unknown reasons.
    See http://health.uottawa.ca/biomech/courses/apa6903/amticalc.pdf """
    dz = 41.3  # fp thickness magical value
    fz = medfilt(fz, 3)  # suppress noise by medfilt; not sure what Nexus uses
    fz_0_ind = np.where(fz == 0)
    copx = (my + fx * dz)/fz
    copy = (mx - fy * dz)/fz
    copx[fz_0_ind] = 0
    copy[fz_0_ind] = 0
    copz = np.zeros(copx.shape)
    cop = np.array([copx, copy, copz]).transpose()
    fall = np.array([fx, fy, fz]).transpose()
    ftot = np.sqrt(np.sum(fall**2, axis=1))
    return {'fall': fall, 'ftot': ftot, 'cop': cop,
            'samplesperframe': samplesperframe, 'sfrate': sfrate}



