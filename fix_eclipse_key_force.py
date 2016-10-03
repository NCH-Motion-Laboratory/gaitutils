# -*- coding: utf-8 -*-
"""
Created on Thu Oct 29 11:17:45 2015

Utility to fix unwanted Eclipse entries.
Fixes all enf files in given directory.

Be careful! Overwrites files without asking anything.

@author: jussi
"""


from gaitutils import nexus, eclipse
import glob
import sys

KEY = 'FP1'  # Eclipse key
NEWVAL = 'Auto'      # change into this value
ENF_GLOB = '*Trial*enf'

# get session path from Nexus, find processed trials
vicon = nexus.viconnexus()
trialname_ = vicon.GetTrialName()
subjectname = vicon.GetSubjectNames()[0]
sessionpath = trialname_[0]
enffiles = glob.glob(sessionpath+'*Trial*.enf')


enffiles = glob.glob(sessionpath+ENF_GLOB)

if not enffiles:
    sys.exit('No enf files in {0}'.format(sessionpath))

for enffile in enffiles:
    eclipse.set_eclipse_key(enffile, KEY, NEWVAL, update_existing=True)
