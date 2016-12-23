# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:25:38 2015

EMG plot from Nexus.

@author: Jussi
"""


from gaitutils import Plotter, layouts, register_gui_exception_handler


def do_plot():

    pl = Plotter()
    pl.open_nexus_trial()
    pdf_prefix = 'EMG_'
    maintitle = pl.title_with_eclipse_info('EMG plot for')

    pl.layout = layouts.std_emg_right
    pl.plot_trial(maintitle=maintitle, emg_cycles={'R': 1})
    """ This changes layouts on a Plotter instance,
    which is a bit of a hack """
    pl.layout = layouts.std_emg_left
    pl.plot_trial(maintitle=maintitle, emg_cycles={'L': 1})

    pl.create_pdf(pdf_prefix=pdf_prefix)

if __name__ == '__main__':
    register_gui_exception_handler()
    do_plot()
