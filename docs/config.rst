Package configuration
=====================

The first import of the package (see 'Verification' above) should create a
config file named ``.gaitutils.cfg`` in your home directory. You can edit the
file to reflect your own system settings. You can also change config items from
the graphical user interface (go to File/Options) and save either into
``.gaitutils.cfg`` (will be automatically loaded on startup) or some other file.

The most important settings to customize are described below, by section:

[general]
---------

If you want to plot normal data for Plug-in Gait variables, edit
``normaldata_files`` to reflect the path to your normaldata file. ``.gcd`` and
``.xlsx`` (Polygon normal data export) file formats are supported.

[emg]
-----

Set ``devname`` to name of your EMG device shown in Nexus (for example 'Myon
EMG'). When reading data from Nexus, analog devices cannot be reliably
identified, except by name. This setting does not affect reading c3d files.

``channel_labels`` has the following structure: ``{'ch1': 'EMG channel 1',
'ch2': 'EMG channel 2', ...}`` Edit ``ch1``, ``ch2`` etc. to match your EMG
channel names (as shown in Nexus). Edit the descriptions as you desire. Partial
matches for channel names are sufficient, e.g. if you have a channel named
'RGas14' in Nexus you can specify the name as 'RGas'. In case of conflicting
names, a warning will be given and the shortest matching name will be picked.

[plot]
------

``default_model_cycles`` and ``default_emg_cycles`` specify which gait cycles to
plot by default. The options are

-  ``'all'``: plot all gait cycles
-  ``'forceplate'``: plot all cycles that begin on valid forceplate
   contact
-  ``'1st_forceplate'``: plot first forceplate cycle
-  ``0``: plot first cycle (NOTE: explicit cycle numbering is
   zero-based!)
-  A list, e.g. ``'[0,1,2]'``: plots first to third cycles
-  A tuple, e.g. ``(forceplate, 0)``: plot forceplate cycles, or if
   there are none, first gait cycle

[autoproc]
----------

Set ``events_range`` to limit automatically marked events to certain coordinate
range in the principal gait direction.

Set ``eclipse_write_key`` to e.g. ``'DESCRIPTION'`` to automatically update
Eclipse fields after processing. Set it to None if you want to leave the Eclipse
fields alone. The ``enf_descriptions`` determines what to write into the Eclipse
field.


[layouts]
---------

Layouts defines the predetermined plotting layouts. Defaults include
layouts such as

::

   lb_kinematics = [['PelvisAnglesX', 'PelvisAnglesY', 'PelvisAnglesZ'],
                     ['HipAnglesX', 'HipAnglesY', 'HipAnglesZ'],
                     ['KneeAnglesX', 'KneeAnglesY', 'KneeAnglesZ'],
                     ['AnkleAnglesX', 'FootProgressAnglesZ', 'AnkleAnglesZ']]

This would be 4 rows and 3 columns of PiG variables. Rows are inside the inner
brackets, separated by commas. You can add your own layouts.

Currently, reading data from the following models is supported: Plug-in Gait
upper and lower body, CGM2, Oxford foot model, muscle length. The variable names
are not yet documented here, but see ``models.py`` for details.
