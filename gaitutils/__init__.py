import sys
import os

from .envutils import GaitDataError


def run_from_ipython():
    try:
        __IPYTHON__
        return True
    except NameError:
        return False


# fake stdout and stderr not being available if run
# under pythonw.exe on Windows
if (
    sys.platform.find('win') != -1
    and sys.executable.find('pythonw') != -1
    and not run_from_ipython()
):
    blackhole = open(os.devnull, 'w')
    sys.stdout = sys.stderr = blackhole

# in case we want to print stuff from config.py, it's better to delay
# the import until this point (after the stdout fix above)
from .config import cfg
