#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Functions for automated processing of data in Nexus.

@author: Jussi (jnu@iki.fi)
"""


from pathlib import Path
import os
import numpy as np
import time
import logging
import itertools
import shutil

from . import nexus, eclipse, utils, sessionutils, read_data, videos, events
from .envutils import GaitDataError
from .config import cfg
from .gui.qt_widgets import ProgressSignals

logger = logging.getLogger(__name__)


def _do_autoproc(enffiles, signals=None, pipelines_in_proc=True):
    """Run autoprocessing for given enf files."""

    if not cfg.autoproc.run_models_only and cfg.autoproc.delete_c3ds:
        _delete_c3ds(enffiles)

    # signals is used to track progress across threads; if not given, just
    # create a dummy one to simplify calls later
    if signals is None:
        signals = ProgressSignals()

    # whether to run Nexus pipelines in separate processes
    run_pipelines = (
        nexus._run_pipelines_multiprocessing
        if pipelines_in_proc
        else nexus._run_pipelines
    )

    def _save_trial():
        """Save trial in Nexus"""
        logger.debug('saving trial')
        vicon.SaveTrial(cfg.autoproc.nexus_timeout)

    def _context_desc(evs):
        """Eclipse description string for a given events dict evs"""
        n_right = len(
            evs.get_events(context='R', event_type='strike', forceplate=True)
        )
        n_left = len(
            evs.get_events(context='L', event_type='strike', forceplate=True)
        )
        s = ""
        if n_right:
            s += f'{n_right}R'
        if n_right and n_left:
            s += '/'
        if n_left:
            s += f'{n_left}L'
        return s or cfg.autoproc.enf_descriptions['context_none']

    def _fail(trial_info, reason):
        """Abort processing: mark and save trial"""
        fail_desc = (
            cfg.autoproc.enf_descriptions[reason]
            if reason in cfg.autoproc.enf_descriptions
            else reason
        )
        logger.info(f'preprocessing failed: {fail_desc}')
        trial_info['recon_ok'] = False
        trial_info['description'] = fail_desc
        _save_trial()

    def _range_to_roi(subj_pos, gait_dim, mov_range):
        """Try to determine ROI (in frames) from movement range"""
        subj_pos1 = subj_pos[:, [gait_dim]]
        # find non-gap frames where we are inside movement range
        dist_ok = np.where(
            (subj_pos1 >= mov_range[0])
            & (subj_pos1 <= mov_range[1])
            & (subj_pos1 != 0.0)
        )[0]
        if dist_ok.size > 0:
            return min(dist_ok), max(dist_ok)
        else:
            raise GaitDataError('no frames inside given range')

    # 1st pass
    logger.debug(f'\n1st pass - processing {len(enffiles)} trial(s)\n')
    trials = dict()

    vicon = nexus.viconnexus()
    nexus_ver_major, nexus_ver_minor = nexus._nexus_version()
    if nexus_ver_major is not None:
        logger.debug(f'running Nexus version: {nexus_ver_major}.{nexus_ver_minor}')
    # close trial to prevent 'Save trial?' dialog on first open
    nexus._close_trial()

    # init trials dict
    for enffile in enffiles:
        filepath = sessionutils.enf_to_trialfile(enffile, None)
        trials[filepath] = dict()

    # run preprocessing operations
    for ind, enffile in enumerate(enffiles):
        if cfg.autoproc.run_models_only:
            break  # skip preprocessing completely
        filepath = sessionutils.enf_to_trialfile(enffile, None)
        filename = filepath.name
        trial_info = trials[filepath]

        signals.progress.emit(
            f'Preprocessing: {filename}', int(100 * ind / len(enffiles))
        )
        if signals.canceled:
            return None

        logger.debug(f'loading in Nexus: {filename}')
        nexus._open_trial(filepath)

        try:
            nexus._get_metadata(vicon)
        except GaitDataError:
            # may indicate broken or video-only trial
            logger.warning('cannot read metadata')
            trial_info['recon_ok'] = False
            trial_info['description'] = 'skipped'
            continue

        edata = eclipse.get_eclipse_keys(enffile, return_empty=True)
        logger.debug(f'type: {edata["TYPE"]}')
        logger.debug(f'current description: {edata["DESCRIPTION"]}')
        logger.debug(f'current notes: {edata["NOTES"]}')
        eclipse_str = ''

        # check whether to skip trial
        if edata['TYPE'] in cfg.autoproc.type_skip:
            logger.debug(f'skipping based on type: {edata["TYPE"]}')
            trial_info['recon_ok'] = False
            trial_info['description'] = 'skipped'
            continue
        skip = [s.upper() for s in cfg.autoproc.eclipse_skip]
        if any([s in edata['DESCRIPTION'].upper() for s in skip]) or any(
            [s in edata['NOTES'].upper() for s in skip]
        ):
            logger.debug('skipping based on description/notes')
            # run preprocessing + save even for skipped trials, to mark
            # them as processed - mostly so that Eclipse export to Polygon
            # will work
            run_pipelines(cfg.autoproc.pre_pipelines)
            _save_trial()
            trial_info['recon_ok'] = False
            trial_info['description'] = 'skipped'
            continue

        # try to run preprocessing pipelines
        run_pipelines(cfg.autoproc.pre_pipelines)

        # check trial length
        trange = vicon.GetTrialRange()
        if (trange[1] - trange[0]) < cfg.autoproc.min_trial_duration:
            _fail(trial_info, 'short')
            continue

        # check for valid marker data
        allmarkers = nexus._get_marker_names(vicon, trajs_only=True)
        try:
            mkrdata = read_data.get_marker_data(vicon, allmarkers, ignore_missing=True)
        except GaitDataError:
            logger.info('get_marker_data failed')
            _fail(trial_info, 'label_failure')
            continue

        # fail on any gaps in trial (off by default)
        gaps_found = False
        if cfg.autoproc.fail_on_gaps:
            for marker in set(allmarkers) - set(cfg.autoproc.ignore_markers):
                gaps = utils.marker_gaps(mkrdata[marker])
                if gaps.size > 0:
                    gaps_found = True
                    break
            if gaps_found:
                _fail(trial_info, 'gaps')
                continue

        # check for valid Plug-in Gait set
        if cfg.autoproc.check_marker_set:
            if not utils.is_plugingait_set(mkrdata):
                logger.info('marker set does not correspond to Plug-in Gait')
                _fail(trial_info, 'label_failure')
                continue
        # check for flipped markers
        flipped = list(utils._check_markers_flipped(mkrdata))
        if flipped:
            for m1, m2 in flipped:
                logger.info(f'trying to swap trajectories for {m1} and {m2}')
                nexus._swap_markers(vicon, m1, m2)

        # get subject position by tracking markers
        try:
            subj_pos = utils.avg_markerdata(mkrdata, cfg.autoproc.track_markers)
        except GaitDataError:
            logger.info('gaps in tracking markers')
            _fail(trial_info, 'label_failure')
            continue
        gait_dim = utils._principal_movement_direction(subj_pos)
        # our roi (in frames) according to events_range (which is in lab coords)
        # this is not the same as Nexus ROI, which is unset at this point
        try:
            roi = _range_to_roi(subj_pos, gait_dim, cfg.autoproc.events_range)
            logger.debug(f'events range corresponds to frames {roi[0]}-{roi[1]}')
            trial_info['roi'] = roi
        except GaitDataError:
            _fail(trial_info, 'no_frames_in_range')
            continue

        if signals.canceled:
            return None

        # check forceplate data
        fp_info = (
            eclipse._eclipse_forceplate_keys(edata)
            if cfg.autoproc.use_eclipse_fp_info
            else None
        )
        try:
            fpev, n_plates = utils.detect_forceplate_events(
                vicon, mkrdata, eclipse_fp_info=fp_info, roi=roi, return_nplates=True
            )
        except GaitDataError:
            logger.warning('cannot determine forceplate events, possibly due to gaps')
            _fail(trial_info, 'gaps')
            continue
        # get foot velocity info for all events (do not reduce to median)
        try:
            foot_vel = utils._get_foot_contact_vel(mkrdata, fpev, medians=True, roi=roi)
        except GaitDataError:
            logger.warning('cannot determine foot velocity, possibly due to gaps')
            _fail(trial_info, 'gaps')
            continue

        # preprocessing looks ok at this stage
        trial_info['recon_ok'] = True
        trial_info['mkrdata'] = mkrdata

        eclipse_str += _context_desc(fpev)
        eclipse_str += ','

        trial_info['fpev'] = fpev
        trial_info['foot_vel'] = foot_vel

        if signals.canceled:
            return None

        # main direction in lab frame (1,2,3 for x,y,z)
        inds_ok = np.where(np.any(subj_pos, axis=1))  # ignore gaps
        subj_pos_ = subj_pos[inds_ok]
        # +1/-1 for forward/backward (coord increase / decrease)
        gait_dir = np.median(np.diff(subj_pos_, axis=0), axis=0)[gait_dim]
        # write Eclipse key for direction
        if (
            'dir_forward' in cfg.autoproc.enf_descriptions
            and 'dir_backward' in cfg.autoproc.enf_descriptions
        ):
            dir_str = 'dir_forward' if gait_dir > 0 else 'dir_backward'
            dir_desc = cfg.autoproc.enf_descriptions[dir_str]
            eclipse_str += f'{dir_desc},'

        # compute gait velocity
        median_vel = utils._trial_median_velocity(vicon)
        logger.debug(f'median forward velocity: {median_vel:.2f} m/s')
        eclipse_str += f'{median_vel:.2f} m/s'

        _save_trial()
        trial_info['description'] = eclipse_str

        # write Eclipse fp values according to our detection, or reset them
        # note that Eclipse fp data affects e.g. Plug-in Gait functioning
        fp_info, _ = events.get_forceplate_info(fpev, n_plates)
        # try to avoid a possible race condition where Nexus is still
        # holding the .enf file open
        time.sleep(0.1)
        try:
            if cfg.autoproc.write_eclipse_fp_info == 'write':
                logger.debug('writing detected forceplate info into Eclipse')
                eclipse.set_eclipse_keys(enffile, fp_info, update_existing=True)
            elif cfg.autoproc.write_eclipse_fp_info == 'reset':
                logger.debug('resetting Eclipse forceplate info')
                fp_info_auto = {k: 'Auto' for k, v in fp_info.items()}
                eclipse.set_eclipse_keys(enffile, fp_info_auto, update_existing=True)
            else:
                logger.debug('not setting Eclipse forceplate info')
        except IOError:
            logger.warning(f'failed to update Eclipse forceplate info in {enffile}')

    #
    # all preprocessing done
    #

    # if preprocessing was skipped, mark all trials for subsequent processing
    if cfg.autoproc.run_models_only:
        for tr in trials.values():
            tr['recon_ok'] = True

    # 2nd pass
    sel_trials = {
        filepath: trial for filepath, trial in trials.items() if trial['recon_ok']
    }
    logger.debug('\n2nd pass - processing %d trials\n' % len(sel_trials))

    for ind, (filepath, trial_info) in enumerate(sel_trials.items()):
        filename = filepath.name
        logger.debug(f'loading in Nexus: {filename}')
        nexus._open_trial(filepath)
        enf_file = filepath.with_suffix('.Trial.enf')

        signals.progress.emit(
            f'Events and models: {filename}', int(100 * ind / len(sel_trials))
        )
        if signals.canceled:
            return None

        if not cfg.autoproc.run_models_only:
            # automark using global velocity thresholds
            try:
                vicon.ClearAllEvents()
                evs = utils.automark_events(
                    vicon,
                    vel_thresholds=trial_info['foot_vel'],
                    mkrdata=trial_info['mkrdata'],
                    events_range=cfg.autoproc.events_range,
                    roi=trial_info['roi'],
                )
                # adjust the marker-based events according to forceplate data
                evs.merge_forceplate_events(trial_info['fpev'], adjust_frames=True)
                nexus._create_events(vicon, evs)
            except GaitDataError:  # cannot automark
                eclipse_str = '%s,%s' % (
                    trial_info['description'],
                    cfg.autoproc.enf_descriptions['automark_failure'],
                )
                logger.debug('automark failed')
                _save_trial()
                trial_info['description'] = eclipse_str
                continue  # next trial

            if signals.canceled:
                return None

            # crop trial around events
            if cfg.autoproc.crop_margin is not None:
                if nexus._nexus_ver_greater(2, 5):
                    ev_frames = [ev.frame for ev in evs.get_events()]
                    if ev_frames:
                        # when setting roi, do not go beyond trial range
                        minfr, maxfr = vicon.GetTrialRange()
                        roistart = max(min(ev_frames) - cfg.autoproc.crop_margin, minfr)
                        roiend = min(max(ev_frames) + cfg.autoproc.crop_margin, maxfr)
                        # method cannot take numpy.int64
                        vicon.SetTrialRegionOfInterest(int(roistart), int(roiend))
                else:
                    logger.info(
                        'Nexus API version does not support cropping, please update Nexus'
                    )

            desc = f"{cfg.autoproc.enf_descriptions['ok']},{trial_info['description']}"
            trial_info['description'] = desc

        # run model pipeline and save
        run_pipelines(cfg.autoproc.model_pipelines)
        _save_trial()

    # all done; update enf files
    if cfg.autoproc.eclipse_write_key and not cfg.autoproc.run_models_only:
        # try to avoid a possible race condition where Nexus is still
        # holding the .enf file open
        time.sleep(0.1)
        for filepath, trial_info in trials.items():
            enf_file = filepath.with_suffix('.Trial.enf')
            try:
                eclipse.set_eclipse_keys(
                    enf_file,
                    {cfg.autoproc.eclipse_write_key: trial_info['description']},
                    update_existing=True,
                )
            except IOError:
                logger.warning(f'failed to update Eclipse description in {enf_file}')
    else:
        logger.debug('not updating Eclipse data')

    # print stats
    logger.debug('Complete')
    logger.debug('Trials opened: %d' % len(trials))
    logger.debug('Trials with recon ok: %d' % len(sel_trials))


def _delete_c3ds(enffiles):
    """Delete all c3d files corresponding to the given .enf files.

    This is a good thing to do before autoprocessing, since otherwise Nexus will
    load analog data from the existing c3d files which are affected by e.g.
    previous crop operations.
    """
    logger.debug('deleting previous c3d files')
    c3dfiles = sessionutils._filter_to_c3ds(enffiles)
    for enffile, c3dfile in zip(enffiles, c3dfiles):
        if not c3dfile.is_file():
            continue
        if not enffile.is_file():
            logger.warning(f'.enf file {enffile} does not exist')
        edata = eclipse.get_eclipse_keys(enffile, return_empty=True)
        # do not delete static .c3d files (needed for dynamic processing)
        if edata['TYPE'] == 'Static':
            logger.debug(f'keeping static c3d file {c3dfile}')
            continue

        # to prevent data loss, do not delete c3d if original
        # x1d and x2d do not exist
        x1dfile = sessionutils.enf_to_trialfile(enffile, 'x1d')
        x2dfile = sessionutils.enf_to_trialfile(enffile, 'x2d')
        if x1dfile.is_file() and x2dfile.is_file():
            logger.debug(f'deleting existing c3d file {c3dfile}')
            c3dfile.unlink()
        else:
            logger.debug(
                'refusing to delete c3d file %s since original '
                'data files .(x1d and .x2d) do not exist' % c3dfile
            )


def autoproc_session(signals=None):
    """Autoprocess the current Nexus session.

    Parameters
    ----------
    signals : ProgressSignals | None
        This is used to emit processing-related status signals for the GUI. If
        None, a dummy instance will be created.
    """
    sessionpath = nexus.get_sessionpath()
    if enffiles := sessionutils.get_enfs(sessionpath):
        _do_autoproc(enffiles, signals=signals)
    else:
        raise GaitDataError('No trials found (no .enf files in session)')


def autoproc_trial(signals=None):
    """Autoprocess the currently open Nexus trial.

    Parameters
    ----------
    signals : ProgressSignals | None
        This is used to emit processing-related status signals. If None, a dummy
        instance will be created.
    """
    if not (fn := nexus._get_trialname()):
        raise GaitDataError('No trial open in Nexus')
    # XXX: this may fail with old-style enf naming (2015 and pre)
    fn += '.Trial.enf'
    enffiles = [nexus.get_sessionpath() / fn]
    # for single trial autoprocess, running pipelines in separate processes is
    # not really necessary and seems to cause slowdowns
    if enffiles:
        _do_autoproc(enffiles, pipelines_in_proc=False, signals=signals)


def automark_trial(plot=False):
    """Automatically mark events for the currently loaded Nexus trial.

    Parameters
    ----------
    plot : bool
        Create a velocity/events plot. Mostly for debug purposes.
    """
    vicon = nexus.viconnexus()
    roi = vicon.GetTrialRegionOfInterest()
    vicon.ClearAllEvents()

    foot_markers = cfg.autoproc.left_foot_markers + cfg.autoproc.right_foot_markers
    mkrs = foot_markers + utils._pig_pelvis_markers()
    mkrdata = read_data.get_marker_data(vicon, mkrs, ignore_missing=True)
    fpev = utils.detect_forceplate_events(vicon, mkrdata, roi=roi)
    vel = utils._get_foot_contact_vel(mkrdata, fpev, roi=roi)
    evs = utils.automark_events(vicon, vel_thresholds=vel, roi=roi, plot=plot)
    evs.merge_forceplate_events(fpev, adjust_frames=True)
    nexus._create_events(vicon, evs)


def _copy_session_videos():
    """Copy Nexus session videos to desktop"""
    nexus._check_nexus()

    dest_dir = Path.home() / 'Desktop' / 'nexus_videos'
    if not dest_dir.is_dir():
        os.mkdir(dest_dir)

    sessionpath = nexus.get_sessionpath()
    c3dfiles = sessionutils.get_c3ds(
        sessionpath, tags=cfg.eclipse.repr_tags, trial_type='dynamic'
    )
    vidfiles = itertools.chain.from_iterable(
        videos.get_trial_videos(c3d, vid_ext='.avi') for c3d in c3dfiles
    )
    vidfiles = list(vidfiles)
    if not vidfiles:
        raise GaitDataError('No video files found for representative trials')

    for vidfile in vidfiles:
        logger.debug(f'copying {vidfile} -> {dest_dir}')
        shutil.copy2(vidfile, dest_dir)
