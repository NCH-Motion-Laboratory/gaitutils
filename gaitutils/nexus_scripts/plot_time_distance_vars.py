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

categs = ['Normal', 'Cognitive']

# make a dict for testing
values = dict()
units = dict()
for var in vars:
    values[var] = dict()
    units[var] = an[var]['unit']
    for categ in categs:
        values[var][categ] = dict()
        for side in ['Left', 'Right']:
            values[var][categ][side] = (an[var][side] if categ == 'Normal'
                                        else 1.5 * an[var][side])


# this does one barchart
# for comparison, write version that does two side by side

def _plot_barchart(values, units, thickness=.5, color=None):
    """ Multi-variable and multi-category barchart plot.
    values dict is keyed as values[var][category][side] """

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
        color = ['tab:orange', 'tab:green', 'tab:red', 'tab:brown',
                 'tab:pink', 'tab:gray', 'tab:olive']
    vars = values.keys()
    units = [units[var] for var in vars]
    gs = GridSpec(len(vars), 3, width_ratios=[1, 1/3., 1])

    for ind, var in enumerate(vars):
        # variable name
        textax = plt.subplot(gs[ind, 1])
        textax.axis('off')
        textax.text(0, .5, var, ha='center', va='center')
        categs = values[var].keys()
        # left
        ax = plt.subplot(gs[ind, 0])
        ax.axis('off')
        vals_this = [values[var][categ]['Left'] for categ in categs]
        ypos = np.arange(0, len(vals_this) * thickness, thickness)
        rects = ax.barh(ypos, vals_this, thickness, align='edge', color=color)
        # FIXME: set axis scale according to var normal values
        ax.set_xlim([0, 2. * max(vals_this)])
        _plot_len(ax, rects, add_text=' %s' % units[ind])
        # right
        ax = plt.subplot(gs[ind, 2])
        ax.axis('off')
        vals_this = [values[var][categ]['Right'] for categ in categs]
        ypos = np.arange(0, len(vals_this) * thickness, thickness)
        rects = ax.barh(ypos, vals_this, thickness, align='edge', color=color)
        # FIXME: set axis scale according to var normal values
        ax.set_xlim([0, 2. * max(vals_this)])
        _plot_len(ax, rects, add_text=' %s' % units[ind])

    if len(categs) > 1:
        plt.figlegend(rects[::-1], categs[::-1], loc=1)

    plt.subplot(gs[0, 0]).set_title('Left')
    plt.subplot(gs[0, 2]).set_title('Right')

_plot_barchart(values, units)

