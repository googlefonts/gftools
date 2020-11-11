#!/usr/bin/env python3
# Copyright 2013,2016 The Font Bakery Authors.
# Copyright 2017 The Google Font Tools Authors
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
#
"""
Hinted fonts must have head table flag bit 3 set.

Per https://docs.microsoft.com/en-us/typography/opentype/spec/head,
bit 3 of Head::flags decides whether PPEM should be rounded.
This bit should always be set for hinted fonts.
Note:
Bit 3 = Force ppem to integer values for all internal scaler math;
        May use fractional ppem sizes if this bit is clear;
"""
from __future__ import print_function, unicode_literals
import argparse
from fontTools.ttLib import TTFont
from gftools.fix import fix_hinted_font


def font_has_hinting(font):
    return 'fpgm' in font


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("font")
    args = parser.parse_args()

    font = TTFont(args.font)
    if font_has_hinting(font):
        fix_hinted_font(font)
    else:
        print("Skipping. Font is not hinted")
    font.save(args.font + ".fix")


if __name__ == '__main__':
    main()

