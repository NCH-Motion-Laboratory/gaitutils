#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

Script to create the comparison pdf report.
Note: specific to the Helsinki gait lab.


@author: Jussi (jnu@iki.fi)
"""
from __future__ import absolute_import

import logging
import os.path as op
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from collections import defaultdict

from gaitutils import (Plotter, cfg, register_gui_exception_handler, layouts,
                       numutils, normaldata, nexus, sessionutils)
from PyQt5 import QtWidgets
from gaitutils.scripts import (nexus_kin_consistency,
                               nexus_time_distance_vars)

logger = logging.getLogger(__name__)

sort_field = 'NOTES'  # sort trials by the given Eclipse key
repr_tags = cfg.eclipse.repr_tags
page_size = (11.69, 8.27)  # report page size


def _add_footer(fig, txt):
    fig.text(0, 0, txt, fontsize=8, color='black', ha='left', va='bottom')


def _add_header(fig, txt):
    fig.text(0, 1, txt, fontsize=8, color='black', ha='left', va='top')


def _savefig(pdf, fig, header=None, footer=None):
    """add header/footer into page and save as A4"""
    if fig is None:
        return
    if header is not None:
        _add_header(fig, header)
    if footer is not None:
        _add_footer(fig, footer)
    fig.set_size_inches(page_size[0], page_size[1])
    pdf.savefig(fig)


def do_plot(sessions, pdfpath=None, pages=None):
    """ Do a quick comparison report between sessions """

    if pages is None:
        # if no pages specified, do them all
        pages = defaultdict(lambda: True)
    else:
        if not any(pages.values()):
            raise Exception('No pages to print')

    sessions_str = u' vs. '.join([op.split(s)[-1] for s in sessions])

    # make header page
    fig_hdr = plt.figure()
    ax = plt.subplot(111)
    plt.axis('off')
    title_txt = 'HUS Liikelaboratorio\n'
    title_txt += u'Kävelyanalyysin vertailuraportti\n'
    title_txt += '\n'
    title_txt += sessions_str
    ax.text(.5, .8, title_txt, ha='center', va='center', weight='bold',
            fontsize=14)

    fig_timedist_cmp = (nexus_time_distance_vars.
                        do_comparison_plot(sessions, tags=repr_tags,
                                           show=False))

    fig_kin_cmp = nexus_kin_consistency.do_plot(sessions, tags=repr_tags,
                                                session_styles=True,
                                                show=False)

    if pdfpath is None:
        pdfpath = QtWidgets.QFileDialog.getSaveFileName(None,
                                                        'Save PDF',
                                                        sessions[0],
                                                        '*.pdf')[0]
    if pdfpath:

        header = u'Comparison %s' % sessions_str
        logger.debug('creating multipage comparison pdf %s' % pdfpath)
        with PdfPages(pdfpath) as pdf:
            _savefig(pdf, fig_hdr)
            _savefig(pdf, fig_timedist_cmp, header)
            _savefig(pdf, fig_kin_cmp, header)

    # close all created figures, otherwise they'll pop up on next show() call
    plt.close('all')


if __name__ == '__main__':
    raise Exception('Not runnable yet (need a way to specify sessions)')
    logging.basicConfig(level=logging.DEBUG)
    register_gui_exception_handler()
    do_plot()
