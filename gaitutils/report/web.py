# -*- coding: utf-8 -*-
"""
Report related functions

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division
from matplotlib.backends.backend_qt5agg import (FigureCanvasQTAgg as
                                                FigureCanvas)

from builtins import str
from past.builtins import basestring
import numpy as np
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import flask
from flask import request
from collections import OrderedDict
import logging
import os.path as op
import base64
import io
import dill

from .. import (cfg, normaldata, models, layouts, GaitDataError,
                sessionutils, numutils, videos)
from ..trial import Trial
from ..viz.plot_plotly import plot_trials
from ..viz import timedist
from ..stats import AvgTrial


logger = logging.getLogger(__name__)


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


def _time_dist_plot_svg(sessions):
    """Return time-dist plot in SVG format"""
    fig = timedist.do_comparison_plot(sessions)
    _canvas = FigureCanvas(fig)  # savefig requires a canvas
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


def _report_name(sessions, long_name=True):
    """Create a title for the dash report"""
    sessions_str = ' / '.join([op.split(s)[-1] for s in sessions])
    if long_name:
        report_type = ('Single session report' if len(sessions) == 1
                       else 'Comparison report')
    else:
        report_type = 'Single' if len(sessions) == 1 else 'Comparison'
    return '%s: %s' % (report_type, sessions_str)


def dash_report(info=None, sessions=None, tags=None, signals=None):
    """Returns dash app for web report.
    info: patient info
    sessions: list of session dirs
    tags: tags for dynamic gait trials
    signals: instance of ProgressSignals, used to send progress updates across
    threads
    """

    signals.progress.emit('Collecting trials...', 0)
    # relative width of left panel (1-12)
    # 3-session comparison uses narrower video panel
    # LEFT_WIDTH = 8 if len(sessions) == 3 else 7
    LEFT_WIDTH = 8
    VIDS_TOTAL_HEIGHT = 88  # % of browser window height
    # reduce to set, since there may be several labels for given id
    camera_labels = set(cfg.general.camera_labels.values())
    model_cycles = cfg.plot.default_model_cycles
    emg_cycles = cfg.plot.default_emg_cycles

    if len(sessions) < 1 or len(sessions) > 3:
        raise ValueError('Need a list of one to three sessions')

    is_comparison = len(sessions) > 1

    report_name = _report_name(sessions)
    info = info or sessionutils.default_info()

    # tags for dynamic trials
    # if doing a comparison, pick representative trials only
    dyn_tags = tags or (cfg.eclipse.repr_tags if is_comparison else
                        cfg.eclipse.tags)
    # will be shown in the menu for static trials
    static_tag = 'Static'

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

    # find the c3d files and build a nice dict
    c3ds = {session: dict() for session in sessions}
    for session in sessions:
        c3ds[session] = dict(dynamic=dict(), static=dict(), vid_only=dict())
        # collect dynamic trials for each tag
        for tag in dyn_tags:
            dyns = sessionutils.get_c3ds(session, tags=tag,
                                         trial_type='dynamic')
            if len(dyns) > 1:
                logger.warning('multiple tagged trials (%s) for %s' %
                               (tag, session))
            c3ds[session]['dynamic'][tag] = dyns[-1:]
        # require at least one dynamic for each session
        if not any(c3ds[session]['dynamic'][tag] for tag in dyn_tags):
            raise GaitDataError('No tagged dynamic trials found for %s' %
                                (session))
        # collect static trial (at most 1 per session)
        sts = sessionutils.get_c3ds(session, trial_type='static')
        if len(sts) > 1:
            logger.warning('multiple static trials for %s, using last one'
                           % session)
        c3ds[session]['static'][static_tag] = sts[-1:]
        # collect video-only dynamic trials
        for tag in cfg.eclipse.video_tags:
            dyn_vids = sessionutils.get_c3ds(session, tags=tag)
            if len(dyn_vids) > 1:
                logger.warning('multiple tagged video-only trials (%s) for %s'
                               % (tag, session))
            c3ds[session]['vid_only'][tag] = dyn_vids[-1:]

    # collect data trials (static and dynamic) that affect the graphs
    # report 'data digest' is based on these trials only
    data_c3ds = list()
    for session in sessions:
        for type in ['dynamic', 'static']:
            for fnl in c3ds[session][type].values():
                data_c3ds.extend(fnl)
    digest = numutils.files_digest(data_c3ds)
    logger.debug('report data digest: %s' % digest)
    data_dir = sorted(sessions)[0]
    data_fn = op.join(data_dir, 'web_report_%s.dat' % digest)
    if op.isfile(data_fn):
        logger.debug('loading saved report data from %s' % data_fn)
        with open(data_fn, 'rb') as f:
            report_data = dill.load(f)
            logger.debug(report_data.keys())
    else:
        report_data = dict()
        logger.debug('no saved data found')

    # make Trial instances for all dynamic and static trials
    trials_dyn = list()
    trials_static = list()
    _trials_avg = dict()
    for session in sessions:
        _trials_avg[session] = list()
        for tag in dyn_tags:
            if c3ds[session]['dynamic'][tag]:
                if signals.canceled:
                    return None
                tri = Trial(c3ds[session]['dynamic'][tag][0])
                trials_dyn.append(tri)
                _trials_avg[session].append(tri)
        if c3ds[session]['static'][static_tag]:
            tri = Trial(c3ds[session]['static']['Static'][0])
            trials_static.append(tri)

    # make average trials
    avg_trials = [AvgTrial(_trials_avg[session], sessionpath=session)
                  for session in sessions]

    # read some extra data from trials and create supplementary data
    tibial_torsion = dict()
    for tr in trials_dyn:
        # read tibial torsion for each trial and make supplementary traces
        # these will only be shown for KneeAnglesZ (knee rotation) variable
        tors = dict()
        tors['R'], tors['L'] = (tr.subj_params['RTibialTorsion'],
                                tr.subj_params['LTibialTorsion'])
        if tors['R'] is None or tors['L'] is None:
            logger.warning('could not read tibial torsion values from %s'
                           % tr.trialname)
            continue
        # include torsion info for all cycles; this is useful when plotting
        # isolated cycles
        cycs = tr.get_cycles(model_cycles)
        for cyc in cycs:
            tibial_torsion[cyc] = dict()
            for ctxt in tors:
                var_ = ctxt + 'KneeAnglesZ'
                tibial_torsion[cyc][var_] = dict()
                # x = % of gait cycle
                tibial_torsion[cyc][var_]['t'] = np.arange(101)
                # static tibial torsion value as function of x
                # convert radians -> degrees
                tibial_torsion[cyc][var_]['data'] = (np.ones(101) * tors[ctxt]
                                                     / np.pi * 180)
                tibial_torsion[cyc][var_]['label'] = ('Tib. tors. (%s) % s' %
                                                      (ctxt, tr.trialname))

    # find video files for all trials
    signals.progress.emit('Finding videos...', 0)
    # add camera labels for overlay videos
    # XXX: may cause trouble if labels already contain the string 'overlay'
    camera_labels_overlay = [lbl+' overlay' for lbl in camera_labels]
    camera_labels.update(camera_labels_overlay)

    # build dict of videos for given tag / camera label
    # videos will be listed in session order
    vid_urls = dict()
    all_tags = dyn_tags + [static_tag] + cfg.eclipse.video_tags
    for tag in all_tags:
        vid_urls[tag] = dict()
        for camera_label in camera_labels:
            vid_urls[tag][camera_label] = list()

    # collect all videos for given tag and camera, listed in session order
    for session in sessions:
        for trial_type in c3ds[session]:
            for tag, c3ds_this in c3ds[session][trial_type].items():
                if c3ds_this:
                    c3d = c3ds_this[0]  # only one c3d per tag and session
                    for camera_label in camera_labels:
                        overlay = 'overlay' in camera_label
                        real_camera_label = (camera_label[:camera_label.find(' overlay')]
                                             if overlay else camera_label)
                        vids_this = videos.get_trial_videos(c3d, camera_label=real_camera_label, vid_ext='.ogv', overlay=overlay)
                        if vids_this:
                            vid = vids_this[0]
                            url = '/static/%s' % op.split(vid)[1]
                            vid_urls[tag][camera_label].append(url)

    # build dcc.Dropdown options list for cameras and tags
    # list cameras which have videos for any tag
    opts_cameras = list()
    for camera_label in sorted(camera_labels):
        if any(vid_urls[tag][camera_label] for tag in all_tags):
            opts_cameras.append({'label': camera_label, 'value': camera_label})
    # list tags which have videos for any camera
    opts_tags = list()
    for tag in all_tags:
        if any(vid_urls[tag][camera_label] for camera_label in camera_labels):
            opts_tags.append({'label': '%s' % tag, 'value': tag})
    # add null entry in case we got no videos at all
    if not opts_tags:
        opts_tags.append({'label': 'No videos', 'value': 'no videos',
                          'disabled': True})

    # build dcc.Dropdown options list for the trials
    trials_dd = list()
    for tr in trials_dyn:
        trials_dd.append({'label': tr.name_with_description,
                          'value': tr.trialname})

    # in EMG layout, keep chs that are active in any of the trials
    signals.progress.emit('Reading EMG data', 0)
    try:
        emgs = [tr.emg for tr in trials_dyn]
        emg_layout = layouts.rm_dead_channels_multitrial(emgs,
                                                         cfg.layouts.std_emg)
    except GaitDataError:
        emg_layout = 'disabled'

    # FIXME: layouts into config?
    _layouts = OrderedDict([
            ('Patient info', 'patient_info'),
            ('Kinematics', cfg.layouts.lb_kinematics),
            ('Kinematics average', 'kinematics_average'),
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

    # add supplementary data for normal layouts
    supplementary_default = dict()
    supplementary_default.update(tibial_torsion)

    dd_opts_multi_upper = list()
    dd_opts_multi_lower = list()

    report_data_new = dict()
    for k, (label, layout) in enumerate(_layouts.items()):
        signals.progress.emit('Creating plot: %s' % label, 100*k/len(_layouts))
        if signals.canceled:
            return None
        # for comparison report, include session info in plot legends and
        # use session specific line style
        style_by = dict()
        color_by = dict()
        emg_mode = None
        if is_comparison:
            style_by['model'] = cfg.web_report.comparison_model_style_by
            color_by['model'] = cfg.web_report.comparison_model_color_by
            color_by['emg'] = cfg.web_report.comparison_emg_color_by
            if cfg.web_report.comparison_emg_rms:
                emg_mode = 'rms'
        else:
            style_by['model'] = cfg.web_report.model_style_by
            color_by['model'] = cfg.web_report.model_color_by
            color_by['emg'] = cfg.web_report.emg_color_by
        legend_type = (cfg.web_report.comparison_legend_type if is_comparison
                       else cfg.web_report.legend_type)
        try:
            if label in report_data:
                logger.debug('loading %s from saved report data' % label)
                figdata = report_data[label]
            else:
                logger.debug('creating figure data for %s' % label)
                if isinstance(layout, basestring):  # handle special layout codes
                    if layout == 'time_dist':
                        # get plot in svg format and encode to base64 for html.Img
                        buf = _time_dist_plot_svg(sessions)
                        figdata = base64.b64encode(buf.read())
                    elif layout == 'patient_info':
                        figdata = patient_info_text
                    elif layout == 'static_kinematics':
                        layout_ = cfg.layouts.lb_kinematics
                        figdata = plot_trials(trials_static, layout_,
                                        model_normaldata=model_normaldata,
                                        model_cycles='unnormalized',
                                        emg_cycles=[],
                                        legend_type='short_name_with_cyclename',
                                        style_by=style_by, color_by=color_by,
                                        big_fonts=True)
                    elif layout == 'static_emg':
                        layout_ = cfg.layouts.std_emg
                        figdata = plot_trials(trials_static, layout_,
                                        model_normaldata=model_normaldata,
                                        model_cycles=[],
                                        emg_cycles='unnormalized',
                                        legend_type='short_name_with_cyclename',
                                        style_by=style_by, color_by=color_by,
                                        big_fonts=True)
                    elif layout == 'kinematics_average':
                        layout_ = cfg.layouts.lb_kinematics
                        figdata = plot_trials(avg_trials, layout_,
                                        style_by=style_by, color_by=color_by,                    
                                        model_normaldata=model_normaldata,
                                        big_fonts=True)
                    # will be caught and menu item will be empty
                    elif layout == 'disabled':
                        raise ValueError
                    else:  # unrecognized layout; this is not caught by us
                        raise Exception('Unrecognized layout: %s' % layout)

                else:  # regular gaitutils layout
                    figdata = plot_trials(trials_dyn, layout,
                                    model_normaldata=model_normaldata,
                                    emg_mode=emg_mode,
                                    legend_type=legend_type,
                                    style_by=style_by, color_by=color_by,
                                    supplementary_data=supplementary_default,
                                    big_fonts=True)
            # save created data
            report_data_new[label] = figdata

            # make the upper and lower panel graphs from figdata, depending
            # on data type
            if layout == 'time_dist':
                graph_upper = html.Img(src='data:image/svg+xml;base64,{}'.
                                    format(figdata),
                                    id='gaitgraph%d' % k,
                                    style={'height': '100%'})
                graph_lower = html.Img(src='data:image/svg+xml;base64,{}'.
                                    format(figdata),
                                    id='gaitgraph%d'
                                    % (len(_layouts)+k),
                                    style={'height': '100%'})
            elif layout == 'patient_info':
                graph_upper = dcc.Markdown(patient_info_text)
                graph_lower = graph_upper
            else:
                # plotly fig -> dcc.Graph
                graph_upper = dcc.Graph(figure=figdata, id='gaitgraph%d' % k,
                                        style={'height': '100%'})
                graph_lower = dcc.Graph(figure=figdata, id='gaitgraph%d'
                                        % (len(_layouts)+k),
                                        style={'height': '100%'})
            dd_opts_multi_upper.append({'label': label, 'value': graph_upper})
            dd_opts_multi_lower.append({'label': label, 'value': graph_lower})

        except (ValueError, GaitDataError) as e:
            logger.warning('failed to create figure for %s: %s' % (label, e))
            # insert the menu options but make them disabled
            dd_opts_multi_upper.append({'label': label, 'value': label,
                                        'disabled': True})
            dd_opts_multi_lower.append({'label': label, 'value': label,
                                        'disabled': True})
            continue

    opts_multi, mapper_multi_upper = _make_dropdown_lists(dd_opts_multi_upper)
    opts_multi, mapper_multi_lower = _make_dropdown_lists(dd_opts_multi_lower)

    logger.debug('saving report data into %s' % data_fn)
    with open(data_fn, 'wb') as f:
        dill.dump(report_data_new, f)

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
    app = dash.Dash('gaitutils')
    # use local packaged versions of JavaScript libs etc. (no internet needed)
    app.css.config.serve_locally = True
    app.scripts.config.serve_locally = True
    app.title = _report_name(sessions, long_name=False)

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

    # inject some info of our own
    app._gaitutils_report_name = report_name

    return app
