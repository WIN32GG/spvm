import os
from os.path import join

metaFileName = "pyp.json"
scriptVersionCheckURL = None  # Last version
metaFileLocation = join(os.path.dirname(__file__), 'res', metaFileName)

if not os.path.isfile(metaFileLocation):
    raise EnvironmentError("Meta file template not found")

STATUS_PROJECT_DOES_NOT_EXIST = "does_not_exist"
STATUS_PROJECT_NOT_INITIALIZED = "not_initialized"
STATUS_PROJECT_INITIALIZED = "initialized"

PADLOCK = '🔒'
OPEN_PADLOCK = '🔓'

config = {
    'mock': False,
    'signed': False
}


class NoFailReadOnlyDict(object):
    def __init__(self, dict, default=''):
        self.dict = dict
        self.default = default

    def __getitem__(self, key):
        try:
            return self.dict[key]
        except KeyError:
            return self.default

    def __setitem__(self, key, value):
        raise AttributeError("This dictionary is read only")

    def __getattribute__(self, name):
        raise AttributeError("Cannot access attributes")

    def __setattr__(self, name, value):
        raise AttributeError("Cannot set attributes")
