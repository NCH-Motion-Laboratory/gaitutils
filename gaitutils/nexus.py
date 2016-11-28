# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 10:27:56 2016

@author: jnu@iki.fi

Data readers & processing utils for Vicon Nexus.

"""

from __future__ import print_function
import sys
import numpy as np
from scipy import signal
import os.path as op
import psutil
from numutils import rising_zerocross, falling_zerocross
import matplotlib.pyplot as plt
from config import Config

cfg = Config()

if cfg.nexus_path:
    if op.isdir(cfg.nexus_path):
        if not cfg.nexus_path + "/SDK/Python" in sys.path:
            sys.path.append(cfg.nexus_path + "/SDK/Python")
            # needed at least when running outside Nexus
            sys.path.append(cfg.nexus_path + "/SDK/Win32")
try:
    import ViconNexus
except ImportError:
    print('Warning: cannot import Nexus SDK, unable to communicate with Nexus')


def pid():
    """ Tries to return the PID of the running Nexus process. """
    PROCNAME = "Nexus.exe"
    for proc in psutil.process_iter():
        try:
            if proc.name() == PROCNAME:
                return proc.pid
        except psutil.AccessDenied:
            pass
    return None


def nexus_ver():
    return float(NEXUS_VER)


def viconnexus():
    """ Return a ViconNexus instance. """
    return ViconNexus.ViconNexus()


def is_vicon_instance(obj):
    """ Check if obj is an instance of ViconNexus """
    return obj.__class__.__name__ == 'ViconNexus'



def get_metadata(vicon):
    """ Read trial and subject metadata """
    subjectnames = vicon.GetSubjectNames()
    if len(subjectnames) > 1:
        raise ValueError('Nexus returns multiple subjects')
    if not subjectnames:
        raise ValueError('No subject defined in Nexus')
    name = subjectnames[0]
    Bodymass = vicon.GetSubjectParam(name, 'Bodymass')
    # for unknown reasons, above method may return tuple or float
    # depending on whether script is run from Nexus or outside
    if type(Bodymass) == tuple:
        bodymass = vicon.GetSubjectParam(name, 'Bodymass')[0]
    else:  # hopefully float
        bodymass = vicon.GetSubjectParam(name, 'Bodymass')
    trialname_ = vicon.GetTrialName()
    sessionpath = trialname_[0]
    trialname = trialname_[1]
    if not trialname:
        raise ValueError('No trial loaded')
    # Get events - GetEvents() indices seem to often be 1 frame less than on
    # Nexus display - only happens with ROI?
    lstrikes = vicon.GetEvents(name, "Left", "Foot Strike")[0]
    rstrikes = vicon.GetEvents(name, "Right", "Foot Strike")[0]
    ltoeoffs = vicon.GetEvents(name, "Left", "Foot Off")[0]
    rtoeoffs = vicon.GetEvents(name, "Right", "Foot Off")[0]
    # frame offset (start of trial data in frames)
    offset = 1
    # trial length
    rng = vicon.GetTrialRange()
    length = rng[1] - rng[0] + 1
    framerate = vicon.GetFrameRate()
    # Get analog rate. This may not be mandatory if analog devices
    # are not used, but currently it needs to succeed.
    devids = vicon.GetDeviceIDs()
    if not devids:
        raise ValueError('Cannot determine analog rate')
    else:
        devid = devids[0]
        _, _, analograte, _, _, _ = vicon.GetDeviceDetails(devid)
    samplesperframe = analograte / framerate
    # sort events (may be in wrong temporal order, at least in c3d files)
    for li in [lstrikes, rstrikes, ltoeoffs, rtoeoffs]:
        li.sort()
    return {'trialname': trialname, 'sessionpath': sessionpath,
            'offset': offset, 'framerate': framerate, 'analograte': analograte,
            'name': name, 'bodymass': bodymass, 'lstrikes': lstrikes,
            'rstrikes': rstrikes, 'ltoeoffs': ltoeoffs, 'rtoeoffs': rtoeoffs,
            'length': length, 'samplesperframe': samplesperframe}


def get_emg_data(vicon):
    """ Read EMG data from Nexus """
    emg_devname = cfg.emg_devname
    devnames = vicon.GetDeviceNames()
    if emg_devname in devnames:
        emg_id = vicon.GetDeviceIDFromName(emg_devname)
    else:
        raise ValueError('EMG device not found')
    # DType should be 'other', drate is sampling rate
    dname, dtype, drate, outputids, _, _ = vicon.GetDeviceDetails(emg_id)
    # Myon should only have 1 output; if zero, EMG was not found (?)
    if len(outputids) != 1:
        raise ValueError('Expected single EMG output')
    outputid = outputids[0]
    # get list of channel names and IDs
    _, _, _, _, elnames, chids = vicon.GetDeviceOutputDetails(emg_id, outputid)
    data = dict()
    for elid in chids:
        eldata, elready, elrate = vicon.GetDeviceChannel(emg_id, outputid,
                                                         elid)
        elname = elnames[elid-1]  # chids start from 1
        data[elname] = np.array(eldata)
    return {'t': np.arange(len(eldata)) / drate, 'data': data}


def get_forceplate_data(vicon):
    """ Read forceplate data from Nexus. Does not support multiple plates
    yet. """
    fpdevicename = 'Forceplate'
    devicenames = vicon.GetDeviceNames()
    if fpdevicename in devicenames:
        # not sure what happens to fpid if multip. plates
        fpid = vicon.GetDeviceIDFromName(fpdevicename)
    else:
        raise ValueError('Forceplate device not found')
    framerate = vicon.GetFrameRate()
    # DType should be 'ForcePlate', drate is sampling rate
    dname, dtype, drate, outputids, _, _ = vicon.GetDeviceDetails(fpid)
    samplesperframe = drate / framerate  # fp samples per Vicon frame
    # outputs should be force, moment, cop. select force
    outputid = outputids[0]
    # get list of channel names and IDs
    _, _, _, _, chnames, chids = vicon.GetDeviceOutputDetails(fpid, outputid)
    # read x,y,z forces
    chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Fx')
    fx, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Fy')
    fy, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Fz')
    fz, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, chid)
    # moments
    outputid = outputids[1]
    chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Mx')
    mx, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'My')
    my, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Mz')
    mz, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, chid)
    # read CoP
    outputid = outputids[2]
    chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Cx')
    copx, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Cy')
    copy, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, chid)
    chid = vicon.GetDeviceChannelIDFromName(fpid, outputid, 'Cz')
    copz, chready, chrate = vicon.GetDeviceChannel(fpid, outputid, chid)
    cop = np.array([copx, copy, copz]).transpose()
    fall = np.array([fx, fy, fz]).transpose()
    mall = np.array([mx, my, mz]).transpose()
    ftot = np.sqrt(np.sum(fall**2, axis=1))
    return {'fall': fall, 'mall': mall, 'ftot': ftot, 'cop': cop,
            'samplesperframe': samplesperframe, 'analograte': drate}


def get_marker_data(vicon, markers):
    """ From Nexus, get position, velocity and acceleration for
    specified markers.  """
    if not isinstance(markers, list):
        markers = [markers]
    subjectnames = vicon.GetSubjectNames()
    if not subjectnames:
        raise ValueError('No subject defined in Nexus')
    mdata = dict()
    for marker in markers:
        x, y, z, _ = vicon.GetTrajectory(subjectnames[0], marker)
        if len(x) == 0:
            raise ValueError('Cannot get marker trajectory: %s' % marker)
        mP = np.array([x, y, z]).transpose()
        mdata[marker + '_P'] = mP
        mdata[marker + '_V'] = np.gradient(mP)[0]
        mdata[marker + '_A'] = np.gradient(mdata[marker+'_V'])[0]
        # find gaps
        allzero = np.logical_and(mP[:, 0] == 0, mP[:, 1] == 0, mP[:, 2] == 0)
        mdata[marker + '_gaps'] = np.where(allzero)[0]
    return mdata


def get_roi(vicon):
    """ Return array of frames corresponding to Nexus ROI """
    roi = vicon.GetTrialRegionOfInterest()
    return np.arange(roi[0], roi[1])


def get_fp_strike_and_toeoff(vicon):
    """ Return forceplate strike and toeoff frames. """
    FP_THRESHOLD = .02  # % of maximum force
    MEDIAN_FILTER_WIDTH = 5
    ftot = get_forceplate_data(vicon)['ftot']
    # try to remove forceplate noise & spikes with median filter
    ftot = signal.medfilt(ftot, MEDIAN_FILTER_WIDTH)
    frel = ftot/ftot.max()
    # in analog frames
    # first large force increase
    fpstrike = rising_zerocross(frel - FP_THRESHOLD)[0]
    # last force decrease
    fptoeoff = falling_zerocross(frel - FP_THRESHOLD)[-1]
    return (int(np.round(fpstrike / ftot.samplesperframe)),
            int(np.round(fptoeoff / ftot.samplesperframe)))


def get_center_frame(vicon, marker):
    """ Return frame where marker crosses x axis of coordinate system
    (y = 0) """
    mrkdata = get_marker_data(vicon, marker)
    P = mrkdata[marker + '_P']
    y = P[:, 1]
    zx = np.append(rising_zerocross(y), falling_zerocross(y))
    ycross = list()
    # sanity checks
    for p in zx:
        # y must be nonzero on either side of crossing (valid data)
        if p-10 > 0 and p+10 < len(y):
            if y[p-10] != 0 and y[p+10] != 0:
                # y must change sign also around p
                if np.sign(y[p-10]) != np.sign(y[p+10]):
                        ycross.append(p)
    if len(ycross) > 1:
        print('Warning: multiple crossings detected')
        ycross = ycross[0]
    return ycross


def get_movement_direction(vicon, marker, dir):
    """ Return average direction of movement for given marker """
    dir = dir.lower()
    dir = {'x': 0, 'y': 1, 'z': 2}[dir]
    mrkdata = get_marker_data(vicon, marker)
    P = mrkdata[marker+'_P']
    ydiff = np.median(np.diff(P[:, dir]))  # median of y derivative
    return 1 if ydiff > 0 else -1


def get_model_data(vicon, model):
    """ Read model output variables (e.g. Plug-in Gait) """
    modeldata = dict()
    subjectname = vicon.GetSubjectNames()[0]
    for var in model.read_vars:
        nums, bools = vicon.GetModelOutput(subjectname, var)
        if not nums:
            raise ValueError('Cannot read model variable %s. Make sure that '
                             'the appropriate model has been run.' % var)
        # remove singleton dimensions
        modeldata[var] = np.squeeze(np.array(nums))
    return modeldata


def automark_events(vicon, vel_thresholds={'L_strike': None, 'L_toeoff': None,
                    'R_strike': None, 'R_toeoff': None}, context=None,
                    strike_frame=None,
                    events_context=(-1, 0, 1), events_nocontext=(-1, 0, 1),
                    plot=False):
    """ Mark events based on velocity thresholding. Absolute thresholds
    can be specified as arguments. Otherwise relative thresholds will be
    calculated based on the data. Optimal results will be obtained when
    thresholds based on force plate data are available.

    vel_threshold gives velocity thresholds for identifying events. These
    can be obtained from forceplate data.

    context gives forceplate context for the trial: 'R', 'L', or None.
    strike_frame is the frame where forceplate contact occurs.

    events_context specified which events to mark for the side where forceplate
    strike occurs. For example (-1, 0, 1) would mark one event before the
    strike and one event after (and the strike itself = 0).
    events_nocontext is similarly interpreted and applied for the side(s)
    where there is no valid forceplate contact.

    If plot=True, velocity curves and events are plotted.

    Before automark, run reconstruct, label and gap fill pipelines.
    """

    frate = vicon.GetFrameRate()
    if not frate:
        raise Exception('Cannot get framerate from Nexus')

    # relative thresholds (of maximum velocity)
    REL_THRESHOLD_FALL = .2
    REL_THRESHOLD_RISE = .5
    # marker data is assumed to be in mm
    # mm/frame = 1000 m/frame = 1000/frate m/s
    VEL_CONV = 1000/frate
    # reasonable limits for peak velocity (m/s before multiplier)
    MAX_PEAK_VELOCITY = 12 * VEL_CONV
    MIN_PEAK_VELOCITY = .5 * VEL_CONV
    # reasonable limits for velocity on slope (increasing/decreasing)
    MAX_SLOPE_VELOCITY = 6 * VEL_CONV
    MIN_SLOPE_VELOCITY = .05 * VEL_CONV
    # median prefilter width
    MEDIAN_WIDTH = 3
    # right feet markers
    RIGHT_FOOT_MARKERS = ['RHEE', 'RTOE', 'RANK']
    # left foot markers
    LEFT_FOOT_MARKERS = ['LHEE', 'LTOE', 'LANK']
    # tolerance between forceplate strike (parameter) and detected event
    FP_STRIKE_TOL = 7
    # marker for finding trial center frame
    TRACK_MARKER = 'LASI'

    # get subject info
    subjectnames = vicon.GetSubjectNames()
    if not subjectnames:
        raise ValueError('No subject defined in Nexus')
    subjectname = subjectnames[0]

    # get foot center velocity vectors and scalar velocities
    mrkdata = get_marker_data(vicon, RIGHT_FOOT_MARKERS+LEFT_FOOT_MARKERS)

    rfootctrV = np.zeros(mrkdata[RIGHT_FOOT_MARKERS[0]+'_V'].shape)
    for marker in RIGHT_FOOT_MARKERS:
        rfootctrV += mrkdata[marker+'_V'] / len(RIGHT_FOOT_MARKERS)
    rfootctrv = np.sqrt(np.sum(rfootctrV[:, 1:3]**2, 1))

    lfootctrV = np.zeros(mrkdata[LEFT_FOOT_MARKERS[0]+'_V'].shape)
    for marker in LEFT_FOOT_MARKERS:
        lfootctrV += mrkdata[marker+'_V'] / len(LEFT_FOOT_MARKERS)
    lfootctrv = np.sqrt(np.sum(lfootctrV[:, 1:3]**2, 1))

    strikes_all = {}
    toeoffs_all = {}

    # loop: same operations for left / right foot
    for ind, footctrv in enumerate((rfootctrv, lfootctrv)):
        this_side = 'R' if ind == 0 else 'L'
        print('automark: side ', this_side)
        # filter to scalar velocity data to suppress noise and spikes
        footctrv = signal.medfilt(footctrv, MEDIAN_WIDTH)

        # compute local maxima of velocity: derivative crosses zero, values ok
        vd = np.gradient(footctrv)
        vdz_ind = falling_zerocross(vd)
        inds = np.where(np.logical_and(footctrv[vdz_ind] > MIN_PEAK_VELOCITY,
                        footctrv[vdz_ind] < MAX_PEAK_VELOCITY))
        maxv = np.median(footctrv[vdz_ind[inds]])

        if maxv > MAX_PEAK_VELOCITY:
            raise ValueError('Velocity thresholds too high, data may be noisy')

        # compute thresholds
        threshold_fall_ = (vel_thresholds[this_side+'_strike'] or
                           maxv * REL_THRESHOLD_FALL)
        threshold_rise_ = (vel_thresholds[this_side+'_toeoff'] or
                           maxv * REL_THRESHOLD_RISE)

        print('automark: rel. thresholds: fall: %.2f rise %.2f' %
              (maxv * REL_THRESHOLD_FALL, maxv * REL_THRESHOLD_RISE))
        print('automark: using fall threshold: %s=%.2f' %
              (this_side, threshold_fall_))
        print('automark: using rise threshold: %s=%.2f' %
              (this_side, threshold_rise_))

        # find point where velocity crosses threshold
        # strikes (velocity decreases)
        cross = falling_zerocross(footctrv - threshold_fall_)
        # exclude edges of data vector
        cross = cross[np.where(np.logical_and(cross > 0,
                                              cross < (len(footctrv) - 1)))]
        cind_min = np.logical_and(footctrv[cross-1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross-1] > MIN_SLOPE_VELOCITY)
        cind_max = np.logical_and(footctrv[cross+1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross+1] > MIN_SLOPE_VELOCITY)
        strikes = cross[np.logical_and(cind_min, cind_max)]
        # toeoffs (velocity increases)
        cross = rising_zerocross(footctrv - threshold_rise_)
        cross = cross[np.where(np.logical_and(cross > 0,
                                              cross < len(footctrv)))]
        cind_min = np.logical_and(footctrv[cross-1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross-1] > MIN_SLOPE_VELOCITY)
        cind_max = np.logical_and(footctrv[cross+1] < MAX_SLOPE_VELOCITY,
                                  footctrv[cross+1] > MIN_SLOPE_VELOCITY)
        toeoffs = cross[np.logical_and(cind_min, cind_max)]

        # if fp data available, mark only events around forceplate strike
        if context and strike_frame:
            strikes_ = []
            if context == this_side:
                # find event corresponding to forceplate strike
                auto_strike_ind = np.argmin(abs(strikes - strike_frame))
                if abs(strikes[auto_strike_ind] -
                        strike_frame) > FP_STRIKE_TOL:
                    raise ValueError('Detected strike event does not match ',
                                     'strike_frame')
                # add other events as required
                for fr in events_context:
                    if 0 <= auto_strike_ind + fr <= len(strikes) - 1:
                        strikes_.append(strikes[auto_strike_ind + fr])
            else:  # opposite side
                # find the next strike following the (opposite) fp strike
                diffv = strikes - strike_frame
                nextdiff = [x for x in diffv if x > 0][0]
                closest_next_ind = np.where(diffv == nextdiff)[0][0]
                for fr in events_nocontext:
                    if 0 <= closest_next_ind + fr <= len(strikes) - 1:
                        strikes_ += [strikes[closest_next_ind + fr]]
            strikes = strikes_
        # else mark around 'center frame'
        else:
            ctr_frame = get_center_frame(vicon, TRACK_MARKER)
            if not ctr_frame:
                raise ValueError('Cannot find center frame (y crossing)')
            # strike nearest to ctr frame
            ctr_strike_ind = np.argmin(abs(strikes - ctr_frame))
            # shift event indices
            strike_inds = np.array(events_nocontext) + ctr_strike_ind
            strikes = strikes[strike_inds]

        # mark toeoffs that are between strike events
        toeoffs = [fr for fr in toeoffs
                   if any(strikes < fr) and any(strikes > fr)]
        # create the events in Nexus
        side_str = 'Right' if this_side == 'R' else 'Left'
        for fr in strikes:
                vicon.CreateAnEvent(subjectname, side_str,
                                    'Foot Strike', fr, 0.0)
        for fr in toeoffs:
                vicon.CreateAnEvent(subjectname, side_str, 'Foot Off', fr, 0.0)
        strikes_all[this_side] = strikes
        toeoffs_all[this_side] = toeoffs

        # plot velocities w/ thresholds
        if plot:
            if ind == 0:
                plt.figure()
            plt.subplot(2, 1, ind+1)
            plt.plot(footctrv, 'g', label='foot center velocity ' + this_side)
            # algorithm, fixed thresholds
            plt.plot(strikes, footctrv[strikes], 'kD', markersize=10,
                     label='strike')
            plt.plot(toeoffs, footctrv[toeoffs], 'k^', markersize=10,
                     label='toeoff')
            plt.legend(numpoints=1)
            plt.ylim(0, maxv+10)
            plt.xlabel('Frame')
            plt.ylabel('Velocity (mm/frame)')
            plt.title('Automark ' + this_side)

    return (strikes_all['R'], strikes_all['L'],
            toeoffs_all['R'], toeoffs_all['L'])
