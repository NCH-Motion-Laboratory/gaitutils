Installation (Linux)
====================
Linux support is somewhat experimental, however you should be able to get it
running on Linux (sans Vicon Nexus integration, naturally).

The installation instructions are in general similar to those for Windows
(see :doc:`install_win`) with a few differences.

No viconnexusapi
----------------

There is no viconnexusapi for Linux, so you just skip the viconnexusapi installation step.

Installing Chrome
-----------------

You'll need to install Chrome into the conda environment, as it is used for creating
PDF reports.

#. Activate the gaitutils environment

#. Install Chrome
    
    ::

        plotly_get_chrome
