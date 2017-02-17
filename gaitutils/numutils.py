# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 11:17:10 2016

Misc numerical utils

@author: jnu@iki.fi
"""

import numpy as np
from scipy.signal import medfilt


def rising_zerocross(x):
    """ Return indices of rising zero crossings in sequence,
    i.e. n where x[n] >= 0 and x[n-1] < 0 """
    x = np.array(x)  # this should not hurt
    return np.where(np.logical_and(x[1:] >= 0, x[:-1] < 0))[0] + 1


def falling_zerocross(x):
    return rising_zerocross(-x)


def isfloat(x):
    try:
        float(x)
        return True
    except ValueError:
        return False


def _baseline(data):
    """ Baseline data using histogram. Subtracts the most prominent
    signal level """
    data = np.array(data)
    nbins = int(len(data) / 10)  # exact n of bins should not matter
    ns, edges = np.histogram(data, bins=nbins)
    peak_ind = np.where(ns == np.max(ns))[0][0]
    return data - np.mean(edges[peak_ind:peak_ind+2])


def cop(F, M):
    """ Compute CoP according to AMTI instructions. The results differ
    slightly (few mm) from Nexus, for unknown reasons (different filter?)
    See http://health.uottawa.ca/biomech/courses/apa6903/amticalc.pdf """
    # suppress noise by medfilt; not sure what Nexus uses
    FP_DZ = 41.3  # forceplate thickness in mm
    # CoP calculation uses filter
    FP_FILTFUN = medfilt  # filter function
    FP_FILTW = 3  # median filter width
    fx, fy, fz = tuple(F.T)
    mx, my, mz = tuple(M.T)
    fz = FP_FILTFUN(fz, FP_FILTW)
    fz_0_ind = np.where(fz == 0)
    copx = (my + fx * FP_DZ)/fz
    copy = (mx - fy * FP_DZ)/fz
    copx[fz_0_ind] = 0
    copy[fz_0_ind] = 0
    copz = np.zeros(copx.shape)
    return np.array([copx, copy, copz]).T
