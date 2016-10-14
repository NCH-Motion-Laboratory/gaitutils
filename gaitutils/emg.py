# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Class for reading EMG

@author: Jussi (jnu@iki.fi)
"""


from __future__ import division, print_function
import numpy as np
from scipy import signal
import btk  # biomechanical toolkit for c3d reading
from gaitutils import nexus
from envutils import debug_print
import site_defs


class EMG:
    """ Read and process EMG data. """
    def __init__(self, source, emg_auto_off=True):
        self.source = source
        # default plotting scale in medians (channel-specific)
        self.yscale_medians = 1
        # order of Butterworth filter
        self.buttord = 5
        # whether to auto-find disconnected EMG channels
        self.emg_auto_off = emg_auto_off
        # normal data and logical chs
        self.define_emg_names()
        self.passband = None

    def set_filter(self, passband):
        """ Set EMG passband (in Hz). None for off. Affects get_channel. """
        self.passband = passband

    def define_emg_names(self):
        """ Defines the electrode mapping. """
        self.ch_normals = site_defs.emg_normals
        self.ch_names = site_defs.emg_names
        self.ch_labels = site_defs.emg_labels

    def is_logical_channel(self, chname):
        return chname in self.ch_names

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
        debug_print('Using linefreqs:', linefreqs)
        intvar = 0
        for f in linefreqs:
            intvar += np.var(self.filt(y, [f-power_bw/2.,
                                           f+power_bw/2.])) / power_bw
        # broadband signal
        emgvar = np.var(self.filt(y, [powerline_freq+10,
                                      powerline_freq+10+broadband_bw])) / broadband_bw
        intrel = 10*np.log10(intvar/emgvar)
        debug_print('rel. interference: ', intrel)
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



        self.t = np.arange(self.datalen)/self.sfrate
        self.map_data()
        # set scales for plotting channels. Automatic scaling logic may
        # be put here if needed
        self.yscale = {}
        for logch in self.ch_names:
            self.yscale[logch] = .5e-3
            # median scaling - beware of DC!
            # self.yscale_gc1r[elname] = yscale_medians * np.median(np.abs(self.datagc1r[elname]))
        # set flag if none of EMG channels contain data
        self.no_emg = all([type(chandata) == str and chandata == 'EMG_DISCONNECTED' for chandata in self.data.values()])

    def map_data(self):
        """ Map logical channels into physical ones. For example, the logical
        name can be  'LPer' and the physical channel 'LPer12' will be a match.
        Thus, the logical names can be shorter than the physical ones. The
        shortest matches will be found. """
        self.logical_data = {}
        for datach in self.ch_names:
                matches = [x for x in self.elnames if x.find(datach) >= 0]
                if len(matches) == 0:
                    raise GaitDataError('Cannot find a match for requested EMG channel '+datach)
                elname = min(matches, key=len)  # choose shortest matching name
                if len(matches) > 1:
                    debug_print('map_data:', matches, '->', elname)
                self.logical_data[logch] = self.data[elname]

