# -*- coding: utf-8 -*-
"""
Clean up configparser cfg file:
-remove extra whitespace
-sort sections by headers
-sort variable defs by variable, keeping comment lines for each var
-properly indent list and dict type variables

"""

from __future__ import print_function
import re




def is_comment(s):
    """Match line comment starting with # or ;"""
    p = re.compile('[\s]*[#;].*')
    return bool(p.match(s))        


def is_var_def(s):
    """Match var definition"""
    p = re.compile('[\s]*[\S]+[\s]*=[\s]*[\S]+[\s]*')
    return bool(p.match(s))


def is_list_def(s):
    """Match list or dict definition"""
    p = re.compile('[\s]*[\S]+[\s]*=[\s]*[\[,\{][\S]+[\s]*')
    return bool(p.match(s))


def is_section_header(s):
    """Match section headers of form [string]"""
    p = re.compile('^\[[\w]*\]$')
    return bool(p.match(s))


def not_whitespace(s):
    """Non-whitespace line, should be a continuation of definition"""
    p = re.compile('[\s]*[\S]+')  # match whitespace-only lines
    return bool(p.match(s))




class Var:
    """Holds data for a config variable"""
    def __init__(self, comments=None, def_lines=None):
        self.comments = comments or list()
        self.def_lines = def_lines or list()


class Section:
    """Holds data for a config section"""
    def __init__(self, comments=None, sectvars=None):
        self.comments = comments or list()
        self.sectvars = sectvars or dict()
        
        


def cfg_di(lines):
    """Parse cfg lines into a dict"""
    _comments = list()  # comments for current variable
    this_section = None
    cfg_di = dict()
    for li in lines:
        if is_section_header(li):
            this_section = li
            cfg_di[this_section] = Section(comments=_comments)
            _comments = list()
        elif is_comment(li):
            # collect comments until we encounter next section header or variable
            _comments.append(li)
        elif is_var_def(li):
            if this_section is None:
                raise ValueError('definition outside a section')
            var = li.split('=')[0]
            cfg_di[this_section].sectvars[var] = Var(comments=_comments,
                                                     def_lines=[li])
            _comments = list()
            # get indentation for list-type defs so it can be preserved
            if is_list_def(li):
                idnt = max(li.find('['), li.find('{'))
        elif not_whitespace(li):  # continuation line
            if var in cfg_di[this_section].sectvars:
                if idnt is not None and idnt > 0:  # indent also def continuation lines
                    li = (idnt + 1) * ' ' + li.strip()
                cfg_di[this_section].sectvars[var].def_lines.append(li)
    return cfg_di


def clean_cfg(lines):

    di = cfg_di(lines)
            
    # compose output
    for i, sect in enumerate(sorted(di.keys())):
        if i > 0:
            yield ''
        if di[sect][datatypes.comments]:
            yield '\n'.join(di[sect][datatypes.comments])
        yield sect
        # whether section has var definitions spanning multiple lines
        has_multiline_defs = any(len(di[sect][var][datatypes.def_lines]) > 1
                                 for var in di[sect][datatypes.varlist])
        for var in sorted(di[sect][datatypes.varlist]):
            # print comments and definition for this var
            if di[sect][var][datatypes.comments]:
                yield '\n'.join(di[sect][var][datatypes.comments])
            def_this = di[sect][var][datatypes.def_lines]
            yield '\n'.join(def_this)
            # output extra whitespace for sections that have multiline defs
            if has_multiline_defs:
                yield ''
            

with open(r"C:\Users\hus20664877\gaitutils\gaitutils\data\default.cfg", 'r') as f:
    lines = f.read().splitlines()

di = cfg_di(lines)

#for li in clean_cfg(lines):
#    print(li)

# lic = list(clean_cfg(lines))

