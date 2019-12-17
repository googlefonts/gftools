#!/usr/bin/env python3
#
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
"""Utility to print unicode character names from a nam file.

Input file should have one codepoint per line in hex (0xXXXX).

"""
from __future__ import print_function
import unicodedata
import sys
if sys.version[0] == '3':
    unichr = chr
from absl import flags, app

FLAGS = flags.FLAGS

flags.DEFINE_string('nam_file', None, 'Location of nam file')


def main(_):
  with open(FLAGS.nam_file, 'r') as f:
    for line in f:
      print(_ReformatLine(line))


def _ReformatLine(line):
  if line.startswith('0x'):
    codepoint = int(line[2:6], 16)
    out = unichr(codepoint) + ' ' + unicodedata.name(unichr(codepoint), '')
    return '0x%04X  %s' % (codepoint, out)
  else:
    return line

if __name__ == '__main__':
  flags.mark_flag_as_required('nam_file')
  app.run(main)
