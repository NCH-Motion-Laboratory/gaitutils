import sys
import os
import logging

def run_from_ipython():
    try:
        __IPYTHON__
        return True
    except NameError:
        return False

# fake stdout and stderr not being available if run
# under pythonw.exe on Windows
if (sys.platform.find('win') != -1 and sys.executable.find('pythonw') != -1 and
   not run_from_ipython()):
    blackhole = open(os.devnull, 'w')
    sys.stdout = sys.stderr = blackhole

from .envutils import GaitDataError
from .config import cfg
from . import trial, viz, report, stats
