#!/usr/bin/env python3
# Copyright 2017 The Font Bakery Authors.
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
import argparse
import os
import tabulate
from fontTools import ttLib

parser = argparse.ArgumentParser(description="Print out italicAngle of the fonts")
parser.add_argument("font", nargs="+")
parser.add_argument("--csv", default=False, action="store_true")


def main(args=None):
    arg = parser.parse_args(args)

    headers = ["filename", "italicAngle"]
    rows = []
    for font in arg.font:
        ttfont = ttLib.TTFont(font)
        rows.append([os.path.basename(font), ttfont["post"].italicAngle])

    if arg.csv:
        import csv
        import sys

        writer = csv.writer(sys.stdout)
        writer.writerows([headers])
        writer.writerows(rows)
    else:
        print(tabulate.tabulate(rows, headers, tablefmt="pipe"))


if __name__ == "__main__":
    main()
