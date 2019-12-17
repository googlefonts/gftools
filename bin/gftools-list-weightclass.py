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
import argparse
import os
import tabulate
from fontTools import ttLib

parser = argparse.ArgumentParser(description='Print out'
                                             ' usWeightClass of the fonts')
parser.add_argument('font', nargs="+")
parser.add_argument('--csv', default=False, action='store_true')


def main():
  args = parser.parse_args()
  headers = ['filename', 'usWeightClass']
  rows = []
  for font in args.font:
    ttfont = ttLib.TTFont(font)
    rows.append([os.path.basename(font), ttfont['OS/2'].usWeightClass])

  def as_csv(rows):
    import csv
    import sys
    writer = csv.writer(sys.stdout)
    writer.writerows([headers])
    writer.writerows(rows)
    sys.exit(0)

  if args.csv:
    as_csv(rows)

  print(tabulate.tabulate(rows, headers, tablefmt="pipe"))

if __name__ == '__main__':
  main()

