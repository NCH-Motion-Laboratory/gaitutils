
gaitutils technical documentation
=================================

Overview
========

This document is intended to provide technical information about the gaitutils
package for developers and advanced users. It assumes basic knowledge about gait
analysis and related concepts (e.g. trials, gait cycles and gait events.)

gaitutils provides the following core functionality:

- automatically process gait data using Vicon Nexus
- load data from C3D files or Vicon Nexus
- plot gait curves, EMG data, time-distance parameters etc.
- create reports based on the plots

A lot of the functionality is based on the ``Trial`` class, which handles data
normalization etc. The package functionality can be accessed in scripts via
(``import gaitutils``) or from a PyQt5-based GUI.


Installation and dependencies
=============================

gaitutils depends on a lot of other packages, including ``PyQt, SciPy, NumPy,
dash, plotly, matplotlib, btk`` etc. To facilitate the installation, a Conda
``environment.yml`` file is provided, which should install all the dependencies.
One potentially problematic dependency is the ``btk`` package (Biomechanical
ToolKit), which is no longer maintained. However, an unofficial Python 3
compatible release of ``btk`` is available at
https://anaconda.org/conda-forge/btk. 

The Vicon Nexus Python API and ``btk`` are "soft" dependencies. It's not
necessary to have Vicon Nexus installed to run gaitutils. Without Nexus, you can
still read data from C3D files, but obviously autoprocessing will not work. Even
though ``btk`` is technically a soft dependency, the package cannot do very much
without it.

The Vicon Nexus Python API is currently (as of Nexus 2.12) provided as a ``pip``
package in the Vicon Nexus installation. After creating the conda environment,
the API package still needs to be installed as follows (edit the Nexus path as
necessary).

::

   C:\>cd "C:\Program Files (x86)\Vicon\Nexus2.12\SDK\Win64\Python"
   pip install ./viconnexusapi

Misc dependencies
-----------------

The package depends on two other packages by the author: ``ulstools`` and
``configdot``. ``ulstools`` contains various functions shared by the
applications used in the Helsinki gait lab, such as the desktop shortcut
mechanism. ``configdot`` provides an extended mechanism for reading and writing
INI files.


Installation for development
----------------------------

The default installation mechanism will install a snapshot of the package from the
latest GitHub master branch. It can then be updated with ``pip``. However,
developers and advanced users will wish to install in "git mode" instead (i.e.
run the package directly from a cloned repository). This can be done as follows:

- clone the repository from GitHub
- perform a normal install using the conda environment
- activate the new environment
- remove the pip install using ``pip uninstall gaitutils``
- change directory to root of cloned repository
- run ``pip install -e .`` (previously ``python setup.py develop`` which is now deprecated)

Desktop shortcuts
-----------------

To facilitate use of the GUI, a desktop shortcut mechanism is included. You can
run ``gaitmenu_make_shortcut`` from the activated environment to create a
shortcut. This should create a shortcut that activates the correct conda
environment and runs the GUI.


Documentation
=============

The documentation is written in RST using Sphinx. It is available online at
https://gaitutils.readthedocs.io/en/latest/#. There is a commit hook on GitHub
that automatically updates the online documentation when the master branch is
updated. Locally, the documentation can be recreated by running

::

    ./make.bat html

in the ``docs`` directory. The resulting html documentation will appear in
``docs/_build/html``.

To build the documentation, you need to have the ``sphinx_rtd_theme`` package
installed. It can be installed using ``pip``.

Unit tests
==========

The package includes unit tests written with ``pytest``. The tests can be run
from the ``tests/`` directory by typing

::
    
    python -m pytest --runslow --runnexus

The ``--runnexus`` option runs also tests that require a working installation of
Vicon Nexus. Leave it out if you don't have Nexus. ``--runslow`` runs additional
tests that are marked as slow (e.g. report creation.) 

Many of the tests require test data that is currently not distributed with the
package, so they can currently be run only at the Helsinki gait lab.


Configuration
=============

The package is configured via an INI file. The user-specific INI file
``.gaitutils.cfg`` file is located in the users' home directory. Initially it is
a copy of ``data/default.cfg`` from the package. The user can modify it either
from a text editor or via the GUI configuration interface.

The configuration INI files are parsed and written by the ``configdot`` package
written by the author. The idea of ``configdot`` is to support direct definition
of Python objects in config files, among other features not provided by standard
packages such as ``ConfigObj``.

During module import, a config object called ``cfg`` is created in ``config.py``
by reading the default configuration values and overriding them with any
user-specified values. After importing the config (``from gaitutils import
cfg``), the items defined in the config are accessible as ``cfg.section.item``.
For example, ``print(cfg.autoproc.crop_margin)`` will print ``10`` in the
default configuration. The values can be set using similar syntax, i.e.
``cfg.autoproc.crop_margin = 15``. The configuration is package-global, i.e. any
changes will immediately be reflected in any other code that uses ``cfg``

New config items can be defined simply by inserting the item and its default
value into a section in ``gaitutils/data/default.cfg``.

The GUI has dialog under File/Options that will automatically display all
configuration items defined in ``default.cfg`` on a tabbed page and allow the
user to edit them.


Algorithms
==========

Two important algorithms in gaitutils are

- automatic detection of gait events
- automatic detection of forceplate contacts

These are defined in ``utils.py``.

Event detection
---------------

See :func:`gaitutils.utils.automark_events`.

gaitutils is able to detect gait events based purely on marker data. The
algorithm is based on velocity thresholding. At the frame where the velocity of
the foot falls below a certain threshold, a foot strike event is created. When
the velocity rises above another threshold, a toeoff event is created. The foot
velocity is computed from the foot markers (ankle, toe and heel).

If forceplate data with valid foot contacts is available, it will provide the
"golden standard" for gait events: both foot strike and toeoff can be accurately
determined from the force data. Thus, gaitutils uses the force plate data to
replace events determined by velocity thresholding, when appropriate. This uses
a tolerance of 7 frames (currently hardcoded). For example, if velocity
thresholding results in a foot strike at frame 204 and a valid forceplate
contact is determined to occur almost simultaneously at frame 202, the foot
strike event is placed at frame 202 and not at 204.

The velocity thresholds can be determined based on heuristics. The default
heuristic is that the foot strike and toeoff occur at 20% and 45% of the
subject's peak foot velocity during the trial, respectively. This gives
surprisingly good results for most subjects. However, more accurate thresholds
can be determined based on the forceplate data. That is, if a valid forceplate
contact is available for the trial, the foot velocity is determined at the
moment of foot strike and toeoff, and those values are used as thresholds. When
processing a whole gait session, it would in principle be possible to use all
trials to determine the velocity threshold. However, this doesn't work in cases
where there is a lot of intertrial variance (the threshold doesn't generalize
across trials).


Evaluation of forceplate contacts
---------------------------------

For the implementation, see :func:`gaitutils.utils.detect_forceplate_events`.

Detection of forceplate contacts is necessary for kinetic models. If a gait
cycle starts with a valid foot contact, we will be able know the reaction force
for the duration of the cycle. From this force, various kinetic values can be
computed, such as the moment at the knee joint.

“Valid” forceplate contact means that 1) the foot is completely inside the
forceplate area and 2) the contralateral foot does not contact the same plate
during the cycle.

In gaitutils, the foot is modelled as a simple triangle. The vertices of the
triangle are estimated from marker data. The position of the heel marker is used
as the heel vertex. For the other two vertices ("big toe" and "little toe")
there are no markers available. Thus, the code attempts to estimate their
positions. If explicit information about foot length is available, the accuracy
will be improved. Foot length can be supplied as an extra model parameter in
Nexus (``RightFootLen`` and ``LeftFootLen``).


Contributing
============

Code guidelines
---------------

I have tried to adhere to the following guidelines (not always successfully):

- Use NumPy-style docstrings. This is also assumed by the API documentation
  generator.

- Properly document at least the functions intended for API.

- Functions not intended for API are prefixed with underscore.

- Add unit tests for functions, especially API ones.

- Avoid writing lots of classes, especially thin ones that don't provide much
  functionality. Classes are great, but they also introduce hidden "magic" that
  can make it difficult for others to reason about the code.

Code formatting
---------------

From time to time, all the code has been formatted with ``black``, using the
``-S`` option (no string normalization, i.e. both single and double quotes are
preserved and can be used as preferred). New code can be formatted in-place by
running

::

    black -S .

in the root package directory. Various IDEs such as VS Code also support
formatting with black.

Version control
---------------

The code is stored at a public GitHub repository at
https://github.com/jjnurminen/gaitutils. In the past, PyPi packages for
gaitutils were actively created for gaitutils, but currently the philosophy is
to install directly from the latest GitHub master branch. Thus, the PyPi
packages are likely to be out of date. ``pip`` can install directly from GitHub
master using a URL specifier such as
https://github.com/jjnurminen/gaitutils/archive/master.zip.



Miscellaneous technical notes
=============================

Exception handling
------------------

The package defines one custom exception class: ``GaitDataError``. It is used to
signify a general problem with the gait data that is usually non-fatal. Several
API functions raise ``GaitDataError`` when there is "something wrong" with the
data (the exact meaning depends on the function).

GUI
---

The GUI is currently written for PyQt5. With very minor modifications, it should
also work with PySide2 and PyQt6.

Threads are used to keep the GUI responsive during long running operations. The
method :meth:`gaitutils.gui._gaitmenu.Gaitmenu._run_in_thread` is used to run a
long-running operation in a worker thread. It's recommended to use this for any
operation that is expected to take longer than a second or two. The point is not
for the user to be able to run several operations in parallel, but just to keep
the GUI (e.g. the progress meter and the cancel button) responsive. In fact, by
default ``_run_in_thread()`` disables the elements of the main UI window, so that
the user cannot start multiple operations at the same time. ``_run_in_thread()``
also handles any exceptions raised during the operation and reports them via a
GUI window, without terminating the program.

Long-running Vicon Nexus operations (typically Nexus pipelines) require special
care. Seemingly, it should be enough to run the operation in a worker thread, as
described above. However, Python has a restriction known as the Global
Interpreter Lock (GIL): only one thread of a process can execute Python bytecode
at a time. It appears that the Nexus API does not release the GIL until the
Nexus operation is finished. Thus, starting a Nexus operation in a thread
freezes all other threads, potentially for a long time. A simple workaround is
to run any Nexus pipeline operations in a separate process instead of a thread
(i.e. a new interpreter is started for the operation). This is accomplished by
``gaitutils.nexus._run_pipelines_multiprocessing()``.  

For GUI operations that are not started via ``_run_in_thread()``, you must catch
and handle any exceptions yourself, otherwise they will cause a termination.
Such unhandled exceptions are propagated to a custom exception hook
(``my_excepthook()``) that will display a message and terminate the GUI.

The GUI includes a logging window that will display any messages emitted via the
standard Python logging module. This is implemented via a special logging
handler ``QtHandler()``. The logging level can be set in the configuration.


Wishlist/TODO
=============

Ideas on how to improve the package.

- Reading accelerometer data is supported, but there is no specific support for
  plotting it it (or other non-EMG analog data, such as raw forceplate data).
  Something similar to EMG handling should be implemented (i.e. list of
  accelerometer channel names, etc.) 

- Some of the configuration values really need to be adjusted for each
  particular lab (such as EMG channel names) and some can be left as they are.
  It would be nice to have a list of "critical" config values and maybe a GUI
  wizard that would allow the user to set them easily.

- The configuration GUI is a bit half-baked. It doesn't know about the potential
  types of config items, thus it has to use a "universal" line input widget for
  most items. This enables the user to input basically any Python type. However,
  if we know that a certain value is e.g. numerical only (and can't be None or a
  string etc.), we could use a spinbox, which would be neater. This would
  require a system for declaring types for config items. There could be a
  separate file that would list the allowable types (and possibly e.g. ranges of
  values) for each config type.


Description of modules and other files
======================================

This is a list of modules and other files included in the package. It is not
100% complete yet, but should contain the most important components.

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

    ``gui/gaitmenu.py``
        Launches the PyQt5 GUI.

    ``gui/gaitmenu.ui``
        UI file for the GUI, created in Qt Designer.

    ``gui/_tardieu.py``
        A GUI for Tardieu tests (not actively maintained, may not work).

    ``gui/_windows.py``
        GUI functionality specific to Microsoft Windows.

    ``gui/qt_dialogs.py``
    ``gui/qt_widgets.py``    
        Various custom Qt components.

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

    ``thirdparty/ffmpeg2theora.exe``
        Used to provide conversion from Nexus AVI video files to Theora. The web
        report needs this in order to show videos.

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

