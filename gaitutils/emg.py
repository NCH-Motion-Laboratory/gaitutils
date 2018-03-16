# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Class for reading EMG

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division
import numpy as np
from scipy import signal
import logging

from . import read_data
from .config import cfg
from .nexus import _list_to_str


logger = logging.getLogger(__name__)


class EMG(object):
    """ Class for handling EMG data. """

    def __init__(self, source):
        logger.debug('new EMG instance from %s' % source)
        self.source = source
        # order of Butterworth filter
        self.buttord = 5
        self.passband = cfg.emg.passband
        self.linefreq = cfg.emg.linefreq
        self.data = None

    def __getitem__(self, item):
        """ Return data for a channel (filtered if self.passband is set).
        Uses name matching: if the specified channel is not found in the data,
        partial name matches are considered and data for the shortest match is
        returned. For example, 'LGas' could be mapped to 'Voltage.LGas8' """
        if item is None or len(item) < 2:
            raise KeyError('Invalid channel name')
        if self.data is None:
            self.read()
        matches = [x for x in self.data if x.find(item) >= 0]
        if len(matches) == 0:
            raise KeyError('No matching channel for %s' % item)
        else:
            ch = min(matches, key=len)  # choose shortest matching name
        if len(matches) > 1:
            logger.warning('multiple channel matches for %s: %s -> %s' %
                           (item, _list_to_str(matches), ch))
        data = self.data[ch]
        return self.filt(data, self.passband) if self.passband else data

    def is_channel(self, item):
        """ Convenience to see whether a channel exists in the data """
        try:
            self[item]
            return True
        except KeyError:
            return False

    def status_ok(self, item):
        """ Returns True for existing channel with signal ok, False
        otherwise """
        return self.is_channel(item) and self._is_valid_emg(self[item])

    def _is_valid_emg(self, y):
        """ Check whether channel contains a valid EMG signal. Usually invalid
        signal can be identified by the presence of large powerline (harmonics)
        compared to broadband signal. Cause is typically disconnected/badly
        connected electrodes.
        TODO: should use multiple-zero IIR notch filter """
        # max. relative interference at 50 Hz harmonics
        emg_max_interference = 20  # maximum relative interference level (dB)
        # bandwidth of broadband signal. should be less than dist between
        # the powerline harmonics
        broadband_bw = 30
        power_bw = 4  # width of power line peak detector (bandpass)
        nharm = 3  # number of harmonics to detect
        # detect 50 Hz harmonics
        linefreqs = (np.arange(nharm+1)+1) * self.linefreq
        intvar = 0
        for f in linefreqs:
            intvar += np.var(self.filt(y, [f-power_bw/2.,
                                           f+power_bw/2.])) / power_bw
        # broadband signal
        band = [self.linefreq+10, self.linefreq+10+broadband_bw]
        emgvar = np.var(self.filt(y, band)) / broadband_bw
        intrel = 10*np.log10(intvar/emgvar)
        return intrel < emg_max_interference

    def filt(self, y, passband):
        """ Filter given data y to passband, e.g. [1, 40].
        Passband is given in Hz. None for no filtering.
        Implemented as pure lowpass, if highpass freq = 0 """
        if passband is None:
            return y
        passbandn = 2 * np.array(passband) / self.sfrate
        if max(passbandn) > 1:
            raise ValueError('Lowpass frequency is above Nyquist frequency')
        if passbandn[0] > 0:  # bandpass
            b, a = signal.butter(self.buttord, passbandn, 'bandpass')
        else:  # lowpass
            b, a = signal.butter(self.buttord, passbandn[1])
        yfilt = signal.filtfilt(b, a, y)
        # yfilt = yfilt - signal.medfilt(yfilt, 21)
        return yfilt

    def read(self):
        meta = read_data.get_metadata(self.source)
        logger.debug('Reading EMG from %s' % meta['trialname'])
        self.sfrate = meta['analograte']
        emgdi = read_data.get_emg_data(self.source)
        self.data = emgdi['data']
        self.t = emgdi['t']
