#!/usr/bin/env python3
# Copyright 2022 The Google Fonts Tools Authors
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
from argparse import ArgumentParser
from fontTools.ttLib import TTFont

from gftools.meta import gen_meta_table


description = "Add a meta table to a font."

def main():
  parser = ArgumentParser(description=description)
  parser.add_argument('fonts', nargs='+')
  parser.add_argument('--dlng', help="Design languages (comma separated)")
  parser.add_argument('--slng', help="Supported languages (comma separated)")
  args = parser.parse_args()

  for path in args.fonts:
    font = TTFont(path)
    gen_meta_table(font, { "dlng": args.dlng or [], "slng": args.slng or [] })
    font.save(path)



if __name__ == '__main__':
  main()
