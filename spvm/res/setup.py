#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import os
import sys
from shutil import rmtree
import json
from setuptools import find_packages, setup, Command

here = os.path.abspath(os.path.dirname(__file__))
metaFileName = "pyp.json"

#  os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

# Import the package meta data
meta = {}
with open(os.path.join(here, metaFileName)) as pmfile:
    exec(pmfile.read(), meta)

# Check the pmfile content
# TODO

# Use the README.md as the Long description
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = '\n' + f.read()

# Load the package's __version__.py module as a dictionary.
about = {}
with open(os.path.join(here, NAME, '__version__.py')) as f:
    exec(f.read(), about)

if not about['__version__']:
    about['__version__'] = '0.0.1' # warn default version

setup(
    name=meta['NAME'],
    version=about['__version__'],
    description=meta['DESCRIPTION'],
    long_description=long_description,
    long_description_content_type='text/markdown'
    author=meta['AUTHOR'],
    author_email=meta['EMAIL'],
    python_requires=meta['REQUIRES_PYTHON'],
    url=meta['URL'],
    packages=find_packages(exclude=('tests',)),

    # entry_points={
    #     'console_scripts': ['mycli=mymodule:cli'],
    # },
    install_requires=meta['REQUIRED'],
    include_package_data=True,
    license=meta['LICENSE'] ,
    # classifiers=[
    #     # Trove classifiers
    #     # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
    #     'License :: OSI Approved :: MIT License',
    #     'Programming Language :: Python',
    #     'Programming Language :: Python :: 3',
    #     'Programming Language :: Python :: 3.6',
    #     'Programming Language :: Python :: Implementation :: CPython',
    #     'Programming Language :: Python :: Implementation :: PyPy'
    # ],
    # $ setup.py publish support.
    # cmdclass={
    #     'upload': UploadCommand,
    # },
)