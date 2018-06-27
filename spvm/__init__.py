import json
from os.path import join
from os.path import dirname

meta = None
with open(join(dirname(__file__), '..', 'pyp.json'), 'r') as fh:
    meta = json.loads(fh.read())

__version__ = meta['project_vcs']['version']
__author__ = meta['project_authors'][0]['name']
__email__ = meta['project_authors'][0]['email']
__license__ = meta['project_info']['license']
__url__ = meta['project_info']['url']
