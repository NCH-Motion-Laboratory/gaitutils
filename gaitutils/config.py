# -*- coding: utf-8 -*-
"""
Handles gaitutils config files.

@author: Jussi (jnu@iki.fi)
"""
from __future__ import print_function

from builtins import str
from builtins import object
import ast
import os.path as op
import os
import sys
import re
from pkg_resources import resource_filename

from . import envutils


""" Work around stdout and stderr not being available, if we are run
using pythonw.exe on Windows. Without this, exception will be raised
e.g. on any print statement. """
if (sys.platform.find('win') != -1 and sys.executable.find('pythonw') != -1 and
   not envutils.run_from_ipython()):
    blackhole = open(os.devnull, 'w')
    sys.stdout = sys.stderr = blackhole

# default config
cfg_template = resource_filename(__name__, 'data/default.cfg')
# user specific config
# On Windows, this typically puts the config at C:\Users\Username, since the
# USERPROFILE environment variable points there. Putting the config in a
# networked home dir requires some tinkering with environment variables
# (e.g. setting HOME)
homedir = op.expanduser('~')
cfg_user = op.join(homedir, '.gaitutils.cfg')


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
    def __init__(self, comments=None, def_lines=None):
        if comments is None:
            comments = list()
        elif not isinstance(comments, list):
            comments = [comments]
        self._comments = comments
        if def_lines is not None:
            self._def_lines = def_lines
            
    def get_comment(self):
        return '\n'.join(self._comments)
    
    def _get_literal_value(self):
        varname, val = parse_var_def(''.join(self._def_lines))
        return val
        
    def get_value(self):
        val = self._get_literal_value()
        return ast.literal_eval(val)
    
    def update_value(self, value):
        varname, _ = parse_var_def(''.join(self._def_lines))
        defline = '%s = %s' % (varname, repr(value))
        self._def_lines = [defline]

    def __repr__(self):
        return self._get_literal_value() or '<malformed config item>'


class Section(object):
    """Holds data for a config section"""
    def __init__(self, comments=None, items=None):
        # need to modify __dict__ directly to avoid infinite __setattr__ loop
        self.__dict__['_items'] = items or dict()
        self.__dict__['_comments'] = comments or dict()

    def __getattr__(self, attr):
        """Returns the value for a config item. This allows syntax of 
        cfg.section.item"""
        return self._items[attr].get_value()
    
    def __getitem__(self, item):
        """Returns a config item"""
        return self._items[item]
        
    def __setattr__(self, item, value):
        if not isinstance(value, ConfigItem):
            raise ValueError('value must be a ConfigItem instance')
        self.__dict__['_items'][item] = value
        
    def get_comment(self):
        return '\n'.join(self._comments)
    
    def get_description(self):
        """Parse section comment into a descriptive section name"""
        p = re.compile('^[\s]*#[\s]*(.+)')
        m = p.match(self.get_comment())             
        if m:
            return m.group(1).strip()

    def get_items(self):
        return self._items

    def __repr__(self):
        s = '<Section|'
        s += ' items: %s' % str(self._items.keys())
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
    
    def get_sections(self):
        return self._sections
        
       
def parse_config(filename):
    """Parse cfg lines (ConfigParser format) into a Config instance"""
    with open(filename, 'r') as f:
        lines = f.read().splitlines()
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
        elif varname is not None:
            if current_section is None:
                raise ValueError('variable definition outside a section')
            current_var = ConfigItem(comments=_comments, def_lines=[li])
            setattr(current_section, varname, current_var)
            _comments = list()
        elif is_comment(li):
            # collect comments until we encounter next section header or variable
            _comments.append(li)
        elif not_whitespace(li):  # (hopefully) continuation of var definition
            if current_var is None:
                raise ValueError('continuation outside of variable definition')
            current_var._def_lines.append(li.strip())
    return config


def update_config(cfg, filename):
    """Update existing Config from lines"""
    cfg_new = parse_config(filename)
    for secname, sec in cfg_new.get_sections().items():
        sec_old = getattr(cfg, secname)
        items_old = sec_old.get_items()
        for itname, item in sec.get_items().items():
            if itname not in items_old:
                pass
                #logger.warning('unknown item %s' % itname)
            else:
                # only modify definition, not comments
                items_old[itname]._def_lines = item._def_lines


def dump_config(cfg):
    """Produce text version of Config instance that can be read back"""
    def _gen_dump(cfg):
        sectnames = sorted(cfg.get_sections().keys())
        for k, sectname in enumerate(sectnames):
            if k > 0:
                yield ''
            sect = getattr(cfg, sectname)
            sect_comment = sect.get_comment()
            if sect_comment:
                yield sect_comment
            yield '[%s]' % sectname
            for itemname, item in sect.get_items().items():
                yield item.get_comment()
                yield item._format_def()
    return '\n'.join(_gen_dump(cfg))


# provide the global cfg instance
# read template config
cfg = parse_config(cfg_template)
if op.isfile(cfg_user):
    update_config(cfg, cfg_user)
else:
    print('no config file, trying to create %s' % cfg_user)
    cfg_txt = dump_config(cfg)
    with open(cfg_user, 'w', encoding='utf8') as f:
        f.writelines(cfg_txt)

# handle some deprecated/changed types for user convenience
if not isinstance(cfg.plot.emg_yscale, float):
    ysc = cfg.plot.emg_yscale[1]
    print('WARNING: emg_yscale was changed to float, using %g' % ysc)
    cfg.plot.emg_yscale = str(cfg.plot.emg_yscale[1])
if cfg.general.normaldata_files == 'default':
    fn = resource_filename('gaitutils', 'data/normal.gcd')
    cfg.general['normaldata_files'].update_value(fn)
if cfg.general.videoconv_path == 'default':
    fn = resource_filename('gaitutils', 'thirdparty/ffmpeg2theora.exe')
    cfg.general['videoconv_path'].update_value(fn)



sys.stdout.flush()  # make sure that warnings are printed out
