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
"""Tool to print subsets supported by a given font file.

"""
from __future__ import print_function
import argparse
import os

from gfsubsets import SubsetsInFont

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--min_pct",
    type=int,
    default=0,
    help="What percentage of subset codepoints have to be supported"
    " for a non-ext subset.",
)
parser.add_argument(
    "--min_pct_ext",
    type=int,
    default=0,
    help="What percentage of subset codepoints have to be supported"
    " for an -ext subset.",
)
parser.add_argument("fonts", nargs="+", metavar="FONT")


def main(args=None):
    args = parser.parse_args(args)
    for arg in args.fonts:
        subsets = SubsetsInFont(arg, args.min_pct, args.min_pct_ext)
        for subset, available, total in subsets:
            print("%s %s %d/%d" % (os.path.basename(arg), subset, available, total))


if __name__ == "__main__":
    main()
