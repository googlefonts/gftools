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

from fontTools import ttLib
import tabulate
from gftools.utils import get_fsSelection_byte1, get_fsSelection_byte2
from gftools.util.styles import STYLE_NAMES, is_filename_canonical
from gftools.fix import fix_fs_selection, FontFixer

parser = argparse.ArgumentParser(description='Print out fsSelection'
                                             ' bitmask of the fonts')
parser.add_argument('font', nargs="+")
parser.add_argument('--csv', default=False, action='store_true')
parser.add_argument('--usetypometrics', default=False, action='store_true')
parser.add_argument('--autofix', default=False, action='store_true')


def printInfo(fonts, print_csv=False):
  rows = []
  headers = ['filename', 'fsSelection']
  for font in fonts:
    ttfont = ttLib.TTFont(font)
    row = [os.path.basename(font)]
    row.append(('{:#010b} '
                '{:#010b}'
                '').format(get_fsSelection_byte2(ttfont),
                           get_fsSelection_byte1(ttfont)).replace('0b', ''))
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

def main():
  args = parser.parse_args()
  if args.autofix:
    fixed_fonts = []
    for font in args.font:
      filename = os.path.basename(font)

      if not is_filename_canonical(filename):
        print(f"Font filename '{filename}' is not canonical!\n\n"
              f"Filename must be structured as familyname-style.ttf and "
              f"the style must be any of the following {STYLE_NAMES}")
        exit(-1)

      fixer = FontFixer(font)
      fixer.fixes = [fix_fs_selection]
      fixer.fix()
      if fixer.saveit:
        fixed_fonts.append(font)

    if len(fixed_fonts) > 0:
      printInfo([f + '.fix' for f in fixed_fonts], print_csv=args.csv)

    sys.exit(0)

  printInfo(args.font, print_csv=args.csv)


if __name__ == '__main__':
    main()

