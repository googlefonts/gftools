#!/usr/bin/env python3
#
# Copyright 2017 The Google Font Tools Authors
# Copyright 2010, Google Inc.
# Author: Dave Crossland (dave@understandinglimited.com)
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
A Python script for printing nametables to stdout.

e.g:

Check nametables of fonts in collection:
gftools check-name [fonts]

Output in csv format
gftools check-name [fonts] --csv
"""
from argparse import (ArgumentParser,
                      RawTextHelpFormatter)
import csv
import sys
from fontTools.ttLib import TTFont
import tabulate
import ntpath

parser = ArgumentParser(description=__doc__,
                        formatter_class=RawTextHelpFormatter)
parser.add_argument('fonts',
                    nargs="+",
                    help="Fonts in OpenType (TTF/OTF) format")
parser.add_argument('--csv', default=False, action='store_true')


def printInfo(rows, save=False):
  header = [r[0] for r in rows[0]]
  t = []
  for row in rows:
    t.append([r[1] for r in row])

  if save:
    writer = csv.writer(sys.stdout)
    writer.writerows([header])
    writer.writerows(t)
    sys.exit(0)
  else:
    print(tabulate.tabulate(t, header, tablefmt="plain"))


def main():
  args = parser.parse_args()

  rows = []
  for font_filename in args.fonts:
    font = TTFont(font_filename)
    for field in font['name'].names:
      enc = field.getEncoding()
      rows.append([
        ('Font', ntpath.basename(font_filename)),
        ('platformID', field.platformID),
        ('encodingID', field.platEncID),
        ('languageID', field.langID),
        ('nameID', field.nameID),
        ('nameString', field.toUnicode()),
      ])

  if args.csv:
    printInfo(rows, save=True)
  else:
    printInfo(rows)


if __name__ == '__main__':
  main()
