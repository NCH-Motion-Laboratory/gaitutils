Installation (Linux)
====================
Linux support is somewhat experimental, however you should be able to get it
running on Linux (sans Vicon Nexus integration, naturally).

The installation instructions are in general similar to those for Windows
(see :doc:`install_win`) with a few differences.

Conda environment file
----------------------

You should use ``environment_linux.yml`` file (instead of ``environment.yml``)
for creating the conda environment for Linux:

::

    curl -O https://raw.githubusercontent.com/NCH-Motion-Laboratory/gaitutils/master/environment_linux.yml
    conda env create -f environment_linux.yml

No viconnexusapi
----------------

There is no viconnexusapi for Linux, so you just skip the viconnexusapi installation step.

Setting up BTK
--------------

If you want support for reading C3D files (and gaitutils on Linux is pretty
useless without it), you'll have to build BTK yourself. Here are the main
steps:

Building and installing BTK
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. Activate the gaitutils environment

#. Clone BTKCore (unless it has already been cloned as a submodule)
    
    ::

        git clone git@github.com:Biomechanical-ToolKit/BTKCore.git
    
#. Run cmake

    ::

        cd BTKCore
        cmake . -DBTK_WRAP_PYTHON=True -DNUMPY_INCLUDE_DIR=/home/andrey/opt/anaconda3/envs/gaitutils/lib/python3.11/site-packages/numpy/core/include/ -DNUMPY_VERSION=1.23.4 -DCMAKE_CXX_STANDARD=11 -DCMAKE_POSITION_INDEPENDENT_CODE=True -DCMAKE_INSTALL_PREFIX=/home/andrey/opt/anaconda3/envs/gaitutils/

    You will likely need to change the values of ``-DNUMPY_INCLUDE_DIR``, 
    ``-DNUMPY_VERSION``, and ``-DCMAKE_INSTALL_PREFIX`` to correctly
    reflect your installation.

#. Build:

    ::

        make

    **NOTE!** This uses the system's gcc compiler (and probably other tools).
    It doesn't work with the gcc installed through conda, co there should
    be no gcc in your conda environment.

#. Install:

    ::

        make install

#. In the site-packages folder of the anaconda environment create a new subfolder
   called ``btk``. Assuming that you installed anaconda in
   ``/home/andrey/opt/anaconda3`` and you are using Python 3.11:

    ::

        mkdir /home/andrey/opt/anaconda3/envs/gaitutils/lib/python3.11/site-packages/btk

#. Copy the package files there:  

    ::

        cp bin/btk.py bin/_btk.so /home/andrey/opt/anaconda3/envs/gaitutils/lib/python3.11/site-packages/btk

#. Rename ``btk.py`` to ``__init__.py``:

    ::

        cd /home/andrey/opt/anaconda3/envs/gaitutils/lib/python3.11/site-packages/btk
        mv btk.py __init__.py


Testing BTK installation
^^^^^^^^^^^^^^^^^^^^^^^^

#.  Open a new terminal and activate the environment  

#.  Run python  

#.  In Python run:  

    ::

        import btk
        reader = btk.btkAcquisitionFileReader()
        reader.SetFilename("dynamic.c3d")    # replace dynamic.c3d with your own file
        reader.Update()
        acq = reader.GetOutput()
        acq.GetPointFrequency()
        