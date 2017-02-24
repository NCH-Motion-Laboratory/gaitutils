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

import btk





logger = logging.getLogger()
handler = logging.StreamHandler()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s: %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


# c3dfile = u'c:\\Users\\hus20664877\\Desktop\\Vicon\\vicon_data\\test\\H0036_EV\\2015_9_21_seur_EV\\2015_9_21_seur_EV19.c3d'

vicon = nexus.viconnexus()
#fpdata = read_data.get_forceplate_data(vicon)
meta = read_data.get_metadata(vicon)

kin = utils.kinetics_available(vicon)


sys.exit()




c3dfile = "C:/Users/hus20664877/Desktop/NVUG2017/Example Data Workshop/Carita/Level/Dynamic 03.c3d"
c3dfile = "C:/Users/hus20664877/Desktop/Vicon/vicon_data/test/Verrokki6v_IN/2015_10_22_girl6v_IN/2015_10_22_girl6v_IN57.c3d"

c3dfile = "C:/Users/hus20664877/Desktop/trondheim_gait_data/Tobias Goihl - 4-511_P3_Tardieu02.c3d"


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






