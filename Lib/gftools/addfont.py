from __future__ import print_function
import re
from functools import cmp_to_key
import os
import contextlib
import errno
import glob
from fontTools import ttLib
import time
from google.protobuf import text_format
import gftools.fonts_public_pb2 as fonts_pb2
from gftools.util import google_fonts as fonts
from gftools.utils import cmp

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


def MakeMetadata(fontdir, is_new, min_pct=50, min_pct_ext=0.01):
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
    first_file, min_pct, min_pct_ext
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


def _AddHumanReadableDateComment(text_proto):
  return re.sub(r'(date_added: \d+)',
                r'\1  # ' + time.strftime('%Y-%m-%d'), text_proto)