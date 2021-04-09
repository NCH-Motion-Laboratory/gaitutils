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
    'Comparison report': 'Vertailuraportti',
    'Patient code': 'Potilaskoodi',
    'Session date': 'Mittauksen päivämäärä',
    'Normal data': 'Normaalidata',
    'Session': 'Mittaus',
    'Description': 'Kuvaus',
    'Years': 'vuotta',
    'Age at time of measurement': 'Ikä mittaushetkellä',
    'unknown': 'ei tiedossa',
    'Social security number': 'Henkilötunnus',
    'Name': 'Nimi',
    'Results of gait analysis': '3D-kävelyanalyysin tulokset',
    'Right': 'Oikea',
    'Left': 'Vasen',
    'R': 'O',
    'L': 'V',
    'Time-distance variables': 'Matka-aikamuuttujat',
    'Single Support': 'Yksöistukivaihe',
    'Double Support': 'Kaksoistukivaihe',
    'Opposite Foot Contact': 'Vastakkaisen jalan kontakti',
    'Opposite Foot Off': 'Vastakkainen jalka irti',
    'Limp Index': 'Limp-indeksi',
    'Step Length': 'Askelpituus',
    'Foot Off': 'Tukivaiheen kesto',
    'Walking Speed': 'Kävelynopeus',
    'Stride Length': 'Askelsyklin pituus',
    'Step Width': 'Askelleveys',
    'Step Time': 'Askeleen kesto',
    'Cadence': 'Kadenssi',
    'Stride Time': 'Askelsyklin kesto',
    'steps/min': '1/min',
}

# rewrite keys in lower case
translations = {key.lower(): val for key, val in translations.items()}
for key, val in translations.items():
    translations[key] = {lang.lower(): trans_di for lang, trans_di in val.items()}


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
