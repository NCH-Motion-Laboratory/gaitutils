# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 11:17:10 2016

Misc numerical utils

@author: Jussi (jnu@iki.fi)
"""

import numpy as np
from scipy.linalg import norm
from scipy.signal import medfilt
from numpy.lib.stride_tricks import as_strided


def rolling_fun_strided(m, fun, win, axis=None):
    """ Window array along given axis and apply fun() to the windowed data.
    No padding, i.e. returned array is shorter in the axis dim by (win-1) """
    if axis is None:
        m = m.flatten()
        axis = 0
    sh = m.shape
    st = m.strides
    # break up the given dim into windows, insert a new dim
    sh_ = sh[:axis] + (sh[axis] - win + 1, win) + sh[axis+1:]
    # insert a stride for the new dim, same as for the given dim
    st_ = st[:axis] + (st[axis], st[axis]) + st[axis+1:]
    # apply fun on the new dimension
    return fun(as_strided(m, sh_, st_), axis=axis+1)


def rising_zerocross(x):
    """ Return indices of rising zero crossings in sequence,
    i.e. n where x[n] >= 0 and x[n-1] < 0 """
    x = np.array(x)  # this should not hurt
    return np.where(np.logical_and(x[1:] >= 0, x[:-1] < 0))[0] + 1


def falling_zerocross(x):
    return rising_zerocross(-x)


def best_match(v, b):
    """ Replace elements of v using their closest matches in b """
    v = np.array(v)
    b = np.array(b)
    if b.size == 0:
        return v
    inds = np.abs(v[np.newaxis, :] - b[:, np.newaxis]).argmin(axis=0)
    return b[inds]


def isfloat(x):
    try:
        float(x)
        return True
    except ValueError:
        return False


def isint(x):
    try:
        int(x)
        return True
    except ValueError:
        return False


def _baseline(v):
    """ Baseline v using histogram. Subtracts the most prominent
    signal level """
    v = v.squeeze()
    if len(v.shape) != 1:
        raise ValueError('Need 1-dim input')
    v = np.array(v)
    nbins = int(len(v) / 10)  # exact n of bins should not matter
    ns, edges = np.histogram(v, bins=nbins)
    peak_ind = np.where(ns == np.max(ns))[0][0]
    return v - np.mean(edges[peak_ind:peak_ind+2])


def center_of_pressure(F, M, dz):
    """ Compute CoP according to AMTI instructions. The results differ
    slightly (few mm) from Nexus, for unknown reasons (different filter?)
    See http://health.uottawa.ca/biomech/courses/apa6903/amticalc.pdf """
    FP_FILTFUN = medfilt  # filter function
    FP_FILTW = 5  # median filter width
    fx, fy, fz = tuple(F.T)  # split columns into separate vars
    mx, my, mz = tuple(M.T)
    fz = FP_FILTFUN(fz, FP_FILTW)
    nz_inds = np.where(np.abs(fz) > 0)[0]  # only divide on nonzero inds
    cop = np.zeros((fx.shape[0], 3))
    cop[nz_inds, 0] = -(my[nz_inds] + fx[nz_inds] * dz)/fz[nz_inds]
    cop[nz_inds, 1] = (mx[nz_inds] - fy[nz_inds] * dz)/fz[nz_inds]
    return cop


def change_coords(pts, wR, wT):
    """ Translate pts (N x 3) into a new coordinate system described by
    rotation matrix wR and translation vector wT """
    pts = np.array(pts)
    return np.dot(wR, pts.T).T + wT


def segment_angles(P):
    """ Compute angles between segments defined by ordered points in P
    (N x 3 array). Can also be 3-d matrix of T x N x 3 to get time-dependent
    data. Output will be (N-2) vector or T x (N-2) matrix of angles in radians.
    If successive points are identical, nan:s will be output for the
    corresponding angles.
    """
    if P.shape[-1] != 3 or len(P.shape) not in [2, 3]:
        raise ValueError('Invalid shape of input matrix')
    if len(P.shape) == 2:
        P = P[np.newaxis, ...]  # insert singleton time axis
    Pd = np.diff(P, axis=1)  # point-to-point vectors
    vnorms = norm(Pd, axis=2)[..., np.newaxis]
    # ignore 0/0 and x/0 errors -> nan
    with np.errstate(divide='ignore', invalid='ignore'):
        Pdn = Pd / vnorms
    # take dot products between successive vectors and angles by arccos
    dots = np.sum(Pdn[:, 0:-1, :] * Pdn[:, 1:, :], axis=2)
    dots = dots[0, :] if dots.shape[0] == 1 else dots  # rm singleton dim
    return np.pi - np.arccos(dots)


def running_sum(M, win, axis=None):
    """ Running (windowed) sum of sequence M using cumulative sum,
        along given axis. Inspired by
        http://arogozhnikov.github.io/2015/09/30/NumpyTipsAndTricks2.html """
    if axis is None:
        M = M.flatten()
    s = np.cumsum(M, axis=axis)
    s = np.insert(s, 0, [0], axis=axis)
    len = s.shape[0] if axis is None else s.shape[axis]
    return (s.take(np.arange(win, len), axis=axis) -
            s.take(np.arange(0, len-win), axis=axis))


def rms(data, win):
    """ Return RMS for a given data (1-d; will be flattened if not) """
    if win % 2 != 1:
        raise ValueError('Need RMS window of odd length')
    rms = np.sqrt(running_sum(data**2, win) / float(win))
    # pad ends of RMS data so that lengths are matched
    pad = np.repeat(0, (win-1)/2)
    return np.concatenate([pad, rms, pad])
