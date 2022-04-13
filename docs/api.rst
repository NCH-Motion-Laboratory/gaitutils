Using the package API in your own scripts
=========================================

In addition to the graphical user interface, you can import the package in your
own Python scripts. Note that you have to run the scripts in the gaitutils
environment for the package to be available.

Example: extracting data from a gait trial in Python
----------------------------------------------------

To do your own data processing in Python, you can extract trial data as numpy
arrays. The ``Trial`` class is used to represent data from a single gait trial.

Load a gait trial in Nexus. Run at least reconstruct, label and the Plug-in Gait
model. Also mark some foot strikes and toeoffs (at least one gait cycle).

Loading the trial into Python:

::

   from gaitutils import trial

   tr = trial.nexus_trial()
   print(tr)

The result is a  ``Trial`` object:

::

    <Trial | trial: 2018_11_14_seur_paljal_AH02, data source: <ViconNexus.ViconNexus instance at 0x000000000DE62648>, subject: Aamu, gait cycles: 6>

You could load the trial from a C3D file instead:

::

   from gaitutils import trial

   c3dfile = r"C:\gait_data\example.c3d"
   tr = trial.Trial(c3dfile)

Extracting some marker data from the trial as Nx3 NumPy array:

::

   t, mdata = tr.get_marker_data('RASI')

Extracting Plug-in Gait outputs:

::

   t, mdata = tr.get_model_data('LPelvisAnglesX')

These will give frame-based data for the whole trial. ``t`` gives the frame
number and has length equal to the length of the data. To get data normalized to
the first gait cycle, do:

::

   t, mdata = tr.get_model_data('LPelvisAnglesX', 0)

Note that cycle numbering is 0-based, so 0 represents the first gait cycle. Now
``t`` is the percentage of gait cycle 0..100% and ``mdata`` is the normalized
LPelvisAnglesX variable.

``get_cycles`` can be used to get a specific gait cycle. For example, to
normalize to first right foot cycle and forceplate contact, do:

::

   cycles = tr.get_cycles({'R': 'forceplate'})  # returns all gait cycles on R that start with forceplate contact
   cyc = cycles[0]  # pick the 1st one from those cycles
   t, mdata = tr.get_model_data('LPelvisAnglesX', cyc)  # extract cycle normalized data

Example: plotting data
----------------------

The plotter supports a number of predefined layouts, such as Plug-in Gait lower
body kinematics. This example plots lower body kinematics and kinetics from two
C3D files using the matplotlib backend.

::

   from gaitutils.viz import plots, show_fig

   c3ds = ['data1.c3d', 'data2.c3d']

   fig = plots.plot_trials(c3ds, layout='lb_kin', backend='matplotlib')
   show_fig(fig)

Example: finding gait trials
----------------------------

The ``sessionutils`` module contains some utilities for handling gait sessions.
For example, to find all dynamic trials in a session:

::

   from gaitutils import sessionutils

   sessionpath = r"C:\gait_data\patient1\session1"
   c3ds = gaitutils.sessionutils.get_c3ds(sessionpath, trial_type='dynamic')

To find trials by tag:

::

   c3ds = gaitutils.sessionutils.get_c3ds(sessionpath, tag=['good'], trial_type='dynamic')

would find any dynamic trials that are marked by the string "good" in the
Eclipse Description or Notes fields.

Example: extracting data and doing statistics
---------------------------------------------

For research studies, it may be useful to aggregate data into NumPy arrays. Here
we accumulate the left sagittal knee angle from a bunch of trials into a NumPy
array and plot it.

::

   from gaitutils import stats, sessionutils
   import matplotlib.pyplot as plt

   sessionpath = r"C:\gait_data\patient1\session1"
   c3ds = gaitutils.sessionutils.get_c3ds(sessionpath, trial_type='dynamic')

   data_all, cycles_all = stats.collect_trial_data(c3ds, collect_types=['model'])

   knee_flex = data_all['model']['LKneeAnglesX']
   plt.figure()
   plt.plot(knee_flex.T)  # matplotlib plots columns by default, so transpose

