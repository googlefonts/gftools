#!/usr/bin/env python3
"""
gftools lang

Generates Language/Region metadata.

CLDR info is supplemented with Hyperglot
(https://github.com/rosettatype/hyperglot), which pulls from other data sources
and consequently has a more complete set of language metadata.

Usage:

# Standard usage. Output lang metadata to a dir. Does not overwrite existing data.
gftools add-glyphs -l ./lang/ ./ofl/noto*/METADATA.pb

# Generate a report with insights about data and potential metadata holes.
gftools add-glyphs -l ./lang/ -r ./ofl/noto*/METADATA.pb

"""

from absl import app
from absl import flags
from gftools import fonts_public_pb2
from gftools.util import google_fonts as fonts
from gftools.util import unicode_sections
from google.protobuf import text_format
import glob
import os

FLAGS = flags.FLAGS
flags.DEFINE_string('lang', None, 'Path to lang metadata package', short_name='l')
flags.mark_flag_as_required('lang')

def _ReadProto(proto, path):
  with open(path, 'r', encoding='utf-8') as f:
    proto = text_format.Parse(f.read(), proto)
    return proto


def _WriteProto(proto, path, comments = None):
  with open(path, 'w', newline='') as f:
    textproto = text_format.MessageToString(proto, as_utf8=True)
    if comments is not None:
      lines = [s if s not in comments else s + '  # ' + comments[s] for s in textproto.split('\n')]
      textproto = '\n'.join(lines)
    f.write(textproto)


def _GetExemplarFont(family):
  assert len(family.fonts) > 0, 'Unable to select exemplar in family with no fonts: ' + family.name
  for font in family.fonts:
    if font.style == 'normal' and font.weight == 400:
      # Prefer default style (Regular, not Italic)
      return font
  return family.fonts[0]


def _Ordinal(char):
    if len(char) != 2:
        return ord(char)
    return 0x10000 + (ord(char[0]) - 0xD800) * 0x400 + (ord(char[1]) - 0xDC00)


def _GetSampleGlyphs(fontfile):
  codepoints = fonts.CodepointsInFont(fontfile)
  for section in unicode_sections.DATA:
    supported = []
    for codepoint in unicode_sections.DATA[section]:
      if len(codepoint) == 0: continue
      if _Ordinal(codepoint) in codepoints:
        supported.append(codepoint)
    if len(supported) > 0:
      yield section, ' '.join(supported)

def _AddGlyphMetadata(metadata_path):
  family = _ReadProto(fonts_public_pb2.FamilyProto(), metadata_path)
  font = _GetExemplarFont(family)
  fontfile = os.path.join(os.path.dirname(metadata_path), font.filename)
  family.sample_glyphs.clear()
  for section, glyphs in _GetSampleGlyphs(fontfile):
    family.sample_glyphs[section] = glyphs
  _WriteProto(family, metadata_path)


def _AddLangNames(metadata_path, line_to_lang_name):
  family = _ReadProto(fonts_public_pb2.FamilyProto(), metadata_path)
  _WriteProto(family, metadata_path, comments=line_to_lang_name)


def _LoadLanguages(languages_dir):
  languages = {}
  for textproto_file in glob.iglob(os.path.join(languages_dir, '*.textproto')):
    with open(textproto_file, 'r', encoding='utf-8') as f:
      language = text_format.Parse(f.read(), fonts_public_pb2.LanguageProto())
      languages[language.id] = language
  return languages


def main(argv):
  languages = _LoadLanguages(os.path.join(FLAGS.lang, 'languages'))

  assert len(argv) > 1, 'No METADATA.pb files specified'
  line_to_lang_name = {}
  for l in languages:
    line = 'languages: "{code}"'.format(code=languages[l].id)
    line_to_lang_name[line] = languages[l].name
  for path in argv[1:]:
    _AddGlyphMetadata(path)
    _AddLangNames(path, line_to_lang_name)


if __name__ == '__main__':
  app.run(main)
