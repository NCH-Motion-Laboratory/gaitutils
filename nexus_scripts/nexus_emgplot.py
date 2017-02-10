# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:25:38 2015

EMG plot from Nexus.

@author: Jussi
"""


from gaitutils import Plotter, layouts, nexus, register_gui_exception_handler

import logging
logging.basicConfig(level=logging.DEBUG)


def do_plot():
    pl = Plotter()
    pl.open_nexus_trial()
    pdf_prefix = 'EMG_'
    maintitle = pl.title_with_eclipse_info('EMG plot for')

    vicon = nexus.viconnexus()
    layout = layouts.std_emg
    pl.layout = layouts.rm_dead_channels(vicon, layout)
    pl.plot_trial(maintitle=maintitle)

    pl.create_pdf(pdf_prefix=pdf_prefix)

if __name__ == '__main__':
    register_gui_exception_handler()
    do_plot()
