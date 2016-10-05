# -*- coding: utf-8 -*-
"""

Wrapper methods that read from either Vicon Nexus or c3d files.
'source' argument can be either ViconNexus.ViconNexus instance or
a path to a c3d file.


@author: jnu@iki.fi

"""

from __future__ import print_function
import nexus
import c3d


def reader_module(source):
    """ Determine the appropriate module to use """
    if nexus.is_vicon_instance(source):
        return nexus
    elif c3d.is_c3dfile(source):
        return c3d
    else:
        raise ValueError('Unknown source')


def get_metadata(source):
    """ Get trial and subject info """
    return reader_module(source).get_metadata(source)


def get_forceplate_data(source):
    """ Get force, moment and center of pressure """
    return reader_module(source).get_forceplate_data(source)


def get_marker_data(source, markers):
    """ Get position, velocity and acceleration for a given marker """
    return reader_module(source).get_marker_data(source, markers)


def get_emg_data(source):
    """ Get EMG data """
    return reader_module(source).get_emg(source)


def get_variables(source, vars):
    """ Get other variables such as model outputs """
    return reader_module(source).get_variables(source)


#def kinetics_available(source):
#    return reader_module(source).kinetics_available(source)


#def get_roi(source, markers):
#    return reader_module(source).get_roi(source, markers)




