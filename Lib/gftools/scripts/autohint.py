#!/usr/bin/env python3
# Copyright 2022 The Google Font Tools Authors
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
"""gftools-autohint provides a wrapper around ttfautohint. We do this
for three reasons:

1) Installing gftools gives you the latest version of ttfautohint,
but the Python module we install does not provide a ttfautohint binary.
This script allows you to call the latest ttfautohint from the command
line.

2) ttfautohint does not allow you to save the autohinted output font
with the same path as the input font, requiring you to do boring
renaming dances. This script deals with that for you.

3) ttfautohint has a -D parameter to choose the default script for
OpenType features. gftools-autohint can determine this script
automatically.
"""

import argparse
import os
import shutil
import sys

from gftools.builder.autohint import autohint


def main(args=None):
    parser = argparse.ArgumentParser(
        description=("Automatically hint a TrueType font"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="#" * 79 + "\n" + __doc__,
    )
    parser.add_argument(
        "--fail-ok",
        action="store_true",
        help="If the autohinting fails, copy the input file to the output",
    )
    parser.add_argument(
        "--auto-script",
        action="store_true",
        help="Automatically determine the script for key glyphs",
    )
    parser.add_argument(
        "--discount-latin",
        action="store_true",
        help="When determining the script, ignore Latin glyphs",
    )
    parser.add_argument(
        "--args", help="Any additional arguments to pass to ttfautohint"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="File to save the autohinted font (may be same as input). Defaults to same as input.",
    )
    parser.add_argument("input", metavar="FONT", help="Font to hint")

    args = parser.parse_args(args)

    if not args.output:
        args.output = args.input

    rename = False
    if args.output == args.input:
        rename = True
        args.output += ".autohinted"

    extra_args = []
    if args.args:
        extra_args.extend(args.args.split(" "))

    if args.auto_script:
        add_script = "auto"
    else:
        add_script = False

    try:
        autohint(
            args.input,
            args.output,
            args=extra_args,
            discount_latin=args.discount_latin,
            add_script=add_script,
        )
    except Exception as e:
        if args.fail_ok:
            print(f"ttfautohint failed, just copying file: {e}", file=sys.stderr)
            shutil.copy(args.input, args.output)
        else:
            raise e

    if rename:
        os.rename(args.output, args.input)
