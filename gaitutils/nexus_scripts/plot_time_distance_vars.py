# -*- coding: utf-8 -*-
"""
Created on Tue Nov 14 16:45:32 2017

@author: hus20664877
"""

from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
import gaitutils
import numpy as np

fn = 'Z:\\Userdata_Vicon_Server\\CP-projekti\\TD26\\20160824\\TD26_N1_05.c3d'


"""
pl = gaitutils.Plotter()

pl.open_trial(fn)

pl.layout = gaitutils.cfg.layouts.lb_kin

pl.plot_trial()
"""


an = gaitutils.c3d.get_c3d_analysis(fn)


vars = ['Cadence', 'Walking Speed', 'Stride Time', 'Stride Length',
        'Single Support', 'Double Support', 'Step Length']
categs = ['Left', 'Right']


def _plot_barchart(values, thickness=.5, color=None):
    """Multi-variable and multi-category barchart plot"""

    def _plot_len(ax, rects, add_text=None):
        """Attach a text inside each bar displaying its length"""
        for rect in rects:
            width = rect.get_width()
            txt = '%.2f' % width
            txt += add_text if add_text else ''
            ax.text(rect.get_width() * .75,
                    rect.get_y() + rect.get_height()/2.,
                    txt, ha='center', va='center')

    if color is None:
        color = ['r', 'g', 'b']
    vars = values.keys()
    units = [values[var]['unit'] for var in vars]
    gs = GridSpec(len(vars), 2, width_ratios=[1/3., 1])
    for ind, var in enumerate(vars):
        ax = plt.subplot(gs[ind, 1])
        ax.axis('off')
        textax = plt.subplot(gs[ind, 0])
        textax.axis('off')
        textax.text(0, .5, var, ha='left', va='center')
        vals_this = [values[var][categ] for categ in categs]
        ypos = np.arange(0, len(vals_this) * thickness, thickness)
        rects = ax.barh(ypos, vals_this, thickness, align='edge', color=color)
        # set axis scale according to var normal values
        ax.set_xlim([0, 2. * max(vals_this)])
        _plot_len(ax, rects, add_text=' %s' % units[ind])
    return fig


_plot_barchart(an)



