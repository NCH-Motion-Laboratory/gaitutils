# -*- coding: utf-8 -*-
"""
Reporting functions, WIP

@author: Jussi (jnu@iki.fi)
"""

import logging
import numpy as np
import jinja2
import os.path as op
import os
import subprocess

import gaitutils
from gaitutils import cfg


logger = logging.getLogger(__name__)


def convert_videos(vidfiles):
    """ Convert video files using command and options defined in cfg """
    if not isinstance(vidfiles, list):
        vidfiles = [vidfiles]
    vidconv_bin = cfg.general.videoconv_path
    vidconv_opts = cfg.general.videoconv_opts
    if not (op.isfile(vidconv_bin) and os.access(vidconv_bin, os.X_OK)):
        raise ValueError('Invalid video converter executable: %s'
                         % vidconv_bin)
    # command needs to be constructed in a very particular way
    # see subprocess.list2cmdline
    convf = list()
    for vidfile in vidfiles:
        # FIXME: check return status
        convfile = op.splitext(vidfile)[0] + '.ogv'
        if not op.isfile(convfile):
            logger.debug('converting %s' % vidfile)
            subprocess.call([vidconv_bin]+vidconv_opts.split()+[vidfile])
        else:
            logger.debug('%s already exists' % vidfile)
        convf.append(convfile)
    return convf


def render_template(tpl_filename, context):
    """ Render template with given context """
    templateLoader = jinja2.FileSystemLoader(searchpath=cfg.general.
                                             template_path)
    templateEnv = jinja2.Environment(loader=templateLoader)
    template = templateEnv.get_template(tpl_filename)
    return template.render(context, trim_blocks=True)
