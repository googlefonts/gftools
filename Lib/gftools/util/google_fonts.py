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
"""Helper APIs for interaction with Google Fonts.

Provides APIs to interact with font subsets, codepoints for font or subset.


To run the tests:
$ cd fonts/tools
fonts/tools$ python util/google_fonts.py
# or do:
fonts/tools$ python util/google_fonts.py --nam_dir encodings/
"""

from __future__ import print_function
from __future__ import unicode_literals

import codecs
import collections
import contextlib
import errno
import os
import re
import sys
import unittest
from pkg_resources import resource_filename
from warnings import warn

if __name__ == '__main__':
  # some of the imports here wouldn't work otherwise
  sys.path.append(
      os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gftools.fonts_public_pb2 as fonts_pb2
from fontTools import ttLib
from absl import flags
from gftools.util import py_subsets
from google.protobuf import text_format


FLAGS = flags.FLAGS
flags.DEFINE_string('nam_dir',
                    resource_filename("gftools", "encodings"), 'nam file dir')

# See https://www.microsoft.com/typography/otspec/name.htm.
NAME_COPYRIGHT = 0
NAME_FAMILY = 1
NAME_UNIQUEID = 3
NAME_FULLNAME = 4
NAME_PSNAME = 6


_PLATFORM_ID_MICROSOFT = 3
_PLATFORM_ENC_UNICODE_BMP = 1
_PLATFORM_ENC_UNICODE_UCS4 = 10
_PLATFORM_ENCS_UNICODE = (_PLATFORM_ENC_UNICODE_BMP, _PLATFORM_ENC_UNICODE_UCS4)

_FAMILY_WEIGHT_REGEX = r'([^/-]+)-(\w+)\.[ot]tf$'

# Matches 4 or 5 hexadecimal digits that are uppercase at the beginning of the
# test string. The match is stored in group 0, e.g:
# >>> _NAMELIST_CODEPOINT_REGEX.match('1234X').groups()[0]
# '1234'
# >>> _NAMELIST_CODEPOINT_REGEX.match('1234A').groups()[0]
# '1234A'
_NAMELIST_CODEPOINT_REGEX = re.compile('^([A-F0-9]{4,5})')

# The canonical [to Google Fonts] name comes before any aliases
_KNOWN_WEIGHTS = collections.OrderedDict([
    ('Thin', 100),
    ('Hairline', 100),
    ('ExtraLight', 200),
    ('Light', 300),
    ('Regular', 400),
    ('', 400),  # Family-Italic resolves to this
    ('Medium', 500),
    ('SemiBold', 600),
    ('Bold', 700),
    ('ExtraBold', 800),
    ('Black', 900)
])

_VALID_STYLES = {'normal', 'italic'}

# (Mask, Name) pairs.
# See https://www.microsoft.com/typography/otspec/os2.htm#fss.
_FS_SELECTION_BITS = tuple(
    (1 << i, n)
    for i, n in enumerate(('ITALIC', 'UNDERSCORE', 'NEGATIVE', 'OUTLINED',
                           'STRIKEOUT', 'BOLD', 'REGULAR', 'USE_TYPO_METRICS',
                           'WWS', 'OBLIQUE')))


# license_dir => license name mappings
_KNOWN_LICENSE_DIRS = {
    'apache': 'APACHE2',
    'ofl': 'OFL',
    'ufl': 'UFL',
}


FileFamilyStyleWeightTuple = collections.namedtuple(
    'FileFamilyStyleWeightTuple', ['file', 'family', 'style', 'weight'])


class Error(Exception):
  """Base for Google Fonts errors."""


class ParseError(Error):
  """Exception used when parse failed."""




def UnicodeCmapTables(font):
  """Find unicode cmap tables in font.

  Args:
    font: A TTFont.
  Yields:
    cmap tables that contain unicode mappings
  """
  for table in font['cmap'].tables:
    if (table.platformID == _PLATFORM_ID_MICROSOFT and
        table.platEncID in _PLATFORM_ENCS_UNICODE):
      yield table


_displayed_errors = set()
def ShowOnce(msg):
  """Display a message if that message has not been shown already.

  Unlike logging.log_first_n, this will display multiple messages from the same
  file/line if they are different. This helps for things like the same line
  that shows 'missing %s': we'll see each value of %s instead of only the first.

  Args:
    msg: A string message to write to stderr.
  """
  global _displayed_errors
  if msg in _displayed_errors:
    return
  _displayed_errors.add(msg)
  print(msg, file=sys.stderr)


def UniqueSort(*args):
  """Returns a sorted list of the unique items from provided iterable(s).

  Args:
    *args: Iterables whose items will be merged, sorted and de-duplicated.
  Returns:
    A list.
  """
  s = set()
  for arg in args:
    s.update(arg)
  return sorted(s)


def RegularWeight(metadata):
  """Finds the filename of the regular (normal/400) font file.

  Args:
    metadata: The metadata to search for the regular file data.
  Returns:
    The name of the regular file, usually Family-Regular.ttf.
  Raises:
    OSError: If regular file could not be found. errno.ENOENT.
  """
  for f in metadata.fonts:
    if f.weight == 400 and f.style == 'normal':
      return os.path.splitext(f.filename)[0] + '.ttf'

  name = '??'
  if metadata.HasField('name'):
    name = metadata.name
  raise OSError(errno.ENOENT, 'unable to find regular weight in %s' % name)


def ListSubsets():
  """Returns a list of all subset names, in lowercase."""
  return py_subsets.SUBSETS


def Metadata(file_or_dir):
  """Returns fonts_metadata.proto object for a metadata file.

  If file_or_dir is a file named METADATA.pb, load it. If file_or_dir is a
  directory, load the METADATA.pb file in that directory.

  Args:
    file_or_dir: A file or directory.
  Returns:
    Python object loaded from METADATA.pb content.
  Raises:
    ValueError: if file_or_dir isn't a METADATA.pb file or dir containing one.
  """
  if (os.path.isfile(file_or_dir) and
      os.path.basename(file_or_dir) == 'METADATA.pb'):
    metadata_file = file_or_dir
  elif os.path.isdir(file_or_dir):
    metadata_file = os.path.join(file_or_dir, 'METADATA.pb')
    if not os.path.isfile(metadata_file):
      raise ValueError('No METADATA.pb in %s' % file_or_dir)
  else:
    raise ValueError(
        '%s is neither METADATA.pb file or a directory' % file_or_dir)

  msg = fonts_pb2.FamilyProto()
  with codecs.open(metadata_file, encoding='utf-8') as f:
    text_format.Merge(f.read(), msg)

  return msg


def SubsetsForCodepoint(cp):
  """Returns all the subsets that contains cp or [].

  Args:
    cp: int codepoint.
  Returns:
    List of lowercase names of subsets or [] if none match.
  """
  subsets = []
  for subset in ListSubsets():
    cps = CodepointsInSubset(subset, unique_glyphs=True)
    if not cps:
      continue
    if cp in cps:
      subsets.append(subset)
  return subsets


def SubsetForCodepoint(cp):
  """Returns the highest priority subset that contains cp or None.

  Args:
    cp: int codepoint.
  Returns:
    The lowercase name of the subset, e.g. latin, or None.
  """
  subsets = SubsetsForCodepoint(cp)
  if not subsets:
    return None

  result = subsets[0]
  for subset in sorted(subsets):
    # prefer x to x-ext
    if result + '-ext' == subset:
      pass
    elif result == subset + '-ext':
      # prefer no -ext to -ext
      result = subset
    elif subset.startswith('latin'):
      # prefer latin to anything non-latin
      result = subset

  return result


def CodepointsInSubset(subset, unique_glyphs=False):
  """Returns the set of codepoints contained in a given subset.

  Args:
    subset: The lowercase name of a subset, e.g. latin.
    unique_glyphs: Optional, whether to only include glyphs unique to subset.
  Returns:
    A set containing the glyphs in the subset.
  """
  if unique_glyphs:
    filenames = [CodepointFileForSubset(subset)]
  else:
    filenames = CodepointFiles(subset)

  filenames = [f for f in filenames if f is not None]

  if not filenames:
    return None

  cps = set()
  for filename in filenames:
    with codecs.open(filename, encoding='utf-8') as f:
      for line in f:
        if not line.startswith('#'):
          match = _NAMELIST_CODEPOINT_REGEX.match(line[2:7])
          if match is not None:
            cps.add(int(match.groups()[0], 16))

  return cps


def CodepointsInFont(font_filename):
  """Returns the set of codepoints present in the font file specified.

  Args:
    font_filename: The name of a font file.
  Returns:
    A set of integers, each representing a codepoint present in font.
  """

  font_cps = set()
  with contextlib.closing(ttLib.TTFont(font_filename)) as font:
    for t in UnicodeCmapTables(font):
      font_cps.update(t.cmap.keys())

  return font_cps


def CodepointFileForSubset(subset):
  """Returns the full path to the file of codepoints unique to subset.

  This API does NOT return additional codepoint files that are normally merged
  into the subset. For that, use CodepointFiles.

  Args:
    subset: The subset we want the codepoint file for.
  Returns:
    Full path to the file containing the codepoint file for subset or None if it
    could not be located.
  Raises:
    OSError: If the --nam_dir doesn't exist. errno.ENOTDIR.
  """
  # expanduser so we can do things like --nam_dir=~/oss/googlefontdirectory/
  enc_path = os.path.expanduser(FLAGS.nam_dir)
  if not os.path.exists(enc_path):
    raise OSError(errno.ENOTDIR, 'No such directory', enc_path)

  filename = os.path.join(enc_path, '%s_unique-glyphs.nam' % subset)
  if not os.path.isfile(filename):
    ShowOnce('no cp file for %s found at %s' % (subset,
                                                filename[len(enc_path):]))
    return None

  return filename


def CodepointFiles(subset):
  """Returns the codepoint files that contain the codepoints in a merged subset.

  If a subset X includes codepoints from multiple files, this function
  returns all those files while CodepointFileForSubset returns the single
  file that lists the codepoints unique to the subset. For example, greek-ext
  contains greek-ext, greek, and latin codepoints. This function would return
  all three files whereas CodepointFileForSubset would return just greek-ext.

  Args:
    subset: The subset we want the codepoint files for.
  Returns:
    A list of 1 or more codepoint files that make up this subset.
  """
  files = [subset]

  # y-ext includes y
  # Except latin-ext which already has latin.
  if subset != 'latin-ext' and subset.endswith('-ext'):
    files.append(subset[:-4])

  # almost all subsets include latin.
  if subset not in ('khmer', 'latin'):
    files.append('latin')

  return map(CodepointFileForSubset, files)


def SubsetsInFont(file_path, min_pct, ext_min_pct=None):
  """Finds all subsets for which we support > min_pct of codepoints.

  Args:
    file_path: A file_path to a font file.
    min_pct: Min percent coverage to report a subset. 0 means at least 1 glyph.
    25 means 25%.
    ext_min_pct: The minimum percent coverage to report a -ext
    subset supported. Used to admit extended subsets with a lower percent. Same
    interpretation as min_pct. If None same as min_pct.
  Returns:
    A list of 3-tuples of (subset name, #supported, #in subset).
  """
  all_cps = CodepointsInFont(file_path)

  results = []
  for subset in ListSubsets():
    subset_cps = CodepointsInSubset(subset, unique_glyphs=True)
    if not subset_cps:
      continue

    # Khmer includes latin but we only want to report support for non-Latin.
    if subset == 'khmer':
      subset_cps -= CodepointsInSubset('latin')

    overlap = all_cps & subset_cps

    target_pct = min_pct
    if ext_min_pct is not None and subset.endswith('-ext'):
      target_pct = ext_min_pct

    if 100.0 * len(overlap) / len(subset_cps) > target_pct:
      results.append((subset, len(overlap), len(subset_cps)))

  return results


def FamilyName(fontname):
  """Attempts to build family name from font name.

  For example, HPSimplifiedSans => HP Simplified Sans.

  Args:
    fontname: The name of a font.
  Returns:
    The name of the family that should be in this font.
  """
  # SomethingUpper => Something Upper
  fontname = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', fontname)
  # Font3 => Font 3
  fontname = re.sub('([a-z])([0-9]+)', r'\1 \2', fontname)
  # lookHere => look Here
  return re.sub('([a-z0-9])([A-Z])', r'\1 \2', fontname)


def Weight(stylename):
  """Derive weight from a stylename.

  Args:
    stylename: string, e.g. Bold, Regular, or ExtraLightItalic.
  Returns:
    weight: integer
  """
  if stylename.endswith('Italic'):
    return _KNOWN_WEIGHTS[stylename[:-6]]
  return _KNOWN_WEIGHTS[stylename]


def VFWeight(font):
  """Return a variable fonts weight. Return 400 if 400 is within the wght
  axis range else return the value closest to 400

  Args:
    font: TTFont
  Returns:
    weight: integer
  """
  wght_axis = None
  for axis in font['fvar'].axes:
    if axis.axisTag == "wght":
      wght_axis = axis
      break
  value = 400
  if wght_axis:
    if wght_axis.minValue >= 400:
      value = wght_axis.minValue
    if wght_axis.maxValue <= 400:
      value = wght_axis.maxValue
  # TODO (MF) check with GF Eng if we should just assume it's safe to return
  # 400 if a wght axis doesn't exist.
  return int(value)


def Style(stylename):
  return 'italic' if "Italic" in stylename else "normal"


def FamilyStyleWeight(path):
    filename = os.path.basename(path)
    if "[" in filename and "]" in filename:
        return VFFamilyStyleWeight(path)
    return FileFamilyStyleWeight(path)


def FileFamilyStyleWeight(path):
  """Extracts family, style, and weight from Google Fonts standard filename.

  Args:
    path: Font path, eg ./fonts/ofl/lobster/Lobster-Regular.ttf.
  Returns:
    FileFamilyStyleWeightTuple for file.
  Raises:
    ParseError: if file can't be parsed.
  """
  m = re.search(_FAMILY_WEIGHT_REGEX, path)
  if not m:
    raise ParseError('Could not parse %s' % path)
  style = Style(m.group(2))
  weight = Weight(m.group(2))
  return FileFamilyStyleWeightTuple(path, FamilyName(m.group(1)), style,
                                    weight)

def VFFamilyStyleWeight(path):
  """Extract family, style and weight from a variable font's name table.

  Args:
      path: Font path, eg ./fonts/ofl/lobster/Lobster[wght].ttf.
  Returns:
    FileFamilyStyleWeightTuple for file.
  """
  with ttLib.TTFont(path) as font:
    typoFamilyName = font['name'].getName(16, 3, 1, 1033)
    familyName = font['name'].getName(1, 3, 1, 1033)
    family = typoFamilyName.toUnicode() if typoFamilyName else \
             familyName.toUnicode()

    typoStyleName = font['name'].getName(17, 3, 1, 1033)
    styleName = font['name'].getName(2, 3, 1, 1033)
    style = typoStyleName.toUnicode() if typoStyleName else \
            styleName.toUnicode()
    style = "italic" if "Italic" in style.replace(" ", "") else "normal"
    # For each font in a variable font family, we do not want to return
    # the style's weight. We want to return 400 if 400 is within the
    # the wght axis range. If it isn't, we want the value closest to 400.
    weight = VFWeight(font)
    return FileFamilyStyleWeightTuple(path, family, style, weight)



def ExtractNames(font, name_id):
  return [
      n.toUnicode()
      for n in font['name'].names
      if n.nameID == name_id
  ]


def ExtractName(font_or_file, name_id, default):
  """Extracts a name table field (first value if many) from a font.

  Args:
    font_or_file: path to a font file or a TTFont.
    name_id: the ID of the name desired. Use NAME_* constant.
    default: result if no value is present.
  Returns:
    The value of the first entry for name_id or default if there isn't one.
  """
  value = default
  names = []
  if isinstance(font_or_file, ttLib.TTFont):
    names = ExtractNames(font_or_file, name_id)
  else:
    with contextlib.closing(ttLib.TTFont(font_or_file)) as font:
      names = ExtractNames(font, name_id)

  if names:
    value = names[0]

  return value


def NamePartsForStyleWeight(astyle, aweight):
  """Gives back the parts that go into the name for this style/weight.

  Args:
    astyle: The style name, eg "normal" or "italic"
    aweight: The font weight
  Returns:
    Tuple of parts that go into the name, typically the name for the weight and
    the name for the style, if any ("normal" typically doesn't factor into
    names).
  Raises:
    ValueError: If the astyle or aweight isn't a supported value.
  """
  astyle = astyle.lower()
  if astyle not in _VALID_STYLES:
    raise ValueError('unsupported style %s' % astyle)

  correct_style = None
  if astyle == 'italic':
    correct_style = 'Italic'

  correct_name = None
  for name, weight in _KNOWN_WEIGHTS.items():
    if weight == aweight:
      correct_name = name
      break

  if not correct_name:
    raise ValueError('unsupported weight: %d' % aweight)

  return tuple([n for n in [correct_name, correct_style] if n])


def _RemoveAll(alist, value):
  while value in alist:
    alist.remove(value)


def FilenameFor(family, style, weight, ext=''):
  family = family.replace(' ', '')
  style_weight = list(NamePartsForStyleWeight(style, weight))
  if 'Italic' in style_weight:
    _RemoveAll(style_weight, 'Regular')

  style_weight = ''.join(style_weight)
  return '%s-%s%s' % (family, style_weight, ext)


def FullnameFor(family, style, weight):
  name_parts = [family]
  name_parts.extend(list(NamePartsForStyleWeight(style, weight)))
  _RemoveAll(name_parts, 'Regular')
  return ' '.join(name_parts)


def FontDirs(path):
  """Finds all the font directories (based on METADATA.pb) under path.

  Args:
    path: A path to search under.
  Yields:
    Directories under path that have a METADATA.pb.
  """
  for dir_name, _, _ in os.walk(path):
    if os.path.isfile(os.path.join(dir_name, 'METADATA.pb')):
      yield dir_name




def FsSelectionMask(flag):
  """Get the mask for a given named bit in fsSelection.

  Args:
    flag: Name of the flag per otspec, eg ITALIC, BOLD, etc.
  Returns:
    Bitmask for that flag.
  Raises:
    ValueError: if flag isn't the name of any fsSelection bit.
  """
  for (mask, name) in _FS_SELECTION_BITS:
    if name == flag:
      return mask
  raise ValueError('No mask for %s' % flag)


def FsSelectionFlags(fs_selection):
  """Get the named flags enabled in a given fsSelection.

  Args:
    fs_selection: An fsSelection value.
  Returns:
    List of names of flags enabled in fs_selection.
  """
  names = []
  for (mask, name) in _FS_SELECTION_BITS:
    if fs_selection & mask:
      names.append(name)
  return names


def _EntryForEndOfPath(path, answer_map):
  segments = [s.lower() for s in path.split(os.sep)]
  answers = [answer_map[s] for s in segments if s in answer_map]
  if len(answers) != 1:
    raise ValueError('Found %d possible matches: %s' % (len(answers), answers))
  return answers[0]


def LicenseFromPath(path):
  """Try to figure out the license for a given path.

  Splits path and looks for known license dirs in segments.

  Args:
    path: A filesystem path, hopefully including a license dir.
  Returns:
    The name of the license, eg OFL, UFL, etc.
  Raises:
    ValueError: if 0 or >1 licenses match path.
  """
  return _EntryForEndOfPath(path, _KNOWN_LICENSE_DIRS)




def _ParseNamelistHeader(lines):
  includes = set()
  for line in lines:
    if not line.startswith('#$'):
      # not functional line, regular comment
      continue
    keyword, args = line.rstrip()[2:].lstrip().split(' ', 1)
    if keyword == 'include':
      includes.add(args)
  return {'lines': list(lines), 'includes': includes}


def GetCodepointFromLine(line):
  assert line.startswith('0x')
  match = _NAMELIST_CODEPOINT_REGEX.match(line[2:7])
  if match is None:
    match = _NAMELIST_CODEPOINT_REGEX.match(line[2:7].upper())
    if match is not None:
      # Codepoints must be uppercase, it's documented
      warn('Found a codepoint with lowercase unicode hex value: 0x{0}'.format(
          match.groups()[0]))
    return None
  return int(match.groups()[0], 16)


def _ParseNamelist(lines):
  cps = set()
  noncodes = set()
  header_lines = []
  reading_header = True
  for line in lines:
    if reading_header:
      if not line.startswith('#'):
        # first none comment line ends the header
        reading_header = False
      else:
        header_lines.append(line)
        continue

    # reading the body, i.e. codepoints
    if line.startswith('0x'):
      codepoint = GetCodepointFromLine(line)
      if codepoint is None:
        # ignore all lines that we don't understand
        continue
      cps.add(codepoint)
      # description
      # line[(2+len(codepoint)),]
    elif line.startswith('      '):
      noncode = line.strip().rsplit(' ')[-1]
      if noncode:
        noncodes.add(noncode)

  header = _ParseNamelistHeader(header_lines)
  return cps, header, noncodes


def ParseNamelist(filename):
  """Parse a given Namelist file.

  Args:
    filename: The path to the Namelist file.

  Returns:
    A tuple of (Codepoints set, header data dict).
  """
  with codecs.open(filename, encoding='utf-8') as nam_file:
    return _ParseNamelist(nam_file)


def _LoadNamelistIncludes(item, unique_glyphs, cache):
  """Load the includes of an encoding Namelist files.

  This is an implementation detail of ReadNameList.

  Args:
    item: A dict representing a loaded Namelist file.
    unique_glyphs: Whether to only include glyphs unique to subset.
    cache: A dict used to cache loaded Namelist files.

  Returns:
    The item with its included Namelists loaded.
  """
  includes = item['includes'] = []
  charset = item['charset'] = set() | item['ownCharset']

  no_charcode = item['noCharcode'] = set() | item['ownNoCharcode']

  dirname = os.path.dirname(item['fileName'])
  for include in item['header']['includes']:
    include_file = os.path.join(dirname, include)
    included_item = None
    try:
      included_item = ReadNameList(include_file, unique_glyphs, cache)
    except NamelistRecursionError:
      continue
    if included_item in includes:
      continue
    includes.append(included_item)
    charset |= included_item['charset']
    no_charcode |= included_item['ownNoCharcode']
  return item


def _ReadNameList(cache, filename, unique_glyphs):
  """Return a dict with the data of an encoding Namelist file.

  This is an implementation detail of ReadNameList.

  Args:
    cache: A dict used to cache loaded Namelist files.
    filename: The path to the  Namelist file.
    unique_glyphs: Whether to only include glyphs unique to subset.

  Returns:
    A dict containing the data of an econding Namelist file.
  """
  if filename in cache:
    item = cache[filename]
  else:
    cps, header, noncodes = ParseNamelist(filename)
    item = {
        'fileName': filename,
        'ownCharset': cps,
        'header': header,
        'ownNoCharcode': noncodes,
        'includes': None,  # placeholder
        'charset': None,  # placeholder
        'noCharcode': None
    }
    cache[filename] = item

  if unique_glyphs or item['charset'] is not None:
    return item

  # full-charset/includes are requested and not cached yet
  _LoadNamelistIncludes(item, unique_glyphs, cache)
  return item


class NamelistRecursionError(Error):
  """Exception to control infinite recursion in Namelist includes."""
  pass


def _ReadNameListSafetyLayer(currently_including, cache, nam_filename,
                             unique_glyphs):
  """Detect infinite recursion and prevent it.

  This is an implementation detail of ReadNameList.

  Args:
    currently_including: The set of Namelist files that are in the process of
      being included.
    cache: A dict used to cache loaded Namelist files.
    nam_filename: The path to the  Namelist file.
    unique_glyphs: Whether to only include glyphs unique to subset.

  Returns:
    A dict containing the data of an econding Namelist file.

  Raises:
    NamelistRecursionError: If nam_filename is in the process of being included.
  """
  # normalize
  filename = os.path.abspath(os.path.normcase(nam_filename))
  if filename in currently_including:
    raise NamelistRecursionError(filename)
  currently_including.add(filename)
  try:
    result = _ReadNameList(cache, filename, unique_glyphs)
  finally:
    currently_including.remove(filename)
  return result


def ReadNameList(nam_filename, unique_glyphs=False, cache=None):
  """Reads a given Namelist file.

  Args:
    nam_filename: The path to the  Namelist file.
    unique_glyphs: Optional, whether to only include glyphs unique to subset.
    cache: Optional, a dict used to cache loaded Namelist files.

  Returns:
  A dict with following keys:
  "fileName": (string) absolut path to nam_filename
  "ownCharset": (set) the set of codepoints defined by the file itself
  "header": (dict) the result of _ParseNamelistHeader
  "includes":
      (set) if unique_glyphs=False, the resulting dicts of ReadNameList
            for each of the include files
      (None) if unique_glyphs=True
  "charset":
      (set) if unique_glyphs=False, the union of "ownCharset" and all
            "charset" items of each included file
      (None) if unique_glyphs=True

  Raises:
    NamelistRecursionError: If nam_filename is in the process of being included.

  If you are using  unique_glyphs=True and an external cache, don't expect
  the keys "includes" and "charset" to have a specific value.
  Depending on the state of cache, if unique_glyphs=True the returned
  dict may have None values for its "includes" and "charset" keys.
  """
  currently_including = set()
  if not cache:
    cache = {}
  return _ReadNameListSafetyLayer(currently_including, cache, nam_filename,
                                  unique_glyphs)


def CodepointsInNamelist(nam_filename, unique_glyphs=False, cache=None):
  """Returns the set of codepoints contained in a given Namelist file.

  This is a replacement CodepointsInSubset and implements the "#$ include"
  header format.

  Args:
    nam_filename: The path to the  Namelist file.
    unique_glyphs: Optional, whether to only include glyphs unique to subset.
    cache: Optional, a dict used to cache loaded Namelist files.

  Returns:
    A set containing the glyphs in the subset.
  """
  key = 'charset' if not unique_glyphs else 'ownCharset'
  result = ReadNameList(nam_filename, unique_glyphs, cache)
  return result[key]


### unit tests ###


def MakeTestMethod(subset, namelist_filename):
  name = 'test_legacy_subsets_{0}'.format(subset.replace('-', '_'))

  def Test(self):
    """Comapre output of CodepointsInSubset and CodepointsInNamelist.

    The old function CodepointsInSubset and the new function
    CodepointsInNamelist should both output the same sets. This will only work
    as long as the #$inlcude statements in the Namelist files reproduce the old
    dependency logic implemented in CodepointFiles.

    Args:
      self: The test object itself.
    """
    charset_old_method = set(
        hex(c)
        for c in CodepointsInSubset(subset, unique_glyphs=self.unique_glyphs))

    charset_new_method = set(
        hex(c)
        for c in CodepointsInNamelist(
            namelist_filename,
            unique_glyphs=self.unique_glyphs,
            cache=self._cache))
    self.assertTrue(charset_old_method)
    self.assertEqual(charset_old_method, charset_new_method)

  return name, Test


def InitTestProperties(cls):
  initialized = []
  for subset in ListSubsets():
    namelist_filename = CodepointFileForSubset(subset)
    if namelist_filename is None:
      continue
    name, test = MakeTestMethod(subset, namelist_filename)
    setattr(cls, name, test)
    initialized.append(name)
  return initialized


class TestCodepointReading(unittest.TestCase):
  unique_glyphs = True
  _cache = None

  @classmethod
  def setUpClass(cls):
    cls._cache = {}

  @classmethod
  def tearDownClass(cls):
    cls._cache = None


def main(argv):
  # CodepointFileForSubset needs gflags to be parsed and that happens in
  # app.run(). Thus, we can't dynamically build our test cases before.
  InitTestProperties(TestCodepointReading)
  unittest.main(argv=argv, verbosity=2)


if __name__ == '__main__':
  from absl import app
  app.run(main)
