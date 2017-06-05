# -*- coding: utf-8 -*-
"""

Process all trials in current session directory. Need to load a trial first
(to get session path.)


1st pass (all trials):
-recon+label
-fill gaps
-filter
-get fp context + strike/toeoff velocities + velocity data
-get gait direction

2nd pass:
-automark (using velocity stats)
-run models + save

-mark all trials in Eclipse .enf files


NOTES:

-ROI operations only work for Nexus >= 2.5
-Eclipse desc of last processed trial is not updated properly (gets overwritten
by Eclipse?)


@author: Jussi
"""

from gaitutils import (nexus, eclipse, utils, register_gui_exception_handler,
                       GaitDataError)
from gaitutils.config import cfg
import os
import numpy as np
import time
import argparse
import logging
import sys


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
        if type(plines) != list:
            plines = [plines]
        for pipeline in plines:
            logger.debug('Running pipeline: %s' % pipeline)
            vicon.RunPipeline(pipeline, '', cfg.autoproc.pipeline_timeout)

    def _save_trial():
        logger.debug('Saving trial')
        vicon.SaveTrial(cfg.autoproc.save_timeout)

    def _context_desc(context):
        if not context:
            return cfg.autoproc.enf_descriptions['context_none']
        if context == 'L':
            return cfg.autoproc.enf_descriptions['context_left']
        elif context == 'R':
            return cfg.autoproc.enf_descriptions['context_right']
        else:
            return cfg.autoproc.enf_descriptions['context_both']

    if not nexus.pid():
        raise Exception('Vicon Nexus not running')
    vicon = nexus.viconnexus()

    subjectname = nexus.get_metadata(vicon)['name']
    nexus_ver = nexus.true_ver()

    # used to store stats about foot velocity
    foot_vel = {'L_strike': np.array([]), 'R_strike': np.array([]),
                'L_toeoff': np.array([]), 'R_toeoff': np.array([])}
    trials = {}

    """ 1st pass - reconstruct, label, sanity check, check forceplate and gait
    direction """
    logger.debug('\n1st pass - processing %d trial(s)\n' % len(enffiles))

    for filepath_ in enffiles:
        filepath = filepath_[:filepath_.find('.Trial')]  # rm .Trial and .enf
        filename = os.path.split(filepath)[1]
        logger.debug('\nprocessing: %s' % filename)
        vicon.OpenTrial(filepath, cfg.autoproc.trial_open_timeout)
        edi = eclipse.get_eclipse_keys(filepath_, return_empty=True)
        trial_type = edi['TYPE']
        trial_desc = edi['DESCRIPTION']
        if trial_type in cfg.autoproc.type_skip:
            logger.debug('Not a dynamic trial, skipping')
            continue
        if trial_desc.upper() in [s.upper() for s in cfg.autoproc.desc_skip]:
            logger.debug('Skipping based on description')
            # run preprocessing + save even for skipped trials, to mark
            # them as processed
            _run_pipelines(cfg.autoproc.pre_pipelines)
            _save_trial()
            continue
        eclipse_str = ''
        trials[filepath] = Trial()
        allmarkers = vicon.GetMarkerNames(subjectname)
        # reset ROI before operations
        if cfg.autoproc.reset_roi and nexus_ver >= 2.5:
            (fstart, fend) = vicon.GetTrialRange()
            vicon.SetTrialRegionOfInterest(fstart, fend)
        # try to run preprocessing pipelines
        fail = None
        _run_pipelines(cfg.autoproc.pre_pipelines)
        # trial sanity checks
        trange = vicon.GetTrialRange()
        gaps_found = False
        if (trange[1] - trange[0]) < cfg.autoproc.min_trial_duration:
            fail = 'short'
        else:  # duration ok
            # try to figure out trial center frame
            for marker in cfg.autoproc.track_markers:
                try:
                    dim = utils.principal_movement_direction(vicon, cfg.
                                                             autoproc.
                                                             track_markers)
                    ctr = utils.get_crossing_frame(vicon, marker=marker,
                                                   dim=dim,
                                                   p0=cfg.autoproc.
                                                   walkway_ctr[dim])
                except (GaitDataError, ValueError):
                    ctr = None
                ctr = ctr[0] if ctr else None
                if ctr:  # ok and no gaps
                    trials[filepath].ctr_frame = ctr
                    break
            if ctr is not None:
                logger.debug('walkway center frame: %d' % ctr)
            # cannot find center frame - possible rasi or lasi gaps
            if not ctr:
                fail = 'gaps_or_short'
                gaps_found = True
            else:
                for marker in allmarkers:  # check for gaps / lbl failures
                    try:
                        gaps = (nexus.get_marker_data(vicon, marker)
                                [marker + '_gaps'])
                    except GaitDataError:
                        fail = 'label_failure'
                        break
                    # check for gaps near the center frame
                    if gaps.size > 0:
                        if (np.where(abs(gaps - ctr) <
                           cfg.autoproc.gaps_min_dist)[0].size >
                           cfg.autoproc.gaps_max):
                            gaps_found = True
                            break
        if gaps_found:
            fail = 'gaps'

        # move to next trial if preprocessing failed
        if fail is not None:
            logger.debug('preprocessing failed: %s'
                         % cfg.autoproc.enf_descriptions[fail])
            trials[filepath].description = cfg.autoproc.enf_descriptions[fail]
            _save_trial()
            continue
        else:
            trials[filepath].recon_ok = True

        # preprocessing ok, check forceplate data
        fpev = utils.detect_forceplate_events(vicon)
        # get foot velocity info for all events (do not reduce to median)
        vel = utils.get_foot_velocity(vicon, fpev, medians=False)
        valid = fpev['valid']
        eclipse_str += _context_desc(valid)
        trials[filepath].valid = valid
        trials[filepath].fpev = fpev
        for context in valid:  # save velocity data
            nv = np.append(foot_vel[context+'_strike'],
                           vel[context+'_strike'])
            foot_vel[context+'_strike'] = nv
            nv = np.append(foot_vel[context+'_toeoff'],
                           vel[context+'_toeoff'])
            foot_vel[context+'_toeoff'] = nv
        eclipse_str += ','

        # hack(ish): get movement velocity
        mkr = cfg.autoproc.track_markers[0]
        vel_ = nexus.get_marker_data(vicon, mkr)[mkr+'_V'][:, dim]
        vel = np.median(np.abs(vel_[np.where(vel_)]))
        vel_ms = vel * vicon.GetFrameRate() / 1000.
        logger.debug('median forward velocity: %.2f m/s' % vel_ms)
        eclipse_str += '%.2f m/s' % vel_ms

        _save_trial()
        # time.sleep(1)
        trials[filepath].description = eclipse_str

    # compute velocity thresholds using all trials
    vel_th = {key: (np.median(x) if x.size > 0 else None) for key, x in
              foot_vel.items()}

    """ 2nd pass - detect gait events, run models, crop """
    sel_trials = {k: v for k, v in trials.items() if v.recon_ok}
    logger.debug('\n2nd pass - processing %d trials\n' % len(sel_trials))
    for filepath, trial in sel_trials.items():
        filename = os.path.split(filepath)[1]
        logger.debug('\nprocessing: %s' % filename)
        vicon.OpenTrial(filepath, cfg.autoproc.trial_open_timeout)
        enf_file = filepath + '.Trial.enf'

        # automark using global velocity thresholds
        try:
            vicon.ClearAllEvents()
            nexus.automark_events(vicon, vel_thresholds=vel_th,
                                  max_dist=cfg.autoproc.automark_max_dist,
                                  fp_events=trial.fpev, plot=False,
                                  start_on_forceplate=
                                  cfg.autoproc.start_on_forceplate,
                                  ctr_pos=cfg.autoproc.walkway_ctr)
            trial.events = True
        except GaitDataError:  # cannot automark
            eclipse_str = '%s,%s' % (trials[filepath].description,
                                     cfg.autoproc.enf_descriptions
                                     ['automark_failure'])
            _save_trial()
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
        _run_pipelines(cfg.autoproc.model_pipeline)
        _save_trial()
        trials[filepath].description = eclipse_str

    # all done; update Eclipse descriptions
    if cfg.autoproc.eclipse_write_key and update_eclipse:
        for filepath, trial in trials.items():
            enf_file = filepath + '.Trial.enf'
            eclipse.set_eclipse_key(enf_file, cfg.autoproc.eclipse_write_key,
                                    trial.description, update_existing=True)
    else:
        logger.debug('Not updating Eclipse entries')

    # print stats
    n_events = len([tr for tr in trials.values() if tr.events])
    logger.debug('Complete')
    logger.debug('Trials opened: %d' % len(trials))
    logger.debug('Trials with recon ok: %d' % len(sel_trials))
    logger.debug('Automarked: %d' % n_events)


def autoproc_session(patterns=None, update_eclipse=True):
    enffiles = nexus.get_trial_enfs()

    if patterns:
        # filter trial names according to patterns
        enffiles = [s for s in enffiles if any([p in s for p in patterns])]
        if not enffiles:
            logger.info('No trials match specified include patterns')

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
