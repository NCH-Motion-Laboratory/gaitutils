# -*- coding: utf-8 -*-
"""
Parse INI files into nested config objects

@author: Jussi (jnu@iki.fi)
"""
from __future__ import print_function

from builtins import str
from builtins import object
import ast
import re
import logging


logger = logging.getLogger(__name__)


# regexes
RE_ALPHANUMERIC = r'\w+$'  # at least 1 alphanumeric char
RE_WHITESPACE = r'\s*$'  # empty or whitespace
# match line comment; group 1 will be the comment
RE_COMMENT = r'\s*[#;]\s*(.*)'
# match item def; groups 1 and 2 are the item and the (possibly empty) value
RE_VAR_DEF = r'\s*([^=\s]+)\s*=\s*(.*?)\s*$'
# match section header of form [section]; group 1 is the section
# section names can include alphanumeric chars, _ and -
RE_SECTION_HEADER = r'\s*\[([\w-]+)\]\s*'


def _simple_match(r, s):
    return bool(re.match(r, s))


def is_comment(s):
    return _simple_match(RE_COMMENT, s)


def is_proper_varname(s):
    return _simple_match(RE_ALPHANUMERIC, s)


def is_whitespace(s):
    return _simple_match(RE_WHITESPACE, s)


def parse_var_def(s):
    """Match (possibly partial) var definition. Return varname,
    val tuple if successful"""
    m = re.match(RE_VAR_DEF, s)
    if m:
        varname, val = m.group(1).strip(), m.group(2).strip()
        if is_proper_varname(varname):
            return varname, val
    return None, None


def is_var_def(s):
    varname, val = parse_var_def(s)
    return varname is not None


def parse_section_header(s):
    """Match section headers of form [header] and return header as str"""
    m = re.match(RE_SECTION_HEADER, s)
    return m.group(1) if m else None


def get_description(item_or_section):
    """Returns a nice description based on section or item comment. This is not
    implemented as an instance method to avoid polluting the class namespace"""
    desc = item_or_section._comment
    # currently just capitalizes first letter of comment string
    return desc[:1].upper() + desc[1:]


class ConfigItem(object):
    """Holds data for a config item"""

    def __init__(self, name=None, value=None, comment=None):
        if comment is None:
            comment = ''
        self._comment = comment
        self.name = name
        self.value = value

    def __repr__(self):
        return '<ConfigItem| %s = %r>' % (self.name, self.value)

    @property
    def literal_value(self):
        """Returns a string that is supposed to evaluate to the value"""
        return repr(self.value)

    @property
    def item_def(self):
        """Print item definition"""
        return '%s = %r' % (self.name, self.value)


class ConfigContainer(object):
    """Holds config items (ConfigContainer or ConfigItem instances)"""

    def __init__(self, items=None, comment=None):
        # need to modify __dict__ directly to avoid infinite __setattr__ loop
        if items is None:
            items = dict()
        if comment is None:
            comment = ''
        self.__dict__['_items'] = items
        self.__dict__['_comment'] = comment

    def __contains__(self, item):
        """Checks items by name"""
        return item in self._items

    def __iter__(self):
        """Yields tuples of (item_name, item)"""
        for val in self._items.items():
            yield val

    def __getattr__(self, attr):
        """Returns an item. For ConfigItem instances, the item value is
        returned. This gets the value directly by the syntax section.item"""
        item = self._items[attr]
        return item.value if isinstance(item, ConfigItem) else item

    def __getitem__(self, item):
        """Returns an item"""
        return self._items[item]

    def __setattr__(self, attr, value):
        """Set attribute"""
        if isinstance(value, ConfigItem) or isinstance(value, ConfigContainer):
            # replace existing section/item
            self.__dict__['_items'][attr] = value
        elif attr in self._items:
            # update value of existing item (by syntax sec.item = value)
            self.__dict__['_items'][attr].value = value
        else:
            # implicitly create a new ConfigItem
            self.__dict__['_items'][attr] = ConfigItem(name=attr, value=value)

    def __repr__(self):
        s = '<ConfigContainer|'
        s += ' items: %s' % str(self._items.keys())
        s += '>'
        return s


def parse_config(filename):
    with open(filename, 'r') as f:
        lines = f.read().splitlines()
    return _parse_config(lines)


def _parse_config(lines):

    """Parse INI files into a ConfigContainer instance.
    Supports:
        -multiline variable definitions
    Does not support:
        -inline comments (would be too confusing with multiline defs)
        -nested sections (though possible with ConfigContainer)
    """

    _comments = list()  # comments for current variable
    _def_lines = list()  # definition lines for current variable
    current_section = None
    collecting_def = False
    config = ConfigContainer()

    for lnum, li in enumerate(lines, 1):
        # every line is either: comment, section header, variable definition,
        # continuation of variable definition, or whitespace

        secname = parse_section_header(li)
        item_name, val = parse_var_def(li)

        # new section
        if secname:
            if collecting_def:  # did not finish definition
                raise ValueError('could not evaluate definition at line %d' % lnum)
            comment = ' '.join(_comments)
            current_section = ConfigContainer(comment=comment)
            setattr(config, secname, current_section)
            _comments = list()

        # new item definition
        elif item_name:
            if collecting_def:  # did not finish previous definition
                raise ValueError('could not evaluate definition at line %d' % lnum)
            elif not current_section:
                raise ValueError('item definition outside of section '
                                 'on line %d' % lnum)
            elif item_name in current_section:
                raise ValueError('duplicate definition on line %d' % lnum)
            try:
                val_eval = ast.literal_eval(val)
                # if eval is successful, record the variable
                comment = ' '.join(_comments)
                item = ConfigItem(comment=comment, name=item_name,
                                  value=val_eval)
                setattr(current_section, item_name, item)
                _comments = list()
                _def_lines = list()
                collecting_def = None
            except (ValueError, SyntaxError):  # eval failed, continued def?
                collecting_def = item_name
                _def_lines.append(val)
                continue

        elif is_comment(li):
            if collecting_def:  # did not finish definition
                raise ValueError('could not evaluate definition at line %d' % lnum)
            m = re.match(RE_COMMENT, li)
            cmnt = m.group(1)
            _comments.append(cmnt)

        elif is_whitespace(li):
            if collecting_def:  # did not finish definition
                raise ValueError('could not evaluate definition at line %d' % lnum)

        # either a continued def or a syntax error
        else:
            if not collecting_def:
                raise ValueError('syntax error at line %d: %s' % (lnum, li))
            _def_lines.append(li.strip())
            try:
                val_new = ''.join(_def_lines)
                val_eval = ast.literal_eval(val_new)
                comment = ' '.join(_comments)
                item = ConfigItem(comment=comment,
                                  name=collecting_def, value=val_eval)
                setattr(current_section, collecting_def, item)
                _comments = list()
                _def_lines = list()
                collecting_def = None
            except (ValueError, SyntaxError):  # cannot evaluate def (yet)
                continue

    if collecting_def:  # did not finish definition
        raise ValueError('could not evaluate definition at line %d: %s' % (lnum, li))

    return config


def update_config(cfg, cfg_new, create_new_sections=True,
                  create_new_items=True, update_comments=False):
    """Update existing Config instance from another."""
    for secname, sec in cfg_new:
        if secname not in cfg and create_new_sections:
            # create nonexisting section anew
            setattr(cfg, secname, sec)
        elif secname in cfg:
            # update items in existing section
            sec_old = cfg[secname]
            if update_comments:
                sec_old._comment = sec._comment
            for itname, item in sec:
                if itname in sec_old:
                    if update_comments:
                        setattr(sec_old, itname, item)
                    else:  # update value only
                        item_old = sec_old[itname]
                        item_old.value = item.value
                elif create_new_items:
                    setattr(sec_old, itname, item)


def dump_config(cfg):
    """Produce text version of Config instance that can be read back"""
    def _gen_dump(cfg):
        sects = sorted(cfg, key=lambda tup: tup[0])  # sort by name
        for sectname, sect in sects:
            if sectname != sects[0][0]:
                yield ''  # empty line before each section (not the first)
            if sect._comment:
                yield '# %s ' % sect._comment
            yield '[%s]' % sectname
            items = sorted(sect, key=lambda tup: tup[0])
            for itemname, item in items:
                yield '# %s' % item._comment
                yield item.item_def
    return u'\n'.join(_gen_dump(cfg))
