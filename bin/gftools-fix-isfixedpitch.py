#!/usr/bin/env python3

# Copyright 2013,2016 The Font Bakery Authors.
# Copyright 2017,2020 The Google Font Tools Authors
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

"""
It is important for monospaced fonts to have the 'isFixedPitch' flag set to 1
in the post table. If it is set to 0, Windows coding programs categorize them
as proportional fonts, and they will not appear as options in font selection 
preferences.
\n
This script checks whether a font or collection of fonts appears to be monospaced 
by checking for equal widths in the entire Latin lowercase, a to z. If these are 
equal, 'isFixedPitch' will be set to 1. If a-z are unequal, 'isFixedPitch' will be 
set to 0.

Usage:

gftools-fix-isfixedpitch --fonts [font1.ttf font2.ttf ...]

"""

from fontTools.ttLib import TTFont
from fontTools.misc.fixedTools import otRound
import argparse


def fix_isFixedPitch(ttfont):

    same_width = set()
    glyph_metrics = ttfont['hmtx'].metrics
    for character in [chr(c) for c in range(65, 91)]:
        same_width.add(glyph_metrics[character][0])

    if len(same_width) == 1:
        if ttfont['post'].isFixedPitch == 1:
            print("Skipping isFixedPitch is set correctly")
        else:
            print("Font is monospace. Updating isFixedPitch to 0")
            ttfont['post'].isFixedPitch = 1

        familyType = ttfont['OS/2'].panose.bFamilyType
        if familyType == 2:
            expected = 9
        elif familyType == 3 or familyType == 5:
            expected = 3
        elif familyType == 0:
            print("Font is monospace but panose fields seems to be not set."
                  " Setting values to defaults (FamilyType = 2, Proportion = 9).")
            ttfont['OS/2'].panose.bFamilyType = 2
            ttfont['OS/2'].panose.bProportion = 9
            expected = None
        else:
            expected = None

        if expected:
            if ttfont['OS/2'].panose.bProportion == expected:
                print("Skipping OS/2.panose.bProportion is set correctly")
            else:
                print(("Font is monospace."
                       " Since OS/2.panose.bFamilyType is {}"
                       " we're updating OS/2.panose.bProportion"
                       " to {}").format(familyType, expected))
                ttfont['OS/2'].panose.bProportion = expected

        widths = [m[0] for m in ttfont['hmtx'].metrics.values() if m[0] > 0]
        width_max = max(widths)
        if ttfont['hhea'].advanceWidthMax == width_max:
            print("Skipping hhea.advanceWidthMax is set correctly")
        else:
            print("Font is monospace. Updating hhea.advanceWidthMax to %i" %
                  width_max)
            ttfont['hhea'].advanceWidthMax = width_max

        avg_width = otRound(sum(widths) / len(widths))
        if avg_width == ttfont['OS/2'].xAvgCharWidth:
            print("Skipping OS/2.xAvgCharWidth is set correctly")
        else:
            print("Font is monospace. Updating OS/2.xAvgCharWidth to %i" %
                  avg_width)
            ttfont['OS/2'].xAvgCharWidth = avg_width
    else:
        ttfont['post'].isFixedPitch = 0
        ttfont['OS/2'].panose.bProportion = 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", nargs="+", required=True)
    args = parser.parse_args()

    for font in args.fonts:
        ttfont = TTFont(font)
        fix_isFixedPitch(ttfont)

        new_font = font + ".fix"
        print("Saving font to {}".format(new_font))
        ttfont.save(new_font)


if __name__ == "__main__":
    main()

