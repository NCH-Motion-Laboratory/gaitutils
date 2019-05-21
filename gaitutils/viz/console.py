# -*- coding: utf-8 -*-
"""

Console script wrappers for the plotters. These are used as setuptools
entry points.

@author: Jussi (jnu@iki.fi)
"""


import logging
import argparse

from . import plots
from .plot_misc import show_fig
from ..envutils import register_gui_exception_handler
from .. import nexus, cfg


def _console_init():
    """Set up some things for console scripts"""
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()


# FIXME: need to load normal data for all plotters
def plot_nexus_trial():
    """Plot currently loaded Nexus trial"""
    _console_init()
    parser = argparse.ArgumentParser()
    parser.add_argument('--layout', type=str)
    parser.add_argument('--backend', type=str)
    parser.add_argument('--unnorm', action='store_true')
    parser.add_argument('--model_cycles', type=str)
    parser.add_argument('--emg_cycles', type=str)
    args = parser.parse_args()

    if args.unnorm:
        args.model_cycles = args.emg_cycles = 'unnormalized'

    fig = plots.plot_nexus_trial(layout_name=args.layout, backend=args.backend,
                                 model_cycles=args.model_cycles,
                                 emg_cycles=args.emg_cycles)
    show_fig(fig, args.backend)


def plot_nexus_session():
    """Plot tagged dynamic trials from current Nexus session"""
    _console_init()
    parser = argparse.ArgumentParser()
    parser.add_argument('--layout', type=str)
    parser.add_argument('--backend', type=str)
    parser.add_argument('--unnorm', action='store_true')
    parser.add_argument('--model_cycles', type=str)
    parser.add_argument('--emg_cycles', type=str)
    parser.add_argument('--tags', nargs='+')
    args = parser.parse_args()

    if args.unnorm:
        args.model_cycles = args.emg_cycles = 'unnormalized'

    sessions = [nexus.get_sessionpath()]
    fig = plots.plot_sessions(sessions, tags=args.tags,
                              backend=args.backend,
                              layout_name=args.layout,
                              model_cycles=args.model_cycles,
                              emg_cycles=args.emg_cycles)
    show_fig(fig)


def plot_nexus_session_average():
    """Kin average plot for session"""
    _console_init()
    session = nexus.get_sessionpath()
    figs = plots.plot_session_average(session)
    for fig in figs:
        show_fig(fig)
