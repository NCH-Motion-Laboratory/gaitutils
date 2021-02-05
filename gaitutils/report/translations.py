# -*- coding: utf-8 -*-
"""
Translate text.

@author: Jussi (jnu@iki.fi)
"""

import logging

from ..config import cfg

logger = logging.getLogger(__name__)


translations = dict()
translations['finnish'] = {
    'Comparison report': u'Vertailuraportti',
    'Patient code': u'Potilaskoodi',
    'Session date': u'Mittauksen päivämäärä',
    'Normal data': u'Normaalidata',
    'Session': u'Mittaus',
    'Description': u'Kuvaus',
    'vuotta': u'years',
    'Age at time of measurement': u'Ikä mittaushetkellä',
    'unknown': u'ei tiedossa',
    'Social security number': u'Henkilötunnus',
    'Name': u'Nimi',
    'Results of gait analysis': u'Kävelyanalyysin tulokset',
    'Right': u'Oikea',
    'Left': u'Vasen',
    'R': u'O',
    'L': u'V',
    'Time-distance variables': u'Matka-aikamuuttujat',
    'Single Support': u'Yksöistukivaihe',
    'Double Support': u'Kaksoistukivaihe',
    'Opposite Foot Contact': u'Vastakkaisen jalan kontakti',
    'Opposite Foot Off': u'Vastakkainen jalka irti',
    'Limp Index': u'Limp-indeksi',
    'Step Length': u'Askelpituus',
    'Foot Off': u'Tukivaiheen kesto',
    'Walking Speed': u'Kävelynopeus',
    'Stride Length': u'Askelsyklin pituus',
    'Step Width': u'Askelleveys',
    'Step Time': u'Askeleen kesto',
    'Cadence': u'Kadenssi',
    'Stride Time': u'Askelsyklin kesto',
    'steps/min': u'1/min',
}

# make case insensitive
for lang, trans in translations.items():
    translations.pop(lang)
    translations[lang.lower()] = trans
    for key, val in trans.items():
        trans.pop(key)
        trans[key.lower()] = val


def translate(text):
    """Simple mechanism for translating words and expressions.

    The translation language is taken from the config. Currently supported
    values: 'finnish'. If None, do not translate.

    Parameters
    ----------
    text : str
        Word or expression to translate.

    Returns
    -------
    str
        The translated text.
    """
    global translations
    language = cfg.report.language
    if language is None:
        return text
    elif language not in translations:
        raise ValueError('Unknown translation language')
    elif text.lower() not in translations[language]:
        logger.info('no translation for %s' % text)
        return text
    else:
        return translations[language][text.lower()]
