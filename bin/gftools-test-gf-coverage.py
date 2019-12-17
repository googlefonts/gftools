#!/usr/bin/env python3
# Copyright 2016 The Fontbakery Authors
# Copyright 2017 The Google Fonts Tools Authors
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
from __future__ import print_function
import os
import sys
from gftools.util.google_fonts import (CodepointsInFont,
                                       CodepointsInNamelist)
from pkg_resources import resource_filename


NAM_DIR = os.path.join(
    resource_filename("gftools", "encodings"), "GF Glyph Sets"
)
NAM_FILES = [os.path.join(NAM_DIR, f) for f in os.listdir(NAM_DIR)]


def main():
  if len(sys.argv) != 2 or sys.argv[1][-4:] != ".ttf":
    sys.exit('Usage: {} fontfile.ttf'.format(sys.argv[0]))

  expected = set()
  for nam_file in NAM_FILES:
    nam_filepath = os.path.join(NAM_DIR, nam_file)
    expected.update(CodepointsInNamelist(nam_filepath))

  filename = sys.argv[1]
  diff = expected - CodepointsInFont(filename)

  print(filename),
  if bool(diff):
    print('missing'),
    for c in sorted(diff):
      print('0x%04X' % (c)),
  else:
    print('OK')


if __name__ == '__main__':
  main()
