Installation
============

Python
------

As a prerequisite, you need a Python environment. `Anaconda
<https://www.anaconda.com/distribution/#download-section>`__ is the recommended
distribution. Alternatively you can use `Miniconda
<https://docs.conda.io/en/latest/miniconda.html>`__ for a smaller download. It's
recommended to install a 64-bit version, with Python 3.6 or newer.

Installation via environment file
---------------------------------

It is possible to install gaitutils via pip. However as there are quite a lot of
dependencies, it is usually easier to install them all at the same time using a
conda feature called environments.

To install using environments, open Anaconda Prompt from Windows menu. Download
the environment specification by giving the command:

::

   curl -O http://raw.githubusercontent.com/jjnurminen/gaitutils/master/environment.yml

Alternatively, if ``curl`` does not work, download ``environment.yml`` by
visiting the link given in the above command and saving the file. Make sure that
it is saved under the correct filename - the browser save dialog may change the
name. Then create the environment by typing:

::

   conda env create -f environment.yml

To activate the environment in Anaconda Prompt, type

::

   conda activate gaitutils

This will activate the environment for the current session only. For
instructions on how to activate it every time you open the shell, see the
Appendix.

Install viconnexusapi
---------------------

To use gaitutils with Vicon Nexus (version 2.12 and above), you need to install
the ``viconnexusapi`` package that comes with Nexus. After activating the
environment as above, give the following commands:

::

   C:\>cd "C:\Program Files (x86)\Vicon\Nexus2.12\SDK\Win64\Python"
   pip install ./viconnexusapi

The install may sometimes fail due to "Permission denied" or similar error. In
that case, try to start Anaconda Prompt as superuser.


Starting the menu
-----------------

After activating the environment, you can run

::

   gaitmenu

to start the graphical user interface (GUI) to gaitutils.

Creating a desktop shortcut
---------------------------

In the activated environment, type

::

   gaitmenu_make_shortcut

An icon should appear on your desktop, which will activate the correct
environment and start the GUI.

Using the GUI
=============

Plotting trials
---------------

The graphical interface allows plotting of trials from C3D files or a running
Vicon Nexus instance. Click "Add session..." to add either tagged trials or all
trials from a given session. Alternatively, use "Add C3D files..." to load C3D
files via the OS file dialog.

The plot layout defines the variables to plot. Some common layouts such as
Plug-in Gait come predefined with gaitutils. You can also define your own
layouts in the config (see below).

Two different plotting backends are currently supported: plotly and matplotlib.
The Plotly backend creates interactive plots in a web browser and is somewhat
more polished. The matplotlib package creates static plots that may be more
useful for hardcopies (e.g. PDF reports).

Tagging trials
--------------

In gaitutils, the trials of interest are identified by tagging. For example, the
gait report function picks the tagged trials into the report. Tagging means that
you mark the Eclipse "Notes" or "Description" fields of the desired trials with
specific strings. The default tag strings are "E1", "E2", "E3", "E4", "T1",
"T2", "T3", "T4", but this can be changed in the config (see below). Note that the
Eclipse fields can also contain other information, as long as the tag is present.


Autoprocessing
--------------

The autoprocessing functionality is intended for processing of dynamic trials in
gait sessions (may also work for running, but less tested). It works in
conjunction with Vicon Nexus and performs the following tasks:

-  run preprocessing pipeline(s)
-  evaluate forceplate contact for each forceplate and mark the
   corresponding Eclipse database fields
-  automatically mark gait events (foot strike and toeoff)
-  run dynamic model(s)
-  write trial info (processing results) into Eclipse, e.g. Description
   or Notes field

You should first create two pipelines in Nexus, called "Preprocessing" and
"Dynamic model". (These are default names for the preprocessing and model
pipelines, but this can be configured). The preprocessing pipeline should yield
filtered marker trajectories, i.e. it should perform reconstruct, label gap fill
(if necessary) and filter operations. You may also want to filter analog
(forceplate) data. The modeling pipeline should run any subsequent modeling
operations, e.g. Plug-in Gait. Note that save operations are not needed in
either pipeline (and they will unnecessarily slow down the processing).

NOTE: it has been found out that long pipelines with multiple operations may
occasionally cause Nexus to crash. If you experience this, break your
preprocessing pipeline into a set of several smaller pipelines and specify those
in the configuration instead (see Options/Autoprocessing).

In Nexus Data management window, browse to the session you want to process. Make
sure the static trial has been processed, so that labeling will work for dynamic
trials. This needs to be done manually.

Start up the gaitutils menu. Select "Autoprocess session" or "Autoprocess single
trial". The event detection is more accurate when processing the whole session,
since it uses session level statistics.

You can improve the accuracy of forceplate contact detection by including foot
lengths into your subject info (labeling skeleton template). In Nexus, click on
the subject and select "Add parameter..." Add parameters called RightFootLen and
LeftFootLen with the unit set as mm. Empty out all parameters and save the
labeling skeleton as a new template. When taking subject measurements, measure
the maximum length of the foot from heel to toe. If the subject is wearing
shoes, measure the shoe instead.

Report creation
---------------

The package includes simple PDF and web-based (interactive) gait reports. These
can be created from the Reports menu. The report functionality requires first
tagging the trials of interest (see above). The tagged trials will be included
into the report.

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

Package configuration
=====================

The first import of the package (see 'Verification' above) should create a
config file named ``.gaitutils.cfg`` in your home directory. You can edit the
file to reflect your own system settings. You can also change config items from
the graphical user interface (go to File/Options) and save either into
``.gaitutils.cfg`` (will be automatically loaded on startup) or some other file.

The most important settings to customize are described below, by section:

[general]
---------

If you want to plot normal data for Plug-in Gait variables, edit
``normaldata_files`` to reflect the path to your normaldata file. ``.gcd`` and
``.xlsx`` (Polygon normal data export) file formats are supported.

[emg]
-----

Set ``devname`` to name of your EMG device shown in Nexus (for example 'Myon
EMG'). When reading data from Nexus, analog devices cannot be reliably
identified, except by name. This setting does not affect reading c3d files.

``channel_labels`` has the following structure: ``{'ch1': 'EMG channel 1',
'ch2': 'EMG channel 2', ...}`` Edit ``ch1``, ``ch2`` etc. to match your EMG
channel names (as shown in Nexus). Edit the descriptions as you desire. Partial
matches for channel names are sufficient, e.g. if you have a channel named
'RGas14' in Nexus you can specify the name as 'RGas'. In case of conflicting
names, a warning will be given and the shortest matching name will be picked.

[plot]
------

``default_model_cycles`` and ``default_emg_cycles`` specify which gait cycles to
plot by default. The options are

-  ``'all'``: plot all gait cycles
-  ``'forceplate'``: plot all cycles that begin on valid forceplate
   contact
-  ``'1st_forceplate'``: plot first forceplate cycle
-  ``0``: plot first cycle (NOTE: explicit cycle numbering is
   zero-based!)
-  A list, e.g. ``'[0,1,2]'``: plots first to third cycles
-  A tuple, e.g. ``(forceplate, 0)``: plot forceplate cycles, or if
   there are none, first gait cycle

[autoproc]
----------

Set ``events_range`` to limit automatically marked events to certain coordinate
range in the principal gait direction.

Set ``eclipse_write_key`` to e.g. ``'DESCRIPTION'`` to automatically update
Eclipse fields after processing. Set it to None if you want to leave the Eclipse
fields alone. The ``enf_descriptions`` determines what to write into the Eclipse
field.


[layouts]
---------

Layouts defines the predetermined plotting layouts. Defaults include
layouts such as

::

   lb_kinematics = [['PelvisAnglesX', 'PelvisAnglesY', 'PelvisAnglesZ'],
                     ['HipAnglesX', 'HipAnglesY', 'HipAnglesZ'],
                     ['KneeAnglesX', 'KneeAnglesY', 'KneeAnglesZ'],
                     ['AnkleAnglesX', 'FootProgressAnglesZ', 'AnkleAnglesZ']]

This would be 4 rows and 3 columns of PiG variables. Rows are inside the inner
brackets, separated by commas. You can add your own layouts.

Currently, reading data from the following models is supported: Plug-in Gait
upper and lower body, CGM2, Oxford foot model, muscle length. The variable names
are not yet documented here, but see ``models.py`` for details.

Appendix
========

Updating the package
--------------------

To update, give the command

::

   pip install --upgrade https://github.com/jjnurminen/gaitutils/archive/master.zip

Occassionally it may be beneficial or necessary to upgrade the
dependencies as well. Unfortunately, there's currently no easy way to do
this. The best way may be to simply delete the whole environment with

::

   conda activate base
   conda env remove -n gaitutils

and reinstall via ``conda env create -f environment.yml``

Activating the environment automatically - bash-style shells
------------------------------------------------------------

Create a file called ``.bashrc`` in your home directory. Put the
following lines there:

::

   . /c/Anaconda2/etc/profile.d/conda.sh
   conda activate gaitutils

These commands will activate the gaitutils enviroment whenever you open
git bash. Change ``c/Anaconda2`` to your Anaconda install directory.
``c`` is the drive letter.

Known issues
============

If you create new layouts in ``gaitutils.cfg``, you need to restart
``gaitmenu``. The layouts config tab cannot handle loading new layouts
yet.
