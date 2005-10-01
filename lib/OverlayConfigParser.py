"""Overlay config parser

This module offers a SafeConfigParser subclass OverlayConfigParser, which
accepts a new parameter at initialization named 'parent'.  This is expected
to be another ConfigParser instance, which will be used as a fallback 
default whenever a section or option isn't found.

In effect, an instance of this class is an "overlay" atop the parent 
instance.
"""

from StringIO import StringIO
from ConfigParser import SafeConfigParser as ConfigParser
from ConfigParser import NoSectionError, NoOptionError

class OverlayConfigParser(ConfigParser):

    def __init__(self, parent=None, defaults=None):
        ConfigParser.__init__(self, defaults=defaults)
        self._parent = parent

    def get(self, section, option):
        try:
            return ConfigParser.get(self, section, option)
        except (NoSectionError,NoOptionError):
            return self._parent.get(section, option)
