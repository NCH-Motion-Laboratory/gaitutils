# -*- coding: utf-8 -*-
"""

c3d functions


@author: Jussi (jnu@iki.fi)
"""


import btk



def get_forceplate_data(c3dfile):
    """ Read forceplate data. """
   
    reader = btk.btkAcquisitionFileReader()
    reader.SetFilename(str(c3dfile))  # btk does not tolerate unicode
    reader.Update()
    acq = reader.GetOutput()
    self.frame1 = acq.GetFirstFrame()  # start of ROI (1-based)
    self.samplesperframe = acq.GetNumberAnalogSamplePerFrame()
    self.sfrate = acq.GetAnalogFrequency()
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




    # read x,y,z forces
    fxid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Fx')
    fx, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, fxid)
    fxid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Fy')
    fy, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, fxid)
    fxid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Fz')
    fz, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, fxid)
    # read CoP
    outputid = outputids[2]
    fxid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Cx')
    copx, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, fxid)
    fxid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Cy')
    copy, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, fxid)
    fxid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Cz')
    copz, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, fxid)
    cop = np.array([copx, copy, copz]).transpose()
    fall = np.array([fx, fy, fz]).transpose()
    ftot = np.sqrt(np.sum(fall**2, axis=1))
    return {'fall': fall, 'ftot': ftot, 'cop': cop,
            'samplesperframe': samplesperframe, 'sfrate': drate}





