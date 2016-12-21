# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Kinetics-EMG plot from Nexus.

@author: Jussi
"""

from gaitutils import Plotter, layouts


def do_plot():

    pl = Plotter()
    pl.open_nexus_trial()
    pdf_prefix = 'Kinetics_EMG_'
    maintitleprefix = 'Kinetics-EMG plot for '

    trialname = pl.trial.trialname
    maintitle = maintitleprefix + trialname
    if 'DESCRIPTION' in pl.trial.eclipse_data:
        maintitle += ' (' + pl.trial.eclipse_data['DESCRIPTION'] + ')'
    if 'NOTES' in pl.trial.eclipse_data:
        maintitle += ' (' + pl.trial.eclipse_data['NOTES'] + ')'

    pl.layout = layouts.kinematics_emg('L')
    pl.plot_trial(maintitle=maintitle,
                  emg_cycles={'L': 1}, emg_tracecolor='red', show=False)  # we only want emg for one side
                 
    pl.layout = layouts.kinematics_emg('R')
    pl.plot_trial(maintitle=maintitle, emg_tracecolor='green',
                  emg_cycles={'R': 1})  # we only want emg for one side

    pl.create_pdf(pdf_prefix=pdf_prefix)


if __name__ == '__main__':
    do_plot()
