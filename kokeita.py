# -*- coding: utf-8 -*-
"""
Created on Mon Oct 17 14:06:22 2016

Test new gaitutils code

@author: HUS20664877
"""

from gaitutils import EMG, nexus, config, read_data, trial, eclipse, models, Plotter, layouts, utils
import matplotlib.pyplot as plt
import sys
import logging
import scipy.linalg
import numpy as np
import btk


def segment_angles(P):
    """ Compute angles between segments defined by ordered points in P
    (N x 3 array). Can also be 3-d matrix of T x N x 3 to get time-dependent
    data. Output will be (N-2) vector or T x (N-2) matrix of angles in radians.
    If successive points are identical, nan:s will be output for the
    corresponding angles.
    """
    if P.shape[-1] != 3 or len(P.shape) not in [2, 3]:
        raise ValueError('Invalid shape of input matrix')
    if len(P.shape) == 2:
        P = P[np.newaxis, ...]  # insert singleton time axis
    Pd = np.diff(P, axis=1)  # point-to-point vectors
    # normalize avoiding div by zero (caused by identical successive pts)
    vnorms = scipy.linalg.norm(Pd, axis=2)[..., np.newaxis]
    nonzero = np.where(vnorms)[1]
    Pdn = np.full(Pd.shape, np.nan)
    Pdn[:, nonzero, :] = Pd[:, nonzero, :] / vnorms[:, nonzero, :]
    # take dot products between successive vectors and angles by arccos
    dots = np.sum(Pdn[:, 0:-1, :] * Pdn[:, 1:, :], axis=2)
    dots = dots[0, :] if dots.shape[0] == 1 else dots  # rm singleton dim
    return np.pi - np.arccos(dots)


# time varying segment angle
Ptoe = read_data.get_marker_data(vicon, ['RTOE', 'RANK', 'RTIB'])['RTOE_P']
Pank = read_data.get_marker_data(vicon, ['RTOE', 'RANK', 'RTIB'])['RANK_P']
Ptib = read_data.get_marker_data(vicon, ['RTOE', 'RANK', 'RTIB'])['RTIB_P']
Pall = np.stack([Ptoe,Pank,Ptib])

for k in np.arange(Pall.shape[1]):
    P = Pall[:, k, :]
    print segment_angles(P) / np.pi * 180
    
    
    




logger = logging.getLogger()
handler = logging.StreamHandler()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s: %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)



#vicon = nexus.viconnexus()
#fpdata = read_data.get_forceplate_data(vicon)
#meta = read_data.get_metadata(vicon)

#kin = utils.kinetics_available(vicon, check_cop=True)


c3dfile = ('C:/Users/hus20664877/Desktop/Vicon/vicon_data/test/Verrokki6v_IN/'
           '2015_10_22_girl6v_IN/2015_10_22_girl6v_IN57.c3d')
# c3dfile = 'Z:/siirto/coptest/session101.c3d'

c3dfile = "C:/Users/hus20664877/Desktop/NVUG2017/Example Data Workshop/Carita/Level/Dynamic 03.c3d"

vicon = nexus.viconnexus()

fpn = read_data.get_forceplate_data(vicon)[0]
plt.figure()
plt.plot(fpn['CoP'])
plt.legend(['x', 'y', 'z'])
plt.title('Nexus')

fp3 = read_data.get_forceplate_data(c3dfile)[0]
plt.figure()
plt.plot(fp3['CoP'])
plt.legend(['x', 'y', 'z'])
plt.title('C3D')



sys.exit()



c3dfile = "C:/Users/hus20664877/Desktop/trondheim_gait_data/astrid_080515_02.c3d"

pl = Plotter()

#pl.open_nexus_trial()
pl.open_trial(c3dfile)

pl.layout = [['HipMomentX']]
pl.layout = layouts.std_kinall

pl.plot_trial(model_cycles='all')

sys.exit()


#fpdn = read_data.get_forceplate_data(vicon)

utils.check_forceplate_contact(vicon)

utils.check_forceplate_contact(c3dfile)


sys.exit()




c3dfile = "C:/Users/hus20664877/Desktop/trondheim_gait_data/Tobias Goihl - 4-511_P3_Tardieu02.c3d"

c3dfile = "C:/Users/hus20664877/Desktop/Vicon/vicon_data/test/Verrokki6v_IN/2015_10_22_girl6v_IN/2015_10_22_girl6v_IN57.c3d"



# c3dfile = "C:/Users/hus20664877/Desktop/NVUG2017/Example Data Workshop/Carita/Level/Dynamic 03.c3d"


tr = trial.Trial(c3dfile)

fpd3 = read_data.get_forceplate_data(c3dfile)
ka = utils.check_forceplate_contact(c3dfile)

sys.exit()


vicon = nexus.viconnexus()

fpdn = read_data.detect_forceplate_events(vicon)

sys.exit()

fpd3 = read_data.get_forceplate_data(c3dfile)

cop_3 = fpd3[0]['CoP']
cop_n = fpdn[0]['CoP']

"""plt.figure()
plt.subplot(2, 1, 1)
plt.plot(cop_3)
plt.ylim([-700, 700])
plt.legend(['x','y','z'])
plt.subplot(2, 1, 2)
plt.plot(cop_n)
plt.ylim([-700, 700])
plt.legend(['x','y','z'])
plt.ylim()
"""


#utils.kinetics_available(c3dfile)

sys.exit()



cop_3 = fpd3[0]['CoP']
cop_n = fpdn[0]['CoP']


wR = fpd3[0]['wR']
wT = fpd3[0]['wT']
cop_w = np.dot(wR, cop.T).T + wT

              
plt.plot(cop_w)
plt.legend(['x','y','z'])




sys.exit()


# btk 

reader	=	btk.btkAcquisitionFileReader()	
reader.SetFilename(c3dfile)	
reader.Update()
acq	=	reader.GetOutput()
pfe	 =	btk.btkForcePlatformsExtractor()	
pfe.SetInput(acq)	
pfe.Update()
pfc	= pfe.GetOutput()	#	a	btkPlateFormCollec1on	
pf1	= pfc.GetItem(0)	#	item	0	=	First	force	plagorm	

for it in btk.Iterate(pfc):
    print it.GetCalMatrix()
    
    
                 
                 

sys.exit()

                 
#fpdata = read_data.get_forceplate_data(vicon)
meta = read_data.get_metadata(vicon)

kin = utils.kinetics_available(vicon)


sys.exit()


#pl = Plotter()

#pl.open_nexus_trial()

#print utils.kinetics_available(vicon, check_cop=True)

#pl.open_trial(c3dfile)

#print pl.trial.forceplate_data


sys.exit()



lout = [['RGlut', 'LGlut'], ['LRec', 'RRec']]
#lout = layouts.kinetics_emg('R')

#lout = layouts.std_emg

pl = Plotter()
pl.layout = layouts.rm_dead_channels(vicon, lout)
pl.open_nexus_trial()
pl.plot_trial()






