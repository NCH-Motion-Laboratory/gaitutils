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
    m = re.match(RE_COMMENT, item_or_section._comment)
    if m:
        desc = m.group(1)
        return desc[:1].upper() + desc[1:]


class ConfigItem(object):
    """Holds data for a config item"""

    def __init__(self, value=None, def_lines=None, comment=None):
        if comment is None:
            comment = ''
        self._comment = comment
        if def_lines is None:
            if value is None:
                raise ValueError('need either definition line or value')
            else:
                self.value = value
        else:
            if not isinstance(def_lines, list):
                def_lines = [def_lines]
            self.def_lines = def_lines

    def __repr__(self):
        return '<ConfigItem| %s = %r>' % (self._name, self.value)

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
        # use repr formatter %r to get strings in quoted form
        self._def_lines = ['%s = %r' % (self._name, _val)]

    @property
    def literal_value(self):
        """Returns a string that is supposed to evaluate to the value"""
        return repr(self.value)

    @property
    def item_def(self):
        """Pretty-print item definition with indentation"""
        return '\n'.join(self.def_lines)


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
            self.__dict__['_items'][attr] = ConfigItem(value=value)

    def __repr__(self):
        s = '<ConfigContainer|'
        s += ' items: %s' % str(self._items.keys())
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
    config = ConfigContainer()

    for li in lines:

        # print('parsing: %s' % li)
        secname = parse_section_header(li)
        item_name, val = parse_var_def(li)

        # whether to finish an item def
        if collecting_def and (secname or item_name is not None or
                               is_comment(li) or is_whitespace(li)):
            comment = '\n'.join(_comments)
            item = ConfigItem(comment=comment, def_lines=_def_lines)
            setattr(current_section, collecting_def, item)
            # print('finished def for %s' % collecting_def)
            _comments = list()
            collecting_def = None
            _def_lines = list()

        if secname:
            comment = '\n'.join(_comments)
            current_section = ConfigContainer(comment=comment)
            setattr(config, secname, current_section)
            _comments = list()

        elif item_name is not None:  # start of item definition
            # print('parsed: %s=%s' % (item_name, val))
            if not current_section:
                raise ValueError('item definition outside of section')
            collecting_def = item_name
            _def_lines.append(li)

        elif is_comment(li):
            # print('collected comment %s' % li)
            _comments.append(li)

        elif not is_whitespace(li):  # continuation of item definition
            if collecting_def is None:
                # continuation outside of item def
                raise ValueError('invalid input line: %s' % li)
            _def_lines.append(li)

    if collecting_def:  # finish def if it ended on the last line
        comment = '\n'.join(_comments)
        item = ConfigItem(comment=comment, def_lines=_def_lines)
        setattr(current_section, collecting_def, item)
        # print('finished def for %s' % collecting_def)

    return config


def update_config(cfg, filename):
    """Update existing Config from filename. Will not create new sections or
    keys"""
    cfg_new = parse_config(filename)
    for secname, sec in cfg_new:
        try:
            sec_old = getattr(cfg, secname)
        except KeyError:
            logger.warning('not updating nonexistent section: %s' % secname)
        else:
            for itname, item in sec:
                if itname not in sec_old:
                    logger.warning('not updating nonexistent item: %s' % itname)
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
            if sect._comment:
                yield sect._comment
            yield '[%s]' % sectname
            for itemname, item in sect:
                yield item._comment
                yield item.item_def
    return u'\n'.join(_gen_dump(cfg))
