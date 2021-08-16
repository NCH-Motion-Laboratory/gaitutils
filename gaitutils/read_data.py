# -*- coding: utf-8 -*-
"""
Wrapper methods that read from Vicon Nexus or c3d files.
The 'source' argument can be either a ViconNexus.ViconNexus instance or a c3d
filename. Returned values should be independent of source.

@author: Jussi (jnu@iki.fi)
"""

from collections import defaultdict
import numpy as np
import logging

from . import nexus, c3d
from .config import cfg


logger = logging.getLogger(__name__)


def _reader_module(source):
    """Determine the appropriate data reader module to use"""
    if nexus._is_vicon_instance(source):
        return nexus
    elif c3d._is_c3d_file(source):
        return c3d
    else:
        raise RuntimeError('Unknown type for data source %s' % source)


def get_metadata(source):
    """Get trial metadata from a source.

    Parameters
    ----------
    source : str | Path | instance of ViconNexus
        Source to read the data from. Can be a c3d file or a ViconNexus SDK object.

    Returns
    -------
    dict
        Metadata dict with the following keys and values:

        trialname : str
            Name of trial.
        eclipse_data : dict
            The Eclipse data for the trial. Keys are Eclipse fields and values are
            the corresponding data.
        sessionpath : Path
            Path to session directory.
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

        def _rewrite_ctxt(s):
            if 'Right' in s:
                s = s.replace('Right', 'R')
            if 'Left' in s:
                s = s.replace('Left', 'L')
            return s

        pars = meta['subj_params'].copy()
        meta['subj_params'] = defaultdict(lambda: None)
        meta['subj_params'].update({_rewrite_ctxt(k): v for k, v in pars.items()})
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
        The forceplate data dict with the following keys and values:
        F : ndarray
            Nx3 array with x,y,z components of the force.
        M : ndarray
            Nx3 array with x,y,z components of the moment.
        Ftot : ndarray
            Nx1 array of total force.
        CoP : ndarray
            Nx3 array of center of pressure data.
        analograte : float
            Sampling rate.
        samplesperframe : int
            Analog samples per capture frame.
    """
    return _reader_module(source)._get_forceplate_data(source)


def get_marker_data(source, markers, ignore_missing=False):
    """Get position, velocity and acceleration for given markers.

    Parameters
    ----------
    source : ViconNexus | str
        The data source. Can be a c3d filename or a ViconNexus instance.
    markers : list | str
        Marker name, or list of marker names.
    ignore_missing : bool, optional
        If True, ignore missing markers on read. Otherwise raise an exception.

    Returns
    -------
    dict
        Marker data dict. Keys are marker names and values are Nx3 ndarrays of
        x,y,z data.
    """
    return _reader_module(source)._get_marker_data(
        source,
        markers,
        ignore_missing=ignore_missing,
    )


def get_emg_data(source):
    """Read EMG data.

    Parameters
    ----------
    source : ViconNexus | str
        The data source. Can be a c3d filename or a ViconNexus instance.

    Returns
    -------
    dict
        Dict with following keys:
        t : ndarray
            Time axis in seconds.
        data : dict
            The data. Keys are channel names and values are ndarrays.
    """
    return _reader_module(source)._get_emg_data(source)


def get_analysis(source, condition='unknown'):
    """Read analysis data (e.g. time-distance vars).

    Parameters
    ----------
    source : str
        Name of a c3d file. Reads from Nexus are not supported yet.
    condition : str, optional
        The condition name for the analysis dict, by default 'unknown'.

    Returns
    -------
    dict
        A nested dict of the analysis values, keyed by variable name and
        context. The first key is the condition name.
    """
    if nexus._is_vicon_instance(source):
        raise Exception('Analysis var reads from Nexus not supported yet')
    return _reader_module(source).get_analysis(source, condition)


def get_accelerometer_data(source):
    """Read accelerometer data.

    Parameters
    ----------
    source : ViconNexus | str
        The data source. Can be a c3d filename or a ViconNexus instance.

    Returns
    -------
    dict
        Dict with following keys:
        t : ndarray
            Time axis in seconds.
        data : dict
            The data. Keys are channel names and values are ndarrays.
    """
    return _reader_module(source)._get_accelerometer_data(source)


def get_model_data(source, model):
    """Read model data (e.g. Plug-in Gait).

    Parameters
    ----------
    source : ViconNexus | str
        The data source. Can be a c3d filename or a ViconNexus instance.
    model : GaitModel
        The model to read. For available models, see models.py. For a known
        variable name, the corresponding model can be obtained by calling
        models.model_from_var(varname).

    Returns
    -------
    dict
        The model data. Keys are model variable names and values are ndarrays of
        data.
    """
    modeldata = _reader_module(source)._get_model_data(source, model)
    for var in model.read_vars:
        # convert Moment variables into SI units
        if var.find('Moment') > 0:
            modeldata[var] /= 1.0e3  # Nmm -> Nm
        # split 3D arrays into x,y,z variables
        if model.read_strategy == 'split_xyz':
            if modeldata[var].shape[0] == 3:
                modeldata[var + 'X'] = modeldata[var][0, :]
                modeldata[var + 'Y'] = modeldata[var][1, :]
                modeldata[var + 'Z'] = modeldata[var][2, :]
            else:
                raise RuntimeError('Expected a 3D array')
    # For basic Plug-in Gait, add the tibial torsion value to knee rotation.
    # This is to compensate for a weird PiG feature that offsets knee rotation
    # by tibial torsion, so that it always rotates around zero. With this fix,
    # we get the actual (anatomical) knee rotation.
    if (
        model.desc == 'Plug-in Gait lower body kinematics'
        and cfg.models.add_tibial_torsion
    ):
        params = get_metadata(source)['subj_params']
        for ctxt in 'RL':
            var_knee = ctxt + 'KneeAnglesZ'
            var_torsion = ctxt + 'TibialTorsion'
            if var_torsion in params and var_knee in modeldata:
                tibt = params[var_torsion]
                # for c3d data, need to convert radians -> degrees
                if c3d._is_c3d_file(source):
                    tibt /= np.pi / 180
                if np.abs(tibt) > 1e-2:  # do not add insignificant values
                    logger.info('adding %s tibial torsion: %g deg' % (ctxt, tibt))
                    modeldata[var_knee] += tibt
    return modeldata
