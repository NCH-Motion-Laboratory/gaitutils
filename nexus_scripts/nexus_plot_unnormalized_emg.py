# -*- coding: utf-8 -*-
"""
Created on Mon Oct 17 14:06:22 2016

Plot unnormalized EMG (special case)

@author: HUS20664877
"""

from gaitutils import Plotter, nexus
import os.path as op


lout = [['LVas', 'RVas'], ['LRec', 'RRec'], ['LHam', 'RHam']]

enffiles = nexus.get_trial_enfs()

for filepath_ in enffiles:
    filepath = filepath__[:filepath__.find('.Trial')]  # rm .Trial and .enf

    pl = Plotter(lout)
    pl.open_trial(filepath+'.c3d')

    pl.trial.emg.passband = [10, 400]

    maintitle = 'EMG for %s\n%s' % (pl.trial.trialname,
                                    pl.trial.eclipse_data['NOTES'])

    pl.plot_trial(cycles=None, maintitle=maintitle)
    pl.create_pdf(pdf_prefix='EMG_unnorm_')
