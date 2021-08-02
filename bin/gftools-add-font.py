#!/usr/bin/env python3
# Copyright 2018 Google Inc. All Rights Reserved.
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
"""Utility to setup a font for addition to Piper.


Generate METADATA.pb files for font families.

METADATA.pb files are used to serve the families on http://fonts.google.com.
Font families are stored in this repo by license type. The following
directories contain font families:

../fonts/ofl
../fonts/apache
../fonts/ufl

Generating a METADATA.pb file for a new family:

1. Determine the family's license type, ofl, ufl or apache
2. Create a new folder under the license type directory
3. Name the folder so it's the family name, all lowercase and no spaces.
4. Run the following: gftools add-font /path/to/new/family
5. Update the category field in the generated METADATA.pb file.

Generating a METADATA.pb file for an existing family:

1. run the following: gftools add-font /path/to/existing/family
"""
import os
import sys
from google.protobuf import text_format
from gftools.addfont import MakeMetadata
from absl import flags
from absl import app


FLAGS = flags.FLAGS
flags.DEFINE_integer('min_pct', 50,
                     'What percentage of subset codepoints have to be supported'
                     ' for a non-ext subset.')
# if a single glyph from the 81 glyphs in *-ext_unique-glyphs.nam file is present, the font can have the "ext" subset
flags.DEFINE_float('min_pct_ext', 0.01,
                   'What percentage of subset codepoints have to be supported'
                   ' for a -ext subset.')


def _WriteTextFile(filename, text):
  """Write text to file.

  Nop if file exists with that exact content. This allows running against files
  that are in Piper and not marked for editing; you will get an error only if
  something changed.

  Args:
    filename: The file to write.
    text: The content to write to the file.
  """
  if os.path.isfile(filename):
    with open(filename, 'r') as f:
      current = f.read()
    if current == text:
      print('No change to %s' % filename)
      return

  with open(filename, 'w') as f:
    f.write(text)
  print('Wrote %s' % filename)


def main(argv):
  if len(argv) != 2:
    sys.exit('One argument, a directory containing a font family')
  fontdir = argv[1]

  is_new = True
  old_metadata_file = os.path.join(fontdir, 'METADATA.pb')
  if os.path.isfile(old_metadata_file):
    is_new = False

  metadata = MakeMetadata(fontdir, is_new, FLAGS.min_pct, FLAGS.min_pct_ext)
  text_proto = text_format.MessageToString(metadata, as_utf8=True)

  desc = os.path.join(fontdir, 'DESCRIPTION.en_us.html')
  if os.path.isfile(desc):
    print('DESCRIPTION.en_us.html exists')
  else:
    _WriteTextFile(desc, 'N/A')

  _WriteTextFile(os.path.join(fontdir, 'METADATA.pb'), text_proto)


if __name__ == '__main__':
    app.run(main)
