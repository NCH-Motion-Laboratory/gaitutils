# -*- coding: utf-8 -*-
"""

models.py - definitions for various models (PiG, muscle length, etc.)

To create a new model, create a GaitModel() instance, fill in the data and
append to models_all.

@author: Jussi
"""

import os.path as op
import numpy as np
from numutils import isfloat
from config import Config

models_all = []

cfg = Config()


def model_from_var(var):
    """ Return model for specified variable.
    model: model instance that has the specified variable. """
    for model in models_all:
        if var in model.varnames:
            return model
    return None


# convenience methods for model creation
def _list_with_side(vars):
    """ Prepend variables in vars with 'L' and 'R', creating a new list of
    variables. Many model variables share the same name, except for leading
    'L' or 'R' that indicates side. """
    return ['L'+var for var in vars]+['R'+var for var in vars]


def _dict_with_side(dict, append_side=False):
    """ Prepend dict keys with 'R' or 'L'. If append_side,
    also append corresponding ' (R)' or ' (L)' to every dict value. """
    di = {}
    if append_side:
        Rstr, Lstr = (' (R)', ' (L)')
    else:
        Rstr, Lstr = ('', '')
    for key in dict:
        di['R'+key] = dict[key]+Rstr
        di['L'+key] = dict[key]+Lstr
    return di


class GaitModel(object):
    """ A class for storing a model information, e.g. Plug-in Gait. The data
    indicates variable names etc. and is intended (currently not forced) to
    be non-mutable. The actual data is stored elsewhere. """

    def __init__(self):
        self.read_vars = list()  # vars to be read from data
        # How to read multidimensional variables: 'split_xyz' splits each
        # variable into x,y,z components and names them appropriately.
        # 'last' reads the last component only (c3d scalars are saved
        # as last component of 3-d array (??))
        self.read_strategy = None
        self.desc = ''  # description of model
        self.varnames = list()   # resulting variable names
        self.varnames_noside = list()  # variables without side
        self.varlabels_noside = dict()  # variables without side
        self.varlabels = dict()  # descriptive label for each variable
        self.normaldata_path = None  # location of normal data
        # mapping from variable names to normal data variables (optional)
        self.normaldata_map = dict()
        # the actual normal data
        self._normaldata = dict()
        # y axis labels for plotting the variables (optional)
        self.ylabels = dict()

    def get_normaldata(self, var):
        """ Get normal data for specified variable. Returns (t, data) tuple
        (see below) """
        if self.normaldata_path is None:
            return None
        if not self._normaldata:  # not read yet
            self._normaldata = self._read_normaldata()
        if var in self.normaldata_map:
            nvar = self.normaldata_map[var]
            return self._normaldata[nvar]
        else:
            return None

    def _read_normaldata(self):
        """ Read normal data into dict. Dict keys are variables and dict
        values are (t, data) tuples. t is the normalized x axis (0..100)
        of length n and data has shape (n, ndim). The ndim columns may
        represent e.g. mean and stddev etc. depending on the normal data
        file. """
        normaldata = dict()
        filename = self.normaldata_path
        type = op.splitext(filename)[1].lower()
        varname = None
        if type == '.gcd':
            with open(filename, 'r') as f:
                lines = f.readlines()
            for li in lines:
                lis = li.split()
                if li[0] == '!':
                    varname = lis[0][1:]
                    normaldata[varname] = list()
                elif varname and isfloat(lis[0]):
                    normaldata[varname].append([float(x) for x in lis])
            for var, data in normaldata.items():
                normaldata[var] = (np.linspace(0, 100, len(data)),
                                   np.array(data))
        else:
            raise ValueError('Only .gcd file format supported for now')
        return normaldata


""" Create models """

#
# Plug-in Gait lowerbody
#
pig_lowerbody = GaitModel()
pig_lowerbody.desc = 'Plug-in Gait lower body'
pig_lowerbody.type = 'PiG'
pig_lowerbody.read_strategy = 'split_xyz'
pig_lowerbody.read_vars = _list_with_side(['HipMoment',
                                           'KneeMoment',
                                           'AnkleMoment',
                                           'HipPower',
                                           'KneePower',
                                           'AnklePower',
                                           'HipAngles',
                                           'KneeAngles',
                                           'AbsAnkleAngle',
                                           'AnkleAngles',
                                           'PelvisAngles',
                                           'FootProgressAngles'])

pig_lowerbody.varlabels_noside = {
                             'AnkleAnglesX': 'Ankle dorsi/plant',
                             'AnkleAnglesZ': 'Ankle rotation',
                             'AnkleMomentX': 'Ankle dors/plan moment',
                             'AnklePowerZ': 'Ankle power',
                             'FootProgressAnglesZ': 'Foot progress angles',
                             'HipAnglesX': 'Hip flexion',
                             'HipAnglesY': 'Hip adduction',
                             'HipAnglesZ': 'Hip rotation',
                             'HipMomentX': 'Hip flex/ext moment',
                             'HipMomentY': 'Hip ab/add moment',
                             'HipMomentZ': 'Hip rotation moment',
                             'HipPowerZ': 'Hip power',
                             'KneeAnglesX': 'Knee flexion',
                             'KneeAnglesY': 'Knee adduction',
                             'KneeAnglesZ': 'Knee rotation',
                             'KneeMomentX': 'Knee flex/ext moment',
                             'KneeMomentY': 'Knee ab/add moment',
                             'KneeMomentZ': 'Knee rotation moment',
                             'KneePowerZ': 'Knee power',
                             'PelvisAnglesX': 'Pelvic tilt',
                             'PelvisAnglesY': 'Pelvic obliquity',
                             'PelvisAnglesZ': 'Pelvic rotation'}

pig_lowerbody.varlabels = _dict_with_side(pig_lowerbody.varlabels_noside)

pig_lowerbody.varnames = pig_lowerbody.varlabels.keys()
pig_lowerbody.varnames_noside = pig_lowerbody.varlabels_noside.keys()

pig_lowerbody.normaldata_map = _dict_with_side({
             'AnkleAnglesX': 'DorsiPlanFlex',
             'AnkleAnglesZ': 'FootRotation',
             'AnkleMomentX': 'DorsiPlanFlexMoment',
             'AnklePowerZ': 'AnklePower',
             'FootProgressAnglesZ': 'FootProgression',
             'HipAnglesX': 'HipFlexExt',
             'HipAnglesY': 'HipAbAdduct',
             'HipAnglesZ': 'HipRotation',
             'HipMomentX': 'HipFlexExtMoment',
             'HipMomentY': 'HipAbAdductMoment',
             'HipMomentZ': 'HipRotationMoment',
             'HipPowerZ': 'HipPower',
             'KneeAnglesX': 'KneeFlexExt',
             'KneeAnglesY': 'KneeValgVar',
             'KneeAnglesZ': 'KneeRotation',
             'KneeMomentX': 'KneeFlexExtMoment',
             'KneeMomentY': 'KneeValgVarMoment',
             'KneeMomentZ': 'KneeRotationMoment',
             'KneePowerZ': 'KneePower',
             'PelvisAnglesX': 'PelvicTilt',
             'PelvisAnglesY': 'PelvicObliquity',
             'PelvisAnglesZ': 'PelvicRotation'})

pig_lowerbody.ylabels = _dict_with_side({
                         'AnkleAnglesX': 'Pla     ($^\\circ$)      Dor',
                         'AnkleAnglesZ': 'Ext     ($^\\circ$)      Int',
                         'AnkleMomentX': 'Int dors    Nm/kg    Int plan',
                         'AnklePowerZ': 'Abs    W/kg    Gen',
                         'FootProgressAnglesZ': 'Ext     ($^\\circ$)      Int',
                         'HipAnglesX': 'Ext     ($^\\circ$)      Flex',
                         'HipAnglesY': 'Abd     ($^\\circ$)      Add',
                         'HipAnglesZ': 'Ext     ($^\\circ$)      Int',
                         'HipMomentX': 'Int flex    Nm/kg    Int ext',
                         'HipMomentY': 'Int add    Nm/kg    Int abd',
                         'HipMomentZ': 'Int flex    Nm/kg    Int ext',
                         'HipPowerZ': 'Abs    W/kg    Gen',
                         'KneeAnglesX': 'Ext     ($^\\circ$)      Flex',
                         'KneeAnglesY': 'Val     ($^\\circ$)      Var',
                         'KneeAnglesZ': 'Ext     ($^\\circ$)      Int',
                         'KneeMomentX': 'Int flex    Nm/kg    Int ext',
                         'KneeMomentY': 'Int var    Nm/kg    Int valg',
                         'KneeMomentZ': 'Int flex    Nm/kg    Int ext',
                         'KneePowerZ': 'Abs    W/kg    Gen',
                         'PelvisAnglesX': 'Pst     ($^\\circ$)      Ant',
                         'PelvisAnglesY': 'Dwn     ($^\\circ$)      Up',
                         'PelvisAnglesZ': 'Bak     ($^\\circ$)      For'})

pig_lowerbody.normaldata_path = cfg.pig_normaldata_path

pig_lowerbody.is_kinetic_var = (lambda varname: 'Moment' in varname or
                                'Power' in varname)

models_all.append(pig_lowerbody)

#
# Muscle length (MuscleLength.mod)
#

musclelen = GaitModel()
musclelen.desc = 'Muscle length (MuscleLength.mod)'
musclelen.type = 'musclelen'
musclelen.read_strategy = 'last'

musclelen.varlabels_noside = {
                        'AdBrLength': 'AdBrLength',
                        'AdLoLength': 'AdLoLength',
                        'AdMaInfLength': 'AdMaInfLength',
                        'AdMaMidLength': 'AdMaMidLength',
                        'AdMaSupLength': 'AdMaSupLength',
                        'BiFLLength': 'Biceps femoris length',
                        'BiFSLength': 'BiFSLength',
                        'ExDLLength': 'ExDLLength',
                        'ExHLLength': 'ExHLLength',
                        'FlDLLength': 'FlDLLength',
                        'FlHLLength': 'FlHLLength',
                        'GMedAntLength': 'GMedAntLength',
                        'GMedMidLength': 'GMedMidLength',
                        'GMedPosLength': 'GMedPosLength',
                        'GMinAntLength': 'GMinAntLength',
                        'GMinMidLength': 'GMinMidLength',
                        'GMinPosLength': 'GMinPosLength',
                        'GemeLength': 'GemeLength',
                        'GlMaInfLength': 'GlMaInfLength',
                        'GlMaMidLength': 'GlMaMidLength',
                        'GlMaSupLength': 'GlMaSupLength',
                        'GracLength': 'Gracilis length',
                        'IliaLength': 'IliaLength',
                        'LaGaLength': 'Lateral gastrocnemius length',
                        'MeGaLength': 'Medial gastrocnemius length',
                        'PELOLength': 'PELOLength',
                        'PeBrLength': 'PeBrLength',
                        'PeTeLength': 'PeTeLength',
                        'PectLength': 'PectLength',
                        'PeriLength': 'PeriLength',
                        'PsoaLength': 'Psoas length',
                        'QuFeLength': 'QuFeLength',
                        'ReFeLength': 'Rectus femoris length',
                        'SartLength': 'SartLength',
                        'SeMeLength': 'Semimembranosus length',
                        'SeTeLength': 'Semitendinosus length',
                        'SoleLength': 'Soleus length',
                        'TiAnLength': 'Tibialis anterior length',
                        'TiPoLength': 'TiPoLength',
                        'VaInLength': 'VaInLength',
                        'VaLaLength': 'VaLaLength',
                        'VaMeLength': 'VaMeLength'}

musclelen.varlabels = _dict_with_side(musclelen.varlabels_noside)
musclelen.read_vars = musclelen.varlabels.keys()
musclelen.varnames = musclelen.read_vars
musclelen.varnames_noside = musclelen.varlabels_noside.keys()

musclelen.ylabels = {}
for var in musclelen.varnames:
    musclelen.ylabels[var] = 'Length (mm)'

models_all.append(musclelen)
