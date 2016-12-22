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
    side = pl.trial.kinetics
    pl.layout = layouts.kinetics_emg(side)
    pdf_prefix = 'Kinetics_EMG_'
    maintitleprefix = 'Kinetics-EMG plot for'

    maintitle = '%s %s (%s) (%s)' % (maintitleprefix,
                                     pl.trial.trialname,
                                     pl.trial.eclipse_data['DESCRIPTION'],
                                     pl.trial.eclipse_data['NOTES'])

    pl.plot_trial(maintitle=maintitle, emg_cycles={side: 1})
    pl.create_pdf(pdf_prefix=pdf_prefix)

if __name__ == '__main__':
    do_plot()
