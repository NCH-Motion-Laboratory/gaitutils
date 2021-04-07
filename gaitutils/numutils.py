# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 11:17:10 2016

Misc numerical utils

@author: Jussi (jnu@iki.fi)
"""


import logging
import numpy as np
import hashlib
from scipy import signal
from scipy.signal import medfilt
from scipy.special import erfcinv

from .config import cfg


logger = logging.getLogger(__name__)


def kabsch_rotation(P, Q):
    """Calculate a rotation matrix P->Q using the Kabsch algorithm."""
    H = np.dot(P.T, Q)
    U, S, V = np.linalg.svd(H)
    E = np.eye(3)
    E[2, 2] = np.sign(np.linalg.det(np.dot(V.T, U.T)))
    return np.dot(np.dot(V.T, E), U.T)


def _rotation_matrix(yaw, pitch, roll):
    """Rotation matrix from yaw, pitch, roll in degrees"""
    yaw, pitch, roll = np.array([yaw, pitch, roll]) / 180 * np.pi
    cos, sin = np.cos, np.sin
    r1 = [
        cos(yaw) * cos(pitch),
        cos(yaw) * sin(pitch) * sin(roll) - sin(yaw) * cos(roll),
        cos(yaw) * sin(pitch) * cos(roll) + sin(yaw) * sin(roll),
    ]
    r2 = [
        sin(yaw) * cos(pitch),
        sin(yaw) * sin(pitch) * sin(roll) + cos(yaw) * cos(roll),
        sin(yaw) * sin(pitch) * cos(roll) - cos(yaw) * sin(roll),
    ]
    r3 = [-sin(pitch), cos(pitch) * sin(roll), cos(pitch) * cos(roll)]
    return np.array([r1, r2, r3])


def _rigid_body_extrapolate_markers(P0, Pr):
    """Extrapolate some markers in a rigid set.
    P0 (N x 3), the marker positions in the static frame.
    Pr (M x 3), the marker positions in where extrapolation is needed.
    N-M markers will be extrapolated.

    Algorithm:
    -find R and t that take us from Pr0 to Pr, by Kabsch algorithm (Pr0 is the
    reference markers in P0)
    -apply R and t to P0 to get the extrapolated positions
    """
    nref = Pr.shape[0]
    if P0.shape <= nref:
        raise ValueError('1st dim of P0 needs to be larger than 1st dim of Pr')
    Pr0 = P0[:nref, :]  # reference markers
    # find rotation and translation that take the static reference position to the
    # position where extrapolation is needed
    trans0 = Pr0.mean(axis=0)
    Pr0_ = Pr0 - trans0
    P0_ = P0 - trans0
    trans1 = Pr.mean(axis=0)
    Pr_ = Pr - trans1
    R = kabsch_rotation(Pr0_, Pr_)
    # apply the transformation to the markers to be extrapolated
    return np.dot(R, P0_[nref:, :].T).T + trans1


def mad(data, axis=None, scale=1.4826, keepdims=False):
    """Median absolute deviation (MAD).

    Defined as the median absolute deviation from the median of the data. A
    robust alternative to stddev. Results should be identical to
    scipy.stats.median_absolute_deviation(), which does not take a keepdims
    argument.

    Parameters
    ----------
    data : array_like
        The data.
    scale : float, optional
        Scaling of the result. By default, it is scaled to give a consistent
        estimate of the standard deviation of values from a normal
        distribution.
    axis : numpy axis spec, optional
        Axis or axes along which to compute MAD.
    keepdims : bool, optional
        If this is set to True, the axes which are reduced are left in the
        result as dimensions with size one.

    Returns
    -------
    ndarray
        The MAD.
    """
    # keep dims here so that broadcasting works
    med = np.median(data, axis=axis, keepdims=True)
    abs_devs = np.abs(data - med)
    return scale * np.median(abs_devs, axis=axis, keepdims=keepdims)


def modified_zscore(data, axis=None, single_mad=None):
    """Modified Z-score.

    Z-score analogue computed using robust (median-based) statistics.

    Parameters
    ----------
    data : array_like
        The data
    axis : numpy axis spec, optional
        Axis or axes along which to compute the statistic.
    single_mad : bool, optional
        Use a single MAD estimate computed all over the data. If False, MAD
        will be computed along given axis (e.g. separately for each variable).

    Returns
    -------
    ndarray
        The modified Z-score.
    """
    med_ = np.median(data, axis=axis, keepdims=True)
    mad_ = mad(data, axis=axis, keepdims=True)
    if single_mad:
        mad_ = np.median(mad_)
    return (data - med_) / mad_


def outliers(x, axis=0, single_mad=None, p_threshold=1e-3):
    """Robustly detect outliers assuming a normal distribution.

    A modified Z-score is first computed based on the data. Then a threshold
    value Zlim is computed from p_threshold, and values that exceed Zlim are
    rejected. p_threshold is the probability of rejection assuming strictly
    normally distributed data, i.e. probability for "false outlier"

    Parameters
    ----------
    data : array_like
        The data.
    axis : numpy axis spec, optional
        Axis or axes along which to compute the Z scores. E.g. axis=0
        computes row-wise Z scores and rejects based on those.
    single_mad : bool
        Use a single MAD estimate computed all over the data. If False, the MAD
        will be computed along given axis (e.g. separately for each variable).
    p_threshold : float
        The P threshold for rejection.

    Returns
    -------
    tuple
        Indexes of rejected values (np.where output)
    """
    zs = modified_zscore(x, axis=axis, single_mad=single_mad)
    z_threshold = np.sqrt(2) * erfcinv(p_threshold)
    logger.debug('Z threshold: %.2f' % z_threshold)
    return np.where(abs(zs) > z_threshold)


def _files_digest(files):
    """Create overall md5 digest for a sequence of files (filenames)"""
    hashes = sorted(_file_digest(fn) for fn in files)
    # concat as unicode and encode to get a well defined byte representation in
    # both py2 and py3
    hash_str = u''.join(hashes).encode('utf-8')
    return hashlib.md5(hash_str).hexdigest()


def _file_digest(fn):
    """Return md5 digest for file"""
    with open(fn, 'rb') as f:
        data = f.read()
    return hashlib.md5(data).hexdigest()


def rising_zerocross(x):
    """Find indices of rising zero crossings in array.

    The indices are defined as n for which x[n] >= 0 and x[n-1] < 0.

    Parameters
    ----------
    x : array_like
        The data.

    Returns
    -------
    tuple
        The indices (np.where output)
    """
    x = np.array(x)  # we can also handle lists etc.
    return np.where(np.logical_and(x[1:] >= 0, x[:-1] < 0))[0] + 1


def falling_zerocross(x):
    """Find indices of falling zero crossings in array.

    The indices are defined as n for which x[n] <= 0 and x[n-1] > 0.

    Parameters
    ----------
    x : array_like
        The data.

    Returns
    -------
    tuple
        The indices (np.where output)
    """
    return rising_zerocross(-x)


def digitize_array(v, b):
    """Replace all elements of v with their closest matches in b.

    Uses abs(x-y) as the distance metric. This function is similar to
    np.digitize(), but simpler in usage and implementation.

    Parameters
    ----------
    v : array_like
        Array to make replacements in.
    b : array_like
        Array to pick replacements from.

    Returns
    -------
    ndarray
        The result.
    """
    v = np.array(v)
    b = np.array(b)
    if b.size == 0:
        return v
    inds = np.abs(v[np.newaxis, :] - b[:, np.newaxis]).argmin(axis=0)
    return b[inds]


def _isfloat(x):
    """Test for float-conversible value"""
    try:
        float(x)
        return True
    except ValueError:
        return False


def _is_ascii(s):
    """Check for ASCII string"""
    return all(ord(c) < 128 for c in s)


def _isint(x):
    """Test for int-conversible value"""
    try:
        int(x)
        return True
    except ValueError:
        return False


def _baseline(v):
    """Baseline v using histogram.

    Subtracts the most prominent signal level.
    """
    v = np.array(v)
    v = v.squeeze()
    if len(v.shape) != 1:
        raise ValueError('Need 1-dim input')
    nbins = max(int(len(v) / 10), 1000)  # exact n of bins should not matter
    ns, edges = np.histogram(v, bins=nbins)
    peak_ind = np.where(ns == np.max(ns))[0][0]
    return v - np.mean(edges[peak_ind : peak_ind + 2])


def center_of_pressure(F, M, dz):
    """Compute center of pressure from forceplate data.

    Computes CoP according to AMTI formula. The results differ slightly
    (typically few mm) from those given by Nexus, for unknown reasons (different
    filter?) See http://health.uottawa.ca/biomech/courses/apa6903/amticalc.pdf

    Parameters
    ----------
    F : ndarray
        The force vector (Nx3). N is the number of observations.
    M : ndarray
        The moment vector (Nx3)
    dz : float
        The thickness of the plate, or the distance from moment origin to physical origin.

    Returns
    -------
    ndarray
        The center of pressure (Nx3)
    """
    FP_FILTFUN = medfilt  # the filter function
    FP_FILTW = 5  # median filter width
    fx, fy, fz = tuple(F.T)  # split columns into separate vars
    mx, my, _ = tuple(M.T)
    fz = FP_FILTFUN(fz, FP_FILTW)
    nz_inds = np.where(np.abs(fz) > 0)[0]  # only divide on nonzero inds
    cop = np.zeros((fx.shape[0], 3))
    cop[nz_inds, 0] = -(my[nz_inds] + fx[nz_inds] * dz) / fz[nz_inds]
    cop[nz_inds, 1] = (mx[nz_inds] - fy[nz_inds] * dz) / fz[nz_inds]
    return cop


def _change_coords(pts, wR, wT):
    """Translate pts (Nx3) into a new coordinate system described by
    rotation matrix wR and translation vector wT"""
    pts = np.array(pts)
    return np.dot(wR, pts.T).T + wT


def _segment_angles(P):
    """Compute angles between line segments.

    The segments are defined by ordered points in P (Nx3 array). For N points,
    there will be N-1 segments and N-2 angles between those. It can also be 3-d
    matrix of (TxNx3) to get time-dependent data. Output will be (N-2) vector or
    Tx(N-2) matrix of angles in radians. If successive points are identical,
    nan:s will be output for the corresponding angles.
    """
    if P.shape[-1] != 3 or len(P.shape) not in [2, 3]:
        raise ValueError('Invalid shape of input matrix')
    if len(P.shape) == 2:
        P = P[np.newaxis, ...]  # insert singleton time axis
    Pd = np.diff(P, axis=1)  # point-to-point vectors
    vnorms = np.linalg.norm(Pd, axis=2)[..., np.newaxis]
    # ignore 0/0 and x/0 errors -> nan
    with np.errstate(divide='ignore', invalid='ignore'):
        Pdn = Pd / vnorms
    # take dot products between successive vectors and angles by arccos
    dots = np.sum(Pdn[:, 0:-1, :] * Pdn[:, 1:, :], axis=2)
    dots = dots[0, :] if dots.shape[0] == 1 else dots  # rm singleton dim
    return np.pi - np.arccos(dots)


def _running_sum(M, win, axis=None):
    """Calculate running sum for given window length.

    M is the data (ndarray) and sum will be along given axis. win is the window
    length. Uses cumulative sum, inspired by:
    http://arogozhnikov.github.io/2015/09/30/NumpyTipsAndTricks2.html"""
    if axis is None:
        M = M.flatten()
    s = np.cumsum(M, axis=axis)
    s = np.insert(s, 0, [0], axis=axis)
    len_ = s.shape[0] if axis is None else s.shape[axis]
    return s.take(np.arange(win, len_), axis=axis) - s.take(
        np.arange(0, len_ - win), axis=axis
    )


def rms(data, win, axis=None, pad_mode=None):
    """Calculate rolling window RMS.

    Parameters
    ----------
    data : ndarray
        The data.
    win : int
        Window length.
    axis : numpy axis spec, optional
        Axis along which to compute rms.
    pad_mode : str or function, optional
        Padding mode. See np.pad for details.

    Returns
    -------
    ndarray
        The rms data.
    """
    if pad_mode is None:
        pad_mode = 'edge'
    if win % 2 != 1:
        raise ValueError('Need RMS window of odd length')
    datalen = len(data) if axis is None else data.shape[axis]
    if win > datalen:
        raise ValueError('Need win length < data length')
    rms_ = np.sqrt(_running_sum(data ** 2, win, axis=axis) / win)
    # pad RMS data so that lengths are matched
    padw = int((win - 1) / 2)
    padarg_axis = (padw, padw)
    if axis == None:
        eff_dim = 1
        axis = 0
    else:
        eff_dim = data.ndim
    padarg = eff_dim * [(0, 0)]
    padarg[axis] = padarg_axis
    return np.pad(rms_, padarg, mode=pad_mode)


def envelope(data, sfrate=None, axis=None):
    """Calculate an envelope for data using the configured method"""
    if cfg.emg.envelope_method == 'linear_envelope':
        if sfrate is None:
            raise RuntimeError('Linear envelope requires the sampling rate')
        data = _linear_envelope(data, sfrate, axis=axis)
    elif cfg.emg.envelope_method == 'rms':
        data = rms(data, cfg.emg.rms_win, axis=axis)
    else:
        raise RuntimeError('Invalid envelope method: %s' % cfg.emg.envelope_method)
    return data


def _linear_envelope(data, sfrate, axis=None):
    """Calculate a linear envelope"""
    data_rect = np.abs(data)
    return _filtfilt(data_rect, [0, cfg.emg.linear_envelope_lowpass], sfrate, axis=axis)


def _filtfilt(data, passband, sfrate, buttord=5, axis=None):
    """Forward-backward filter.
    Filter data into given passband, e.g. [1, 40].
    Frequencies are given in Hz along with sfrate (sampling rate).
    Implemented as pure lowpass, if highpass freq = 0.
    """
    if axis is None:
        axis = -1  # filtfilt() default
    if passband is None:
        return data
    passbandn = 2 * np.array(passband) / sfrate
    if passbandn[0] > 0:  # bandpass
        b, a = signal.butter(buttord, passbandn, 'bandpass')
    else:  # lowpass
        b, a = signal.butter(buttord, passbandn[1])
    return signal.filtfilt(b, a, data, axis=axis)


def _get_local_max(data):
    """Get local maximum (peak) of 1-D data"""
    # the simpler argrelextrema() would not return flat peaks, which might occur
    # at least in theory
    peak_inds = signal.find_peaks(data)[0]
    if not any(peak_inds):
        return (np.nan, np.nan)
    peak_ind = peak_inds[data[peak_inds].argmax()]
    peak_val = data[peak_ind]
    return peak_ind, peak_val


def _get_local_min(data):
    """Get local minimum  (peak) of 1-D data"""
    ind, val = _get_local_max(-data)
    if ind is np.nan:
        return np.nan, np.nan
    else:
        return ind, -val
