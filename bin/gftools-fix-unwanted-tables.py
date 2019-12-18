#!/usr/bin/env python3

# Copyright 2019 The Google Font Tools Authors
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
# See AUTHORS.txt for the list of Authors and LICENSE.txt for the License.
#

import argparse
import os
import sys

from fontTools.ttLib import TTFont

UNWANTED_TABLES = [
    "FFTM",
    "TTFA",
    "TSI0",
    "TSI1",
    "TSI2",
    "TSI3",
    "TSI5",
    "prop",
    "MVAR",
]


def parse_tables(table_string):
    return table_string.split(",")


def main():
    description = "Removes unwanted tables from one or more font files"
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        "-t", "--tables", type=str, help="One or more comma separated table names"
    )
    parser.add_argument("FONTPATH", nargs="+", help="One or more font files")

    args = parser.parse_args()

    if args.tables:
        user_table_request = parse_tables(args.tables)
        # validate user table removal request
        for table in user_table_request:
            if table not in UNWANTED_TABLES:
                sys.stderr.write(
                    "'{}' table cannot be removed with this script because it is not defined as an unwanted table.{}".format(
                        table, os.linesep
                    )
                )
                sys.stderr.write(
                    "The unwanted table list includes the following tables: {}{}".format(
                        UNWANTED_TABLES, os.linesep
                    )
                )
                sys.exit(1)
    else:
        user_table_request = UNWANTED_TABLES

    for fontpath in args.FONTPATH:
        # validate file
        if not os.path.exists(fontpath):
            sys.stderr.write(
                "The file path '{}' does not appear to be valid.{}".format(
                    fontpath, os.linesep
                )
            )
            sys.exit(1)

        try:
            tt = TTFont(fontpath)

            removed_table_list = []
            for table in user_table_request:
                if table in tt:
                    removed_table_list.append(table)
                    del tt[table]
                else:
                    print("'{}' table was not found in '{}'".format(table, fontpath))

            # save edited font
            tt.save(fontpath)

            # validate table removals
            tt_edited = TTFont(fontpath)
            for removed_table in removed_table_list:
                assert removed_table not in tt_edited
                print("'{}' table removed from '{}'".format(removed_table, fontpath))
        except Exception as e:
            sys.stderr.write("Error during execution: {}{}".format(str(e), os.linesep))
            sys.exit(1)


if __name__ == "__main__":
    main()
