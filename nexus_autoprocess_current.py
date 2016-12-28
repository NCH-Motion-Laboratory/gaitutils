# -*- coding: utf-8 -*-
"""

Auto process single trial.
Note: does not use stats for event detection -> less accurate

@author: Jussi
"""

from nexus_autoprocess_trials import _do_autoproc
from gaitutils import nexus

if __name__ == '__main__':

    if not nexus.pid():
        raise Exception('Vicon Nexus not running')

    vicon = nexus.viconnexus()
    trialname_ = vicon.GetTrialName()
    if not trialname_:
        raise ValueError('No trial loaded in Nexus?')
    subjectname = vicon.GetSubjectNames()[0]
    sessionpath = trialname_[0]
    enfname = ''.join(trialname_)+'.Trial.enf'

    _do_autoproc([enfname])  # need to listify name
