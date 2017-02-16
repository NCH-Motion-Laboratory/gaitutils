# -*- coding: utf-8 -*-
"""

Wrapper methods that read from either Vicon Nexus or c3d files.
'source' argument can be either a ViconNexus.ViconNexus instance or
a path to a c3d file.


@author: jnu@iki.fi

"""

import nexus
import c3d


def _reader_module(source):
    """ Determine the appropriate module to use """
    if nexus.is_vicon_instance(source):
        return nexus
    elif c3d.is_c3dfile(source):
        return c3d
    else:
        raise Exception('Unknown data source')


def get_metadata(source):
    """ Get trial and subject info. Returns dict with:
    trialname: name of trial
    sessionpath: full path to directory where session is contained
    length: trial length in frames
    offset: frame offset of returned data from beginning of trial
    framerate: capture framerate
    analograte: sampling rate for analog devices
    name: subject name
    bodymass: mass of subject
    lstrikes, rstrikes: foot strike events l/r
    ltoeoffs, rtoeoffs: toeoffs l/r
    """
    return _reader_module(source).get_metadata(source)


def get_forceplate_data(source):
    """ Get forceplate data. Returns dict with:
    F: Nx3 array with force x,y,z components
    M: Nx3 array with moment x,y,z components
    Ftot: Nx1 array of total force
    CoP:  Nx3 array, center of pressure
    analograte: sampling rate
    samplesperframe: samples per capture frame
    TODO: return dict/list of dict for multiple forceplates
    """
    return _reader_module(source).get_forceplate_data(source)


def get_marker_data(source, markers):
    """ Get position, velocity and acceleration for a given marker(s)
    (str or list of str).
    Returns dict mdata keyed with marker names followed by _P, _V or _A
    (position, velocity, acceleration). Values are Nx3 matrices
    data, e.g. mdata['RHEE_V'] is a Nx3 matrix with velocity x, y and z
    components. Also computes gaps, with keys as e.g. 'RHEE_gaps'. """
    return _reader_module(source).get_marker_data(source, markers)


def get_emg_data(source):
    """ Get EMG data. Returns dict with keys """
    return _reader_module(source).get_emg_data(source)


def get_model_data(source, model):
    """ Get other variables such as model outputs """
    modeldata = _reader_module(source).get_model_data(source, model)
    for var in model.read_vars:
            # convert Moment variables into SI units
            if var.find('Moment') > 0:
                modeldata[var] /= 1.0e3  # Nmm -> Nm
            # split 3-d arrays into x,y,z variables
            if model.read_strategy == 'split_xyz':
                if modeldata[var].shape[0] == 3:
                    modeldata[var+'X'] = modeldata[var][0, :]
                    modeldata[var+'Y'] = modeldata[var][1, :]
                    modeldata[var+'Z'] = modeldata[var][2, :]
                else:
                    raise ValueError('Expected a 3D array')
    return modeldata


def kinetics_available(source):
    return _reader_module(source).kinetics_available(source)
