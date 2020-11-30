#!/usr/bin/env python3
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
Update a collection of fonts fsType value to Installable Embedding.

Google Fonts requires Installable Embedding (0):
https://github.com/googlefonts/gf-docs/blob/master/ProjectChecklist.md#fstype

Microsoft OpenType specification:
https://www.microsoft.com/typography/otspec/os2.htm#fst
"""
from __future__ import print_function
from argparse import (ArgumentParser,
                      RawTextHelpFormatter)
from gftools.fix import fix_fs_type, FontFixer
parser = ArgumentParser(description=__doc__,
                        formatter_class=RawTextHelpFormatter)
parser.add_argument('fonts',
                    nargs="+",
                    help="Fonts in OpenType (TTF/OTF) format")


def main():
  args = parser.parse_args()
  for font_path in args.fonts:
    FontFixer(font_path, fixes=[fix_fs_type], verbose=True).fix()


if __name__ == '__main__':
  main()
