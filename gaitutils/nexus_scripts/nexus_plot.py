#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 28 11:37:51 2015

Plot currently loaded Nexus trial.

@author: Jussi (jnu@iki.fi)
"""

import logging
import argparse

from gaitutils import (Plotter, cfg, register_gui_exception_handler, layouts,
                       trial, plot_plotly, GaitDataError)


def do_plot(layout_name, backend=None, model_cycles=None, emg_cycles=None,
            maintitle=None):

    try:
        layout = getattr(cfg.layouts, layout_name)
    except AttributeError:
        raise GaitDataError('No such layout %s' % layout_name)

    tr = trial.nexus_trial()
    model_cycles = ('unnormalized' if tr.is_static else
                    model_cycles)
    emg_cycles = ('unnormalized' if tr.is_static else
                  emg_cycles)

    # remove dead EMG channel
    # should be a no-op for non-EMG layouts, but restrict it to '*EMG*' anyway
    if 'EMG' in layout_name.upper():
        layout = layouts.rm_dead_channels(tr.emg, layout)

    if backend is None:
        backend = cfg.plot.backend

    if backend == 'matplotlib':
        pl = Plotter()
        pl.layout = layout
        pl.plot_trial(tr, model_cycles=model_cycles, emg_cycles=emg_cycles,
                      show=False)
        pl.show()

    elif backend == 'plotly':
        plot_plotly.plot_trials_browser([tr], layout, model_cycles=model_cycles,
                                        emg_cycles=emg_cycles,
                                        legend_type='short_name_with_cyclename')

    else:
        raise ValueError('Invalid plotting backend %s' % cfg.plot.backend)


if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    parser = argparse.ArgumentParser()
    parser.add_argument('--layout', type=str)
    parser.add_argument('--backend', type=str)
    parser.add_argument('--unnorm', action='store_true')
    parser.add_argument('--model_cycles', type=str)
    parser.add_argument('--emg_cycles', type=str)
    args = parser.parse_args()
    layout = args.layout or 'lb_kinematics'
    if args.unnorm:
        args.model_cycles = args.emg_cycles = 'unnormalized'

    do_plot(layout, backend=args.backend, model_cycles=args.model_cycles,
            emg_cycles=args.emg_cycles)
