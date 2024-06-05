#!/usr/bin/env python3
# Copyright 2017 The Google Font Tools Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Tool to check codepoint coverage in all font weights.

Ex: If FamilyName-Regular.ttf supports codepoints A-D
       FamilyName-Bold.ttf supports codepoints B-E
       FamilyName-Light.ttf supports codepoints A-E

$ python tools/font_weights_coverage.py ofl/familyname
FamilyName-Regular.ttf failed
0x0045
FamilyName-Bold.ttf failed
0x0041
FamilyName-Light.ttf passed
"""
from __future__ import print_function
import os
from os import listdir
import argparse
import sys
from gfsubsets import CodepointsInFont


parser = argparse.ArgumentParser(description="Compare size and coverage of two fonts")
parser.add_argument("dirpath", help="a directory containing font files.", metavar="DIR")


def main(args=None):
    args = parser.parse_args(args)

    cps = set()
    for f in _GetFontFiles(args.dirpath):
        cps.update(CodepointsInFont(os.path.join(args.dirpath, f)))

    for f in _GetFontFiles(args.dirpath):
        diff = cps - CodepointsInFont(os.path.join(args.dirpath, f))
        if bool(diff):
            print("%s failed" % (f))
            for c in diff:
                print("0x%04X" % (c))
        else:
            print("%s passed" % (f))


def _GetFontFiles(path):
    """Returns list of font files in a path.

    Args:
      path: directory path
    Returns:
      Set of font files
    """
    return [f for f in listdir(path) if os.path.splitext(f)[1] in (".ttf", ".otf")]


if __name__ == "__main__":
    main()
