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
from argparse import ArgumentParser
from gftools.fix import (
    convert_cmap_subtables_to_v4,
    drop_nonpid0_cmap,
    drop_mac_cmap,
    FontFixer,
)

description = "Manipulate a collection of fonts' cmap tables."


def convert_cmap_subtables_to_v4_with_report(font):
    converted = convert_cmap_subtables_to_v4(font)
    for c in converted:
        print(
            (
                "Converted format {} cmap subtable"
                " with Platform ID = {} and Encoding ID = {}"
                " to format 4."
            ).format(c)
        )
    return converted


def main(args=None):
    parser = ArgumentParser(description=description)
    parser.add_argument("fonts", nargs="+")
    parser.add_argument(
        "--format-4-subtables",
        "-f4",
        default=False,
        action="store_true",
        help="Convert cmap subtables to format 4",
    )
    parser.add_argument(
        "--drop-mac-subtable",
        "-dm",
        default=False,
        action="store_true",
        help="Drop Mac cmap subtables",
    )
    parser.add_argument(
        "--keep-only-pid-0",
        "-k0",
        default=False,
        action="store_true",
        help=("Keep only cmap subtables with pid=0" " and drop the rest."),
    )
    args = parser.parse_args(args)

    for path in args.fonts:
        fixer = FontFixer(path, verbose=True)
        if args.format_4_subtables:
            print("\nConverting Cmap subtables to format 4...")
            fixer.fixes.append(convert_cmap_subtables_to_v4_with_report)

        if args.keep_only_pid_0:
            print(
                "\nDropping all Cmap subtables,"
                " except the ones with PlatformId = 0..."
            )
            fixer.fixes.append(drop_nonpid0_cmap)
        elif args.drop_mac_subtable:
            print("\nDropping any Cmap Mac subtable...")
            fixer.fixes.append(drop_mac_cmap)

        fixer.fix()


if __name__ == "__main__":
    main()
