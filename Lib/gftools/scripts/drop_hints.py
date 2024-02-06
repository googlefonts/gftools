#!/usr/bin/env python3
#
# Copyright 2014 Google Inc. All rights reserved.
# Copyright 2021 The Google Font Tools Authors
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
"""Drop hints from a font."""
import argparse
import array
from fontTools.ttLib import TTFont

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("input", help="font file to process")
parser.add_argument("output", help="file to save font", nargs="?")


def drop_hints_from_glyphs(font):
    """Drops the hints from a font's glyphs."""
    glyf_table = font["glyf"]
    for glyph_index in range(len(glyf_table.glyphOrder)):
        glyph_name = glyf_table.glyphOrder[glyph_index]
        glyph = glyf_table[glyph_name]
        if glyph.numberOfContours > 0:
            if glyph.program.bytecode:
                glyph.program.bytecode = array.array("B")


def drop_tables(font, tables):
    """Drops the listed tables from a font."""
    for table in tables:
        if table in font:
            del font[table]


def main(args=None):
    """Drop the hints from the first file specified and save as second."""
    args = parser.parse_args(args)
    font = TTFont(args.input)

    drop_hints_from_glyphs(font)
    drop_tables(font, ["cvt ", "fpgm", "hdmx", "LTSH", "prep", "VDMX"])

    if not args.output:
        args.output = args.input

    font.save(args.output)


if __name__ == "__main__":
    main()
