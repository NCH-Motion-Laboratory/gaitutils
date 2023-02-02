Tested on Ubuntu 22.04

# Installation
2.  Activate the `gaitutils` environment  
3.  Clone BTKCore (unless it has already been cloned as a submodule)  
    `> git clone git@github.com:Biomechanical-ToolKit/BTKCore.git`  
4.  Run  
    `> cd BTKCore`  
5.  Run cmake:  
    `> cmake . -DBTK_WRAP_PYTHON=True -DNUMPY_INCLUDE_DIR=/home/andrey/opt/anaconda3/envs/gaitutils/lib/python3.11/site-packages/numpy/core/include/ -DNUMPY_VERSION=1.23.4 -DCMAKE_CXX_STANDARD=11 -DCMAKE_POSITION_INDEPENDENT_CODE=True -DCMAKE_INSTALL_PREFIX=/home/andrey/opt/anaconda3/envs/gaitutils/`  
    You may need to change the values of -DNUMPY_INCLUDE_DIR, -DNUMPY_VERSION, and -DCMAKE_INSTALL_PREFIX to correctly reflect your installation.  
6.  Build:  
    `> make`  
    NOTE! This uses the system's gcc compiler (and probably other tools). It doesn't work with the gcc installed through anaconda, co there should be no gcc in your environment.  
7.  Install:  
    `> make install`  
8.  In the site-packages folder of the anaconda environment create a new subfolder called btk:  
    `> mkdir /home/andrey/opt/anaconda3/envs/gaitutils/lib/python3.11/site-packages/btk`  
9.  Copy the package files there:  
    `> cp bin/btk.py bin/_btk.so /home/andrey/opt/anaconda3/envs/gaitutils/lib/python3.11/site-packages/btk`  
10. Rename btk.py to \_\_init\_\_.py:  
    `> cd /home/andrey/opt/anaconda3/envs/gaitutils/lib/python3.11/site-packages/btk`  
    `> mv btk.py __init__.py`

# Testing
1.  Open a new terminal and activate the environment  
2.  Run python  
3.  In Python run:  
    `>>> import btk`   
    `>>> reader = btk.btkAcquisitionFileReader()`  
    `>>> reader.SetFilename("dynamic.c3d")    # replace dynamic.c3d with your own file`  
    `>>> reader.Update()`  
    `>>> acq = reader.GetOutput()`  
    `>>> acq.GetPointFrequency()`
