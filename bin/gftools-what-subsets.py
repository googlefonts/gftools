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
"""Tool to print subsets supported by a given font file.

"""
from __future__ import print_function
import os

from absl import flags
from gftools.util import google_fonts as fonts
from absl import app

FLAGS = flags.FLAGS

flags.DEFINE_integer('min_pct', 0,
                     'What percentage of subset codepoints have to be supported'
                     ' for a non-ext subset.')
flags.DEFINE_integer('min_pct_ext', 0,
                     'What percentage of subset codepoints have to be supported'
                     ' for a -ext subset.')


def main(argv):
  for arg in argv[1:]:
    subsets = fonts.SubsetsInFont(arg, FLAGS.min_pct, FLAGS.min_pct_ext)
    for (subset, available, total) in subsets:
      print('%s %s %d/%d' % (os.path.basename(arg), subset, available, total))


if __name__ == '__main__':
  app.run(main)
