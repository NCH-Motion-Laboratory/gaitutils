# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:25:38 2015

EMG plot from Nexus, special case (Lat_gast)

@author: Jussi
"""


from gaitutils import Plotter, register_gui_exception_handler


def do_plot():

    pl = Plotter()
    pl.open_nexus_trial()
    pdf_prefix = 'EMG_'
    maintitle = pl.title_with_eclipse_info('EMG plot for')

    layout = [['RTibA', 'LTibA'],
              ['RPer', 'LPer'],
              ['RGas', 'LGas'],
              ['RLat_gast', 'LLat_gast'],
              ['RSol', 'LSol']]

    # change either size to all None
    layout_R = [[(str if str[0] == 'R' else None) for str in li]
                for li in layout]
    layout_L = [[(str if str[0] == 'L' else None) for str in li]
                for li in layout]

    """ This changes layouts on a Plotter instance,
    which is a bit of a hack """
    pl.layout = layout_R
    pl.plot_trial(maintitle=maintitle, emg_cycles={'R': 1})
    pl.layout = layout_L
    pl.plot_trial(maintitle=maintitle, emg_cycles={'L': 1})

    pl.create_pdf(pdf_prefix=pdf_prefix)

if __name__ == '__main__':
    register_gui_exception_handler()
    do_plot()
