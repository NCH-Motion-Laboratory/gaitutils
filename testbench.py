# -*- coding: utf-8 -*-
"""
Created on Mon Oct 17 14:06:22 2016

Test new gaitutils code

@author: HUS20664877
"""

from gaitutils import EMG, nexus, config, read_data, trial, eclipse, models, Plotter, layouts, utils
import matplotlib.pyplot as plt


c3dfile = u'c:\\Users\\hus20664877\\Desktop\\Vicon\\vicon_data\\test\\H0036_EV\\2015_9_21_seur_EV\\2015_9_21_seur_EV19.c3d'
vicon = nexus.viconnexus()

utils.kinetics_available(vicon)

"""
e1 = EMG(c3dfile)
e2 = EMG(vicon)

e1.read()
e2.read()
ch = 'LGas'

e1.passband = [40,400]
plt.plot(e1.t, e1['LGas'])
plt.plot(e2.t, e2['LGas'])
"""

#clasi = read_data.get_marker_data(c3dfile, 'LASI')
#vlasi = read_data.get_marker_data(vicon, 'LASI')


#ctri = trial.Trial(c3dfile)
#vtri = trial.Trial(vicon)

#pigmod = models.pig_lowerbody

#nmod = read_data.get_model_data(vicon, pigmod)
#cmod = read_data.get_model_data(c3dfile, pigmod)

#pl = Plotter(layouts.kinetics_emg('L'))
#pl = Plotter(layouts.std_kinematics)
#pl.open_trial(vicon)
#pl.plot_trial(cycles=1, context='L')


