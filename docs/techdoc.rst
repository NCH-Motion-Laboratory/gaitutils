
gaitutils technical documentation
=================================

Overview
========

gaitutils provides the following core functions:

- automatically process gait data using Vicon Nexus
- load data from C3D files or Vicon Nexus
- plot gait curves, EMG data, time-distance parameters etc.
- create reports based on the plots

A lot of the functionality is based on the ``Trial`` class, which handles data
normalization etc. 

The functions can be accessed via a Python API (``import gaitutils``) or from a
PyQt5-based GUI.

Code guidelines
===============

I have tried to adhere to the following guidelines (but not always succesfully):

- Use NumPy-style docstrings.

- Properly document at least the functions intended for API.

- Add unit tests for functions (especially API ones).

- Functions not intended for API are prefixed with underscore.

- Avoid writing lots of classes, especially thin ones that don't provide much
  functionality. Classes are great, but they also introduce hidden "magic" that
  can make it difficult for others to reason about the code.

From time to time, all the code has been reformatted with the ``black`` code
formatter, using the ``-S`` option (no string normalization, i.e. both single
and double quotes are preserved and can be used as preferred). Format by running

::

    black -S .

in the 

Version control
===============

The code is stored at a public GitHub repository at
https://github.com/jjnurminen/gaitutils. In the past, PyPi packages for
gaitutils were actively created for gaitutils, but currently the philosophy is
to install directly from the latest GitHub master branch. ``pip`` can do this
using a URL specifier such as
https://github.com/jjnurminen/gaitutils/archive/master.zip.


Installation and dependencies
=============================

gaitutils depends on a lot of other packages, including ``PyQt, SciPy, NumPy,
dash, plotly, matplotlib, btk`` etc. To facilitate the installation, a Conda
``environment.yml`` file is provided, which should install all the dependencies.
One potentially problematic dependency is the ``btk`` package (Biomechanical
ToolKit), which is no longer maintained. However, an unofficial Python 3
compatible release of ``btk`` is available at
https://anaconda.org/conda-forge/btk. 

The Vicon Nexus Python API and ``btk`` are "soft" dependencies. It's not necessary
to have Vicon Nexus installed to run gaitutils. Without Nexus, you can still
read data from C3D files. Obviously autoprocessing will not work. Though ``btk``
is technically a soft dependency, the package cannot do very much without it.

The Vicon Nexus Python API is currently (as of Nexus 2.12) provided as a ``pip``
package in the Vicon Nexus installation. After creating the conda environment,
the API package still needs to be installed as follows (edit the Nexus path as
necessary).

::

   C:\>cd "C:\Program Files (x86)\Vicon\Nexus2.12\SDK\Win64\Python"
   pip install ./viconnexusapi




Documentation
=============

The documentation is written in RST using Sphinx. It is available online at
https://gaitutils.readthedocs.io/en/latest/#. There is an automatic



Unit tests
==========

The package includes unit tests written with ``pytest``. The tests can be run
from the ``tests/`` directory by typing

::
    
    python -m pytest --runslow --runnexus

The ``--runnexus`` option runs also tests that require a working installation of
Vicon Nexus. ``--runslow`` runs additional tests that are marked as slow (e.g.
report creation.) The tests require test data that is currently not distributed
with the package, so they can be run only at the Helsinki gait lab.


Description of modules and other files
======================================

``autoprocess.py``
    Automatically process gait data using Vicon Nexus.

``c3d.py``
    Load data from C3D files. Mostly wrappers around the btk library.

``config.py``
    Read and write package configuration data.

``eclipse.py``
    Read and write Vicon database (Eclipse) files.

``emg.py``
    Handle EMG data.

``envutils.py``
    Functionality related to the operating system and environment.

``models.py``
    Definitions for various gait models, such as Plug-in Gait.

``nexus.py``
    Communicate with Vicon Nexus. Mostly wrappers around the Nexus API.

``normaldata.py``
    Load and save normal (reference) data.

``numutils.py``
    Utilities for numerical computation.

``read_data.py``
    Data reader functions intended for the end user. They delegate to either C3D
    or Nexus readers as needed.

``sessionutils.py``
    Utilities for handling gait sessions, e.g. for finding trials of interest.

``stats.py``
    Aggregate gait data into NumPy arrays and perform statistics.

``timedist.py``
    Handle gait parameters (time-distance data).

``trial.py``
    Defines the ``Trial`` class and related functionality.

``utils.py``
    Utility functions related to gait data, e.g. for recognizing gait events and
    extrapolating marker data.

``videos.py``
    Facilities for handling gait videos.

``assets/``
    Miscellaneous data used by the web report.

``data/``
    Package data. Includes some reference data and default configuration etc.

``gui/``
    The PyQt5 GUI and related functionality.

    ``gui/_gaitmenu.py``
        Main code for the PyQt5 GUI.

    ``gui/gaitmenu.ui``
        UI file for the GUI, created in Qt Designer.

    ``gui/_tardieu.py``
        A GUI for Tardieu tests (not actively maintained, may not work).

    ``gui/_windows.py``
        GUI functionality specific to Microsoft Windows.

    ``gui/qt_dialogs.py``
    ``gui/qt_widgets.py``    
        Various Qt dialogs and widgets.

``report/``
    Web and PDF-based reports.

    ``report/web.py``
        Web report based on the Dash package.

    ``report/pdf.py``
        PDF report based on matplotlib.

    ``report/text.py``
        Text reports.

    ``report/translations.py``
        Provides simple translations.

``thirdparty/``
    Modules and executables provided by third parties.

``viz/``
    Visualization functions.

    ``viz/plot_common.py``
        Common functions shared by all backends.

    ``viz/plot_matplotlib.py``
        Plot using the matplotlib library.

    ``viz/plot_misc.py``
        Utility functions.

    ``viz/plot_plotly.py``
        Plot using the Plotly library.

    ``viz/plots.py``
        The API to plotting trial data (e.g. gait curves and EMG).

    ``viz/timedist.py``
        The API to time-distance plots.

``docs/``
    This (and other) documentation.

``tests/``
    Unit tests.

