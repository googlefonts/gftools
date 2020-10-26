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
from gftools.fix import UNWANTED_TABLES, remove_tables


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

    tables = parse_tables(args.tables) if args.tables else None

    for fontpath in args.FONTPATH:
        ttfont = TTFont(fontpath)
        remove_tables(ttfont, tables)
        ttfont.save(fontpath)


if __name__ == "__main__":
    main()
