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
from gftools import fonts_public_pb2
from gftools.util.udhr import Udhr
from google.protobuf import text_format
from lxml import etree
import csv
import glob
import os
import re
import yaml

FLAGS = flags.FLAGS
flags.DEFINE_string('lang', None, 'Path to lang metadata package', short_name='l')
flags.mark_flag_as_required('lang')
flags.DEFINE_string('udhrs', None, 'Path to UDHR translations (XML)', short_name='u')
flags.DEFINE_string('samples', None, 'Path to per-family samples from noto-data-dev repo', short_name='s')

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


def _LoadRegions(regions_dir):
  regions = {}
  for textproto_file in glob.iglob(os.path.join(regions_dir, '*.textproto')):
    with open(textproto_file, 'r', encoding='utf-8') as f:
      region = text_format.Parse(f.read(), fonts_public_pb2.RegionProto())
      regions[region.id] = region
  return regions


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


def _ReplaceInSampleText(languages):
  for l in languages.values():
    if l.script == 'Latn' or not l.HasField('sample_text'):
      continue
    if '-' in l.sample_text.masthead_full:
      l.sample_text.masthead_full = l.sample_text.masthead_full.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.masthead_partial:
      l.sample_text.masthead_partial = l.sample_text.masthead_partial.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.styles:
      l.sample_text.styles = l.sample_text.styles.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.tester:
      l.sample_text.tester = l.sample_text.tester.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.poster_sm:
      l.sample_text.poster_sm = l.sample_text.poster_sm.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.poster_md:
      l.sample_text.poster_md = l.sample_text.poster_md.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.poster_lg:
      l.sample_text.poster_lg = l.sample_text.poster_lg.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.specimen_48:
      l.sample_text.specimen_48 = l.sample_text.specimen_48.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.specimen_36:
      l.sample_text.specimen_36 = l.sample_text.specimen_36.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.specimen_32:
      l.sample_text.specimen_32 = l.sample_text.specimen_32.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.specimen_21:
      l.sample_text.specimen_21 = l.sample_text.specimen_21.replace(' - ', ' ').replace('-', '').strip()
    if '-' in l.sample_text.specimen_16:
      l.sample_text.specimen_16 = l.sample_text.specimen_16.replace(' - ', ' ').replace('-', '').strip()

    _WriteProto(l, os.path.join(FLAGS.lang, 'languages', l.id + '.textproto'))


def main(argv):
  languages = _LoadLanguages(os.path.join(FLAGS.lang, 'languages'))
  regions = _LoadRegions(os.path.join(FLAGS.lang, 'regions'))

  if FLAGS.samples:
    assert len(argv) > 1, 'No METADATA.pb files specified'
    line_to_lang_name = {}
    for l in languages:
      line = 'languages: "{code}"'.format(code=languages[l].id)
      line_to_lang_name[line] = languages[l].name
    samples = {}
    for sample_filename in os.listdir(FLAGS.samples):
      key = os.path.splitext(os.path.basename(sample_filename))[0]
      samples[key] = os.path.join(FLAGS.samples, sample_filename)
    for path in argv[1:]:
      family = _ReadProto(fonts_public_pb2.FamilyProto(), path)
      if True:#len(family.languages) == 0 or family.name == 'Noto Sans Tamil Supplement':
        key = family.name.replace(' ', '')
        if key not in samples:
          print('Family not found in samples: ' + family.name)
          continue
        with open(samples[key], 'r') as f:
          sample_data = yaml.safe_load(f)
          sample_text = fonts_public_pb2.SampleTextProto()
          sample_text.masthead_full = sample_data['masthead_full']
          sample_text.masthead_partial = sample_data['masthead_partial']
          sample_text.styles = sample_data['styles']
          sample_text.tester = sample_data['tester']
          sample_text.poster_sm = sample_data['poster_sm']
          sample_text.poster_md = sample_data['poster_md']
          sample_text.poster_lg = sample_data['poster_lg']
          family.sample_text.MergeFrom(sample_text)
          _WriteProto(family, path, comments=line_to_lang_name)

  if not FLAGS.udhrs:
    return

  if FLAGS.udhrs.endswith('.yaml'):
    with open(FLAGS.udhrs, 'r') as f:
      data = yaml.safe_load(f)
      for translation, meta in data.items():
        if 'lang_full' not in meta or meta['lang_full'] not in ['ccp-Beng-IN', 'lad-Hebr-IL']:
          continue
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

  elif FLAGS.udhrs.endswith('.csv'):
    with open(FLAGS.udhrs, newline='') as csvfile:
      reader = csv.reader(csvfile, delimiter=',', quotechar='"')
      head = next(reader)
      index_id = head.index('id')
      index_name = head.index('language')
      index_historical = head.index('historical')
      index_sample = head.index('SAMPLE')
      for row in reader:
        id = row[index_id]
        if id in languages:
          language = languages[row[index_id]]
        else:
          language = fonts_public_pb2.LanguageProto()
          language.id = id
          language.language, language.script = id.split('_')
          language.name = row[index_name]
        historical = row[index_historical] == 'X'
        if language.historical != historical:
          if historical:
            language.historical = True
          else:
            language.ClearField('historical')
        sample = row[index_sample]
        if sample and not sample.startswith('http'):
          udhr = Udhr(
            key=id,
            iso639_3=language.language,
            iso15924=language.script,
            bcp47=id,
            direction=None,
            ohchr=None,
            stage=4,
            loc=None,
            name=None
          )
          udhr.LoadArticleOne(sample)
          if not language.HasField('sample_text'):
            language.sample_text.MergeFrom(udhr.GetSampleTexts())
        _WriteProto(language, os.path.join(FLAGS.lang, 'languages', language.id + '.textproto'))

  elif os.path.isdir(FLAGS.udhrs):
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
      if language.id in languages or language.HasField('sample_text'):
        continue
      language.sample_text.MergeFrom(udhr.GetSampleTexts())
      _WriteProto(language, os.path.join(FLAGS.lang, 'languages', language.id + '.textproto'))

  else:
    raise Exception('Unsupported input type for --udhrs: ' + FLAGS.udhrs)


if __name__ == '__main__':
  app.run(main)
