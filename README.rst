gaitutils
=========

The aim of gaitutils is to provide convenient methods for extracting, processing and
plotting of 3D gait analysis data. Compared to packages such as btk, it
provides higher-level interface, with abstractions such as 'trial' and
'gait cycle'. Data can be read from Vicon Nexus or directly from c3d
files.

gaitutils is primarily developed for Windows, but there is also some support for Linux.

Example: to read the current trial from Vicon Nexus and plot the Plug-in Gait
lower body kinematics:

::

  import gaitutils

  tr = gaitutils.trial.nexus_trial()
  gaitutils.viz.plot_trials(tr)


The package also includes a PyQt5-based GUI for plotting and processing
operations.

See the documentation_.

.. _documentation: https://gaitutils.readthedocs.io/en/latest/
