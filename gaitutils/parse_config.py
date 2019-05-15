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


def get_description(item_or_section):
    """Returns a nice description based on section or item comment. This is not
    implemented as an instance method to avoid polluting the class namespaces
    (since instance variables have a special purpose"""
    p = re.compile(r'^[\s]*#[\s]*(.+)')
    m = p.match(item_or_section._comment)
    if m:
        desc = m.group(1)
        return desc[0].upper() + desc[1:]


class ConfigItem(object):
    """Holds data for a config item"""

    def __init__(self, value=None, def_lines=None, comment=None):
        if comment is None:
            comment = ''
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
        self._def_lines = ['%s = %s' % (self._name, _val)]

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
        if (isinstance(value, ConfigItem) or
           isinstance(value, ConfigContainer)):
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
            current_section = ConfigContainer(comment=comment)
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