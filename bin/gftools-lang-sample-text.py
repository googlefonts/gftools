#!/usr/bin/env python3
"""
gftools lang

Adds sample text for a given language using the specified UDHR translation.

Usage:

# Standard usage. Output lang metadata to a dir. Does not overwrite existing data.
gftools lang-sample-text -l ./languages/en.textproto ./udhr_translations/en.xml

"""

from absl import app
from absl import flags
from fontTools.ttLib import TTFont
from gftools import fonts_public_pb2
from gftools.util.udhr import Udhr
from google.protobuf import text_format
from hyperglot import parse
from lxml import etree
import csv
import glob
import os
import re

FLAGS = flags.FLAGS
flags.DEFINE_string('lang', None, 'Path to lang metadata package', short_name='l')
flags.mark_flag_as_required('lang')
flags.DEFINE_string('udhrs', None, 'Path to UDHR translations (XML)', short_name='u')
flags.mark_flag_as_required('udhrs')

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


def _LoadLanguages(languages_dir):
  languages = {}
  for textproto_file in glob.iglob(os.path.join(languages_dir, '*.textproto')):
    with open(textproto_file, 'r', encoding='utf-8') as f:
      language = text_format.Parse(f.read(), fonts_public_pb2.LanguageProto())
      languages[language.id] = language
  return languages


def _GetLanguageForUdhr(languages, udhr):
  for l in languages.values():
    if (l.language == udhr.iso639_3 and l.script == udhr.iso15924) or \
        l.id == udhr.bcp47:
      return l

  language = fonts_public_pb2.LanguageProto()
  language.id = udhr.bcp47
  language.language = udhr.bcp47.split('_')[0]
  language.script = udhr.iso15924
  language.name = udhr.name.replace(' (', ', ').replace(')', '')
  return language


def main(argv):
  languages = _LoadLanguages(os.path.join(FLAGS.lang, 'languages'))

  if FLAGS.udhrs.endswith('.yaml'):
    import yaml
    with open(FLAGS.udhrs, 'r') as f:
      data = yaml.safe_load(f)
      for translation, meta in data.items():
        language = meta['lang']
        if language.startswith('und-'):
          continue
        script = re.search(r'.*-(.*)-.*', meta['lang_full']).group(1) if 'script' not in meta else meta['script']
        key = language + '_' + script
        iso639_3 = meta['lang_639_3']
        iso15924 = script
        name = meta['name_lang'] if 'name_udhr' not in meta else meta['name_udhr']
        udhr = Udhr(
          key=key,
          iso639_3=iso639_3,
          iso15924=iso15924,
          bcp47=key,
          direction=None,
          ohchr=None,
          stage=4,
          loc=None,
          name=name
        )
        udhr.LoadArticleOne(translation)

        language = _GetLanguageForUdhr(languages, udhr)
        if not language.HasField('sample_text'):
          language.sample_text.MergeFrom(udhr.GetSampleTexts())
        if 'name_autonym' in meta and not language.HasField('autonym'):
          language.autonym = meta['name_autonym'].strip()
        _WriteProto(language, os.path.join(FLAGS.lang, 'languages', language.id + '.textproto'))

  else:
    for udhr_path in glob.glob(os.path.join(FLAGS.udhrs, '*')):
      if udhr_path.endswith('index.xml') or os.path.basename(udhr_path).startswith('status'):
        continue
      udhr_data = etree.parse(udhr_path)
      head = udhr_data.getroot()
      for name, value in head.attrib.items():
        if re.search(r'\{.*\}lang', name):
          bcp47 = value.replace('-', '_')
      udhr = Udhr(
          key=head.get('key'),
          iso639_3=head.get('iso639-3'),
          iso15924=head.get('iso15924'),
          bcp47=bcp47,
          direction=head.get('dir'),
          ohchr=None,
          stage=4,
          loc=None,
          name=head.get('n'))
      udhr.Parse(udhr_data)

      language = _GetLanguageForUdhr(languages, udhr)
      if language.HasField('sample_text'):
        continue
      language.sample_text.MergeFrom(udhr.GetSampleTexts())
      _WriteProto(language, os.path.join(FLAGS.lang, 'languages', language.id + '.textproto'))



if __name__ == '__main__':
  app.run(main)
