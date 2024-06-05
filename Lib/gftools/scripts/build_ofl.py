#!/usr/bin/env python3
#
# Copyright 2016 The Fontbakery Authors
# Copyright 2017 The Google Font Tools Authors
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
"""
Generate an OFL.txt license document from font copyright strings
"""
import argparse
import os
import logging
from fontTools.ttLib import TTFont
from pathlib import Path
from gftools.fix import fix_ofl_license


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("fonts", nargs="+", type=TTFont)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args(args)

    with open(args.out_dir / "OFL.txt", "w", encoding="utf-8") as doc:
        doc.write(fix_ofl_license(args.fonts[0]))


if __name__ == "__main__":
    main()
