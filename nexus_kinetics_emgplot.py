# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Kinetics-EMG plot from Nexus.

@author: Jussi
"""

from gaitutils import Plotter, layouts, register_gui_exception_handler


def do_plot(show=True):

    pl = Plotter()
    pl.open_nexus_trial()
    side = pl.trial.kinetics
    pl.layout = layouts.kinetics_emg(side)
    pdf_prefix = 'Kinetics_EMG_'
    maintitle = pl.title_with_eclipse_info('Kinetics-EMG for')
    # for EMG, plot only the cycle that has kinetics info
    pl.plot_trial(maintitle=maintitle, show=show)
    pl.create_pdf(pdf_prefix=pdf_prefix)

if __name__ == '__main__':
    register_gui_exception_handler()
    do_plot()
