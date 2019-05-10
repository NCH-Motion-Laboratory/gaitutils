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


def is_proper_varname(s):
    """Checks for valid identifier"""
    p = re.compile('^[\w]+$')  # accept only alphanumeric chars, no whitespace
    return bool(p.match(s))        
    

def parse_var_def(s):
    """Match var definition. Return varname, val if successful"""
    p = re.compile('^([^=]+)=([^=]+)$')
    m = p.match(s)
    if m:
        varname, val = m.group(1).strip(), m.group(2).strip()
        if is_proper_varname(varname):
            return varname, val
    return None, None


def is_list_def(s):
    """Match (start of) list or dict definition"""
    varname, val = parse_var_def(s)
    if val is None:
        return False
    else:
        # do not include closing ] or }, as it may be a multiline def
        p = re.compile('[\s]*[\[,\{][\S]+[\s]*')
        return bool(p.match(val))


def parse_section_header(s):
    """Match section headers of form [header] and return header as str"""
    p = re.compile('^\[([\w]*)\]$')
    m = p.match(s)
    return m.group(1) if m else None
    


def not_whitespace(s):
    """Non-whitespace line, should be a continuation of definition"""
    p = re.compile('[\s]*[\S]+')  # match non whitespace-only lines
    return bool(p.match(s))



class ConfigItem:
    """Holds data for a config item"""
    # FIXME: this should not hold def lines, but a complete def

    def __init__(self, comments=None, def_lines=None):
        self.comments = comments or list()
        self.def_lines = def_lines or list()

    @property
    def comment(self):
        return '\n'.join(self.comments)
    
    @property
    def value(self):
        _, val = parse_var_def(''.join(self.def_lines))
        return val

    def __repr__(self):
        return self.value or '<malformed config item>'


class Section(object):
    """Holds data for a config section"""
    def __init__(self, comments=None, items=None):
        self.__dict__['_configitems'] = items or dict()
        self.__dict__['_comments'] = comments or dict()

    def __getattr__(self, item):
        """Returns the value for a config item"""
        return self._configitems[item]

    def __setattr__(self, item, value):
        if not isinstance(value, ConfigItem):
            raise ValueError('value must be a ConfigItem instance')
        self.__dict__['_configitems'][item] = value
        
    @property
    def configitems(self):
        return self._configitems

    def __repr__(self):
        s = '<Section|'
        s += ' items: %s' % str(self._configitems.keys())
        s += '>'
        return s
    

class Config:
    """Main config object that holds sections and config items. Sections can be
    accessed and set by the syntax config.section"""
    def __init__(self, sections=None):
        self.__dict__['_sections'] = sections or dict()
        
    def __getattr__(self, section):
        return self._sections[section]
    
    def __setattr__(self, item, value):
        if not isinstance(value, Section):
            raise ValueError('value must be a Section instance')
        self.__dict__['_sections'][item] = value
        
    def __repr__(self):
        s = '<Config|'
        s += ' sections: %s' % str(self._sections.keys())
        s += '>'
        return s
    
    def sections(self):
        return self._sections
        
       
def parse_config(lines):
    """Parse cfg lines (ConfigParser format) into a Config instance"""
    _comments = list()  # comments for current variable
    current_section = None
    current_var = None
    config = Config()
    for li in lines:
        secname = parse_section_header(li)
        varname, val = parse_var_def(li)
        if secname:
            current_section = Section(comments=_comments)
            setattr(config, secname, current_section)
            _comments = list()
            current_var = None
        elif is_comment(li):
            # collect comments until we encounter next section header or variable
            _comments.append(li)
        elif varname is not None:
            if current_section is None:
                raise ValueError('variable definition outside a section')
            current_var = ConfigItem(comments=_comments, def_lines=[li])
            setattr(current_section, varname, current_var)
            _comments = list()
        elif not_whitespace(li):  # (hopefully) continuation of var definition
            if current_var is None:
                raise ValueError('continuation outside of variable definition')
            current_var.def_lines.append(li.strip())
    return config


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
            

#with open(r"C:\Users\hus20664877\gaitutils\gaitutils\data\default.cfg", 'r') as f:
#    lines = f.read().splitlines()

#cfg = cfg_di(lines)

#for li in clean_cfg(lines):
#    print(li)

# lic = list(clean_cfg(lines))

