# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Kinematics-EMG plot from Nexus.

Instead of separate plots, this overlays EMGs from both sides on one plot.

@author: Jussi
"""

from gaitutils import Plotter, layouts, register_gui_exception_handler
import logging


def do_plot():

    pl = Plotter()
    pl.open_nexus_trial()
    pdf_prefix = 'Kinematics_EMG_'
    maintitle = pl.title_with_eclipse_info('Kinematics-EMG for')

    pl.layout = layouts.kinematics_emg('L')
    pl.plot_trial(maintitle=maintitle,
                  emg_cycles={'L': 1}, emg_tracecolor='red', show=False,
                  annotate_emg=False)

    pl.layout = layouts.kinematics_emg('R')
    pl.plot_trial(maintitle=maintitle, emg_tracecolor='green',
                  emg_cycles={'R': 1}, annotate_emg=False)

    pl.create_pdf(pdf_prefix=pdf_prefix)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
