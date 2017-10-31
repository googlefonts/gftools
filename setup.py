# coding: utf-8
# Copyright 2013 The Font Bakery Authors.
# Copyright 2017 The Google Fonts Tools Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# See AUTHORS.txt for the list of Authors and LICENSE.txt for the License.
import os
from setuptools import setup

def gftools_scripts():
  scripts = [os.path.join('bin', f) for f in os.listdir('bin') if f.startswith('gftools-')]
  scripts.append(os.path.join('bin', 'gftools'))
  return scripts

setup(
    name="gftools",
    version='0.1.0-git',
    url='https://github.com/googlefonts/tools/',
    description='Google Fonts Tools is a set of command-line tools'
                ' for testing font projects',
    author=('Google Fonts Tools Authors: '
            'Dave Crossland, '
            'Felipe Sanches, '
            'Lasse Fister, '
            'Marc Foley, '
            'Roderick Sheeter'),
    author_email='dave@lab6.com',
    package_dir={'': 'Lib'},
    packages=['gftools'],
    scripts=gftools_scripts(),
    zip_safe=False,
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Topic :: Text Processing :: Fonts',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7'
    ],
    install_requires=[
# TODO: Review this:
#
#        'lxml',
#        'defusedxml',
#        'requests',
#        'unidecode',
#        'protobuf',
#        'bs4'
    ]
)
