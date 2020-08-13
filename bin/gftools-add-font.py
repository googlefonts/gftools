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
from __future__ import print_function
from functools import cmp_to_key
import contextlib
import errno
import glob
import os
import sys
import time
from fontTools import ttLib


from absl import flags
import gftools.fonts_public_pb2 as fonts_pb2
from gftools.util import google_fonts as fonts
from gftools.utils import cmp
from absl import app
from google.protobuf import text_format

FLAGS = flags.FLAGS

flags.DEFINE_integer('min_pct', 50,
                     'What percentage of subset codepoints have to be supported'
                     ' for a non-ext subset.')
# if a single glyph from the 81 glyphs in *-ext_unique-glyphs.nam file is present, the font can have the "ext" subset
flags.DEFINE_float('min_pct_ext', 0.01,
                   'What percentage of subset codepoints have to be supported'
                   ' for a -ext subset.')


def _FileFamilyStyleWeights(fontdir):
  """Extracts file, family, style, weight 4-tuples for each font in dir.

  Args:
    fontdir: Directory that supposedly contains font files for a family.
  Returns:
    List of fonts.FileFamilyStyleWeightTuple ordered by weight, style
    (normal first).
  Raises:
    OSError: If the font directory doesn't exist (errno.ENOTDIR) or has no font
    files (errno.ENOENT) in it.
    RuntimeError: If the font directory appears to contain files from multiple
    families.
  """
  if not os.path.isdir(fontdir):
    raise OSError(errno.ENOTDIR, 'No such directory', fontdir)

  files = glob.glob(os.path.join(fontdir, '*.[ot]tf'))
  if not files:
    raise OSError(errno.ENOENT, 'no font files found')

  result = [fonts.FamilyStyleWeight(f) for f in files]
  def _Cmp(r1, r2):
    return cmp(r1.weight, r2.weight) or -cmp(r1.style, r2.style)
  result = sorted(result, key=cmp_to_key(_Cmp))

  family_names = {i.family for i in result}
  if len(family_names) > 1:
    raise RuntimeError('Ambiguous family name; possibilities: %s'
                       % family_names)

  return result


def _MakeMetadata(fontdir, is_new):
  """Builds a dictionary matching a METADATA.pb file.

  Args:
    fontdir: Directory containing font files for which we want metadata.
    is_new: Whether this is an existing or new family.
  Returns:
    A fonts_pb2.FamilyProto message, the METADATA.pb structure.
  Raises:
    RuntimeError: If the variable font axes info differs between font files of
    same family.
  """
  file_family_style_weights = _FileFamilyStyleWeights(fontdir)

  first_file = file_family_style_weights[0].file
  old_metadata_file = os.path.join(fontdir, 'METADATA.pb')
  font_license = fonts.LicenseFromPath(fontdir)

  metadata = fonts_pb2.FamilyProto()
  metadata.name = file_family_style_weights[0].family

  subsets_in_font = [s[0] for s in fonts.SubsetsInFont(
    first_file, FLAGS.min_pct, FLAGS.min_pct_ext
  )]

  if not is_new:
    old_metadata = fonts_pb2.FamilyProto()
    with open(old_metadata_file, 'rb') as old_meta:
      text_format.Parse(old_meta.read(), old_metadata)
      metadata.designer = old_metadata.designer
      metadata.category = old_metadata.category
      metadata.date_added = old_metadata.date_added
      subsets = set(old_metadata.subsets) | set(subsets_in_font)
  else:
    metadata.designer = 'UNKNOWN'
    metadata.category = 'SANS_SERIF'
    metadata.date_added = time.strftime('%Y-%m-%d')
    subsets = ['menu'] + subsets_in_font

  metadata.license = font_license
  subsets = sorted(subsets)
  for subset in subsets:
    metadata.subsets.append(subset)

  for (fontfile, family, style, weight) in file_family_style_weights:
    filename = os.path.basename(fontfile)
    font_psname = fonts.ExtractName(fontfile, fonts.NAME_PSNAME,
                                    os.path.splitext(filename)[0])
    font_copyright = fonts.ExtractName(fontfile, fonts.NAME_COPYRIGHT,
                                       '???.').strip()

    font_metadata = metadata.fonts.add()
    font_metadata.name = family
    font_metadata.style = style
    font_metadata.weight = weight
    font_metadata.filename = filename
    font_metadata.post_script_name = font_psname
    default_fullname = os.path.splitext(filename)[0].replace('-', ' ')
    font_metadata.full_name = fonts.ExtractName(fontfile, fonts.NAME_FULLNAME,
                                                default_fullname)
    font_metadata.copyright = font_copyright

  axes_info_from_font_files \
    = {_AxisInfo(f.file) for f in file_family_style_weights}
  if len(axes_info_from_font_files) != 1:
    raise RuntimeError('Variable axes info not matching between font files')

  for axes_info in axes_info_from_font_files:
    if axes_info:
      for axes in axes_info:
        var_axes = metadata.axes.add()
        var_axes.tag = axes[0]
        var_axes.min_value = axes[1]
        var_axes.max_value = axes[2]

  return metadata


def _AxisInfo(fontfile):
  """Gets variable axes info.

  Args:
    fontfile: Font file to look at for variation info

  Returns:
    Variable axes info
  """
  with contextlib.closing(ttLib.TTFont(fontfile)) as font:
    if 'fvar' not in font:
      return frozenset()
    else:
      fvar = font['fvar']
      axis_info = [
          (a.axisTag, a.minValue, a.maxValue) for a in fvar.axes
      ]
      return tuple(sorted(axis_info))


def _GetAvgSize(file_family_style_weights):
  """Gets average file size of all font weights.

  Returns:
       average file size.

  Args:
    file_family_style_weights: List of fonts.FileFamilyStyleWeightTuple.
  """
  total_size = 0
  for list_tuple in file_family_style_weights:
    total_size += os.stat(list_tuple.file).st_size
  return total_size / len(file_family_style_weights)


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




def _AddHumanReadableDateComment(text_proto):
  return re.sub(r'(date_added: \d+)',
                r'\1  # ' + time.strftime('%Y-%m-%d'), text_proto)


def main(argv):
  if len(argv) != 2:
    sys.exit('One argument, a directory containing a font family')
  fontdir = argv[1]

  is_new = True
  old_metadata_file = os.path.join(fontdir, 'METADATA.pb')
  if os.path.isfile(old_metadata_file):
    is_new = False

  metadata = _MakeMetadata(fontdir, is_new)
  text_proto = text_format.MessageToString(metadata, as_utf8=True)

  desc = os.path.join(fontdir, 'DESCRIPTION.en_us.html')
  if os.path.isfile(desc):
    print('DESCRIPTION.en_us.html exists')
  else:
    _WriteTextFile(desc, 'N/A')

  _WriteTextFile(os.path.join(fontdir, 'METADATA.pb'), text_proto)



if __name__ == '__main__':
    app.run(main)
