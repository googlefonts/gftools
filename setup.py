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

# Read the contents of the README file
with open('README.md') as f:
    long_description = f.read()

setup(
    name="gftools",
    use_scm_version={"write_to": "Lib/gftools/_version.py"},
    url='https://github.com/googlefonts/tools/',
    description='Google Fonts Tools is a set of command-line tools'
                ' for testing font projects',
    long_description=long_description,
    long_description_content_type='text/markdown',  # This is important!
    author=('Google Fonts Tools Authors: '
            'Dave Crossland, '
            'Felipe Sanches, '
            'Lasse Fister, '
            'Marc Foley, '
            'Eli Heuer, '
            'Roderick Sheeter'),
    author_email='dave@lab6.com',
    package_dir={'': 'Lib'},
    packages=['gftools',
              'gftools.actions',
              'gftools.util',
              'gftools.builder'],
    package_data={'gftools.util': ["GlyphsInfo/*.xml", "UnicodeSections/*.json"],
                  'gftools': [
                      'template.upstream.yaml',
                      "udhr_all.txt",
                      "templates/*.html",
                      "push-templates/*.html"
                  ]
                 },
    scripts=gftools_scripts(),
    zip_safe=False,
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Topic :: Text Processing :: Fonts',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3'
    ],
    python_requires=">=3.7",
    setup_requires=['setuptools_scm>=4,<6.1'],
    # Dependencies needed for gftools qa.
    extras_require={"qa": ['fontbakery', 'fontdiffenator', 'gfdiffbrowsers']},
    install_requires=[
#       'fontforge', # needed by build-font2ttf script
#                      but there's no fontforge package on pypi
#                      see: https://github.com/fontforge/fontforge/issues/2048
        'setuptools',
        'FontTools[ufo]',
        'axisregistry>=0.3.1', # API update removed fallback names pre-processing
        'absl-py',
        'glyphsLib',
        'gflanguages>=0.4.0',
        'glyphsets>=0.2.1',
        'PyGithub',
        'pillow',
        'protobuf==3.19.4',
        'requests',
        'tabulate',
        'unidecode',
        'opentype-sanitizer',
        'vttlib',
        'pygit2',
        'strictyaml',
        'fontmake>=3.3.0',
        'skia-pathops',
        'statmake',
        'PyYAML',
        'babelfont',
        'ttfautohint-py',
        'brotli',
        'browserstack-local==1.2.2',
        'pybrowserstack-screenshots==0.1',
        'jinja2',
        'hyperglot',
        'fontFeatures',
        'vharfbuzz',
        'bumpfontversion',
    ]
    )
