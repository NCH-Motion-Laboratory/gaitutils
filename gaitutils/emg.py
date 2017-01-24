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
from envutils import debug_print
from config import Config


cfg = Config()


class EMG(object):
    """ Class for handling EMG data. Convert logical names to physical,
    filter data, etc. Channel data can be accessed as emg[chname].
    If passband property is set, data will be bandpass filtered first.
    The ch_status property indicates whether data is OK for a given channel.
    Logical channel names are read from site defs and can be substrings of
    physical channel names read from source; e.g. logical name 'LGas' can
    be mapped to 'Voltage.LGas8'; see map_data()
    """

    def __init__(self, source):
        self.source = source
        # default plotting scale in medians (channel-specific)
        self.yscale_medians = 1
        # order of Butterworth filter
        self.buttord = 5
        # EMG passband
        self.passband = cfg.emg_passband
        # whether to autodetect disconnected EMG channels. set before read()
        self.emg_auto_off = True
        self.ch_normals = cfg.emg_normals  # EMG normal data
        self.ch_names = cfg.emg_names  # EMG logical channel names
        self.ch_labels = cfg.emg_labels  # descriptive labels

    def __getitem__(self, item):
        if item not in self.ch_names:
            raise KeyError('No such channel')
        data_ = self._logical_data[item]
        if self.passband:
            return self.filt(data_, self.passband)
        else:
            return data_

    def is_valid_emg(self, y):
        """ Check whether channel contains a valid EMG signal. Usually invalid
        signal can be identified by the presence of large powerline (harmonics)
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
            intvar += np.var(self.filt(y, [f-power_bw/2.,
                                           f+power_bw/2.])) / power_bw
        # broadband signal
        emgvar = np.var(self.filt(y, [powerline_freq+10,
                                      powerline_freq+10+broadband_bw])) / broadband_bw
        intrel = 10*np.log10(intvar/emgvar)
        # debug_print('rel. interference: ', intrel)
        return intrel < emg_max_interference

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
        yfilt = signal.filtfilt(b, a, y)
        # yfilt = yfilt - signal.medfilt(yfilt, 21)
        return yfilt

    def read(self):
        meta = read_data.get_metadata(self.source)
        self.sfrate = meta['analograte']
        emgdi = read_data.get_emg_data(self.source)
        self.data = emgdi['data']
        self.t = emgdi['t']
        self.elnames = self.data.keys()
        # map channel names
        self.map_chs()
        # check for invalid channels
        if self.emg_auto_off:
            for chname, data in self._logical_data.items():
                if not self.is_valid_emg(data):
                    self.ch_status[chname] = 'DISCONNECTED'
                else:
                    self.ch_status[chname] = 'OK'
        # set scales for plotting channels
        self.yscale = {}
        for logch in self.ch_names:
            self.yscale[logch] = cfg.emg_yscale  # set a constant scale
        # set flag if none of EMG channels contain data
        self.no_emg = all([isinstance(chandata, str) and
                           chandata == 'EMG_DISCONNECTED' for chandata in
                           self.data.values()])

    def map_chs(self):
        """ Map logical channels into physical ones. For example, the logical
        name can be  'LPer' and the physical channel 'Voltage.LPer12' will be
        a match. The shortest matching physical channel will be used. """
        self._logical_data = dict()
        self.ch_status = dict()
        for datach in self.ch_names:
            matches = [x for x in self.elnames if x.find(datach) >= 0]
            if len(matches) > 0:
                elname = min(matches, key=len)  # choose shortest matching name
                if len(matches) > 1:
                    debug_print('map_data:', matches, '->', elname)
                self._logical_data[datach] = self.data[elname]
