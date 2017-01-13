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


TODO:

vars into config data


NOTES:

-ROI operations only work for Nexus >= 2.5
-Eclipse desc of last processed trial is not updated properly (gets overwritten
by Eclipse?)


@author: Jussi
"""

from __future__ import print_function
from gaitutils import nexus, eclipse, utils, config
import glob
import os
import stat
import numpy as np
from numpy import inf
import time


# list of pipelines to run
PRE_PIPELINES = ['Reconstruct and label (legacy)', 'AutoGapFill_mod', 'filter']
MODEL_PIPELINE = 'Dynamic model + save (LEGACY)'
# timeouts for Nexus (sec)
TRIAL_OPEN_TIMEOUT = 45
PIPELINE_TIMEOUT = 45
SAVE_TIMEOUT = 100
# trial types to skip (Eclipse type field) (case sensitive)
TYPE_SKIP = 'Static'
# trial descriptions to skip (Eclipse description field) (not case sensitive)
DESC_SKIP = ['Unipedal right', 'Unipedal left', 'Toe standing']
# min. trial duration (frames)
MIN_TRIAL_DURATION = 100
# how many frames to leave before/after first/last events
CROP_MARGIN = 10
# marker for tracking overall body position (to get gait dir) and center frame
# do not use RPSI and LPSI since they are not always present
TRACK_MARKERS = ['RASI', 'LASI']
# center of walkway
Y_MIDPOINT = 0
# right feet markers
RIGHT_FOOT_MARKERS = ['RHEE', 'RTOE', 'RANK']
# left foot markers
LEFT_FOOT_MARKERS = ['LHEE', 'LTOE', 'LANK']
# Eclipse descriptions for various conditions
DESCRIPTIONS = {'short': 'short trial', 'context_right': 'o',
                'context_left': 'v',
                'no_context': 'ei kontaktia', 'dir_front': 'e',
                'dir_back': 't', 'ok': 'ok',
                'automark_failure': 'not automarked', 'gaps': 'gaps',
                'gaps_or_short': 'gaps or short trial',
                'label_failure': 'labelling failed'}
# gaps min distance from center frame
GAPS_MIN_DIST = 70
# max. tolerated frames with gaps
GAPS_MAX = 10
# whether to use trial specific velocity threshold data when available
TRIAL_SPECIFIC_VELOCITY = True
# write Eclipse descriptions
WRITE_ECLIPSE_DESC = True
# reset ROI before processing; otherwise trajectories won't get reconstructed
# outside ROI
RESET_ROI = True
# check subject weight when analyzing forceplate data
CHECK_WEIGHT = True

# read config data
cfg = config.Config()


class Trial:
    """ Used as data holder """
    def __init__(self):
        self.recon_ok = False
        self.ctr_frame = None
        self.context = None
        self.description = ''
        self.fpdata = None
        self.events = False

    def __repr__(self):
        s = '<Trial |'
        s += ' recon ok,' if self.recon_ok else ' recon failed,'
        s += self.context if self.context else ' no context'
        s += '>'
        return s


def _do_autoproc(enffiles):
    """ Do autoprocessing for all trials listed in enffiles (list of
    paths to .enf files).
    """

    if not nexus.pid():
        raise Exception('Vicon Nexus not running')
    vicon = nexus.viconnexus()

    nexus_ver = nexus.true_ver()

    contact_v = {'L_strike': [], 'R_strike': [],
                 'L_toeoff': [], 'R_toeoff': []}
    trials = {}

    subjectname = vicon.GetSubjectNames()[0]

    """ 1st pass - reconstruct, label, sanity check, check forceplate and gait
    direction """
    print('\n1st pass - processing %d trial(s)\n' % len(enffiles))

    for filepath_ in enffiles:
        filepath = filepath_[:filepath_.find('.Trial')]  # rm .Trial and .enf
        filename = os.path.split(filepath)[1]
        print('\nprocessing: %s' % filename)
        edi = eclipse.get_eclipse_keys(filepath_, return_empty=True)
        trial_type = edi['TYPE']
        trial_desc = edi['DESCRIPTION']
        if trial_type in TYPE_SKIP:
            print('Not a dynamic trial, skipping')
            continue
        if trial_desc.upper() in [s.upper() for s in DESC_SKIP]:
            print('Skipping based on description')
            # run preprocessing + save even for skipped trials, to mark
            # them as processed
            for pipeline in PRE_PIPELINES:
                vicon.RunPipeline(pipeline, '', PIPELINE_TIMEOUT)
            vicon.SaveTrial(SAVE_TIMEOUT)
            continue
        eclipse_str = ''
        trials[filepath] = Trial()
        vicon.OpenTrial(filepath, TRIAL_OPEN_TIMEOUT)
        allmarkers = vicon.GetMarkerNames(subjectname)
        # reset ROI before operations
        if RESET_ROI and nexus_ver >= 2.5:
            (fstart, fend) = vicon.GetTrialRange()
            vicon.SetTrialRegionOfInterest(fstart, fend)

        # try to run preprocessing pipelines
        fail = None
        for pipeline in PRE_PIPELINES:
            vicon.RunPipeline(pipeline, '', PIPELINE_TIMEOUT)
        # trial sanity checks
        trange = vicon.GetTrialRange()
        if (trange[1] - trange[0]) < MIN_TRIAL_DURATION:
            fail = 'short'
        else:  # duration ok
            # try to figure out trial center frame
            for marker in TRACK_MARKERS:
                try:
                    ctr = utils.get_crossing_frame(vicon, marker=marker, dim=1,
                                                   p0=Y_MIDPOINT)
                except ValueError:
                    ctr = None
                ctr = ctr[0] if ctr else None
                if ctr:  # ok and no gaps
                    trials[filepath].ctr_frame = ctr
                    break
            # cannot find center frame - possible rasi or lasi gaps
            if not ctr:
                fail = 'gaps_or_short'
                gaps_found = True
            else:
                gaps_found = False
                for marker in allmarkers:  # check for gaps / lbl failures
                    try:
                        gaps = (nexus.get_marker_data(vicon, marker)
                                [marker + '_gaps'])
                    except ValueError:
                        fail = 'label_failure'
                        break
                    # check for gaps nearby the center frame
                    if gaps.size > 0:
                        if (np.where(abs(gaps - ctr) <
                           GAPS_MIN_DIST)[0].size > GAPS_MAX):
                            gaps_found = True
                            break
        if gaps_found:
            fail = 'gaps'

        # move to next trial if preprocessing failed
        if fail is not None:
            print('preprocessing failed: %s' % DESCRIPTIONS[fail])
            trials[filepath].description = DESCRIPTIONS[fail]
            vicon.SaveTrial(SAVE_TIMEOUT)
            continue
        else:
            trials[filepath].recon_ok = True

        # preprocessing ok, get kinetics info
        fpdata = utils.kinetics_available(vicon, CHECK_WEIGHT)
        context = fpdata['context']
        if context:
            eclipse_str += (DESCRIPTIONS['context_right'] if context == 'R'
                            else DESCRIPTIONS['context_left'])
            contact_v[context+'_strike'].append(fpdata['strike_v'])
            contact_v[context+'_toeoff'].append(fpdata['toeoff_v'])
            trials[filepath].context = context
            trials[filepath].fpdata = fpdata
        else:
            eclipse_str += DESCRIPTIONS['no_context']
        eclipse_str += ','

        # check direction of gait (y coordinate increase/decrease)
        gait_dir = utils.get_movement_direction(vicon, TRACK_MARKERS[0],
                                                'y')
        gait_dir = (DESCRIPTIONS['dir_back'] if gait_dir == 1 else
                    DESCRIPTIONS['dir_front'])
        eclipse_str += gait_dir
        vicon.SaveTrial(SAVE_TIMEOUT)
        # time.sleep(1)
        trials[filepath].description = eclipse_str

        # compute velocity thresholds from preprocessed trial data
        vel_th = {}
        for key in contact_v:
            if contact_v[key]:
                vel_th[key] = np.median(contact_v[key])
            else:
                vel_th[key] = None

    """ 2nd pass - detect gait events, run models, crop """
    sel_trials = {k: v for k, v in trials.items() if v.recon_ok}
    print('\n2nd pass - processing %d trials\n' % len(sel_trials))
    for filepath, trial in sel_trials.items():
        filename = os.path.split(filepath)[1]
        print('\nprocessing: %s' % filename)
        vicon.OpenTrial(filepath, TRIAL_OPEN_TIMEOUT)
        enf_file = filepath + '.Trial.enf'
        # if fp data available from trial itself, use it for automark
        # otherwise use statistics
        context = trial.context
        vel_th_ = vel_th.copy()
        if context:
            vel_th_[context+'_strike'] = trial.fpdata['strike_v']
            vel_th_[context+'_toeoff'] = trial.fpdata['toeoff_v']
            ctr_frame = trial.fpdata['strike']  # mark around fp strike
        else:
            ctr_frame = trial.ctr_frame  # mark around walkway center
        try:
            vicon.ClearAllEvents()
            nexus.automark_events(vicon, context=context,
                                  ctr_frame=ctr_frame,
                                  vel_thresholds=vel_th_)
            trial.events = True
        except ValueError:  # cannot automark
            eclipse_str = (trials[filepath].description + ',' +
                           DESCRIPTIONS['automark_failure'])
            vicon.SaveTrial(SAVE_TIMEOUT)
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
                roistart = max(min(evs)-CROP_MARGIN, minfr)
                roiend = min(max(evs)+CROP_MARGIN, maxfr)
                vicon.SetTrialRegionOfInterest(roistart, roiend)
        # run model pipeline and save
        eclipse_str = DESCRIPTIONS['ok'] + ',' + trial.description
        vicon.RunPipeline(MODEL_PIPELINE, '', PIPELINE_TIMEOUT)
        vicon.SaveTrial(SAVE_TIMEOUT)
        trials[filepath].description = eclipse_str

    # all done; update Eclipse descriptions
    if WRITE_ECLIPSE_DESC:
        for filepath, trial in trials.items():
            enf_file = filepath + '.Trial.enf'
            os.chmod(enf_file, stat.S_IWRITE)
            eclipse.set_eclipse_key(enf_file, 'DESCRIPTION',
                                    trial.description, update_existing=True)
            # this is a hack to prevent Eclipse from changing the values
            os.chmod(enf_file, not stat.S_IWRITE)

    # print stats
    n_events = len([tr for tr in trials.values() if tr.events])
    print('\nComplete\n')
    print('Trials opened: %d' % len(trials))
    print('Trials with recon ok: %d' % len(sel_trials))
    print('Automarked: %d' % n_events)


if __name__ == '__main__':

    enffiles = nexus.get_trial_enfs()
    _do_autoproc(enffiles)
