# -*- coding: utf-8 -*-
"""

Autoprocess all trials in current Nexus session directory.

See autoproc section in config for options.

1st pass (all trials):
-preprocess
-get fp context + strike/toeoff velocities + velocity data
-get gait direction

2nd pass:
-automark (using velocity stats)
-run models + save
-write Eclipse info


NOTES:
-ROI operations only work for Nexus >= 2.5


@author: Jussi (jnu@iki.fi)
"""

import os
import numpy as np
import argparse
import logging

from gaitutils import nexus, eclipse, utils, GaitDataError, sessionutils
from gaitutils.config import cfg


logger = logging.getLogger(__name__)


class Trial:
    """ Used as data holder """
    def __init__(self):
        self.recon_ok = False
        self.ctr_frame = None
        self.context = None
        self.description = ''
        self.fpev = None
        self.events = False

    def __repr__(self):
        s = '<Trial |'
        s += ' recon ok,' if self.recon_ok else ' recon failed,'
        s += self.context if self.context else ' no context'
        s += '>'
        return s


def _do_autoproc(enffiles, update_eclipse=True):
    """ Do autoprocessing for all trials listed in enffiles (list of
    paths to .enf files).
    """

    def _run_pipelines(plines):
        """Run given Nexus pipeline(s)"""
        if type(plines) != list:
            plines = [plines]
        for pipeline in plines:
            logger.debug('running pipeline: %s' % pipeline)
            result = vicon.Client.RunPipeline(pipeline.encode('utf-8'), '',
                                              cfg.autoproc.nexus_timeout)
            if result.Error():
                logger.warning('error while trying to run Nexus pipeline: %s'
                               % pipeline)

    def _save_trial():
        """Save trial in Nexus"""
        logger.debug('saving trial')
        vicon.SaveTrial(cfg.autoproc.nexus_timeout)

    def _context_desc(context):
        """Get description for given context"""
        if not context:
            return cfg.autoproc.enf_descriptions['context_none']
        if context == {'L'}:
            return cfg.autoproc.enf_descriptions['context_left']
        elif context == {'R'}:
            return cfg.autoproc.enf_descriptions['context_right']
        elif context == {'R', 'L'}:
            return cfg.autoproc.enf_descriptions['context_both']
        else:
            raise ValueError('Unexpected context')

    def fail(trial, reason):
        """Abort processing: mark and save trial"""
        logger.debug('preprocessing failed: %s'
                     % cfg.autoproc.enf_descriptions[reason])
        trial.description = cfg.autoproc.enf_descriptions[reason]
        _save_trial()

    vicon = nexus.viconnexus()
    nexus_ver = nexus.true_ver()

    # used to store stats about foot velocity
    foot_vel = {'L_strike': np.array([]), 'R_strike': np.array([]),
                'L_toeoff': np.array([]), 'R_toeoff': np.array([])}
    trials = {}

    # 1st pass
    logger.debug('\n1st pass - processing %d trial(s)\n' % len(enffiles))

    for filepath_ in enffiles:
        filepath = filepath_[:filepath_.find('.Trial')]  # rm .Trial and .enf
        filename = os.path.split(filepath)[1]
        logger.debug('\nprocessing: %s' % filename)
        vicon.OpenTrial(filepath, cfg.autoproc.nexus_timeout)
        subjectname = nexus.get_metadata(vicon)['name']
        edi = eclipse.get_eclipse_keys(filepath_, return_empty=True)
        trial_type = edi['TYPE']
        trial_desc = edi['DESCRIPTION']
        trial_notes = edi['NOTES']
        eclipse_str = ''
        trial = Trial()
        trials[filepath] = trial
        allmarkers = vicon.GetMarkerNames(subjectname)

        # check whether to skip trial
        if trial_type in cfg.autoproc.type_skip:
            logger.debug('skipping based on type: %s' % trial_type)
            continue
        skip = [s.upper() for s in cfg.autoproc.eclipse_skip]
        if trial_desc.upper() in skip or trial_notes.upper in skip:
            logger.debug('skipping based on description')
            # run preprocessing + save even for skipped trials, to mark
            # them as processed - mostly so that Eclipse export to Polygon
            # will work
            _run_pipelines(cfg.autoproc.pre_pipelines)
            _save_trial()
            continue

        # reset ROI before operations
        if cfg.autoproc.reset_roi and nexus_ver >= 2.5:
            (fstart, fend) = vicon.GetTrialRange()
            vicon.SetTrialRegionOfInterest(fstart, fend)

        # try to run preprocessing pipelines
        _run_pipelines(cfg.autoproc.pre_pipelines)

        # check trial length
        trange = vicon.GetTrialRange()
        if (trange[1] - trange[0]) < cfg.autoproc.min_trial_duration:
            fail(trial, 'short')
            continue

        # check for valid marker data
        try:
            mkrdata = nexus.get_marker_data(vicon, allmarkers)
        except GaitDataError:
            fail(trial, 'label_failure')
            continue

        # check markers for remaining gaps; leading
        gaps_found = False
        for marker in set(allmarkers) - set(cfg.autoproc.ignore_markers):
            gaps = mkrdata[marker + '_gaps']
            if gaps.size > 0:
                gaps_found = True
                break
        if gaps_found:
            fail(trial, 'gaps')
            continue

        # preprocessing ok
        trials[filepath].recon_ok = True

        # check forceplate data
        fp_info = (eclipse.eclipse_fp_keys(edi) if
                   cfg.autoproc.use_eclipse_fp_info else None)
        fpev = utils.detect_forceplate_events(vicon, fp_info=fp_info)

        # get foot velocity info for all events (do not reduce to median)
        vel = utils.get_foot_velocity(vicon, fpev, medians=False)
        valid = fpev['valid']
        eclipse_str += _context_desc(valid)
        trials[filepath].valid = valid
        trials[filepath].fpev = fpev

        for context in valid:  # save velocity data
            nv = np.append(foot_vel[context+'_strike'], vel[context+'_strike'])
            foot_vel[context+'_strike'] = nv
            nv = np.append(foot_vel[context+'_toeoff'], vel[context+'_toeoff'])
            foot_vel[context+'_toeoff'] = nv
        eclipse_str += ','

        track_mkr = cfg.autoproc.track_markers[0]
        subj_pos = mkrdata[track_mkr+'_P']
        subj_vel = mkrdata[track_mkr+'_V']

        # check gait direction (forward / backward)
        if ('dir_forward' in cfg.autoproc.enf_descriptions and 'dir_backward'
           in cfg.autoproc.enf_descriptions):
            gait_dim = utils.principal_movement_direction(subj_pos)
            # check principal coordinate increase/decrease in movement dir
            gait_dir = np.median(np.diff(subj_pos, axis=0), axis=0)[gait_dim]
            dir_str = 'dir_forward' if gait_dir == 1 else 'dir_backward'
            dir_desc = cfg.autoproc.enf_descriptions[dir_str]
            eclipse_str += '%s,' % dir_desc

        # gait velocity
        median_vel = np.median(np.abs(subj_vel[np.where(subj_vel)]))
        median_vel_ms = median_vel * vicon.GetFrameRate() / 1000.
        logger.debug('median forward velocity: %.2f m/s' % median_vel_ms)
        eclipse_str += '%.2f m/s' % median_vel_ms

        _save_trial()
        trials[filepath].description = eclipse_str

    # preprocessing done
    # compute velocity thresholds using all trials
    vel_th = {key: (np.median(x) if x.size > 0 else None) for key, x in
              foot_vel.items()}

    # 2nd pass
    sel_trials = {k: v for k, v in trials.items() if v.recon_ok}
    logger.debug('\n2nd pass - processing %d trials\n' % len(sel_trials))

    for filepath, trial in sel_trials.items():
        filename = os.path.split(filepath)[1]
        logger.debug('\nprocessing: %s' % filename)
        vicon.OpenTrial(filepath, cfg.autoproc.nexus_timeout)
        enf_file = filepath + '.Trial.enf'

        # automark using global velocity thresholds
        try:
            vicon.ClearAllEvents()
            nexus.automark_events(vicon, vel_thresholds=vel_th,
                                  fp_events=trial.fpev, plot=False,
                                  events_range=cfg.autoproc.events_range,
                                  start_on_forceplate=cfg.autoproc.
                                  start_on_forceplate)
            trial.events = True
        except GaitDataError:  # cannot automark
            eclipse_str = '%s,%s' % (trials[filepath].description,
                                     cfg.autoproc.enf_descriptions
                                     ['automark_failure'])
            logger.debug('automark failed')
            _save_trial()
            trials[filepath].description = eclipse_str
            continue  # next trial

        # events ok
        # crop trial
        if nexus_ver >= 2.5:
            evs = vicon.GetEvents(subjectname, "Left", "Foot Strike")[0]
            evs += vicon.GetEvents(subjectname, "Right", "Foot Strike")[0]
            evs += vicon.GetEvents(subjectname, "Left", "Foot Off")[0]
            evs += vicon.GetEvents(subjectname, "Right", "Foot Off")[0]

            if evs:
                # when setting roi, do not go beyond trial range
                minfr, maxfr = vicon.GetTrialRange()
                roistart = max(min(evs) - cfg.autoproc.crop_margin, minfr)
                roiend = min(max(evs) + cfg.autoproc.crop_margin, maxfr)
                vicon.SetTrialRegionOfInterest(roistart, roiend)

        # run model pipeline and save
        eclipse_str = '%s,%s' % (cfg.autoproc.enf_descriptions['ok'],
                                 trial.description)
        _run_pipelines(cfg.autoproc.model_pipelines)
        _save_trial()
        trials[filepath].description = eclipse_str

    # all done; update Eclipse descriptions
    if cfg.autoproc.eclipse_write_key and update_eclipse:
        for filepath, trial in trials.items():
            enf_file = filepath + '.Trial.enf'
            eclipse.set_eclipse_keys(enf_file, {cfg.autoproc.eclipse_write_key:
                                     trial.description}, update_existing=True)
    else:
        logger.debug('not updating Eclipse data')

    # print stats
    n_events = len([tr for tr in trials.values() if tr.events])
    logger.debug('Complete')
    logger.debug('Trials opened: %d' % len(trials))
    logger.debug('Trials with recon ok: %d' % len(sel_trials))
    logger.debug('Automarked: %d' % n_events)


def autoproc_session(patterns=None, update_eclipse=True):

    sessionpath = nexus.get_sessionpath()
    enffiles = sessionutils.get_session_enfs(sessionpath)

    if patterns:
        # filter trial names according to patterns
        enffiles = [s for s in enffiles if any([p in s for p in patterns])]
    if enffiles:
        _do_autoproc(enffiles, update_eclipse=update_eclipse)


if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('--include', metavar='p', type=str, nargs='+',
                        help='strings that must appear in trial name')
    parser.add_argument('--no_eclipse', action='store_true',
                        help='disable writing of Eclipse entries')

    args = parser.parse_args()
    autoproc_session(args.include, update_eclipse=not args.no_eclipse)
