#!/usr/bin/env python3
#
# Copyright 2017,2021 Google Inc. All Rights Reserved.
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
import glob
import unicodedata

if __name__ == "__main__":
    # some of the imports here wouldn't work otherwise
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gftools.fonts_public_pb2 as fonts_pb2
from fontTools import ttLib
from gflanguages import LoadLanguages, parse
from google.protobuf import text_format


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

_FAMILY_WEIGHT_REGEX = r"([^/-]+)-(\w+)\.[ot]tf$"

# Matches 4 or 5 hexadecimal digits that are uppercase at the beginning of the
# test string. The match is stored in group 0, e.g:
# >>> _NAMELIST_CODEPOINT_REGEX.match('1234X').groups()[0]
# '1234'
# >>> _NAMELIST_CODEPOINT_REGEX.match('1234A').groups()[0]
# '1234A'
_NAMELIST_CODEPOINT_REGEX = re.compile("^([A-F0-9]{4,5})")

# The canonical [to Google Fonts] name comes before any aliases
_KNOWN_WEIGHTS = collections.OrderedDict(
    [
        ("Thin", 100),
        ("Hairline", 100),
        ("ExtraLight", 200),
        ("Light", 300),
        ("Regular", 400),
        ("", 400),  # Family-Italic resolves to this
        ("Medium", 500),
        ("SemiBold", 600),
        ("Bold", 700),
        ("ExtraBold", 800),
        ("Black", 900),
    ]
)

_VALID_STYLES = {"normal", "italic"}

# (Mask, Name) pairs.
# See https://www.microsoft.com/typography/otspec/os2.htm#fss.
_FS_SELECTION_BITS = tuple(
    (1 << i, n)
    for i, n in enumerate(
        (
            "ITALIC",
            "UNDERSCORE",
            "NEGATIVE",
            "OUTLINED",
            "STRIKEOUT",
            "BOLD",
            "REGULAR",
            "USE_TYPO_METRICS",
            "WWS",
            "OBLIQUE",
        )
    )
)


# license_dir => license name mappings
_KNOWN_LICENSE_DIRS = {
    "apache": "APACHE2",
    "ofl": "OFL",
    "ufl": "UFL",
}


FileFamilyStyleWeightTuple = collections.namedtuple(
    "FileFamilyStyleWeightTuple", ["file", "family", "style", "weight"]
)


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
    for table in font["cmap"].tables:
        if (
            table.platformID == _PLATFORM_ID_MICROSOFT
            and table.platEncID in _PLATFORM_ENCS_UNICODE
        ):
            yield table


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
        if f.weight == 400 and f.style == "normal":
            return os.path.splitext(f.filename)[0] + ".ttf"

    name = "??"
    if metadata.HasField("name"):
        name = metadata.name
    raise OSError(errno.ENOENT, "unable to find regular weight in %s" % name)


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
    if os.path.isfile(file_or_dir) and os.path.basename(file_or_dir) == "METADATA.pb":
        metadata_file = file_or_dir
    elif os.path.isdir(file_or_dir):
        metadata_file = os.path.join(file_or_dir, "METADATA.pb")
        if not os.path.isfile(metadata_file):
            raise ValueError("No METADATA.pb in %s" % file_or_dir)
    else:
        raise ValueError("%s is neither METADATA.pb file or a directory" % file_or_dir)

    msg = fonts_pb2.FamilyProto()
    with codecs.open(metadata_file, encoding="utf-8") as f:
        text_format.Merge(f.read(), msg)

    return msg


def FamilyName(fontname):
    """Attempts to build family name from font name.

    For example, HPSimplifiedSans => HP Simplified Sans.

    Args:
      fontname: The name of a font.
    Returns:
      The name of the family that should be in this font.
    """
    # SomethingUpper => Something Upper
    fontname = re.sub("(.)([A-Z][a-z]+)", r"\1 \2", fontname)
    # Font3 => Font 3
    fontname = re.sub("([a-z])([0-9]+)", r"\1 \2", fontname)
    # lookHere => look Here
    return re.sub("([a-z0-9])([A-Z])", r"\1 \2", fontname)


def Weight(stylename):
    """Derive weight from a stylename.

    Args:
      stylename: string, e.g. Bold, Regular, or ExtraLightItalic.
    Returns:
      weight: integer
    """
    if stylename.endswith("Italic"):
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
    for axis in font["fvar"].axes:
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
    return "italic" if "Italic" in stylename else "normal"


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
        raise ParseError("Could not parse %s" % path)
    style = Style(m.group(2))
    weight = Weight(m.group(2))
    return FileFamilyStyleWeightTuple(path, FamilyName(m.group(1)), style, weight)


def VFFamilyStyleWeight(path):
    """Extract family, style and weight from a variable font's name table.

    Args:
        path: Font path, eg ./fonts/ofl/lobster/Lobster[wght].ttf.
    Returns:
      FileFamilyStyleWeightTuple for file.
    """
    with ttLib.TTFont(path) as font:
        typoFamilyName = font["name"].getName(16, 3, 1, 1033)
        familyName = font["name"].getName(1, 3, 1, 1033)
        family = (
            typoFamilyName.toUnicode() if typoFamilyName else familyName.toUnicode()
        )

        typoStyleName = font["name"].getName(17, 3, 1, 1033)
        styleName = font["name"].getName(2, 3, 1, 1033)
        style = typoStyleName.toUnicode() if typoStyleName else styleName.toUnicode()
        style = "italic" if "Italic" in style.replace(" ", "") else "normal"
        # For each font in a variable font family, we do not want to return
        # the style's weight. We want to return 400 if 400 is within the
        # the wght axis range. If it isn't, we want the value closest to 400.
        weight = VFWeight(font)
        return FileFamilyStyleWeightTuple(path, family, style, weight)


def ExtractNames(font, name_id):
    return [n.toUnicode() for n in font["name"].names if n.nameID == name_id]


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
        raise ValueError("unsupported style %s" % astyle)

    correct_style = None
    if astyle == "italic":
        correct_style = "Italic"

    correct_name = None
    for name, weight in _KNOWN_WEIGHTS.items():
        if weight == aweight:
            correct_name = name
            break

    if not correct_name:
        raise ValueError("unsupported weight: %d" % aweight)

    return tuple([n for n in [correct_name, correct_style] if n])


def _RemoveAll(alist, value):
    while value in alist:
        alist.remove(value)


def FilenameFor(family, style, weight, ext=""):
    family = family.replace(" ", "")
    style_weight = list(NamePartsForStyleWeight(style, weight))
    if "Italic" in style_weight:
        _RemoveAll(style_weight, "Regular")

    style_weight = "".join(style_weight)
    return "%s-%s%s" % (family, style_weight, ext)


def FullnameFor(family, style, weight):
    name_parts = [family]
    name_parts.extend(list(NamePartsForStyleWeight(style, weight)))
    _RemoveAll(name_parts, "Regular")
    return " ".join(name_parts)


def FontDirs(path):
    """Finds all the font directories (based on METADATA.pb) under path.

    Args:
      path: A path to search under.
    Yields:
      Directories under path that have a METADATA.pb.
    """
    for dir_name, _, _ in os.walk(path):
        if os.path.isfile(os.path.join(dir_name, "METADATA.pb")):
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
    for mask, name in _FS_SELECTION_BITS:
        if name == flag:
            return mask
    raise ValueError("No mask for %s" % flag)


def FsSelectionFlags(fs_selection):
    """Get the named flags enabled in a given fsSelection.

    Args:
      fs_selection: An fsSelection value.
    Returns:
      List of names of flags enabled in fs_selection.
    """
    names = []
    for mask, name in _FS_SELECTION_BITS:
        if fs_selection & mask:
            names.append(name)
    return names


def _EntryForEndOfPath(path, answer_map):
    segments = [s.lower() for s in path.split(os.sep)]
    answers = [answer_map[s] for s in segments if s in answer_map]
    if len(answers) != 1:
        raise ValueError("Found %d possible matches: %s" % (len(answers), answers))
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


def SupportedLanguages(ttFont, languages=LoadLanguages()):
    """Get languages supported by given ttFont.

    Languages are pulled from the given set. Based on whether exemplar character
    sets are present in the given font.
    """
    chars = [chr(c) for c in ttFont["cmap"].getBestCmap()]
    supported = []
    for lang in languages.values():
        if not lang.HasField("exemplar_chars") or not lang.exemplar_chars.HasField(
            "base"
        ):
            continue
        base = parse(lang.exemplar_chars.base)
        if base.issubset(chars):
            supported.append(lang)
    return supported


def GetExemplarFont(family):
    assert len(family.fonts) > 0, (
        "Unable to select exemplar in family with no fonts: " + family.name
    )
    for font in family.fonts:
        if font.style == "normal" and font.weight == 400:
            # Prefer default style (Regular, not Italic)
            return font
    return family.fonts[0]


def LanguageComments(languages):
    """Generate a mapping for METADATA.pb language field comments.
    Every language field in a METADATA.pb has a comment which is the language's name e.g
      languages: "xh_Latn"  # Xhosa

    Args:
      languages: a dict with keys for lang tags and values for fonts_public_pb2.LanguageProto objects e.g
        languages={"kr_Arab": <class 'fonts_public_pb2.LanguageProto'>}
    Returns:
      A dict with keys for the language field entry and values for the comment.
          {
          'languages: "kr_Arab"': 'Kanuri',
          'languages: "fi_Latn"': 'Finnish'
        }
    """
    line_to_lang_name = {}
    for language in languages.values():
        line = f'languages: "{language.id}"'
        line_to_lang_name[line] = language.name
    return line_to_lang_name


def ReadProto(proto, path):
    with open(path, "r", encoding="utf-8") as f:
        proto = text_format.Parse(f.read(), proto)
        return proto


def WriteProto(proto: fonts_pb2.FamilyProto, path: str, comments=None):
    with open(path, "w", newline="") as f:
        textproto = text_format.MessageToString(proto, as_utf8=True)
        if comments is not None:
            lines = [
                s if s not in comments else s + "  # " + comments[s]
                for s in textproto.split("\n")
            ]
            textproto = "\n".join(lines)
        f.write(textproto)


def WriteMetadata(
    proto: fonts_pb2.FamilyProto, path: str = "METADATA.pb", comments=True
):
    if comments is None:
        comment_proto = None
    elif comments is True:
        language = LoadLanguages()
        comment_proto = LanguageComments(language)
    else:
        comment_proto = comments
    WriteProto(proto, path, comment_proto)
