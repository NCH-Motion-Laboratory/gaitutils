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

   curl -O https://raw.githubusercontent.com/NCH-Motion-Laboratory/gaitutils/master/environment.yml

Alternatively, if ``curl`` does not work, visit the link
https://raw.githubusercontent.com/NCH-Motion-Laboratory/gaitutils/master/environment.yml
and save the file. Make sure that it is saved with the ``.yml`` extension. Then
create the environment by typing:

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

   cd "C:\Program Files (x86)\Vicon\Nexus2.12\SDK\Win64\Python"
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

Updating the package
--------------------

To update, give the command

::

   pip install --upgrade https://github.com/NCH-Motion-Laboratory/gaitutils/archive/master.zip

Occassionally it may be beneficial or necessary to upgrade the dependencies as
well. Unfortunately, there's currently no simple way to do this. The best way
may be to simply delete the whole environment with

::

   conda activate base
   conda env remove -n gaitutils

and reinstall.


