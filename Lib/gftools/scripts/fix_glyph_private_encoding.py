#!/usr/bin/env python3
# Copyright 2013 The Font Bakery Authors.
# Copyright 2017 The Google Fonts Tools Authors.
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
from fontTools import ttLib
from gftools.fix import fix_pua, FontFixer
from gftools.utils import get_unencoded_glyphs


description = "Fixes TTF unencoded glyphs to have Private Use Area encodings"

parser = argparse.ArgumentParser(description=description)
parser.add_argument("ttf_font", nargs="+", help="Font in OpenType (TTF/OTF) format")
parser.add_argument(
    "--autofix",
    action="store_true",
    help="Apply autofix. " "Otherwise just check if there are unencoded glyphs",
)


def main(args=None):
    args = parser.parse_args(args)
    for path in args.ttf_font:
        if not os.path.exists(path):
            continue

        if args.autofix:
            FontFixer(path, fixes=[fix_pua], verbose=True).fix()
        else:
            font = ttLib.TTFont(path, 0)
            print(
                ("\nThese are the unencoded glyphs in font file '{0}':\n" "{1}").format(
                    path, "\n".join(get_unencoded_glyphs(font))
                )
            )


if __name__ == "__main__":
    main()
