# -*- coding: utf-8 -*-
"""
Handles gaitutils config files.

@author: Jussi (jnu@iki.fi)
"""
from __future__ import print_function

from builtins import str
from builtins import object
import ast
import re
import logging


logger = logging.getLogger(__name__)


def is_comment(s):
    """Match line comment starting with # or ;"""
    p = re.compile(r'[\s]*[#;].*')
    return bool(p.match(s))


def is_proper_varname(s):
    """Checks for valid identifier"""
    p = re.compile(r'^[\w]+$')  # accept only alphanumeric chars, no whitespace
    return bool(p.match(s))


def parse_var_def(s):
    """Match (possibly partial) var definition. Return varname,
    val tuple if successful"""
    p = re.compile(r'^([^=]+)=([^=]+)$')
    m = p.match(s)
    if m:
        varname, val = m.group(1).strip(), m.group(2).strip()
        if is_proper_varname(varname):
            return varname, val
    return None, None


def is_var_def(s):
    varname, val = parse_var_def(s)
    return varname is not None


def is_list_def(s):
    """Match (start of) list or dict definition"""
    varname, val = parse_var_def(s)
    if val is None:
        return False
    else:
        # do not include closing ] or }, as it may be a multiline def
        p = re.compile(r'[\s]*[\[,\{][\S]+[\s]*')
        return bool(p.match(val))


def parse_section_header(s):
    """Match section headers of form [header] and return header as str"""
    p = re.compile(r'^\[([\w]*)\]$')
    m = p.match(s)
    return m.group(1) if m else None


def is_whitespace(s):
    p = re.compile(r'^\s*$')
    return bool(p.match(s))


class ConfigItem(object):
    """Holds data for a config item"""

    def __init__(self, def_lines, comment=None):
        self.comment = comment if comment else ''
        if not isinstance(def_lines, list):
            def_lines = [def_lines]
        self.def_lines = def_lines

    @property
    def def_lines(self):
        return self._def_lines

    @def_lines.setter
    def def_lines(self, _lines):
        """Evaluate def lines"""
        item_def = ''.join(_lines)
        self._name, _val_literal = parse_var_def(item_def)
        if self._name is None:
            raise ValueError('invalid definition')
        try:
            self._val = ast.literal_eval(_val_literal)
        except SyntaxError:
            raise ValueError('invalid definition: %s' % item_def)
        self._def_lines = _lines

    @property
    def value(self):
        return self._val

    @value.setter
    def value(self, _val):
        """Set value and update def lines accordingly"""
        self._val = _val
        self._def_lines = ['%s = %s' % (self._name, _val)]

    @property
    def description(self):
        """Format item comment into description"""
        p = re.compile(r'^[\s]*#[\s]*(.+)')
        m = p.match(self.comment)
        if m:
            desc = m.group(1)
            return desc[0].upper() + desc[1:]

    @property
    def item_def(self):
        """Pretty-print item definition with indentation"""
        return '\n'.join(self.def_lines)

    def __repr__(self):
        return repr(self._val)


class Section(object):
    """Holds data for a config section"""

    def __init__(self, items=None, comment=None):
        # need to modify __dict__ directly to avoid infinite __setattr__ loop
        self.__dict__['_items'] = items or dict()
        self.__dict__['_comment'] = comment or ''

    def __contains__(self, item):
        """Operates on item names"""
        return item in self._items

    def __iter__(self):
        """Yields tuples of (item_name, item)"""
        for val in self._items.items():
            yield val

    def __getattr__(self, attr):
        """Returns the value for a config item. This allows syntax of
        cfg.section.item to get the value"""
        return self._items[attr]._val

    def __getitem__(self, item):
        """Returns a config item as ConfigItem instance"""
        return self._items[item]

    def __setattr__(self, item, value):
        if not isinstance(value, ConfigItem):
            raise ValueError('value must be a ConfigItem instance')
        self.__dict__['_items'][item] = value

    def get_description(self):
        """Format comment into section description"""
        p = re.compile(r'^[\s]*#[\s]*(.+)')
        m = p.match(self._comment)
        if m:
            return m.group(1).strip()

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

    def __contains__(self, section):
        """Operates on section names"""
        return section in self._sections

    def __iter__(self):
        """Yields tuples of (section_name, section)"""
        for val in self._sections.items():
            yield val

    def __setattr__(self, item, value):
        if not isinstance(value, Section):
            raise ValueError('value must be a Section instance')
        self.__dict__['_sections'][item] = value

    def __repr__(self):
        s = '<Config|'
        s += ' sections: %s' % str(self._sections.keys())
        s += '>'
        return s


def parse_config(filename):
    """Parse cfg lines (ConfigParser format) into a Config instance"""

    with open(filename, 'r') as f:
        lines = f.read().splitlines()

    _comments = list()  # comments for current variable
    _def_lines = list()
    current_section = None
    collecting_def = False
    config = Config()

    for li in lines:

        print('parsing: %s' % li)
        secname = parse_section_header(li)
        item_name, val = parse_var_def(li)

        # whether to finish an item def
        if collecting_def and (secname or item_name is not None or
                               is_comment(li) or is_whitespace(li)):
            comment = '\n'.join(_comments)
            item = ConfigItem(comment=comment, def_lines=_def_lines)
            setattr(current_section, collecting_def, item)
            print('finished def for %s' % collecting_def)
            _comments = list()
            collecting_def = None
            _def_lines = list()

        if secname:
            comment = '\n'.join(_comments)
            current_section = Section(comment=comment)
            setattr(config, secname, current_section)
            _comments = list()

        elif item_name is not None:  # start of item definition
            if not current_section:
                raise ValueError('item definition outside of section')
            collecting_def = item_name
            _def_lines.append(li)

        elif is_comment(li):
            print('collected comment %s' % li)
            _comments.append(li)

        elif not is_whitespace(li):  # continuation of item definition
            if collecting_def is None:
                # continuation outside of item def
                raise ValueError('invalid input line: %s' % li)
            _def_lines.append(li)

    return config


def update_config(cfg, filename):
    """Update existing Config from filename. Will not create new sections or
    keys"""
    cfg_new = parse_config(filename)
    for secname, sec in cfg_new:
        try:
            sec_old = getattr(cfg, secname)
        except KeyError:
            logger.warning('section does not exist: %s' % secname)
        else:
            for itname, item in sec:
                if itname not in sec_old:
                    logger.warning('item does not exist: %s' % itname)
                else:
                    item_old = sec_old[itname]
                    item_old.def_lines = item.def_lines


def dump_config(cfg):
    """Produce text version of Config instance that can be read back"""
    def _gen_dump(cfg):
        sectnames = sorted(sname for (sname, sec) in cfg)
        for k, sectname in enumerate(sectnames):
            if k > 0:
                yield ''
            sect = getattr(cfg, sectname)
            sect_comment = sect._comment
            if sect_comment:
                yield sect_comment
            yield '[%s]' % sectname
            for itemname, item in sect:
                yield item.comment
                yield item.item_def
    return u'\n'.join(_gen_dump(cfg))
