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
"""Utility to print unicode character names from a nam file.

Input file should have one codepoint per line in hex (0xXXXX).

"""
from __future__ import print_function
import unicodedata
import sys
import argparse

parser = argparse.ArgumentParser(
    description="Add Unicode character names to a nam file"
)
parser.add_argument("--nam_file", help="Location of nam file")


def main(args=None):
    args = parser.parse_args(args)
    with open(args.nam_file, "r") as f:
        for line in f:
            print(_ReformatLine(line))


def _ReformatLine(line):
    if line.startswith("0x"):
        codepoint = int(line[2:6], 16)  # This'll only work for BMP...
        out = chr(codepoint) + " " + unicodedata.name(chr(codepoint), "")
        return "0x%04X  %s" % (codepoint, out)
    else:
        return line


if __name__ == "__main__":
    main()
