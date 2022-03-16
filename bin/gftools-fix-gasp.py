#!/usr/bin/env python3
# Copyright 2013 The Font Bakery Authors.
# Copyright 2017 The Google Font Tools Authors
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
from gftools.fix import GaspFixer

description = 'Fixes TTF GASP table'
parser = argparse.ArgumentParser(description=description)
parser.add_argument('ttf_font', nargs='+',
                    help="Font in OpenType (TTF/OTF) format")
parser.add_argument('--autofix', action='store_true', help='Apply autofix')
parser.add_argument('--set', type=int,
                    help=('Change gasprange value of key 65535'
                          ' to new value'), default=None)


def main():
    args = parser.parse_args()
    for path in args.ttf_font:
        if args.set is not None:
            GaspFixer(path).fix(args.set)
        elif args.autofix:
            GaspFixer(path).fix()
        else:
            GaspFixer(path).show()

if __name__ == '__main__':
  main()
