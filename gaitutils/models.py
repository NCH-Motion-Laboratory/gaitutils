# -*- coding: utf-8 -*-
"""

Definitions for various gait related models (Plug-in Gait etc.)

To create a new model, create a GaitModel() instance, fill in the data and
append to models_all.

@author: Jussi (jnu@iki.fi)
"""

from collections import defaultdict

# list of all our models
models_all = list()


def model_from_var(var_):
    """Return model corresponding to a variable.

    Parameters
    ----------
    var_ : str
        The variable name.

    Returns
    -------
    GaitModel | None
        The model. None if no models contain the given variable.
    """
    if var_ is None:
        return None
    elif not isinstance(var_, str):
        raise TypeError('Variable name must be a string or None')
    for model in models_all:
        if var_ in model.varnames or var_ in model.varnames_nocontext:
            return model
    return None


# convenience methods for model creation


def _list_with_context(vars_):
    """Prepend variable names in vars_ with 'L' and 'R'."""
    return [context + var for var in vars_ for context in 'LR']


def _dict_with_context_gen(di, append_context=False):
    """Prepend all dict keys in di with 'R' and 'L' and return new dict.
    If append_context, also append corresponding ' (R)' or ' (L)' to every dict
    value."""
    for key, val in di.items():
        for ctxt in 'RL':
            if append_context:
                yield ctxt + key, f'{val} ({ctxt})'
            else:
                yield ctxt + key, val


def _dict_with_context(di, append_context=False):
    """Prepend all dict keys in di with 'R' and 'L' and return new dict.
    If append_context, also append corresponding ' (R)' or ' (L)' to every dict
    value."""
    return dict(_dict_with_context_gen(di, append_context=append_context))


class GaitModel:
    """A class for storing information about a gait model.

    The data describes model-specific variable names etc. and is intended
    (currently not forced) to be non-mutable. The actual data is stored
    elsewhere.
    """

    def __init__(self):
        self.read_vars = list()  # vars to be read from data
        # How to read multidimensional variables: 'split_xyz' splits each
        # variable into x,y,z components and names them appropriately.
        # 'last' reads the last component only (c3d scalars are saved
        # as last component of 3-d array (??))
        self.read_strategy = None
        self.desc = ''  # description of model
        self.varnames = list()  # resulting variable names
        self.varnames_nocontext = list()  # variables without context
        self.varlabels_nocontext = dict()  # variables without context
        self.varlabels = dict()  # descriptive label for each variable
        # mapping from variable names to gcd normal data variables
        self.gcd_normaldata_map = dict()
        # units for the variables
        self.units = dict()
        # description of neg/pos dirs for each variable in
        # tuples, e.g. ('Plantarflexion', 'Dorsiflexion')
        self.ydesc = dict()
        # callable to return whether var requires valid forceplate contact
        self.is_kinetic_var = lambda var: False


"""Create the models"""

#
# Oxford foot model
#
ofm = GaitModel()
ofm.desc = 'Oxford foot model kinematics'
ofm.read_strategy = 'split_xyz'

ofm.read_vars = _list_with_context(
    ['FFHFA', 'FFTBA', 'HFTBA', 'HFTFL', 'HXFFA', 'TIBA']
)

ofm.varlabels_nocontext = {
    'FFHFAX': 'Forefoot-hindfoot dorsiflexion',
    'FFHFAY': 'Forefoot-hindfoot adduction',
    'FFHFAZ': 'Forefoot-hindfoot supination',
    'FFTBAX': 'Forefoot-tibia dorsiflexion',
    'FFTBAY': 'Forefoot-tibia adduction',
    'FFTBAZ': 'Forefoot-tibia supination',
    'HFTBAX': 'Hindfoot-tibia dorsiflexion',
    'HFTBAY': 'Hindfoot-tibia rotation',
    'HFTBAZ': 'Hindfoot-tibia inversion',
    'HFTFLX': 'Hindfoot-lab dorsiflexion',
    'HFTFLY': 'Hindfoot-lab rotation',
    'HFTFLZ': 'Hindfoot-lab inversion',
    'HXFFAX': 'Hallux-forefoot dorsiflexion',
    'HXFFAY': 'Hallux-forefoot varus',
    'HXFFAZ': 'NA',
    'TIBAX': 'Tibia-lab forward tilt',
    'TIBAY': 'Tibia-lab lateral tilt',
    'TIBAZ': 'Tibia internal rotation',
}

ofm.units = defaultdict(lambda: 'deg')
ofm.ydesc = _dict_with_context(
    {
        'FFHFAX': ('Plantarflexion', 'Dorsiflexion'),
        'FFHFAY': ('Abduction', 'Adduction'),
        'FFHFAZ': ('Pronation', 'Supination'),
        'FFTBAX': ('Plantarflexion', 'Dorsiflexion'),
        'FFTBAY': ('Abduction', 'Adduction'),
        'FFTBAZ': ('Pronation', 'Supination'),
        'HFTBAX': ('Plantarflexion', 'Dorsiflexion'),
        'HFTBAY': ('External', 'Internal'),
        'HFTBAZ': ('Eversion', 'Inversion'),
        'HFTFLX': ('Plantarflexion', 'Dorsiflexion'),
        'HFTFLY': ('External', 'Internal'),
        'HFTFLZ': ('Eversion', 'Inversion'),
        'HXFFAX': ('Plantarflexion', 'Dorsiflexion'),
        'HXFFAY': ('Valgus', 'Varus'),
        'HXFFAZ': ('NA', 'NA'),
        'TIBAX': ('Backward', 'Forward'),
        'TIBAY': ('Distal', 'Lateral'),
        'TIBAZ': ('External', 'Internal'),
    }
)


ofm.varlabels = _dict_with_context(ofm.varlabels_nocontext)
ofm.varnames = ofm.varlabels.keys()
ofm.varnames_nocontext = ofm.varlabels_nocontext.keys()

models_all.append(ofm)


#
# Plug-in Gait upper body kinematics
#
pig_upperbody = GaitModel()
pig_upperbody.desc = 'Plug-in Gait upper body kinematics'
pig_upperbody.read_strategy = 'split_xyz'

pig_upperbody.read_vars = _list_with_context(
    [
        'ThoraxAngles',
        'ShoulderAngles',
        'SpineAngles',
        'WristAngles',
        'ElbowAngles',
        'NeckAngles',
        'HeadAngles',
    ]
)

pig_upperbody.varlabels_nocontext = {
    'ThoraxAnglesX': 'Thorax flex/ext',
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
    'ElbowAnglesY': 'Elbow y angle',
    'ElbowAnglesZ': 'Elbow rotation',
    'NeckAnglesX': 'Neck sagittal',
    'NeckAnglesY': 'Neck frontal',
    'NeckAnglesZ': 'Neck rotation',
    'HeadAnglesX': 'Head sagittal',
    'HeadAnglesY': 'Head frontal',
    'HeadAnglesZ': 'Head rotation',
}

# FIXME: for now, ylabel is just the degree sign for all vars
pig_upperbody.units = defaultdict(lambda: 'deg')
# FIXME: incomplete y descriptions
pig_upperbody.ydesc = defaultdict(lambda: ('', ''))  # FIXME: see Vicon docs
upperbody_ydesc_partial = _dict_with_context(
    {
        'ThoraxAnglesX': ('Backward', 'Forward'),
        'ThoraxAnglesY': ('Lateral', 'Medial'),
        'ThoraxAnglesZ': ('Anterior', 'Posterior'),
    }
)
pig_upperbody.ydesc.update(upperbody_ydesc_partial)
pig_upperbody.varlabels = _dict_with_context(pig_upperbody.varlabels_nocontext)
pig_upperbody.varnames = pig_upperbody.varlabels.keys()
pig_upperbody.varnames_nocontext = pig_upperbody.varlabels_nocontext.keys()

models_all.append(pig_upperbody)


#
# Plug-in Gait lower body kinematics
#
pig_lowerbody = GaitModel()
pig_lowerbody.desc = 'Plug-in Gait lower body kinematics'
pig_lowerbody.read_strategy = 'split_xyz'
pig_lowerbody.read_vars = _list_with_context(
    [
        'HipAngles',
        'KneeAngles',
        'AnkleAngles',
        'ForeFootAngles',
        'PelvisAngles',
        'FootProgressAngles',
    ]
)

pig_lowerbody.varlabels_nocontext = {
    'AnkleAnglesX': 'Ankle dorsi/plant',
    'AnkleAnglesY': 'Ankle adduction',
    'AnkleAnglesZ': 'Ankle rotation',
    'FootProgressAnglesZ': 'Foot progress angles',
    'ForeFootAnglesX': 'Fore/hindfoot dorsi/plant',
    'ForeFootAnglesY': 'Fore/hindfoot adduction',
    'ForeFootAnglesZ': 'Fore/hindfoot inversion',
    'HipAnglesX': 'Hip flexion',
    'HipAnglesY': 'Hip adduction',
    'HipAnglesZ': 'Hip rotation',
    'KneeAnglesX': 'Knee flexion',
    'KneeAnglesY': 'Knee adduction',
    'KneeAnglesZ': 'Knee rotation',
    'PelvisAnglesX': 'Pelvic tilt',
    'PelvisAnglesY': 'Pelvic obliquity',
    'PelvisAnglesZ': 'Pelvic rotation',
}

pig_lowerbody.varlabels = _dict_with_context(pig_lowerbody.varlabels_nocontext)

pig_lowerbody.varnames = pig_lowerbody.varlabels.keys()
pig_lowerbody.varnames_nocontext = pig_lowerbody.varlabels_nocontext.keys()

pig_lowerbody.gcd_normaldata_map = {
    'DorsiPlanFlex': 'AnkleAnglesX',
    'FootProgression': 'FootProgressAnglesZ',
    'FootRotation': 'AnkleAnglesZ',
    'HipAbAdduct': 'HipAnglesY',
    'HipFlexExt': 'HipAnglesX',
    'HipRotation': 'HipAnglesZ',
    'KneeFlexExt': 'KneeAnglesX',
    'KneeRotation': 'KneeAnglesZ',
    'KneeValgVar': 'KneeAnglesY',
    'PelvicObliquity': 'PelvisAnglesY',
    'PelvicRotation': 'PelvisAnglesZ',
    'PelvicTilt': 'PelvisAnglesX',
}

# unit is degrees for each kinematic variable
pig_lowerbody.units = defaultdict(lambda: 'deg')

pig_lowerbody.ydesc = _dict_with_context(
    {
        'AnkleAnglesX': ('Plantarflexion', 'Dorsiflexion'),
        'AnkleAnglesY': ('Abduction', 'Adduction'),
        'AnkleAnglesZ': ('External', 'Internal'),
        'FootProgressAnglesZ': ('External', 'Internal'),
        'ForeFootAnglesX': ('Plantarflexion', 'Dorsiflexion'),
        'ForeFootAnglesY': ('Abduction', 'Adduction'),
        'ForeFootAnglesZ': ('Eversion', 'Inversion'),
        'HipAnglesX': ('Extension', 'Flexion'),
        'HipAnglesY': ('Abduction', 'Adduction'),
        'HipAnglesZ': ('External', 'Internal'),
        'KneeAnglesX': ('Extension', 'Flexion'),
        'KneeAnglesY': ('Valgus', 'Varus'),
        'KneeAnglesZ': ('External', 'Internal'),
        'PelvisAnglesX': ('Posterior', 'Anterior'),
        'PelvisAnglesY': ('Down', 'Up'),
        'PelvisAnglesZ': ('External', 'Internal'),
    }
)

models_all.append(pig_lowerbody)


#
# Plug-in Gait lowerbody kinetics
#
pig_lowerbody_kinetics = GaitModel()
pig_lowerbody_kinetics.desc = 'Plug-in Gait lower body kinetics'
pig_lowerbody_kinetics.read_strategy = 'split_xyz'
pig_lowerbody_kinetics.read_vars = _list_with_context(
    [
        'HipMoment',
        'KneeMoment',
        'AnkleMoment',
        'HipPower',
        'KneePower',
        'AnklePower',
        'NormalisedGRF',
    ]
)

pig_lowerbody_kinetics.varlabels_nocontext = {
    'AnkleMomentX': 'Ankle dors/plan moment',
    'AnkleMomentY': 'Ankle ab/add moment',
    'AnkleMomentZ': 'Ankle rotation moment',
    'AnklePowerZ': 'Ankle power',
    'HipMomentX': 'Hip flex/ext moment',
    'HipMomentY': 'Hip ab/add moment',
    'HipMomentZ': 'Hip rotation moment',
    'HipPowerZ': 'Hip power',
    'KneeMomentX': 'Knee flex/ext moment',
    'KneeMomentY': 'Knee ab/add moment',
    'KneeMomentZ': 'Knee rotation moment',
    'KneePowerZ': 'Knee power',
    'NormalisedGRFX': 'Norm. GRF (x)',
    'NormalisedGRFY': 'Norm. GRF (y)',
    'NormalisedGRFZ': 'Norm. GRF (z)',
}

pig_lowerbody_kinetics.varlabels = _dict_with_context(
    pig_lowerbody_kinetics.varlabels_nocontext
)

pig_lowerbody_kinetics.varnames = pig_lowerbody_kinetics.varlabels.keys()
pig_lowerbody_kinetics.varnames_nocontext = (
    pig_lowerbody_kinetics.varlabels_nocontext.keys()
)

pig_lowerbody_kinetics.gcd_normaldata_map = {
    'AnklePower': 'AnklePowerZ',
    'DorsiPlanFlexMoment': 'AnkleMomentX',
    'FootAbAdductMoment': 'AnkleMomentY',
    'FootRotationMoment': 'AnkleMomentZ',
    'HipAbAdductMoment': 'HipMomentY',
    'HipFlexExtMoment': 'HipMomentX',
    'HipPower': 'HipPowerZ',
    'HipRotationMoment': 'HipMomentZ',
    'KneeFlexExtMoment': 'KneeMomentX',
    'KneePower': 'KneePowerZ',
    'KneeRotationMoment': 'KneeMomentZ',
    'KneeValgVarMoment': 'KneeMomentY',
}

pig_lowerbody_kinetics.units = _dict_with_context(
    {
        'AnkleMomentX': 'Nm/kg',
        'AnkleMomentY': 'Nm/kg',
        'AnkleMomentZ': 'Nm/kg',
        'AnklePowerZ': 'W/kg',
        'HipMomentX': 'Nm/kg',
        'HipMomentY': 'Nm/kg',
        'HipMomentZ': 'Nm/kg',
        'HipPowerZ': 'W/kg',
        'KneeMomentX': 'Nm/kg',
        'KneeMomentY': 'Nm/kg',
        'KneeMomentZ': 'Nm/kg',
        'KneePowerZ': 'W/kg',
        'NormalisedGRFX': '%BW',
        'NormalisedGRFY': '%BW',
        'NormalisedGRFZ': '%BW',
    }
)

pig_lowerbody_kinetics.ydesc = _dict_with_context(
    {
        'AnkleMomentX': ('Dorsiflexion', 'Plantarflexion'),
        'AnkleMomentY': ('Adduction', 'Abduction'),
        'AnkleMomentZ': ('Internal', 'External'),  # FIXME: check
        'AnklePowerZ': ('Absorbing', 'Generating'),
        'HipMomentX': ('Flexion', 'Extension'),
        'HipMomentY': ('Adduction', 'Abduction'),
        'HipMomentZ': ('Internal', 'External'),
        'HipPowerZ': ('Absorbing', 'Generating'),
        'KneeMomentX': ('Flexion', 'Extension'),
        'KneeMomentY': ('Varus', 'Valgus'),
        'KneeMomentZ': ('Internal', 'External'),
        'KneePowerZ': ('Absorbing', 'Generating'),
        'NormalisedGRFX': ('', ''),
        'NormalisedGRFY': ('', ''),
        'NormalisedGRFZ': ('Downward', 'Upward'),
    }
)

pig_lowerbody_kinetics.is_kinetic_var = lambda varname: True

models_all.append(pig_lowerbody_kinetics)

#
# Muscle length (MuscleLength.mod)
#

musclelen = GaitModel()
musclelen.desc = 'Muscle length (MuscleLength.mod)'
musclelen.read_strategy = 'last'

musclelen.varlabels_nocontext = {
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
    'VaMeLength': 'VaMeLength',
}

musclelen.varlabels = _dict_with_context(musclelen.varlabels_nocontext)
musclelen.read_vars = musclelen.varlabels.keys()
musclelen.varnames = musclelen.read_vars
musclelen.varnames_nocontext = musclelen.varlabels_nocontext.keys()

musclelen.units = defaultdict(lambda: 'Norm length')  # FIXME: % of what?
musclelen.ydesc = defaultdict(lambda: ('', ''))

models_all.append(musclelen)
