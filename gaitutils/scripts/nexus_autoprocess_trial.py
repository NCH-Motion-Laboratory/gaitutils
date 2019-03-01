#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

Autoprocess single trial.
Note: does not use stats for event detection -> less accurate

@author: Jussi (jnu@iki.fi)
"""
from __future__ import absolute_import

import logging
import os.path as op

from gaitutils.scripts.nexus_autoprocess_session import (_do_autoproc,
                                                         _delete_c3ds)
from gaitutils import nexus, register_gui_exception_handler, GaitDataError


def autoproc_single():
    fn = nexus.get_trialname()
    if not fn:
        raise GaitDataError('No trial open in Nexus')
    fn += '.Trial.enf'
    enffiles = [op.join(nexus.get_sessionpath(), fn)]  # listify single enf
    _delete_c3ds(enffiles)
    _do_autoproc(enffiles)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    autoproc_single()
