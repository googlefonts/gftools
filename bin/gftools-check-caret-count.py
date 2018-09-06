#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2018 The Google Font Tools Authors
# Copyright 2010, Google Inc.
# Author: Eli H (elih@protonmail.com)
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
"""
A Python script for printing expected caret count to stdout.

e.g:

Check expected caret count of a font in collection:
gftools check-caret-count [fonts]

Output in csv format
gftools check-name [fonts] --csv

TODO (Eli H) this is just a simple test of a concept at this point.
See fontbakery issue #1976 for more info:
https://github.com/googlefonts/fontbakery/issues/1976
"
"""
from argparse import ArgumentParser
from fontTools.ttLib import TTFont
import os
import sys

parser = ArgumentParser(description=__doc__)

parser.add_argument('fonts',
                    nargs="+",
                    help="Fonts in OpenType (TTF/OTF) format")


def get_caret_count():
    args = parser.parse_args()

    for font in args.fonts:
        font_path = font
        font = TTFont(font_path)
        for l in font['GDEF'].LookupList:
            print(l)


def main():
    get_caret_count()


if __name__ == '__main__':
    main()
    print("done :-)")
