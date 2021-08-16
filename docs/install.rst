Installation
============

Python
------

`Anaconda <https://www.anaconda.com/distribution/#download-section>`__
is the recommended distribution. Alternatively you can use
`Miniconda <https://docs.conda.io/en/latest/miniconda.html>`__ for a
smaller download. It's recommended to install a 64-bit version with
Python 3.6 or newer.

Installation via environment file
---------------------------------

It is possible to install gaitutils via pip. However as there are quite a lot of
dependencies, it is usually easier to install everything at once using a conda
feature called environments.

Open Anaconda Prompt from Windows menu. Download the environment
specification by giving the command:

::

   curl -O http://raw.githubusercontent.com/jjnurminen/gaitutils/master/environment.yml

Alternatively, if ``curl`` does not work, download ``environment.yml``
by visiting the link given in the above command and saving the file.
Make sure that it is saved under the correct filename - the browser save
dialog may change the name. Then create the environment by typing:

::

   conda env create -f environment.yml

To activate the environment in Anaconda Prompt, type

::

   conda activate gaitutils

This will activate the environment for the current session only. For
instructions on how to activate it every time you open the shell, see
the Appendix.

Install viconnexusapi
---------------------

To use gaitutils with Vicon Nexus (version 2.12 and above), you need to
install the ``viconnexusapi`` package that comes with Nexus. After
activating the environment as above, give the following commands:

::

   C:\>cd "C:\Program Files (x86)\Vicon\Nexus2.12\SDK\Win64\Python"
   pip install ./viconnexusapi

Starting the menu
-----------------

After activating the environment, you can run

::

   gaitmenu

to start the graphical user interface to gaitutils.

Creating a desktop shortcut
---------------------------

In the activated environment, type

::

   gaitmenu_make_shortcut

An icon should appear on your desktop, which will start the menu in the
correct environment.

Using the graphical menu
========================

Plotting trials
---------------

The graphical interface allows plotting of trials from c3d files or a
running Vicon Nexus instance. Click "Add session..." to add either
tagged trials or all trials from a given session. Alternatively, "Add
C3D files..." can be used to load C3D files via the OS file dialog.

The plot layout defines the variables to plot. Some common layouts such
as Plug-in Gait come predefined with the software. You can also define
your own layouts in the config (see below).

Two different plotting backends are currently supported: plotly and
matplotlib. The Plotly backend creates interactive plots in a web
browser and is somewhat more polished. The matplotlib package creates
static plots that may be more useful for hardcopies (e.g. PDF reports).

Tagging trials
--------------

In gaitutils, the trials of interest are marked by tagging. This means
that you mark the Eclipse Notes or Description fields of the desired
trials with specific strings. The default tag strings are "E1", "E2",
"E3", "E4", "T1", "T2", "T3", "T4", but this can be changed in the
config (see below).

Autoprocessing
--------------

The autoprocessing functionality is intended for processing of dynamic
trials in gait sessions (may also work for running, but less tested). It
works in conjunction with Vicon Nexus and performs the following tasks:

-  run preprocessing pipeline(s)
-  evaluate forceplate contact for each forceplate and mark the
   corresponding Eclipse database fields
-  mark gait events (foot strike and toeoff)
-  run dynamic model(s)
-  write trial info (processing results) into Eclipse, e.g. Description
   or Notes field

You should first create two pipelines in Nexus, called "Preprocessing"
and "Dynamic model". (These are default names for the preprocessing and
model pipelines, but this can be configured). The preprocessing pipeline
should yield filtered marker trajectories, i.e. it should perform
reconstruct, label gap fill (if necessary) and filter operations. You
may also want to filter analog (forceplate) data. The modeling pipeline
should run any subsequent modeling operations, e.g. Plug-in Gait. Note
that save operations are not needed in either pipeline (and they will
unnecessarily slow down the processing).

NOTE: it has been found out that long pipelines with multiple operations
may occasionally cause Nexus to crash. If you experience this, break
your preprocessing pipeline into a set of several smaller pipelines and
specify those in the configuration instead (see Options/Autoprocessing).

In Nexus Data management window, browse to the session you want to
process. Make sure the static trial has been processed so that labeling
will work for dynamic trials. Start up the gaitutils menu. Select
"Autoprocess session" or "Autoprocess single trial". The event detection
is more accurate when processing the whole session, since it uses
session level statistics.

You can improve the accuracy of forceplate detection by including foot
lengths into your subject info (labeling skeleton template). In Nexus,
click on the subject and select "Add parameter..." Add parameters called
RightFootLen and LeftFootLen with the unit set as mm. Empty out all
parameters and save the labeling skeleton as a new template. When taking
subject measurements, measure the maximum length of the foot (or shoe)
from heel to toe.

Report creation
---------------

The package includes simple PDF and web-based (interactive) gait
reports. These can be created from the Reports menu. The report
functionality requires tagging the trials of interest (see above). The
tagged trials will be included into the report. Note that the reports
are currently a bit specific to the Helsinki gait lab.

Using the package API in your own scripts
=========================================

In addition to the graphical user interface, you can import the package
in your own Python scripts. To try it out, launch e.g. the Spyder IDE
that comes with Anaconda and run some of the examples below. Note that
you have to start the Python interpreter in the gaitutils environment -
if you installed Anaconda, the Windows menu should already have an entry
that runs Spyder in the correct environment.

Example: extracting data from a gait trial in Python
----------------------------------------------------

To do your own data processing in Python, you can extract trial data as
numpy arrays.

Load a gait trial in Nexus. Run at least reconstruct, label and the
Plug-in Gait model. Also mark some foot strikes and toeoffs (at least
one gait cycle).

Loading the trial into Python:

::

   from gaitutils import trial

   tr = trial.nexus_trial()
   print tr

Result:

::

    <Trial | trial: 2018_11_14_seur_paljal_AH02, data source: <ViconNexus.ViconNexus instance at 0x000000000DE62648>, subject: Aamu, gait cycles: 6>

Extracting some marker data as Nx3 NumPy array:

::

   t, mdata = tr.get_marker_data('RASI')

Extracting Plug-in Gait outputs:

::

   t, mdata = tr.get_model_data('LPelvisAnglesX')

These will give frame-based data for the whole trial. ``t`` gives the
frame number and has length equal to the data. To get data normalized to
the first gait cycle, do:

::

   t, mdata = tr.get_model_data('LPelvisAnglesX', 0)

Note that cycle numbering is 0-based. Now ``t`` is the percentage of
gait cycle 0..100% and ``mdata`` is the normalized LPelvisAnglesX
variable.

``get_cycles`` can be used to get a specific gait cycle. For example, to
normalize to first cycle with right context and forceplate contact, do:

::

   cycles = tr.get_cycles({'R': 'forceplate'})  # returns all gait cycles on R that start with forceplate contact
   cyc = cycles[0]  # pick the 1st one
   t, mdata = tr.get_model_data('LPelvisAnglesX')  # extract cycle normalized data

Example: plotting data
----------------------

The plotter supports a number of predefined layouts such as Plug-in Gait
lower body kinematics. It handles normalization of data etc. This
example plots lower body kinematics and kinetics from two c3d files
using the matplotlib backend.

::

   from gaitutils.viz import plots, show_fig

   c3ds = ['data1.c3d', 'data2.c3d']

   fig = plots.plot_c3ds(c3ds, layout_name='lb_kin', backend='matplotlib')
   show_fig(fig)

Package configuration
=====================

The first import of the package (see 'Verification' above) should create
a config file named ``.gaitutils.cfg`` in your home directory. You can
edit the file to reflect your own system settings. You can also change
config items from the graphical user interface (go to File/Options) and
save either into ``.gaitutils.cfg`` (will be automatically loaded on
startup) or some other file.

The most important settings to customize are described below, by
section:

[general]
---------

If you want to plot normal data for Plug-in Gait variables, edit
``normaldata_files`` to reflect the path to your normaldata file.
``.gcd`` and ``.xlsx`` (Polygon normal data export) file formats are
supported.

[emg]
-----

Set ``devname`` to name of your EMG device shown in Nexus (for example
'Myon EMG'). When reading data from Nexus, analog devices cannot be
reliably identified, except by name. This setting does not affect
reading c3d files.

``channel_labels`` has the following structure:
``{'ch1': 'EMG channel 1', 'ch2': 'EMG channel 2', ...}`` Edit ``ch1``,
``ch2`` etc. to match your EMG channel names (as shown in Nexus). Edit
the descriptions as you desire. Partial matches for channel names are
sufficient, e.g. if you have a channel named 'RGas14' in Nexus you can
specify the name as 'RGas'. In case of conflicting names, a warning will
be given and the shortest matching name will be picked.

[plot]
------

``default_model_cycles`` and ``default_emg_cycles`` specify which gait
cycles to plot. The options are

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

Set ``eclipse_write_key`` to e.g. ``'DESCRIPTION'`` to automatically
update Eclipse fields after processing. Set it to None if you want to
leave the Eclipse fields alone. The ``enf_descriptions`` determines what
to write into the Eclipse field.

Set ``events_range`` to limit automatically marked events to certain
coordinate range in the principal gait direction.

[layouts]
---------

Layouts defines the predetermined plotting layouts. Defaults include
layouts such as

::

   lb_kinematics = [['PelvisAnglesX', 'PelvisAnglesY', 'PelvisAnglesZ'],
                     ['HipAnglesX', 'HipAnglesY', 'HipAnglesZ'],
                     ['KneeAnglesX', 'KneeAnglesY', 'KneeAnglesZ'],
                     ['AnkleAnglesX', 'FootProgressAnglesZ', 'AnkleAnglesZ']]

This would be 4 rows and 3 columns of PiG variables. Rows are inside the
inner brackets, separated by commas. You can add your own layouts.

Currently, reading data from the following models is supported: Plug-in
Gait upper and lower body, CGM2, Oxford foot model, muscle length. The
variable names are not yet documented here, but see ``models.py`` for
details.

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

Installing btk (for legacy Python 2 versions only)
--------------------------------------------------

gaitutils needs the btk package to read c3d files. A 64-bit version for
Python 2.7 is bundled. If you prefer to run 32-bit Python, you need to
install btk yourself.

Download and run the installer from
https://pypi.python.org/pypi/btk/0.3#files. The btk installer always
puts the package into the conda root environment. Thus, after
installation you need to copy the folder
``C:\Anaconda2\Lib\site-packages\btk`` into
``C:\Anaconda2\envs\gaitutils\Lib\site-packages\btk`` (modify paths
depending on where you installed Anaconda)

Known issues
============

If you create new layouts in ``gaitutils.cfg``, you need to restart
``gaitmenu``. The layouts config tab cannot handle loading new layouts
yet.
