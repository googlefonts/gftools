#!/usr/bin/env python3
# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Utility to dump codepoints in a font.

Prints codepoints supported by the font, one per line, in hex (0xXXXX).

"""

import os
import sys
import unicodedata
import argparse

from gfsubsets import CodepointsInFont, SubsetsForCodepoint


parser = argparse.ArgumentParser(description="Dump codepoints in a font")
parser.add_argument(
    "--show_char", action="store_true", help="Print the actual character"
)
parser.add_argument(
    "--show_subsets", action="store_true", help="Print what subsets, if any, char is in"
)
parser.add_argument("font", metavar="TTF", nargs="+", help="font files")


def main(args=None):
    args = parser.parse_args(args)

    cps = set()
    for filename in args.font:
        if not os.path.isfile(filename):
            sys.exit("%s is not a file" % filename)
        cps |= CodepointsInFont(filename)

    for cp in sorted(cps):
        show_char = ""
        if args.show_char:
            show_char = " " + chr(cp).strip() + " " + unicodedata.name(chr(cp), "")
        show_subset = ""
        if args.show_subsets:
            show_subset = " subset:%s" % ",".join(SubsetsForCodepoint(cp))

        print("0x%04X%s%s" % (cp, show_char, show_subset))


if __name__ == "__main__":
    main()
