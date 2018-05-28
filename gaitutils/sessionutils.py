# -*- coding: utf-8 -*-
"""
Patient info functions

FIXME: refactor session related funcs into session.py ?

@author: Jussi (jnu@iki.fi)
"""


def default_info:
    return dict(fullname=None, hetu=None, session_description=None)

    pdata = self._load_patient_data(session)
    pdata.update(patient_data)


def load_info(self, session):
    """Return the patient info dict from the given session"""
    fname = op.join(session, 'patient_info.json')
    if op.isfile(fname):
        with io.open(fname, 'r', encoding='utf-8') as f:
            try:
                patient_data.update(json.load(f))
            except (UnicodeDecodeError, EOFError, IOError, TypeError):
                raise ValueError('Error loading patient info file %s' % fname)
        return patient_data
    else:
        return None


def save_info(self, session, patient_info):
    """Save patient info. Existing unmodified keys will be kept."""
    fname = op.join(session, 'patient_info.json')
    try:
        with io.open(fname, 'w', encoding='utf-8') as f:
            f.write(unicode(json.dumps(patient_info, ensure_ascii=False)))
    except (UnicodeDecodeError, EOFError, IOError, TypeError):
        raise ValueError('Error saving patient info file %s ' % fname)

