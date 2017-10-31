#!/usr/bin/env python2
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
import os
import sys
from util.google_fonts import (CodepointsInFont,
                               codepointsInNamelist)

NAM_DIR = os.path.join("encodings", "GF Glyph Sets")
NAM_FILES = [
  "GF-latin-core_unique-glyphs.nam",
  "GF-latin-expert_unique-glyphs.nam",
  "GF-latin-plus_optional-glyphs.nam",
  "GF-latin-plus_unique-glyphs.nam",
  "GF-latin-pro_optional-glyphs.nam",
  "GF-latin-pro_unique-glyphs.nam"
]

def main():
  if len(sys.argv) != 2 or sys.argv[1][-4:] != ".ttf":
    sys.exit('Usage: {} fontfile.ttf'.format(sys.argv[0]))

  expected = set()
  for nam_file in NAM_FILES:
    nam_filepath = os.path.join(NAM_DIR, nam_file)
    expected.update(codepointsInNamelist(nam_filepath))

  filename = sys.argv[1]
  cps = CodepointsInFont(filename)
  diff = cps - expected
  if bool(diff):
    print 'The following codepoints are\n missing on %s:\n' % (filename)
    for c in sorted(diff):
      print '0x%04X' % (c)
  else:
    print '%s contains all chars in the GF glyph-sets!' % (filename)


if __name__ == '__main__':
  main()
