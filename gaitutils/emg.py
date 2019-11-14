# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Class for reading EMG

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division
from builtins import object
import numpy as np
from scipy import signal
import logging

from . import read_data, cfg, numutils

logger = logging.getLogger(__name__)


class EMG(object):
    """ Class for handling EMG data. """

    def __init__(self, source, correction_factor=1):
        logger.debug('new EMG instance from %s' % source)
        self.source = source
        # order of Butterworth filter
        self.buttord = 5
        self.passband = cfg.emg.passband
        self.linefreq = cfg.emg.linefreq
        self.data = None
        self.correction_factor = correction_factor

    def _match_name(self, chname):
        if not (isinstance(chname, basestring) and len(chname)) >= 2:
            raise ValueError('invalid channel name: %s' % chname)
        matches = [x for x in self.data if x.find(chname) >= 0]
        if len(matches) == 0:
            raise KeyError('No matching channel for %s' % chname)
        else:
            ch = min(matches, key=len)  # choose shortest matching name
        if len(matches) > 1:
            logger.warning(
                'multiple channel matches for %s: %s -> %s' % (chname, matches, ch)
            )
        return ch

    def __getitem__(self, item):
        """ Return data for a channel (filtered if self.passband is set).
        Uses name matching: if the specified channel is not found in the data,
        partial name matches are considered and data for the shortest match is
        returned. For example, 'LGas' could be mapped to 'Voltage.LGas8' """
        if self.data is None:
            self.read()
        ch = self._match_name(item)
        data = self.data[ch]
        data_ = self.filt(data, self.passband) if self.passband else data
        data_ *= self.correction_factor
        return data_

    def get_rms_data(self, chname):
        """Return RMS data for given channel."""
        chdata = self[chname]
        return numutils.rms(chdata, cfg.emg.rms_win)

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

    @staticmethod
    def context_ok(ch, context):
        """Check if channel context matches given context. Returns True if
        channel does not have a context"""
        if (
            ch in cfg.emg.channel_context
            and context.upper() != cfg.emg.channel_context[ch].upper()
        ):
            return False
        return True

    def _is_valid_emg(self, y):
        """ Check whether channel contains a valid EMG signal. Usually, an invalid
        signal can be identified by the presence of large powerline (harmonics)
        compared to broadband signal. Cause is typically disconnected or badly
        connected electrodes.
        TODO: should use multiple-zero IIR notch filter """
        # bandwidth of broadband signal. should be less than dist between
        # the powerline harmonics
        broadband_bw = 30
        power_bw = 4  # width of power line peak detector (bandpass)
        nharm = 3  # number of harmonics to detect
        # detect the 50 Hz harmonics
        linefreqs = (np.arange(nharm + 1) + 1) * self.linefreq
        intvar = 0
        for f in linefreqs:
            intvar += (
                np.var(self.filt(y, [f - power_bw / 2.0, f + power_bw / 2.0]))
                / power_bw
            )
        # broadband signal
        band = [self.linefreq + 10, self.linefreq + 10 + broadband_bw]
        emgvar = np.var(self.filt(y, band)) / broadband_bw
        intrel = 10 * np.log10(intvar / emgvar)
        return intrel < cfg.emg.max_interference

    def filt(self, y, passband):
        """ Filter given data y to passband, e.g. [1, 40].
        Passband is given in Hz. None for no filtering.
        Implemented as pure lowpass, if highpass freq = 0 """
        if passband is None:
            return y
        passbandn = 2 * np.array(passband) / self.sfrate
        if passbandn[0] > 0:  # bandpass
            b, a = signal.butter(self.buttord, passbandn, 'bandpass')
        else:  # lowpass
            b, a = signal.butter(self.buttord, passbandn[1])
        return signal.filtfilt(b, a, y)

    def read(self):
        """Actually read the EMG data from source"""
        meta = read_data.get_metadata(self.source)
        logger.debug('reading EMG from %s' % meta['trialname'])
        self.sfrate = meta['analograte']
        emgdi = read_data.get_emg_data(self.source)
        self.data = emgdi['data']
        self.t = emgdi['t']


class AvgEMG(EMG):
    """Class for storing averaged RMS EMG. This differs from the EMG class in following
    ways:
    -RMS data is stored in self.data
    -only the RMS data can be returned (via the rms method)
    """

    def __init__(self, data):
        self.data = data

    def __getitem__(self, item):
        raise RuntimeError('AvgTrial can only return RMS data')

    def rms(self, chname):
        chname = self._match_name(chname)
        data = self.data[chname]
        return numutils.rms(data, cfg.emg.rms_win)

    def _is_valid_emg(self, y):
        return True

    def filt(self, y, passband):
        raise RuntimeError('filtering not implemented for averaged EMG')

    def read(self):
        raise RuntimeError('read not implemented for averaged EMG')
