# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Kinetics-EMG plot from Nexus.

@author: Jussi
"""

from gaitutils import Plotter, layouts, register_gui_exception_handler

import logging


def do_plot():

    pl = Plotter()
    pl.open_nexus_trial()
    sides = pl.trial.fp_valid
    if not sides:
        raise Exception('No kinetics')
    elif sides == 'LR':
        sides = ['L', 'R']
    else:
        sides = [sides]
    for side in sides:
        pl.layout = layouts.kinetics_emg(side)
        s = 'right' if side == 'R' else 'left'
        maintitle = 'Kinetics-EMG (%s) for %s' % (s,
                                                  pl.title_with_eclipse_info())
        # for EMG, plot only the cycle that has kinetics info
        pl.plot_trial(maintitle=maintitle)
        pdf_name = 'Kinetics_EMG_%s_%s.pdf' % (pl.trial.trialname, s)
        pl.create_pdf(pdf_name=pdf_name)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
