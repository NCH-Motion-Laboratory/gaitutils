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

    def __init__(self, source, ch_names, fuzzy_names=True, emg_passband=None):
        self.source = source
        # whether to autodetect disconnected EMG channels. set before read()
        self.emg_auto_off = True
        self._fuzzy_names = fuzzy_names
        # EMG filter passband
        self.passband = emg_passband
        self.ch_names = ch_names  # EMG logical channel names
        self.ch_status = dict()
        self._data = None

    def __getitem__(self, item):
        if item not in self.ch_names:
            raise KeyError('No such channel')
        if self._data is None:
            self.read()
        data_ = self._data[item]
        return self._filt(data_, self.passband) if self.passband else data_

    def _is_valid_emg(self, y):
        """ Check whether channel contains a valid EMG signal. Usually invalid
        signal can be detected by the presence of large powerline (harmonics)
        compared to broadband signal. Cause is typically disconnected/badly
        connected electrodes. """
        # max. relative interference at 50 Hz harmonics
        emg_max_interference = 30  # maximum relative interference level (dB)
        # bandwidth of broadband signal. should be less than dist between
        # the powerline harmonics
        broadband_bw = 30
        powerline_freq = 50  # TODO: move into config
        power_bw = 4  # width of power line peak detector (bandpass)
        nharm = 3  # number of harmonics to detect
        # detect 50 Hz harmonics
        linefreqs = (np.arange(nharm+1)+1) * powerline_freq
        intvar = 0
        for f in linefreqs:
            pow_band = [f-power_bw/2., f+power_bw/2.]
            intvar += np.var(self._filt(y, pow_band)) / power_bw
        # broadband signal
        br_band = [powerline_freq+10, powerline_freq+10+broadband_bw]
        emgvar = np.var(self._filt(y, br_band)) / broadband_bw
        intrel = 10 * np.log10(intvar/emgvar)
        return intrel < emg_max_interference

    def _filt(self, y, passband):
        """ Filter given data y to passband, e.g. [1, 40].
        Passband is given in Hz. None for no filtering.
        Implemented as pure lowpass, if highpass freq = 0 """
        # order of Butterworth filter
        butter_ord = 5
        if passband is None:
            return y
        passbandn = 2 * np.array(passband) / self.sfrate
        if passbandn[0] > 0:  # bandpass
            b, a = signal.butter(butter_ord, passbandn, 'bandpass')
        else:  # lowpass
            b, a = signal.butter(butter_ord, passbandn[1])
        return signal.filtfilt(b, a, y)

    def read(self):
        """ Read EMG data, assign channel names and status """
        meta = read_data.get_metadata(self.source)
        self.sfrate = meta['analograte']
        emgdi = read_data.get_emg_data(self.source)
        self.t = emgdi['t']  # time axis
        _data = emgdi['data']
        self._elnames = _data.keys()
        # update channel names and status
        self._data = dict()
        for ch in self.ch_names:
            matcher = ((lambda a, b: a.find(b) >= 0) if self._fuzzy_names else
                       lambda a, b: a == b)
            matches = [x for x in self._elnames if matcher(x, ch)]
            if len(matches) == 0:  # no matching channels found
                self._data[ch] = None
                self.ch_status[ch] = 'NOT_FOUND'
            else:
                if len(matches) > 1:
                    print('warning: multiple matching EMG channel names')
                elname = min(matches, key=len)  # choose shortest matching name
                self._data[ch] = _data[elname]
                self.ch_status[ch] = ('OK' if not self.emg_auto_off or
                                      self._is_valid_emg(self._data[ch])
                                      else 'DISCONNECTED')
        # flag for 'no data at all'
        self.no_emg = all([st != 'OK' for st in self.ch_status.values()])
