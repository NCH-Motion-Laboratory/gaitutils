# -*- coding: utf-8 -*-
"""

Wrapper methods that read from either Vicon Nexus or c3d files.
'source' argument can be either a ViconNexus.ViconNexus instance or
a path to a c3d file.


@author: Jussi (jnu@iki.fi)

"""
from past.builtins import basestring
import os.path as op

from . import nexus, c3d


def _reader_module(source):
    """Determine the appropriate data reader module to use"""
    if nexus._is_vicon_instance(source):
        return nexus
    elif isinstance(source, basestring):
        # currently we just check c3d existence, without checking
        # headers etc.
        if op.isfile(source):
            return c3d
        else:
            raise RuntimeError('File %s does not exist' % source)
    else:
        raise RuntimeError('Unknown type for data source %s' % source)


def get_metadata(source):
    """Get trial metadata from a source.
    
    Parameters
    ----------
    source : ViconNexus | str
        The data source. Can be a c3d filename or a ViconNexus instance.
    
    Returns
    -------
    dict
        Metadata dict with the following keys and values:

        trialname : str
            Name of trial.
        eclipse_data : dict
            The Eclipse data for the trial. Keys are Eclipse fields and values are
            the corresponding data.
        sessionpath : str
            Full path to session directory.
        length : int
            Trial length in frames.
        offset : int
            Frame offset of data from beginning of trial. The event numbers will be
            interpreted relative to the offset, e.g. if the trial offset is 100 and
            an event occurs at frame 150, its index in the frame data array is 50.
        framerate : float
            Frame rate for capture (frames / sec).
        analograte : float
            Sampling rate for analog devices (samples / sec)-
        name : str
            Subject name.
        subj_params : dict
            Other subject parameters (bodymass etc.)
        events : TrialEvents
            Trial events (foot strikes, toeoffs etc.)
    """
    meta = _reader_module(source)._get_metadata(source)
    # Nexus uses slightly different metadata field names as c3d,
    # so translate here into c3d naming convention
    # XXX: c3d angle params are apparently in radians while Nexus uses degrees
    # - NOT translated here!
    if nexus._is_vicon_instance(source):
        pars = meta['subj_params']
        for par in pars.keys():
            if 'Right' in par:
                new_par = par.replace('Right', 'R')
                pars[new_par] = pars.pop(par)
            if 'Left' in par:
                new_par = par.replace('Left', 'L')
                pars[new_par] = pars.pop(par)
    return meta


def get_forceplate_data(source):
    """Get forceplate data.

    Parameters
    ----------
    source : ViconNexus | str
        The data source. Can be a c3d filename or a ViconNexus instance.

    Returns
    -------
    dict
        The forceplate data dict with the following keys:
        F: Nx3 array with force x,y,z components
        M: Nx3 array with moment x,y,z components
        Ftot: Nx1 array of total force
        CoP:  Nx3 array, center of pressure
        analograte: sampling rate
        samplesperframe: samples per capture frame
    """
    return _reader_module(source)._get_forceplate_data(source)


def get_marker_data(source, markers, ignore_edge_gaps=True, ignore_missing=False):
    """Get position, velocity and acceleration for given markers.

    Parameters
    ----------
    source : ViconNexus | str
        The data source. Can be a c3d filename or a ViconNexus instance.
    markers : list | str
        Marker name, or list of marker names.
    ignore_edge_gaps : bool, optional
        Whether leading/trailing "gaps" in data should be ignored (default) or marked as
        gaps. Nexus writes out gaps at the beginning and end of trial when
        reconstructions are unavailable.
    ignore_missing : bool, optional
        If True, ignore missing markers on read. Otherwise raise an exception.

    Returns
    -------
    dict
        Marker data dict. Keys are marker names followed by _P, _V or _A for
        position, velocity and acceleration respectively. Values are Nx3 ndarrays.
        Gaps are also returned and keyed as marker names followed by _gaps, e.g.
        'RHEE_gaps'.
    """
    return _reader_module(source)._get_marker_data(
        source,
        markers,
        ignore_edge_gaps=ignore_edge_gaps,
        ignore_missing=ignore_missing,
    )


def get_emg_data(source):
    """ Get EMG data. Returns dict with keys """
    return _reader_module(source)._get_emg_data(source)


def get_analysis(source, condition='unknown'):
    """Get analysis data"""
    if nexus._is_vicon_instance(source):
        raise Exception('Analysis var reads from Nexus not supported yet')
    return _reader_module(source).get_analysis(source, condition)


def get_accelerometer_data(source):
    """ Get accelerometer data. Returns dict with keys """
    return _reader_module(source)._get_accelerometer_data(source)


def get_model_data(source, model):
    """ Get other variables such as model outputs """
    modeldata = _reader_module(source)._get_model_data(source, model)
    for var in model.read_vars:
        # convert Moment variables into SI units
        if var.find('Moment') > 0:
            modeldata[var] /= 1.0e3  # Nmm -> Nm
        # split 3-d arrays into x,y,z variables
        if model.read_strategy == 'split_xyz':
            if modeldata[var].shape[0] == 3:
                modeldata[var + 'X'] = modeldata[var][0, :]
                modeldata[var + 'Y'] = modeldata[var][1, :]
                modeldata[var + 'Z'] = modeldata[var][2, :]
            else:
                raise RuntimeError('Expected a 3D array')
    return modeldata
