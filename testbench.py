# -*- coding: utf-8 -*-
"""
Created on Mon Oct 17 14:06:22 2016

Test new gaitutils code

@author: HUS20664877
"""

from gaitutils import EMG, nexus, config
import matplotlib.pyplot as plt



c3dfile = u'c:\\Users\\hus20664877\\Desktop\\Vicon\\vicon_data\\test\\H0036_EV\\2015_9_21_seur_EV\\2015_9_21_seur_EV19.c3d'
vicon = nexus.viconnexus()


e1 = EMG(c3dfile)
e2 = EMG(vicon)

e1.read()
e2.read()
ch = 'LGas'

e1.passband = [40,400]
plt.plot(e1.t, e1['LGas'])
plt.plot(e2.t, e2['LGas'])


