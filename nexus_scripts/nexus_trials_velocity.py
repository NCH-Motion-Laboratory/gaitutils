# -*- coding: utf-8 -*-
"""
Created on Wed Jun 21 13:48:27 2017

@author: HUS20664877
"""

from gaitutils import nexus, cfg, utils, read_data, eclipse
import numpy as np
import matplotlib.pyplot as plt
import os.path as op


def _trial_index(c3d):
    try:
        return int(op.splitext(c3d)[0][-3:])
    except ValueError:
        try:
            return int(op.splitext(c3d)[0][-2:])
        except ValueError:
            return None


def trial_median_velocity(source):
    frate = read_data.get_metadata(source)['framerate']
    dim = utils.principal_movement_direction(source, cfg.autoproc.
                                             track_markers)
    mkr = cfg.autoproc.track_markers[0]
    vel_ = read_data.get_marker_data(source, mkr)[mkr+'_V'][:, dim]
    vel = np.median(np.abs(vel_[np.where(vel_)]))
    return vel * frate / 1000.


def do_plot():
    enfs = nexus.get_trial_enfs()
    sessionpath = op.split(op.split(enfs[0])[0])[1]
    enfs_ = [enf for enf in enfs if
             eclipse.get_eclipse_keys(enf,
                                      return_empty=True)['TYPE'] == 'Dynamic']
    c3ds = [nexus.enf2c3d(enf) for enf in enfs_]

    indices = [_trial_index(c3d) for c3d in c3ds]
    vels = np.array([trial_median_velocity(trial) for trial in c3ds])

    vavg = vels.mean()

    plt.stem(indices, vels)
    plt.ylabel('Velocity (m/s)')
    plt.xlabel('Trial index')
    plt.title('%s\nvelocity for dynamic trials (average %.2f m/s)' % (sessionpath, vavg))
    plt.show()

if __name__ == '__main__':
    do_plot()
