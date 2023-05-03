#!/usr/bin/env python3
#
# Copyright 2014-2022 Google Inc. All rights reserved.
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

"""Tests vertical extents of fonts for fitting in specified boundaries.

Specifying the language is useful when language-specific features are
supported in the font, like in the case of Marathi, Persian, and Urdu.

Typically, ymin and ymax shouldn't be specified. If not specified, they will
be checked according to Noto specs.

For fonts that don't have UI in their files name but should be tested
according to UI specs, ymin and ymax should be specified on the command line.
"""

from argparse import ArgumentParser

parser = ArgumentParser(description=__doc__)
parser.add_argument("font", help="Fonts in OpenType (TTF/OTF) format")
parser.add_argument("language", help="Language to pass to Harfbuzz", nargs="?")
parser.add_argument("ymin", help="Minimum extent for UI fonts", nargs="?", type=int)
parser.add_argument("ymax", help="Maximum extent for UI fonts", nargs="?", type=int)

__author__ = "roozbeh@google.com (Roozbeh Pournader)"

import itertools
import os
import re
import sys
import xml.etree.ElementTree
from vharfbuzz import Vharfbuzz
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen


def _regular_expression_from_set(character_set):
    """Returns a regexp matching any sequence of a set of input characters."""
    character_set -= set(range(0x00, 0x20))  # Remove ASCII controls

    literal_list = []
    for code in character_set:
        char = chr(code)
        if char in ["\\", "[", "]", "^", "-"]:
            char = "\\" + char
        literal_list.append(char)
    regexp = "[" + "".join(literal_list) + "]+"
    return re.compile(regexp)


def get_glyph_vertical_extents(glyph_id, font):
    glyph_order = font.getGlyphOrder()
    glyf_set = font.getGlyphSet()
    glyphname = glyph_order[glyph_id]
    ttglyph = glyf_set[glyphname]
    pen = BoundsPen(glyf_set, ignoreSinglePoints=True)
    ttglyph.draw(pen)
    if not pen.bounds:
        return None, None
    return pen.bounds[1], pen.bounds[3]


def buf_extents(buf, font):
    maxes = []
    mins = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyph_ymin, glyph_ymax = get_glyph_vertical_extents(info.codepoint, font)
        if glyph_ymax is not None:
            glyph_vertical_offset = pos.position[1]
            maxes.append(glyph_ymax + glyph_vertical_offset)
            mins.append(glyph_ymin + glyph_vertical_offset)
    if maxes and mins:
        return min(mins), max(maxes)


def test_rendering(data, font_file_name, min_allowed, max_allowed, language=None):
    """Test the rendering of the input data in a given font.

    The input data is first filtered for sequences supported in the font.
    """
    vhb = Vharfbuzz(font_file_name)
    font_characters = set(vhb.ttfont.getBestCmap().keys())
    # Hack to add ASCII digits, even if the font doesn't have them,
    # to keep potential frequency info in the input intact
    font_characters |= set(range(ord("0"), ord("9") + 1))

    supported_chars_regex = _regular_expression_from_set(font_characters)

    harfbuzz_input = []
    exceeding_lines = []

    for match in supported_chars_regex.finditer(data):
        harfbuzz_input.append(match.group(0))

    params = None
    if language:
        params = {"language": language}

    for s in harfbuzz_input:
        buf = vhb.shape(s, params)
        min_height, max_height = buf_extents(buf, vhb.ttfont)
        if min_height is None:
            continue
        if min_height < min_allowed or max_height > max_allowed:
            exceeding_lines.append(((min_height, max_height), s))

    return exceeding_lines


def test_rendering_from_file(
    file_handle, font_file_name, min_allowed, max_allowed, language=None
):
    """Test the rendering of the contents of a file for vertical extents.

    Supports both text files and XTB files.
    """

    input_data = file_handle.read()

    if input_data.startswith("<?xml"):
        # XML mode, assume .xtb file
        root = xml.etree.ElementTree.fromstring(input_data)
        assert root.tag == "translationbundle"

        test_strings = []
        for child in root:
            if child.text is not None:
                test_strings.append(child.text)
        input_data = "\n".join(test_strings)

    else:
        # Assume text file, with all the data as one large string
        # input_data = input_data.decode("UTF-8")
        pass

    # Now, input_data is just a long string, with new lines as separators.

    return test_rendering(
        input_data, font_file_name, min_allowed, max_allowed, language
    )


def test_all_combinations(
    max_len, font_file_name, min_allowed, max_allowed, language=None
):
    """Tests the rendering of all combinations up to certain length."""

    font_characters = coverage.character_set(font_file_name)
    font_characters -= set(range(0x00, 0x20))  # Remove ASCII controls
    font_characters = [unichr(code) for code in font_characters]
    font_characters = sorted(font_characters)

    all_strings = []
    for length in range(1, max_len + 1):
        all_combinations = itertools.product(font_characters, repeat=length)
        all_strings += ["".join(comb) for comb in all_combinations]

    test_data = "\n".join(all_strings)
    return test_rendering(test_data, font_file_name, min_allowed, max_allowed, language)


def _is_noto_ui_font(font_file_name):
    """Returns true if a font file is a Noto UI font."""
    base_name = os.path.basename(font_file_name)
    return base_name.startswith("Noto") and "UI-" in base_name


def main(args=None):
    """Check vertical extents to make sure they stay within specified bounds."""
    args = parser.parse_args(args)
    if not args.ymax:
        font = TTFont(args.font)
        args.ymin = -font["OS/2"].usWinDescent
        args.ymax = font["OS/2"].usWinAscent
        if _is_noto_ui_font(args.font):
            args.ymin = max(args.ymin, -555)
            arg.ymax = min(args.ymax, 2163)

    exceeding_lines = test_rendering_from_file(
        sys.stdin, args.font, args.ymin, args.ymax, args.language
    )

    for line_bounds, text_piece in exceeding_lines:
        print(text_piece, line_bounds)

    # print(test_all_combinations(3, font_file_name, ymin, ymax))


if __name__ == "__main__":
    main()
