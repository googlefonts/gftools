#!/usr/bin/env python3
# Copyright 2016 The Fontbakery Authors
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
from __future__ import print_function
import argparse
import csv
import os
import sys
import tabulate
from fontTools import ttLib

parser = argparse.ArgumentParser(description='Print out'
                                             ' usWidthClass of the fonts')
parser.add_argument('font', nargs="+")
parser.add_argument('--csv', default=False, action='store_true')
parser.add_argument('--set', type=int, default=0)
parser.add_argument('--autofix', default=False, action='store_true')

def print_info(fonts, print_csv=False):
    headers = ['filename', 'usWidthClass']
    rows = []
    warnings = []
    for font in fonts:
        ttfont = ttLib.TTFont(font)
        usWidthClass = ttfont['OS/2'].usWidthClass
        rows.append([os.path.basename(font), usWidthClass])
        if usWidthClass != 5:
            warning = "WARNING: {} is {}, expected 5"
            warnings.append(warning.format(font, usWidthClass))

    def as_csv(rows):
        writer = csv.writer(sys.stdout)
        writer.writerows([headers])
        writer.writerows(rows)
        sys.exit(0)

    if print_csv:
        as_csv(rows)

    print(tabulate.tabulate(rows, headers, tablefmt="pipe"))
    for warn in warnings:
        print(warn, file=sys.stderr)


def getFromFilename(filename):
    if "UltraCondensed-" in filename:
        usWidthClass = 1
    elif "ExtraCondensed-" in filename:
        usWidthClass = 2
    elif "SemiCondensed-" in filename:
        usWidthClass = 4
    elif "Condensed-" in filename:
        usWidthClass = 3
    elif "SemiExpanded-" in filename:
        usWidthClass = 6
    elif "ExtraExpanded-" in filename:
        usWidthClass = 8
    elif "UltraExpanded-" in filename:
        usWidthClass = 9
    elif "Expanded-" in filename:
        usWidthClass = 7
    else:
        usWidthClass = 5
    return usWidthClass


def fix(fonts, value=None):
    rows = []
    headers = ['filename', 'usWidthClass was', 'usWidthClass now']

    for font in fonts:
        row = [font]
        ttfont = ttLib.TTFont(font)
        if not value:
            usWidthClass = getFromFilename(font)
        else:
            usWidthClass = value
        row.append(ttfont['OS/2'].usWidthClass)
        ttfont['OS/2'].usWidthClass = usWidthClass
        row.append(ttfont['OS/2'].usWidthClass)
        ttfont.save(font + '.fix')
        rows.append(row)

    if rows:
        print(tabulate.tabulate(rows, headers, tablefmt="pipe"))


def main():
    args = parser.parse_args()
    if args.autofix:
        fix(args.font)
        sys.exit(0)
    if args.set:
        fix(args.font, value=int(args.set))
        sys.exit(0)
    print_info(args.font, print_csv=args.csv)

if __name__ == '__main__':
  main()

