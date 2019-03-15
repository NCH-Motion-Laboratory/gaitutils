"""Create Windows desktop shortcut for gaitutils menu"""
import win32com.client
import pythoncom
import os.path as op

# pythoncom.CoInitialize() # remove the '#' at the beginning of the line if running in a thread.

homedir = op.expanduser('~')
desktop = op.join(homedir, 'Desktop')
path = op.join(desktop, 'gaitutils menu.lnk')

anaconda_root = r'C:\ProgramData\Anaconda2'
envdir_rel = r"AppData\Local\conda\conda\envs\gaitutils"
envdir = op.join(homedir, envdir_rel)

pythonw = op.join(anaconda_root, 'pythonw.exe')
cwp = op.join(anaconda_root, 'cwp.py')
pythonw_env = op.join(envdir, 'pythonw.exe')
script = op.join(envdir, 'Scripts\gaitmenu-script.py')

assert op.isfile(cwp)
assert op.isdir(envdir)
assert op.isfile(pythonw)
assert op.isfile(pythonw_env)
assert op.isfile(script)

target = pythonw
args = '%s %s %s %s' % (cwp, envdir, pythonw_env, script)
icon = r'C:\path\to\icon\resource.ico' # not needed, but nice

shell = win32com.client.Dispatch("WScript.Shell")
shortcut = shell.CreateShortCut(path)
shortcut.Targetpath = target
shortcut.arguments = args
#shortcut.IconLocation = icon
#shortcut.WindowStyle = 7 # 7 - Minimized, 3 - Maximized, 1 - Normal
shortcut.save()
