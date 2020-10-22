#!/usr/bin/env python3
# Copyright 2018 Google Inc. All Rights Reserved.
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
"""
A Python script to set a font's OS/2 usWeightClass value so it conforms to
the Google Fonts specification. The font's filename is used to determine
the correct value.
"""
from __future__ import print_function
from fontTools.ttLib import TTFont
from fontbakery.parse import style_parse
from gftools.fix import fix_weight_class
import sys
import os


def main(font_path):
    filename = os.path.basename(font_path)
    font = TTFont(font_path)
    current_weight_class = font["OS/2"].usWeightClass
    fix_weight_class(font)
    if current_weight_class != font["OS/2"].usWeightClass:
        font.save(font.reader.file.name + ".fix")
    else:
        print("{}: Skipping. Current WeightClass is correct".format(filename))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Please include a path to a font")
    else:
        main(sys.argv[1])

