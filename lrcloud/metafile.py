# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
if sys.version_info >= (3,):
    import configparser as cparser
else:
    import ConfigParser as cparser
import logging
from datetime import datetime
from os.path import join, dirname, isabs

from . import util

DATETIME_FORMAT='%Y-%m-%d %H:%M:%S.%f'

class MetaFile:
    """Representation of a meta-file"""

    def __init__(self, file_path):
        self.file_path = file_path
        config = cparser.ConfigParser()
        config.read(file_path)
        logging.info("Read meta-data file: %s"%file_path)
        self._data = {}
        for sec in config.sections():
            self._data[sec] = {}
            for (name, value) in config.items(sec):
                if value == "True":
                    value = True
                elif value == "False":
                    value = False
                try:# Try to convert the value to a time object
                   t = datetime.strptime(value, DATETIME_FORMAT)
                   value = t
                except ValueError:
                    pass
                except TypeError:
                    pass
                if name == "filename" and not isabs(value):
                    value = join(dirname(file_path), value) # Make filenames absolute
                self._data[sec][name] = value

    def __getitem__(self, section):
        if section not in self._data:
            self._data[section] = {}
        return self._data[section]

    def flush(self):
        logging.info("Writing meta-data file: %s"%self.file_path)
        config = cparser.ConfigParser()
        for (sec, options) in self._data.items():
            config.add_section(sec)
            for (name, value) in options.items():
                config.set(sec, name, str(value))
        with open(self.file_path, 'w') as f:
            config.write(f)
