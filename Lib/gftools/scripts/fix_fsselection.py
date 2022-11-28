#!/usr/bin/env python3
# Copyright 2016 The Fontbakery Authors
# Copyright 2017 The Google Fonts Tools Authors
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
import argparse
import csv
import os
import sys

from fontTools.ttLib import TTFont
import tabulate
from gftools.utils import get_fsSelection_byte1, get_fsSelection_byte2
from gftools.util.styles import STYLE_NAMES, is_filename_canonical
from gftools.fix import fix_fs_selection, FontFixer

parser = argparse.ArgumentParser(
    description="Print out fsSelection" " bitmask of the fonts"
)
parser.add_argument("fonts", nargs="+")
parser.add_argument("--csv", default=False, action="store_true")
parser.add_argument("--usetypometrics", default=False, action="store_true")
parser.add_argument("--autofix", default=False, action="store_true")


def printInfo(fonts, print_csv=False):
    rows = []
    headers = ["filename", "fsSelection"]
    for font in fonts:
        row = [os.path.basename(font.reader.file.name)]
        row.append(
            ("{:#010b} " "{:#010b}" "")
            .format(get_fsSelection_byte2(font), get_fsSelection_byte1(font))
            .replace("0b", "")
        )
        rows.append(row)

    def as_csv(rows):
        writer = csv.writer(sys.stdout)
        writer.writerows([headers])
        writer.writerows(rows)
        sys.exit(0)

    if print_csv:
        as_csv(rows)
    else:
        print(tabulate.tabulate(rows, headers, tablefmt="pipe"))


def main(args=None):
    args = parser.parse_args(args)
    fonts = [TTFont(f) for f in args.fonts]
    for font in fonts:
        os2 = font["OS/2"]
        old_fs = font["OS/2"].fsSelection
        if args.usetypometrics:
            os2.fsSelection |= 1 << 7
        if args.autofix:
            fix_fs_selection(font)
        new_fs = os2.fsSelection
        if new_fs != old_fs:
            out_fp = font.reader.file.name + ".fix"
            print(f"Saving {out_fp}")
            font.save(out_fp)
    printInfo(fonts, print_csv=args.csv)


if __name__ == "__main__":
    main()
