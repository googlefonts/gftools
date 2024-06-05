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
from gftools.utils import has_mac_names
from gftools.fix import drop_mac_names, drop_superfluous_mac_names, FontFixer


parser = argparse.ArgumentParser(description="Print out nameID" " strings of the fonts")
parser.add_argument("font", nargs="+")
parser.add_argument(
    "--autofix", default=False, action="store_true", help="Apply autofix"
)
parser.add_argument(
    "--csv",
    default=False,
    action="store_true",
    help="Output data in comma-separate-values" " (CSV) file format",
)
parser.add_argument("--id", "-i", default="all")
parser.add_argument("--platform", "-p", type=int, default=3)
parser.add_argument(
    "--drop-superfluous-mac-names",
    "-ms",
    default=False,
    action="store_true",
    help="Drop superfluous Mac names",
)
parser.add_argument(
    "--drop-mac-names",
    "-m",
    default=False,
    action="store_true",
    help="Drop all Mac name fields",
)


def delete_non_platform1_names(font):
    changed = False
    for name in font["name"].names:
        if name.platformID != 1:
            del name
            changed = True
    return changed


def main(args=None):
    args = parser.parse_args(args)
    nameids = ["1", "2", "4", "6", "16", "17", "18"]
    user_nameids = [x.strip() for x in args.id.split(",")]

    if "all" not in user_nameids:
        nameids = set(nameids) & set(user_nameids)

    rows = []
    for font in args.font:
        ttfont = ttLib.TTFont(font)
        row = [os.path.basename(font)]
        for name in ttfont["name"].names:
            if str(name.nameID) not in nameids or name.platformID != args.platform:
                continue

            value = name.string.decode(name.getEncoding()) or ""
            row.append(value)

        rows.append(row)

    header = ["filename"] + ["id" + x for x in nameids]

    def as_csv(rows):
        import csv
        import sys

        writer = csv.writer(sys.stdout)
        writer.writerows([header])
        writer.writerows(rows)
        sys.exit(0)

    if args.csv:
        as_csv(rows)

    print(tabulate.tabulate(rows, header, tablefmt="pipe"))

    for path in args.font:
        fixer = FontFixer(path, verbose=True)
        if args.autofix:
            fixer.fixes.append(delete_non_platform1_names)
        if args.drop_superfluous_mac_names:
            if has_mac_names(ttLib.TTFont(path)):
                fixer.fixes.append(drop_superfluous_mac_names)
            else:
                print("font %s has no mac nametable" % path)

        if args.drop_mac_names:
            if has_mac_names(ttLib.TTFont(path)):
                fixer.fixes.append(drop_mac_names)
            else:
                print("font %s has no mac nametable" % path)

        fixer.fix()


if __name__ == "__main__":
    main()
