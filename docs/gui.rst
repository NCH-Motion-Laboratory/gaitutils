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

