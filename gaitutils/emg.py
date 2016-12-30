# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Class for reading EMG

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division, print_function
import numpy as np
from scipy import signal
from gaitutils import read_data


class EMG(object):
    """ Class for handling EMG data. Convert logical names to physical,
    filter data, etc. Channel data can be accessed as emg[chname].
    If passband property is set, data will be bandpass filtered first.
    The ch_status property indicates whether data is OK for a given channel.
    Logical channel names are read from site defs and can be substrings of
    physical channel names read from source; e.g. logical name 'LGas' can
    be mapped to 'Voltage.LGas8'; see _map_data()
    """

    def __init__(self, source, fuzzy_names=True, emg_passband=None):
        self.source = source
        # whether to autodetect disconnected EMG channels. set before read()
        self.emg_auto_off = True
        self._fuzzy_names = fuzzy_names
        # EMG filter passband
        self.passband = emg_passband
        self._ch_status = dict()
        self._filter_coeffs = (None, None)
        self._data = None

    def __getitem__(self, chname):
        chname_ = self._map_ch_name(chname)
        if self._data is None:
            self.read()
        data = self._data[chname_]
        return self._filt(data)  # won't do anything if self.passband=None

    def __contains__(self, chname):
        try:
            self._map_ch_name(chname)
            return True
        except KeyError:
            return False

    @property
    def passband(self):
        return self._passband

    @passband.setter
    def passband(self, passband):
        self._passband = passband
        if passband is not None:  # store corresponding coefficients for filter
            self._filter_coeffs = self._get_bw_coeffs(passband)

    def get_ch_status(self, chname):
        try:
            chname_ = self._map_ch_name(chname)
        except KeyError:
            return 'NOT_FOUND'
        return self._ch_status[chname_]

    def _map_ch_name(self, name):
        matcher = ((lambda a, b: a.find(b) >= 0) if self._fuzzy_names else
                   lambda a, b: a == b)
        matches = [x for x in self._chnames if matcher(x, name)]
        if len(matches) == 0:
            raise KeyError('No such channel')
        else:
            if len(matches) > 1:
                print('warning: multiple matching channel names')
            return min(matches, key=len)  # choose shortest matching name

    def _is_valid_emg(self, y):
        """ Check whether channel contains a valid EMG signal. Usually invalid
        signal can be detected by the presence of large powerline (harmonics)
        compared to broadband signal. Cause is typically disconnected/badly
        connected electrodes. """
        emg_max_interference = 1e-8
        nharm = 3  # number of harmonics to detect
        powerline_freq = 50  # TODO: move into config
        power_bw = 2  # width of power line peak detector (bandpass)
        linefreqs = (np.arange(nharm+1)+1) * powerline_freq
        intvar = 0
        for f in linefreqs:
            pow_band = [f-power_bw/2., f+power_bw/2.]
            intvar += np.var(self._filt(y, passband=pow_band)) / power_bw
        return intvar < emg_max_interference

    def _filt(self, y, passband='default'):
        """ Filter given data y to passband, e.g. [1, 40].
        Passband is given in Hz. None for no filtering.
        Implemented as pure lowpass, if highpass freq = 0 """
        # order of Butterworth filter
        if passband is None:
            return y
        if passband == 'default':
            if self.passband is None:
                return y
            else:
                (b, a) = self._filter_coeffs
        else:
            (b, a) = self._get_bw_coeffs(passband)
        return signal.filtfilt(b, a, y)

    def _get_bw_coeffs(self, passband):
        butter_ord = 5
        passbandn = 2 * np.array(passband) / self.sfrate
        if passbandn[0] > 0:  # bandpass
            return signal.butter(butter_ord, passbandn, 'bandpass')
        else:  # lowpass
            return signal.butter(butter_ord, passbandn[1])

    def read(self):
        """ Read EMG data, assign channel names and status """
        meta = read_data.get_metadata(self.source)
        self.sfrate = meta['analograte']
        emgdi = read_data.get_emg_data(self.source)
        self.t = emgdi['t']  # time axis
        self._data = emgdi['data']
        self._chnames = self._data.keys()
        for ch in self._chnames:
            self._ch_status[ch] = ('OK' if not self.emg_auto_off or
                                   self._is_valid_emg(self[ch])
                                   else 'DISCONNECTED')
        # flag for 'no data at all'
        self.no_emg = all([st != 'OK' for st in self._ch_status.values()])
