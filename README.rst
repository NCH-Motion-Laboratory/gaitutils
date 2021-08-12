gaitutils
=========

The aim of gaitutils is to provide convenient methods for extracting and
plotting 3D gait analysis data. Compared to packages such as btk, it
provides higher-level interface, with abstractions such as 'trial' and
'gait cycle'. Data can be read from Vicon Nexus or directly from c3d
files.

Example: to read the current trial from Vicon Nexus and plot the Plug-in Gait
lower body kinematics:

::

  import gaitutils

  tr = gaitutils.trial.nexus_trial()
  gaitutils.viz.plots.plot_trials(tr)

Typical result:

  


The package also includes a PyQt5-based GUI for plotting and processing
operations.

See the documentation_.

.. _documentation: https://gaitutils.readthedocs.io/en/latest/
