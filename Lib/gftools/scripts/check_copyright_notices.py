#!/usr/bin/env python3
# Copyright 2017 The Fontbakery Authors
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
from gftools.constants import NAMEID_COPYRIGHT_NOTICE, PLATID_STR

parser = argparse.ArgumentParser(description="Print out copyright" " nameIDs strings")
parser.add_argument("font", nargs="+")
parser.add_argument(
    "--csv",
    default=False,
    action="store_true",
    help="Output data in comma-separate-values" " (CSV) file format",
)


def main(args=None):
    args = parser.parse_args(args)

    rows = []
    for font in args.font:
        ttfont = ttLib.TTFont(font)
        for name in ttfont["name"].names:
            if name.nameID != NAMEID_COPYRIGHT_NOTICE:
                continue

            value = name.string.decode(name.getEncoding()) or ""
            rows.append(
                [
                    os.path.basename(font),
                    value,
                    len(value),
                    "{} ({})".format(
                        name.platformID, PLATID_STR.get(name.platformID, "?")
                    ),
                ]
            )

    header = ["filename", "copyright notice", "char length", "platformID"]

    def as_csv(rows):
        import csv
        import sys

        writer = csv.writer(
            sys.stdout, delimiter="|", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )
        writer.writerows([header])
        writer.writerows(rows)
        sys.exit(0)

    if args.csv:
        as_csv(rows)

    print("")  # some spacing
    print(tabulate.tabulate(rows, header, tablefmt="pipe"))
    print("")  # some spacing


if __name__ == "__main__":
    """Example usage:

    gftools check-copyright-notices ~/fonts/*/*/*ttf --csv > ~/notices.txt;
    """
    main()
