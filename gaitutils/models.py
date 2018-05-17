# -*- coding: utf-8 -*-
"""

Definitions for various models (PiG, muscle length, etc.)

To create a new model, create a GaitModel() instance, fill in the data and
append to models_all.

@author: Jussi (jnu@iki.fi)
"""

from collections import defaultdict

from .envutils import GaitDataError


models_all = []


def model_from_var(var):
    """ Return model corresponding to specified variable.
    Returns GaitModel instance that has the specified variable. """
    if var is None:
        return None
    elif not isinstance(var, basestring):
        raise ValueError('Variable name must be a string or None')
    for model in models_all:
        if var in model.varnames or var in model.varnames_noside:
            return model
    return None


def var_with_side(var):
    for model in models_all:
        if var in model.varnames:
            return True
        if var in model.varnames_noside:
            return False
    raise GaitDataError('Model variable not found')


# convenience methods for model creation
def _list_with_side(vars):
    """ Prepend variables in vars with 'L' and 'R', creating a new list of
    variables. Many model variables share the same name, except for leading
    'L' or 'R' that indicates side. """
    return [side+var for var in vars for side in ['L', 'R']]


def _dict_with_side(dict, append_side=False):
    """ Prepend dict keys with 'R' or 'L'. If append_side,
    also append corresponding ' (R)' or ' (L)' to every dict value. """
    return {side+key: val + (' (%s)' % side if append_side else '')
            for key, val in dict.items() for side in ['R', 'L']}


class GaitModel(object):
    """ A class (template) for storing information about a model, e.g.
    Plug-in Gait. The data describes model-specific variable names etc.
    and is intended (currently not forced) to be non-mutable.
    The actual data is stored elsewhere. """

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
        # mapping from variable names to gcd normal data variables
        self.gcd_normaldata_map = dict()
        # y axis labels for plotting the variables (optional)
        self.ylabels = dict()


""" Create models """

#
# Plug-in Gait upper body
# for now, kinematics only
#
pig_upperbody = GaitModel()
pig_upperbody.desc = 'Plug-in Gait upper body kinematics'
pig_upperbody.type = 'PiG'
pig_upperbody.read_strategy = 'split_xyz'

pig_upperbody.read_vars = _list_with_side(['ThoraxAngles',
                                           'ShoulderAngles',
                                           'SpineAngles',
                                           'WristAngles',
                                           'ElbowAngles',
                                           'NeckAngles',
                                           'HeadAngles'])

pig_upperbody.varlabels_noside = {'ThoraxAnglesX': 'Thorax flex/ext',
                                  'ThoraxAnglesY': 'Thorax lateral flex',
                                  'ThoraxAnglesZ': 'Thorax rotation',
                                  'ShoulderAnglesX': 'Shoulder flex/ext',
                                  'ShoulderAnglesY': 'Shoulder abd/add',
                                  'ShoulderAnglesZ': 'Shoulder rotation',                                  
                                  'SpineAnglesX': 'Spine flex/ext',
                                  'SpineAnglesY': 'Spine lateral flex',
                                  'SpineAnglesZ': 'Spine rotation',
                                  'WristAnglesX': 'Wrist flex/ext',
                                  'WristAnglesY': 'Wrist ulnar/radial',
                                  'WristAnglesZ': 'Wrist sup/pron',
                                  'ElbowAnglesX': 'Elbow flex/ext',
                                  'ElbowAnglesY': 'Elbow Y',
                                  'ElbowAnglesZ': 'Elbow Z',
                                  'NeckAnglesX': 'Neck sagittal',
                                  'NeckAnglesY': 'Neck frontal',
                                  'NeckAnglesZ': 'Neck rotation',                                  
                                  'HeadAnglesX': 'Head sagittal',
                                  'HeadAnglesY': 'Head frontal',
                                  'HeadAnglesZ': 'Head rotation'}

# for now, ylabel is just the degree sign for all vars
pig_upperbody.ylabels = defaultdict(lambda: 'deg')

pig_upperbody.varlabels = _dict_with_side(pig_upperbody.varlabels_noside)
pig_upperbody.varnames = pig_upperbody.varlabels.keys()
pig_upperbody.varnames_noside = pig_upperbody.varlabels_noside.keys()

pig_upperbody.is_kinetic_var = (lambda varname: 'Moment' in varname or
                                'Power' in varname)
# TODO: add kinetic vars
# TODO: ylabels
models_all.append(pig_upperbody)


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
                             'AnkleAnglesY': 'Ankle adduction',
                             'AnkleAnglesZ': 'Ankle rotation',
                             'AnkleMomentX': 'Ankle dors/plan moment',
                             'AnkleMomentY': 'Ankle ab/add moment',
                             'AnkleMomentZ': 'Ankle rotation moment',
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


pig_lowerbody.gcd_normaldata_map = {
            'AnklePower': 'AnklePowerZ',
            'DorsiPlanFlex': 'AnkleAnglesX',
            'DorsiPlanFlexMoment': 'AnkleMomentX',
            'FootAbAdductMoment': 'AnkleMomentY',
            'FootProgression': 'FootProgressAnglesZ',
            'FootRotation': 'AnkleAnglesZ',
            'FootRotationMoment': 'AnkleMomentZ',
            'HipAbAdduct': 'HipAnglesY',
            'HipAbAdductMoment': 'HipMomentY',
            'HipFlexExt': 'HipAnglesX',
            'HipFlexExtMoment': 'HipMomentX',
            'HipPower': 'HipPowerZ',
            'HipRotation': 'HipAnglesZ',
            'HipRotationMoment': 'HipMomentZ',
            'KneeFlexExt': 'KneeAnglesX',
            'KneeFlexExtMoment': 'KneeMomentX',
            'KneePower': 'KneePowerZ',
            'KneeRotation': 'KneeAnglesZ',
            'KneeRotationMoment': 'KneeMomentZ',
            'KneeValgVar': 'KneeAnglesY',
            'KneeValgVarMoment': 'KneeMomentY',
            'PelvicObliquity': 'PelvisAnglesY',
            'PelvicRotation': 'PelvisAnglesZ',
            'PelvicTilt': 'PelvisAnglesX'}

# add some space for the labels between units and directions
spacer = (2*(1*' ',))
pig_lowerbody.ylabels = _dict_with_side({
                         'AnkleAnglesX': 'Pla%s($^\\circ$)%sDor' % spacer,
                         'AnkleAnglesY': 'Abd%s($^\\circ$)%sAdd' % spacer,
                         'AnkleAnglesZ': 'Ext%s($^\\circ$)%sInt' % spacer,
                         'AnkleMomentX': 'Idors%sNm/kg%sIplan' % spacer,
                         'AnkleMomentY': 'Iadd%sNm/kg%sIabd' % spacer,
                         # FIXME: not sure about directions of rotation:
                         'AnkleMomentZ': '%sNm/kg%s' % spacer,
                         'AnklePowerZ': 'Abs%sW/kg%sGen' % spacer,
                         'FootProgressAnglesZ': 'Ext%s($^\\circ$)%sInt' % spacer,
                         'HipAnglesX': 'Ext%s($^\\circ$)%sFlex' % spacer,
                         'HipAnglesY': 'Abd%s($^\\circ$)%sAdd' % spacer,
                         'HipAnglesZ': 'Ext%s($^\\circ$)%sInt' % spacer,
                         'HipMomentX': 'Iflex%sNm/kg%sIext' % spacer,
                         'HipMomentY': 'Iadd%sNm/kg%sIabd' % spacer,
                         'HipMomentZ': 'Iflex%sNm/kg%sIext' % spacer,
                         'HipPowerZ': 'Abs%sW/kg%sGen' % spacer,
                         'KneeAnglesX': 'Ext%s($^\\circ$)%sFlex' % spacer,
                         'KneeAnglesY': 'Val%s($^\\circ$)%sVar' % spacer,
                         'KneeAnglesZ': 'Ext%s($^\\circ$)%sInt' % spacer,
                         'KneeMomentX': 'Iflex%sNm/kg%sIext' % spacer,
                         'KneeMomentY': 'Ivar%sNm/kg%sIvalg' % spacer,
                         'KneeMomentZ': 'Iflex%sNm/kg%sIext' % spacer,
                         'KneePowerZ': 'Abs%sW/kg%sGen' % spacer,
                         'PelvisAnglesX': 'Pst%s($^\\circ$)%sAnt' % spacer,
                         'PelvisAnglesY': 'Dwn%s($^\\circ$)%sUp' % spacer,
                         'PelvisAnglesZ': 'Bak%s($^\\circ$)%sFor' % spacer})

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

musclelen.is_kinetic_var = lambda varname: False

musclelen.ylabels = {}
for var in musclelen.varnames:
    musclelen.ylabels[var] = 'Length norm.'

models_all.append(musclelen)
