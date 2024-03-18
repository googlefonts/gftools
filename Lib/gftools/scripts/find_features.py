#!/usr/bin/env python3
#
# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Tool to print GPOS and GSUB features supported by font file(s).

"""
from __future__ import print_function
from argparse import ArgumentParser
import os
import sys
from fontTools.ttLib import TTFont


def ListFeatures(font):
    """List features for specified font. Table assumed structured like GPS/GSUB.

    Args:
      font: a TTFont.
    Returns:
      List of 3-tuples of ('GPOS', tag, name) of the features in the font.
    """
    results = []
    for tbl in ["GPOS", "GSUB"]:
        if tbl in font.keys():
            results += [
                (
                    tbl,
                    f.FeatureTag,
                    "lookups: [{}]".format(
                        ", ".join(map(str, f.Feature.LookupListIndex))
                    ),
                )
                for f in font[tbl].table.FeatureList.FeatureRecord
            ]
    return results


def main(args=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("path", metavar="PATH", help="Path to a font file or directory")

    args = parser.parse_args(args)
    if args.path.endswith(".ttf"):
        font_files = [args.path]
    elif os.path.isdir(args.path):
        font_files = glob(args.path + "/*.ttf")

    for font_file in font_files:
        features = []
        with TTFont(font_file) as font:
            features += ListFeatures(font)

        for table, tag, lookup_name in features:
            print(
                "{:32s} {:4s} {:8s} {:15s}".format(
                    os.path.basename(font_file), table, str(tag), lookup_name
                )
            )


if __name__ == "__main__":
    main()
