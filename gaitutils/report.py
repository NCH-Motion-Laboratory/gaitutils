# -*- coding: utf-8 -*-
"""
Report related functions

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division
from builtins import str
from past.builtins import basestring
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

import flask
from flask import request
from collections import OrderedDict
import logging
import os.path as op
import os
import subprocess
import ctypes
import base64
import io

import gaitutils
from gaitutils import (cfg, normaldata, models, layouts, GaitDataError,
                       sessionutils, numutils)
from gaitutils.plot_plotly import plot_trials
from gaitutils.nexus_scripts import nexus_time_distance_vars


logger = logging.getLogger(__name__)


def convert_videos(vidfiles, check_only=False):
    """Convert video files using command and options defined in cfg.
    If check_only, return whether files were already converted.
    Instantly starts as many converter processes as there are files and
    returns. This has the disadvantage of potentially starting dozens of
    processes, causing slowdown.
    """
    CONV_EXT = '.ogv'  # extension for converted files
    if not isinstance(vidfiles, list):
        vidfiles = [vidfiles]
    convfiles = {vidfile: op.splitext(vidfile)[0] + CONV_EXT for vidfile
                 in vidfiles}
    converted = [op.isfile(fn) for fn in convfiles.values()]  # already done
    if check_only:
        return all(converted)

    # XXX: this disables Windows protection fault dialogs
    # needed since ffmpeg2theora may crash after conversion is complete (?)
    SEM_NOGPFAULTERRORBOX = 0x0002  # From MSDN
    ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)

    vidconv_bin = cfg.general.videoconv_path
    vidconv_opts = cfg.general.videoconv_opts
    if not (op.isfile(vidconv_bin) and os.access(vidconv_bin, os.X_OK)):
        raise ValueError('Invalid video converter executable: %s'
                         % vidconv_bin)
    procs = []
    for vidfile, convfile in convfiles.items():
        if not op.isfile(convfile):
            # supply NO_WINDOW flag to prevent opening of consoles
            cmd = [vidconv_bin]+vidconv_opts.split()+[vidfile]
            cmd = [s.encode('iso-8859-1') for s in cmd]
            p = subprocess.Popen(cmd,
                                 stdout=None, creationflags=0x08000000)
            procs.append(p)
    return procs


def _make_dropdown_lists(options):
    """This takes a list of label/value dicts (with arbitrary type values)
    and returns list and dict. Needed since dcc.Dropdown can only take str
    values. identity is fed to dcc.Dropdown() and mapper is used for getting
    the actual values at the callback."""
    identity = list()
    mapper = dict()
    for option in options:
        di = {'label': option['label'], 'value': option['label']}
        if 'disabled' in option and option['disabled']:
            di['disabled'] = True
        identity.append(di)
        mapper[option['label']] = option['value']
    return identity, mapper


def _time_dist_plot(c3ds, sessions):
    cond_labels = [op.split(session)[-1] for session in sessions]
    fig = nexus_time_distance_vars._plot_trials(c3ds, cond_labels,
                                                interactive=False)
    buf = io.BytesIO()
    fig.savefig(buf, format='svg', bbox_inches='tight')
    buf.seek(0)
    return buf


# helper to shutdown flask server, see http://flask.pocoo.org/snippets/67/
def _shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


def dash_report(info=None, sessions=None, tags=None, signals=None):
    """Returns dash app for web report.
    info: patient info
    sessions: list of session dirs
    tags: tags for gait trials
    signals: instance of ProgressSignals
    """

    signals.progress.emit('Collecting trials...', 0)
    # relative width of left panel (1-12)
    # 3-session comparison uses narrower video panel
    # LEFT_WIDTH = 8 if len(sessions) == 3 else 7
    LEFT_WIDTH = 8
    VIDS_TOTAL_HEIGHT = 88  # % of browser window height
    camera_labels = cfg.general.camera_labels.values()

    if len(sessions) < 1 or len(sessions) > 3:
        raise ValueError('Need a list of one to three sessions')

    is_comparison = len(sessions) > 1

    sessions_str = ' / '.join([op.split(s)[-1] for s in sessions])
    report_type = ('Single session report:' if len(sessions) == 1
                   else 'Comparison report:')
    report_name = '%s %s' % (report_type, sessions_str)

    # if doing a comparison, pick representative trials only
    tags = tags or (cfg.eclipse.repr_tags if is_comparison else
                    cfg.eclipse.tags)

    info = info or sessionutils.default_info()

    age = None
    if info['hetu'] is not None:
        # compute subject age at session time
        session_dates = [sessionutils.get_session_date(session) for
                         session in sessions]
        ages = [numutils.age_from_hetu(info['hetu'], d) for d in
                session_dates]
        age = max(ages)

    # create Markdown text for patient info
    patient_info_text = '##### %s ' % (info['fullname'] if info['fullname']
                                       else 'Name unknown')
    if info['hetu']:
        patient_info_text += '(%s)' % info['hetu']
    patient_info_text += '\n\n'
    # if age:
    #     patient_info_text += 'Age at measurement time: %d\n\n' % age
    if info['report_notes']:
        patient_info_text += info['report_notes']

    # load the trials
    trials = list()
    c3ds_all = list()
    for session in sessions:
        c3ds = sessionutils.find_tagged(session, tags=tags)
        if not c3ds:
            raise GaitDataError('No marked trials %s found for session %s' %
                                (tags, session))
        else:
            c3ds_all.append(c3ds)
            trials_this = [gaitutils.Trial(c3d) for c3d in c3ds]
            trials.extend(trials_this)
    trials = sorted(trials, key=lambda tr: tr.eclipse_tag)
    logger.debug('using dynamic trials: %s' % c3ds_all)

    # load static trials separately
    c3ds_static = list()
    trials_static = list()
    for session in sessions:
        c3ds = sessionutils.find_tagged(session, tags=['Static'],
                                        eclipse_keys=['TYPE'])
        if c3ds:
            c3ds_static.append(c3ds[-1])  # pick at most static trial
    trials_static = [gaitutils.Trial(c3d) for c3d in c3ds_static]
    logger.debug('added static trials: %s' % c3ds_static)

    # load normal data for gait models
    model_normaldata = dict()
    for fn in cfg.general.normaldata_files:
        ndata = normaldata.read_normaldata(fn)
        model_normaldata.update(ndata)
    if age is not None:
        age_ndata_file = normaldata.normaldata_age(age)
        if age_ndata_file:
            age_ndata = normaldata.read_normaldata(age_ndata_file)
            model_normaldata.update(age_ndata)

    signals.progress.emit('Finding videos...', 0)
    # create directory of trial videos for each tag and camera selection
    vid_urls = dict()
    for tag in tags:
        vid_urls[tag] = dict()
        for camera_label in camera_labels:

            tagged = [tr for tr in trials if tag == tr.eclipse_tag]
            vid_files = [tr.get_video_by_label(camera_label, ext='ogv')
                         for tr in tagged]
            vid_urls[tag][camera_label] = dict()
            vid_urls[tag][camera_label] = ['/static/%s' % op.split(fn)[1] if fn
                                           else None for fn in vid_files]

    def _extra_video_urls(eclipse_keys=None, tags=None):
        """Put video files from each session according to Eclipse key and
        tags into vid_urls dict"""
        urls = dict()
        c3ds = list()
        for session in sessions:
            c3ds_this = sessionutils.find_tagged(session, tags=tags,
                                                 eclipse_keys=eclipse_keys)
            if c3ds_this:
                # only pick last matching trial from each session
                c3ds.append(c3ds_this[-1])
        for camera_id, camera_label in cfg.general.camera_labels.items():
            urls[camera_label] = list()
            for c3dfile in c3ds:
                vid_files = gaitutils.nexus.find_trial_videos(c3dfile,
                                                              'ogv', camera_id)
                urls[camera_label].extend(['/static/%s' % op.split(fn)[1]
                                          for fn in vid_files])
        return urls

    vid_urls['Static'] = _extra_video_urls(eclipse_keys=['TYPE'],
                                           tags=['Static'])
    for tag in cfg.eclipse.video_tags:
        vid_urls[tag] = _extra_video_urls(tags=[tag])

    logger.debug('found following video urls: %s' % vid_urls)

    # build dcc.Dropdown options list for the cameras and tags
    opts_cameras = list()
    for label in set(camera_labels):
        opts_cameras.append({'label': label, 'value': label})
    opts_tags = list()
    for tag in tags + cfg.eclipse.video_tags:
        if any([vid_urls[tag][camera_label] for camera_label in
                camera_labels]):
            opts_tags.append({'label': '%s' % tag, 'value': tag})
    if any([vid_urls['Static'][camera_label] for camera_label in
            camera_labels]):
        opts_tags.append({'label': 'Static', 'value': 'Static'})

    # no videos at all
    if not opts_tags:
        opts_tags.append({'label': 'No videos', 'value': 'no videos',
                          'disabled': True})

    # build dcc.Dropdown options list for the trials
    trials_dd = list()
    for tr in trials:
        trials_dd.append({'label': tr.name_with_description,
                          'value': tr.trialname})
    # precreate graphs
    # in EMG layout, keep chs that are active in any of the trials
    signals.progress.emit('Reading EMG data', 0)
    try:
        emgs = [tr.emg for tr in trials]
        emg_layout = layouts.rm_dead_channels_multitrial(emgs,
                                                         cfg.layouts.std_emg)
    except GaitDataError:
        emg_layout = 'disabled'

    # FIXME: into config?
    _layouts = OrderedDict([
            ('Patient info', 'patient_info'),
            ('Kinematics', cfg.layouts.lb_kinematics),
            ('Static kinematics', 'static_kinematics'),
            ('Static EMG', 'static_emg'),
            ('Kinematics + kinetics', cfg.layouts.lb_kin_web),
            ('Kinetics', cfg.layouts.lb_kinetics_web),
            ('EMG', emg_layout),
            ('Kinetics-EMG left', cfg.layouts.lb_kinetics_emg_l),
            ('Kinetics-EMG right', cfg.layouts.lb_kinetics_emg_r),
            ('Muscle length', cfg.layouts.musclelen),
            ('Time-distance variables', 'time_dist'),
            ])

    # pick desired single variables from model and append
    pig_singlevars_ = (models.pig_lowerbody.varlabels_noside.items() +
                       models.pig_lowerbody_kinetics.varlabels_noside.items())
    pig_singlevars = sorted(pig_singlevars_, key=lambda item: item[1])
    singlevars = OrderedDict([(varlabel, [[var]]) for var, varlabel in
                              pig_singlevars])
    _layouts.update(singlevars)

    dd_opts_multi_upper = list()
    dd_opts_multi_lower = list()

    for k, (label, layout) in enumerate(_layouts.items()):
        logger.debug('creating plot for %s' % label)
        signals.progress.emit('Creating plot: %s' % label, 100*k/len(_layouts))
        # for comparison report, include session info in plot legends and
        # use session specific line style
        trial_linestyles = 'session' if is_comparison else 'same'
        legend_type = ('short_name_with_tag' if is_comparison else
                       'tag_with_cycle')

        try:
            # special layout
            if isinstance(layout, basestring):
                if layout == 'time_dist':
                    buf = _time_dist_plot(c3ds_all, sessions)
                    encoded_image = base64.b64encode(buf.read())
                    graph_upper = html.Img(src='data:image/svg+xml;base64,{}'.
                                           format(encoded_image),
                                           id='gaitgraph%d' % k,
                                           style={'height': '100%'})
                    graph_lower = html.Img(src='data:image/svg+xml;base64,{}'.
                                           format(encoded_image),
                                           id='gaitgraph%d'
                                           % (len(_layouts)+k),
                                           style={'height': '100%'})

                elif layout == 'patient_info':
                    graph_upper = dcc.Markdown(patient_info_text)
                    graph_lower = graph_upper

                elif layout == 'static_kinematics':
                    layout_ = cfg.layouts.lb_kinematics
                    fig_ = plot_trials(trials_static, layout_,
                                       model_normaldata,
                                       model_cycles='unnormalized',
                                       emg_cycles=[],
                                       legend_type='short_name_with_cyclename',
                                       trial_linestyles=trial_linestyles)
                    graph_upper = dcc.Graph(figure=fig_, id='gaitgraph%d' % k,
                                            style={'height': '100%'})
                    graph_lower = dcc.Graph(figure=fig_, id='gaitgraph%d'
                                            % (len(_layouts)+k),
                                            style={'height': '100%'})

                elif layout == 'static_emg':
                    layout_ = cfg.layouts.std_emg
                    fig_ = plot_trials(trials_static, layout_,
                                       model_normaldata,
                                       model_cycles=[],
                                       emg_cycles='unnormalized',
                                       legend_type='short_name_with_cyclename',
                                       trial_linestyles=trial_linestyles)
                    graph_upper = dcc.Graph(figure=fig_, id='gaitgraph%d' % k,
                                            style={'height': '100%'})
                    graph_lower = dcc.Graph(figure=fig_, id='gaitgraph%d'
                                            % (len(_layouts)+k),
                                            style={'height': '100%'})

                # will be caught and menu item will be empty
                elif layout == 'disabled':
                    raise ValueError

                else:  # unrecognized layout; this is not caught by us
                    raise Exception('Unrecognized layout: %s' % layout)

            # regular gaitutils layout
            else:
                fig_ = plot_trials(trials, layout, model_normaldata,
                                   legend_type=legend_type,
                                   trial_linestyles=trial_linestyles)
                graph_upper = dcc.Graph(figure=fig_, id='gaitgraph%d' % k,
                                        style={'height': '100%'})
                graph_lower = dcc.Graph(figure=fig_, id='gaitgraph%d'
                                        % (len(_layouts)+k),
                                        style={'height': '100%'})

            dd_opts_multi_upper.append({'label': label, 'value': graph_upper})
            dd_opts_multi_lower.append({'label': label, 'value': graph_lower})

        except (ValueError, GaitDataError) as e:
            logger.warning('Failed to create plot for %s: %s' % (label, e))
            # insert the menu options but make them disabled
            dd_opts_multi_upper.append({'label': label, 'value': label,
                                        'disabled': True})
            dd_opts_multi_lower.append({'label': label, 'value': label,
                                        'disabled': True})
            continue


    opts_multi, mapper_multi_upper = _make_dropdown_lists(dd_opts_multi_upper)
    opts_multi, mapper_multi_lower = _make_dropdown_lists(dd_opts_multi_lower)

    def make_left_panel(split=True, upper_value='Kinematics',
                        lower_value='Kinematics'):
        """Make the left graph panels. If split, make two stacked panels"""

        # the upper graph & dropdown
        items = [
                    dcc.Dropdown(id='dd-vars-upper-multi', clearable=False,
                                 options=opts_multi,
                                 value=upper_value),

                    html.Div(id='div-upper', style={'height': '50%'}
                             if split else {'height': '100%'})
                ]

        if split:
            # add the lower one
            items.extend([
                            dcc.Dropdown(id='dd-vars-lower-multi',
                                         clearable=False,
                                         options=opts_multi,
                                         value=lower_value),

                            html.Div(id='div-lower', style={'height': '50%'})
                        ])

        return html.Div(items, style={'height': '80vh'})

    # create the app
    app = dash.Dash(__name__)
    # use local packaged versions of JavaScript libs etc. (no internet needed)
    app.css.config.serve_locally = True
    app.scripts.config.serve_locally = True

    # this is for generating the classnames in the CSS
    num2words = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five',
                 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten',
                 11: 'eleven', 12: 'twelve'}
    classname_left = '%s columns' % num2words[LEFT_WIDTH]
    classname_right = '%s columns' % num2words[12-LEFT_WIDTH]

    app.layout = html.Div([  # row

            html.Div([  # left main div

                    html.H6(report_name),

                    dcc.Checklist(id='split-left',
                                  options=[{'label': 'Two panels',
                                            'value': 'split'}], values=[]),

                    # need split=True so that both panels are in initial layout
                    html.Div(make_left_panel(split=True), id='div-left-main')

                    ], className=classname_left),

            html.Div([  # right main div

                    dcc.Dropdown(id='dd-camera', clearable=False,
                                 options=opts_cameras,
                                 value='Front camera'),

                    dcc.Dropdown(id='dd-video-tag', clearable=False,
                                 options=opts_tags,
                                 value=opts_tags[0]['value']),

                    html.Div(id='videos'),

                    ], className=classname_right),

                     ], className='row')

    @app.callback(
            Output('div-left-main', 'children'),
            [Input('split-left', 'values')],
            [State('dd-vars-upper-multi', 'value')]
        )
    def update_panel_layout(split_panels, upper_value):
        split = 'split' in split_panels
        return make_left_panel(split, upper_value=upper_value)

    @app.callback(
            Output('div-upper', 'children'),
            [Input('dd-vars-upper-multi', 'value')]
        )
    def update_contents_upper_multi(sel_var):
        return mapper_multi_upper[sel_var]

    @app.callback(
            Output('div-lower', 'children'),
            [Input('dd-vars-lower-multi', 'value')]
        )
    def update_contents_lower_multi(sel_var):
        return mapper_multi_lower[sel_var]

    def _video_elem(title, url, max_height):
        """Create a video element with title"""
        if not url:
            return 'No video found'
        vid_el = html.Video(src=url, controls=True, loop=True, preload='auto',
                            title=title, style={'max-height': max_height,
                                                'max-width': '100%'})
        # return html.Div([title, vid_el])  # titles above videos
        return vid_el

    @app.callback(
            Output('videos', 'children'),
            [Input('dd-camera', 'value'),
             Input('dd-video-tag', 'value')]
        )
    def update_videos(camera_label, tag):
        """Create a list of video divs according to camera and tag selection"""
        if tag == 'no videos':
            return 'No videos found'
        vid_urls_ = vid_urls[tag][camera_label]
        if not vid_urls_:
            return 'No videos found'
        nvids = len(vid_urls_)
        max_height = str(int(VIDS_TOTAL_HEIGHT / nvids)) + 'vh'
        return [_video_elem('video', url, max_height) for url in vid_urls_]

    # add a static route to serve session data. be careful outside firewalls
    @app.server.route('/static/<resource>')
    def serve_file(resource):
        for session in sessions:
            filepath = op.join(session, resource)
            if op.isfile(filepath):
                return flask.send_from_directory(session, resource)
        return None

    # add shutdown method - see http://flask.pocoo.org/snippets/67/
    @app.server.route('/shutdown')
    def shutdown():
        logger.debug('Received shutdown request...')
        _shutdown_server()
        return 'Server shutting down...'

    return app
