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

# create the root logger already here, so it's ready for our own modules
root_logger = logging.getLogger()
handler = logging.StreamHandler()   # log to sys.stdout
handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
root_logger.addHandler(handler)
root_logger.setLevel(logging.DEBUG)

# quiet down some noisy loggers
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PyQt5.uic').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

from .envutils import GaitDataError
from .config import cfg
from . import trial, viz, report, stats
