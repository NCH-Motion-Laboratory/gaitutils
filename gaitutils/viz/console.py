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
from .. import nexus


def _console_init():
    """Set up some things for console scripts"""
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()


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
    """Kin plot for tagged dynamic trials from current Nexus session"""
    _console_init()
    parser = argparse.ArgumentParser()
    parser.add_argument('--tags', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    sessions = [nexus.get_sessionpath()]
    fig = plots.plot_sessions(sessions, tags=args.tags)
    show_fig(fig)


def plot_nexus_session_emg():
    """EMG plot for tagged dynamic trials from current Nexus session"""
    _console_init()
    parser = argparse.ArgumentParser()
    parser.add_argument('--tags', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial '
                        'description or notes')
    args = parser.parse_args()
    sessions = [nexus.get_sessionpath()]
    plots.plot_session_emg(sessions, tags=args.tags)
