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

from gftools.fix import fix_isFixedPitch, FontFixer
import argparse


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", nargs="+", required=True)
    args = parser.parse_args(args)

    for font in args.fonts:
        FontFixer(font, fixes=[fix_isFixedPitch], verbose=True).fix()


if __name__ == "__main__":
    main()
