#!/usr/bin/env python3
# Copyright 2017 Google Inc. All Rights Reserved.
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
"""Utility to dump codepoints in a font.

Prints codepoints supported by the font, one per line, in hex (0xXXXX).

"""

import os
import sys
import unicodedata

from absl import flags
from gftools.util import google_fonts as fonts
from absl import app
import sys
if sys.version[0] == '3':
    unichr = chr

FLAGS = flags.FLAGS
flags.DEFINE_bool('show_char', False, 'Print the actual character')
flags.DEFINE_bool('show_subsets', False,
                  'Print what subsets, if any, char is in')


def main(argv):
  if len(argv) < 2:
    sys.exit('Must specify one or more font files.')

  cps = set()
  for filename in argv[1:]:
    if not os.path.isfile(filename):
      sys.exit('%s is not a file' % filename)
    cps |= fonts.CodepointsInFont(filename)

  for cp in sorted(cps):
    show_char = ''
    if FLAGS.show_char:
      show_char = (' ' + unichr(cp).strip() + ' ' +
                   unicodedata.name(unichr(cp), ''))
    show_subset = ''
    if FLAGS.show_subsets:
      show_subset = ' subset:%s' % ','.join(fonts.SubsetsForCodepoint(cp))

    print(u'0x%04X%s%s' % (cp, show_char, show_subset))

if __name__ == '__main__':
  app.run(main)
