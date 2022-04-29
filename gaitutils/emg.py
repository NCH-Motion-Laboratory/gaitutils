# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 14:41:31 2015

Class for handling EMG data.

@author: Jussi (jnu@iki.fi)
"""

import numpy as np
import logging

from . import read_data, numutils
from .config import cfg

logger = logging.getLogger(__name__)


class EMG:
    """Class for processing and storing EMG data.

    Parameters
    ----------
    source : ViconNexus | str
        The data source. Can be a c3d filename or a ViconNexus instance.
    correction_factor : int, optional
        After read, the EMG data is multiplied by this factor.
    """

    def __init__(self, source, correction_factor=1, chs_disabled=None):
        logger.debug(f'new EMG instance from {source}')
        self.source = source
        self.passband = cfg.emg.passband
        self._data = None
        self.t = None
        self.sfrate = None
        self.correction_factor = correction_factor
        self.chs_disabled = chs_disabled
        if self.chs_disabled is None:
            self.chs_disabled = list()

    @property
    def data(self):
        """Get the EMG data.

        The data is cached in an instance variable, so it's read only once
        during the lifetime of the instance.

        Returns
        -------
        dict
            The EMG data, keyed by channel name. Values are shape (N,) ndarrays
            of sample values.
        """
        if self._data is None:
            self._read_data()
        return self._data

    def _read_data(self):
        """Actually read the EMG data from source"""
        meta = read_data.get_metadata(self.source)
        logger.debug(f"reading EMG from {meta['trialname']}")
        self.sfrate = meta['analograte']
        emgdi = read_data.get_emg_data(self.source)
        self._data = emgdi['data']
        self.t = emgdi['t']

    def _edf_export(self, filename):
        """Export the EMG data to EDF format.

        Dumps raw (unfiltered) data from all physical channels to the given EDF
        file. Format is currently set to EDF plus. Uses pyedflib as a soft dependency.

        Parameters
        ----------
        filename : str
            Name of EDF file to write.

        """
        try:
            import pyedflib
        except ImportError:
            raise RuntimeError(
                'You need to install the pyedflib package to use this function'
            )
        # default to EDF+ for the time being
        file_type = pyedflib.FILETYPE_EDFPLUS
        f = pyedflib.EdfWriter(
            filename,
            len(self.data),
            file_type=file_type,
        )
        channel_info = list()
        data_list = list()
        for chname, chdata in self.data.items():
            # scale signals to more typical EMG unit of mV
            chdata_scaled = chdata * 1e3
            # strip Voltage. prefix that Nexus inserts
            if chname.find('Voltage.') == 0:
                chname = chname[8:]
            # try to conform with the EDF channel label standard
            chname = f'EMG {chname}'
            # EDF stores data as 16 bit ints
            # since ranges can be set per-channel, we map individual
            # range of each signal into the 16-bit digital scale
            nbits = 16
            ch_dict = {
                'label': chname,
                'dimension': 'mV',
                'sample_rate': self.sfrate,
                'physical_max': max(chdata_scaled),
                'physical_min': min(chdata_scaled),
                'digital_max': 2 ** (nbits - 1) - 1,
                'digital_min': -(2 ** (nbits - 1)),
                'transducer': 'EMG',
                'prefilter': '',
            }
            channel_info.append(ch_dict)
            data_list.append(chdata_scaled)
        f.setSignalHeaders(channel_info)
        f.writeSamples(data_list)
        f.close()

    def _match_name(self, chname):
        """Fuzzily match channel name"""
        if not isinstance(chname, str):
            raise ValueError(f'invalid channel name: {chname}')
        if len(chname) < 3:
            logger.warning('Use of very short EMG channel names is discouraged')
        matches = [x for x in self.data if x.find(chname) >= 0]
        if len(matches) == 0:
            raise KeyError(f'No matching channel for {chname}')
        else:
            ch = min(matches, key=len)  # choose shortest matching name
        if len(matches) > 1:
            logger.warning(f'multiple channel matches for {chname}: {matches} -> {ch}')
        return ch

    def get_channel_data(self, chname, envelope=False):
        """Return EMG data for a given channel.

        Uses name matching. The given chname is matched (case sensitive) against
        the channel names in the data source and the shortest match is returned.
        For example, with chname=='LGas', 'Voltage.LGas8' and
        'Voltage.LGas8_filtered' would be matches, and the former would be
        returned.

        Data is returned filtered if self.passband is set.

        Parameters
        ----------
        ch : string
            The EMG channel name. Name matching is used (see above).
        envelope : bool
            Return envelope of data. The envelope is computed as either RMS or
            linear envelope, according to settings in the config.

        Returns
        -------
        ndarray
            The data, shape (N,).
        """
        ch = self._match_name(chname)
        data = self.data[ch]
        if envelope:
            data = numutils.envelope(data, self.sfrate)
        elif self.passband:  # no filtering for RMS data
            # filtered data is currently not cached; _filtfilt() call typically
            # takes less than 1 ms, so this should not be a problem, unless a
            # huge number of calls are made
            data = numutils._filtfilt(data, self.passband, self.sfrate)
        return data * self.correction_factor

    def has_channel(self, chname):
        """Check whether a channel exists in the data.

        Parameters
        ----------
        chname : str
            The desired channel name. Name matching is used (see docstring for
            get_channel_data)

        Returns
        -------
        bool
            True if the channel exists, False otherwise.
        """
        try:
            self._match_name(chname)
        except KeyError:
            return False
        return True

    def status_ok(self, chname):
        """Check whether a channel exists and has valid EMG signal.

        Parameters
        ----------
        chname : str
            The desired channel name. Name matching is used (see docstring for
            get_channel_data)

        Returns
        -------
        bool
            True if the channel exists and has valid data, False otherwise.
        """
        if not self.has_channel(chname):
            return False
        elif chname in self.chs_disabled:
            return False
        elif cfg.emg.chs_disabled and chname in cfg.emg.chs_disabled:
            return False
        data = self.get_channel_data(chname)
        return self._is_valid_emg(data) if cfg.emg.autodetect_bads else True

    @staticmethod
    def context_ok(chname, context):
        """Check if the channel context matches given context.

        Parameters
        ----------
        chname : str
            A configured channel name. (Name matching is not applied here.)
        context : str
            Context ('L' or 'R').

        Returns
        -------
        bool
            False if context does not match. True if the context matches or is unknown.
        """
        if (
            chname in cfg.emg.channel_context
            and context.upper() != cfg.emg.channel_context[chname].upper()
        ):
            return False
        return True

    def _is_valid_emg(self, data):
        """Check whether channel contains a valid EMG signal."""
        return cfg.emg.variance_ok[0] < np.var(data) < cfg.emg.variance_ok[1]


class AvgEMG(EMG):
    """Class for storing averaged RMS EMG.

    Tries to match the API of the EMG class, but differs in following ways:
    precomputed RMS data is stored in self._data, only the RMS data can be
    returned, and no filtering is done.

    Parameters
    ----------
    data : dict
        The averaged data, e.g. from stats.average_analog.data().
    """

    def __init__(self, data):
        self.chs_disabled = list()  # not supported at the moment
        self._data = data

    def get_channel_data(self, chname, envelope=None):
        if not envelope:
            raise RuntimeError('AvgEMG can only return enveloped and averaged data')
        chname = self._match_name(chname)
        return self._data[chname]

    def status_ok(self, chname):
        if chname in self.chs_disabled:
            return False
        elif cfg.emg.chs_disabled and chname in cfg.emg.chs_disabled:
            return False
        else:
            return self.has_channel(chname)

    def _is_valid_emg(self, data):
        raise RuntimeError('signal check not implemented for averaged EMG')

    def filt(self, y, passband):
        raise RuntimeError('filtering not implemented for averaged EMG')

    def read(self):
        raise RuntimeError('read not implemented for averaged EMG')
