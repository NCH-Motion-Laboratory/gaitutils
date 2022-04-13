
gaitutils technical documentation
=================================

Overview
========

The core of the package is the Trial object defined in trial.py, which
represents a gait trial. Typically, a “gait trial” is a short unidirectional
walk, perhaps from one end of the walking track to the other. Several trials
(perhaps dozens) are recorded during a gait session. The trials are recorded
into individual files. Then, successful representative trials are selected for
further analysis.

The trial data may include subject information, 3D marker data, model data
derived from the marker data (such as kinematics and kinetics data), analog data
such as forceplate, EMG and accelerometer data etc. Trials typically contain
several gait cycles. A gait cycle is defined as the period from one foot strike
to the subsequent foot strike on the same side. Gait data is typically
normalized to the gait cycles. The Trial object handles normalization and
provides easy access to data from the desired cycles. A lot of the package
functionality operates on Trial instances.

Trials may be created directly from Vicon Nexus via the Python API, or from C3D
files created by Nexus. Usually it is preferable to load trials from C3D files,
as it is faster than using the Nexus API.

Configuration
=============

The package is configured via an INI file. A .gaitutils.cfg file is located in
the users' home directory. Initially it is a copy of default.cfg that is
provided with the installation. The user can then modify gaitutils.cfg by a text
editor or via the GUI configuration interface. Default values are used for
config items that are not in gaitutils.cfg.

The configuration files are parsed and written by the configdot package written
by the author. The idea of configdot is to support direct definition of Python
objects in config files, among other features not provided by standard packages
such as ConfigObj.

The configuration affects several functions, such as autoprocessing and
plotting. Some hardware and lab specific settings need to be correct for the
package to function (e.g. name of EMG device, possibly names of forceplate
devices, etc.)

After doing from gaitutils import cfg, the Items defined in the config are
accessible as cfg.section.item. For example, print(cfg.autoproc.crop_margin)
will print 10 in the default configuration.

New config items can be defined simply by inserting the item into a section in
gaitutils/data/default.cfg. They will automatically be shown in the
configuration GUI.

Algorithms gaitutils contains two important algorithms: automatic detection of
gait events and automatic detection of forceplate contacts. These are defined in
utils.py.

gaitutils is able to detect gait events (foot strikes and toeoffs) based purely
on marker data. The algorithm is based on velocity thresholding. When the
velocity of the foot falls below a certain threshold, it is interpreted as foot
strike. When it rises above another threshold, it is interpreted as a toeoff.
The foot velocity is computed from the foot markers (ankle, toe and heel).

Detection of forceplate contacts is necessary for kinetic models. If a gait
cycle starts with a valid foot contact, we will be able know the reaction force
for the duration of the cycle. From this force, various kinetic values can be
computed, such as the moment at the knee joint.

“Valid” forceplate contact means that 1) the foot is completely inside the
forceplate area and 2) the contralateral foot does not contact the same plate
during the cycle. The foot is modelled as a simple triangle. The vertices of the
triangle are estimated from marker data. If the triangle is completely inside
the forceplate boundaries, the contact is judged as valid.

Autoprocessing
==============

Autoprocessing refers to automated processing of “raw” gait data into a form
where it can be reviewed. Typically, it involves reconstruction and labelling of
marker data, filling gaps, running filters, determining gait events and running
the relevant models. gaitutils performs autoprocessing by a mixture of its own
algorithms and Vicon Nexus operations run automatically via the Nexus Python
API. For example, marker reconstruction is performed by running Nexus
operations, while event detection uses gaitutils' own algorithm.

Autoprocessing is done in two stages. In the first stage, the marker data is
reconstructed, labeled and filtered. The second stage is run only for trials
that have valid reconstructions and are otherwise of good quality (e.g. not too
short). The second stage involves determination of gait events, execution of
desired gait models, and saving the data into C3D files.

Gait models A gait model is a biomechanical model that takes marker data and
subject information as input and outputs various values such as the knee flexion
angle or the ankle moment. gaitutils does not perform computations related to
biomechanical models, but it still needs to know various details about commonly
used models, e.g. which variables are available, their descriptive names,
whether they require forceplate data to be available etc. This facilitates
plotting and extraction of data. This knowledge is contained in models.py, which
contains data for common models such as Plug-in Gait and the Oxford foot model.
New models can be defined by instantiating the GaitModel class with the relevant
data and adding the instance into the models.models_all list. EMG

Plotting
========

gaitutils can plot marker, model and analog data from trials. It can plot to
different backends. Currently supported backends are plotly and matplotlib.
Plotly can be used to create interactive plots that are viewable in a web
browser (or inside e.g. Jupyter Notebooks). matplotlib plots are mostly for
creating hardcopies (e.g. PDF files), since plotly cannot generate high quality
hardcopies yet.

The plotting functionality is defined under gaitutils.viz. The core plotting
function is gaitutils.viz.plots.plot_trials(). It takes a list of trials, as
well as different specifications, such as the cycles to plot, colors and styles,
backend etc. The functions in plots.py delegate the actual plotting to the
specific backends such as plot_plotly.py.

Plots are defined using layouts. A layout is simply a nested list of variables
to plot, where the inner lists represent rows. For example, the following would
plot two rows (three columns) of Plug-in Gait kinematics variables:


my_kinematics = [['PelvisAnglesX', 'PelvisAnglesY', 'PelvisAnglesZ'],
 ['HipAnglesX', 'HipAnglesY', 'HipAnglesZ']]

The variable names in a layout are interpreted automatically, according to rules
defined in plot_common.py. Different interpretations are tried in sequence until
a match is found. An ambiguous definition (multiple category matches) raises an
error. The interpretation goes in the following sequence:

is it a model variable from models.py is it a marker is it a configured EMG
channel

TODO: how to plot e.g. accelerometer channels?

Reporting
=========

Built on top of the plotting functions are gait reports. Two types of reports
are supported: a PDF report, and an interactive report that runs in a web
browser (web report). 

The PDF report is mostly just a collection of matplotlib plots in a PDF file.

The web report is a Dash application. Dash is a Python “dashboard” library that
provides interactive data visualization in a web browser. It is built on top of
plotly.

Eclipse
=======

Vicon Eclipse is a software component that stores trial-related metadata into
.enf files. It is integrated into Vicon Nexus and Vicon Polygon. The package
provides some functionality for accessing this metadata. It is useful e.g. for
reading Notes and Description fields for a given trial, as well as determining
trial type.

Related to Eclipse is the concept of tags. Tags are short strings that are used
to mark trials in Eclipse. They may be inserted in the NOTES or DESCRIPTION
fields of Eclipse. Default tags used in the Helsinki gait lab are 'E1', 'E2',
'E3', 'E4' and 'T1', 'T2', 'T3', and 'T4', but any tags can be used (they are
set in the config). 

The main point of tags is to mark the trials of interest. Usually there is no
need to plot all of the trials in the session. Using the tags functionality,
e.g. the plotting functions can just automatically plot the trials of interest
from a session.

TODO: sessionutils.py Normal data The gait data is typically plotted along with
corresponding normal data (taken from the relevant healthy population).
gaitutils can read normal data from the old GCD files or XLSX files (Polygon
normal data format). The normal data operations are defined in normaldata.py. In
addition, gaitutils defines its own JSON format for EMG normal data (expected
ranges of muscle activation). Statistics


Handling of video data
======================

Some routines for handling video data are included in the package. These are
defined in videos.py. Notes on dependencies and installation

gaitutils depends on a lot of packages. The most critical one is btk
(biomechanical toolkit) that provides routines to access C3D files.
Unfortunately btk is no longer maintained, but a Python 3 compatible version is
provided on conda-forge for now.

Other major dependencies include dash, plotly, numpy, scipy, matplotlib and
pyqt. gaitutils provides an environment.yml file that should create a suitable
conda environment with all necessary packages (except for the Vicon API; see
below).

Note that an installation of Vicon Nexus isn't required. Without Nexus, you can
still load data from C3D files and create reports etc. If you want to use Nexus,
you need to install the Vicon-provided pip package into the environment.

After installation, you can run gaitutils_create_shortcut.exe from the activated
conda environment. This will create a desktop shortcut for the GUI.

Ideas for enhancements
======================

the configuration GUI is a bit limited more unit tests are needed web report:
sync of gait and video data proper 3D display of skeleton model

