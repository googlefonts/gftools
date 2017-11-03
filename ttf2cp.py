#!/usr/bin/env python2
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
import os
import sys
import unicodedata
from google.apputils import app
import gflags as flags
from util import google_fonts as fonts

FLAGS = flags.FLAGS
flags.DEFINE_bool('show_char', False, 'Print the actual character')


def main(argv):
  if len(argv) != 2 or not os.path.isfile(argv[1]):
    sys.exit('Must have one argument, a font file.')

  for cp in sorted(fonts.CodepointsInFont(argv[1])):
    show_char = ''
    if FLAGS.show_char:
      show_char = ' ' + unichr(cp) + ' ' + unicodedata.name(unichr(cp), '')
    print '0x%04X%s' % (cp, show_char)

if __name__ == '__main__':
  app.run()
