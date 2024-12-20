# -*- coding: utf-8 -*-
"""
Handles gaitutils config files.

@author: Jussi (jnu@iki.fi)
"""

from pathlib import Path
import io
import logging
from pkg_resources import resource_filename
from configdot import parse_config, update_config, dump_config


# logging handlers might not be installed at this point, so config related
# messages may not be seen at all. alternative would be to use print
logger = logging.getLogger(__name__)


def _handle_cfg_defaults(cfg):
    """Handle deprecated and default config values"""
    if isinstance(cfg.plot.emg_yscale, tuple):
        ysc = cfg.plot.emg_yscale[1]
        logger.warning(f'emg_yscale was changed to a float variable, using {ysc}')
        cfg.plot.emg_yscale = str(cfg.plot.emg_yscale[1])
    if cfg.general.normaldata_files == 'default':
        fn = resource_filename('gaitutils', 'data/normal.gcd')
        cfg.general.normaldata_files = [fn]
    if cfg.general.timedist_normaldata == 'default':
        fn = resource_filename('gaitutils', 'data/timedist_normaldata.json')
        cfg.general.timedist_normaldata = fn
    if cfg.emg.normaldata_file == 'default':
        fn = resource_filename('gaitutils', 'data/emg_normaldata.json')
        cfg.emg.normaldata_file = fn
    if cfg.general.videoconv_path == 'default':
        fn = resource_filename('gaitutils', 'thirdparty/ffmpeg.exe')
        cfg.general.videoconv_path = fn
    if cfg.autoproc.write_eclipse_fp_info is True:
        cfg.autoproc.write_eclipse_fp_info = 'write'
    # Deprecated video converter options were given as a list of two lists.
    # For example [['-i', '', '-o', ''], [1, 3]] means that the 1-st and 3-rd
    # elements of ['-i', '', '-o', ''] should be replaced with the input and output
    # filenames correspondingly. It is here converted to the new format.
    vidconv_opts = cfg.general.videoconv_opts
    if isinstance(vidconv_opts, list) and isinstance(vidconv_opts[0], list):
        vidconv_opts[0][vidconv_opts[1][0]] = '{INPUT}'
        if len(vidconv_opts[1]) > 1:
            vidconv_opts[0][vidconv_opts[1][1]] = '{OUTPUT}'
        cfg.general.videoconv_opts = vidconv_opts[0]


# location of the default config file
cfg_template_fn = resource_filename(__name__, 'data/default.cfg')
# Location of the user specific config file. On Windows, this typically puts the
# config at C:\Users\Username, since the USERPROFILE environment variable points
# there. Putting the config in a networked home dir requires some tinkering with
# environment variables (e.g. setting HOME)
cfg_user_fn = Path.home() / '.gaitutils.cfg'

# provide the global cfg instance
# read template config
cfg = parse_config(cfg_template_fn)
if cfg_user_fn.is_file():
    logger.debug(f'reading user config from {cfg_user_fn}')
    cfg_user = parse_config(cfg_user_fn)
    # update config from user file, but do not overwrite comments
    # new config items are only allowed in layouts section
    update_config(
        cfg,
        cfg_user,
        create_new_sections=False,
        create_new_items=['layouts'],
        update_comments=False,
    )
else:
    logger.warning(f'no config file, trying to create {cfg_user_fn}')
    cfg_txt = dump_config(cfg)
    with io.open(cfg_user_fn, 'w', encoding='utf8') as f:
        f.writelines(cfg_txt)

_handle_cfg_defaults(cfg)

# if using print for config messages:
# sys.stdout.flush()  # make sure that warnings are printed out
