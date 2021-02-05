# -*- coding: utf-8 -*-
"""
Translate text.

@author: Jussi (jnu@iki.fi)
"""

import logging

logger = logging.getLogger(__name__)


translations = dict()
translations['finnish'] = {
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


def translate(text, language=None):
    """Simple mechanism for translating text.

    Parameters
    ----------
    text : str
        Text to translate. Currently requires exact case match.
    language : str
        Translation language. Currently supported: 'finnish'

    Returns
    -------
    str
        The translated text.
    """
    global translations
    if language is None:
        return text
    elif language not in translations:
        raise ValueError('Unknown translation language')
    elif text not in translations[language]:
        logger.info('no translation for %s' % text)
        return text
    else:
        return translations[language][text]
