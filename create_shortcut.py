"""Create Windows desktop shortcut for gaitutils menu.
This should be run in the activated environment"""
import win32com.client
import pythoncom
import os
import os.path as op

# pythoncom.CoInitialize() # remove the '#' at the beginning of the line if running in a thread.

homedir = op.expanduser('~')
desktop = op.join(homedir, 'Desktop')
path = op.join(desktop, 'gaitutils menu.lnk')

# for some reason CONDA_ROOT is not set, so get the root from the executable path
anaconda_python = os.environ['CONDA_PYTHON_EXE']
anaconda_root = op.split(anaconda_python)[0]
envdir = os.environ['CONDA_PREFIX']

pythonw = op.join(anaconda_root, 'pythonw.exe')
cwp = op.join(anaconda_root, 'cwp.py')
pythonw_env = op.join(envdir, 'pythonw.exe')
script = op.join(envdir, r'Scripts\gaitmenu-script.py')

assert op.isfile(cwp)
assert op.isdir(envdir)
assert op.isfile(pythonw)
assert op.isfile(pythonw_env)
assert op.isfile(script)

args = '%s %s %s %s' % (cwp, envdir, pythonw_env, script)

shell = win32com.client.Dispatch("WScript.Shell")
shortcut = shell.CreateShortCut(path)
shortcut.Targetpath = pythonw
shortcut.arguments = args
shortcut.save()
