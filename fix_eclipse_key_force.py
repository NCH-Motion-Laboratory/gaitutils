# -*- coding: utf-8 -*-
"""
Created on Thu Oct 29 11:17:45 2015

Utility to fix Eclipse entries.
Fixes all enf files in given directory.

Be careful! Overwrites files without asking anything.

@author: jussi
"""


from gaitutils import nexus, eclipse

KEY = 'Description'  # Eclipse key
NEWVAL = ''      # change into this value

enffiles = nexus.get_trial_enfs()

if not enffiles:
    raise ValueError('No enf files')

for enffile in enffiles:
    eclipse.set_eclipse_key(enffile, KEY, NEWVAL, update_existing=True)
