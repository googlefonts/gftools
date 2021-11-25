#!/usr/bin/env python3
"""
gftools lang

Generates Language/Region metadata.

CLDR info is supplemented with Hyperglot
(https://github.com/rosettatype/hyperglot), which pulls from other data sources
and consequently has a more complete set of language metadata.

Usage:

# Standard usage. Output lang metadata to a dir. Does not overwrite existing data.
gftools lang -l ./lang/ ./ofl/noto*/METADATA.pb

# Generate a report with insights about data and potential metadata holes.
gftools lang -l ./lang/ -r ./ofl/noto*/METADATA.pb

"""

from absl import app
from absl import flags
from fontTools.ttLib import TTFont
from gftools import fonts_public_pb2
from google.protobuf import text_format
from hyperglot import parse
import csv
import glob
import os

FLAGS = flags.FLAGS
flags.DEFINE_string('lang', None, 'Path to lang metadata package', short_name='l')
flags.mark_flag_as_required('lang')
flags.DEFINE_bool('report', False, 'Whether to output a report of lang metadata insights', short_name='r')
flags.DEFINE_bool('sample_text_audit', False, 'Whether to run the sample text audit', short_name='s')
flags.DEFINE_string('out', None, 'Path to output directory for report', short_name='o')


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


def _WriteCsv(path, rows):
  with open(path, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile, delimiter='\t', quotechar='"',
                        quoting=csv.QUOTE_MINIMAL)
    for row in rows:
      writer.writerow(row)


def _LoadLanguages(languages_dir):
  languages = {}
  for textproto_file in glob.iglob(os.path.join(languages_dir, '*.textproto')):
    with open(textproto_file, 'r', encoding='utf-8') as f:
      language = text_format.Parse(f.read(), fonts_public_pb2.LanguageProto())
      languages[language.id] = language
  return languages


def _LoadScripts(scripts_dir):
  scripts = {}
  for textproto_file in glob.iglob(os.path.join(scripts_dir, '*.textproto')):
    with open(textproto_file, 'r', encoding='utf-8') as f:
      script = text_format.Parse(f.read(), fonts_public_pb2.ScriptProto())
      scripts[script.id] = script
  return scripts


def _LoadRegions(regions_dir):
  regions = {}
  for textproto_file in glob.iglob(os.path.join(regions_dir, '*.textproto')):
    with open(textproto_file, 'r', encoding='utf-8') as f:
      region = text_format.Parse(f.read(), fonts_public_pb2.RegionProto())
      regions[region.id] = region
  return regions


def _ParseFontChars(path):
  """
  Open the provided font path and extract the codepoints encoded in the font
  @return list of characters
  """
  font = TTFont(path, lazy=True)
  cmap = font["cmap"].getBestCmap()
  font.close()

  # The cmap keys are int codepoints
  return [chr(c) for c in cmap.keys()]


def _SupportedLanguages(fontfile, languages):
  """Get languages supported by given fontfile.

  Languages are pulled from the given set. Based on whether exemplar character
  sets are present in the given font.

  Logic based on Hyperglot: https://github.com/rosettatype/hyperglot/blob/3172061ca05a62c0ff330eb802a17d4fad8b1a4d/lib/hyperglot/language.py#L273-L301
  """
  chars = _ParseFontChars(fontfile)
  supported = []
  for lang in languages.values():
    if not lang.HasField('exemplar_chars') or not lang.exemplar_chars.HasField('base'):
      continue
    base = parse.parse_chars(lang.exemplar_chars.base,
                             decompose=False,
                             retainDecomposed=False)
    if set(base).issubset(chars):
      supported.append(lang)

  return supported


def _GetExemplarFont(family):
  assert len(family.fonts) > 0, 'Unable to select exemplar in family with no fonts: ' + family.name
  for font in family.fonts:
    if font.style == 'normal' and font.weight == 400:
      # Prefer default style (Regular, not Italic)
      return font
  return family.fonts[0]


def _AddLanguageSupportMetadata(metadata_path, languages, scripts, line_to_lang_name):
  family = _ReadProto(fonts_public_pb2.FamilyProto(), metadata_path)
  if len(family.languages) > 0:
    return
  font = _GetExemplarFont(family)
  fontfile = os.path.join(os.path.dirname(metadata_path), font.filename)
  supported_languages = _SupportedLanguages(fontfile, languages)
  supported_languages = [l.id for l in supported_languages]
  family.languages.extend(sorted(supported_languages))
  _WriteProto(family, metadata_path, comments=line_to_lang_name)


def _WriteReport(metadata_paths, out_dir, languages):
  rows = [[ 'id', 'name', 'lang', 'script', 'population', 'ec_base', 'ec_auxiliary',
           'ec_marks', 'ec_numerals', 'ec_punctuation', 'ec_index', 'st_fallback',
           'st_fallback_name', 'st_masthead_full', 'st_masthead_partial',
           'st_styles', 'st_tester', 'st_poster_sm', 'st_poster_md',
           'st_poster_lg', 'st_specimen_48', 'st_specimen_36', 'st_specimen_32',
           'st_specimen_21', 'st_specimen_16']]

  without_lang = []
  without_sample_text = []
  supported_without_sample_text = {}
  for metadata_path in metadata_paths:
    family = _ReadProto(fonts_public_pb2.FamilyProto(), metadata_path)
    if len(family.languages) == 0:
      without_lang.append(family.name)
    else:
      supports_lang_with_sample_text = False
      for lang_code in family.languages:
        if languages[lang_code].HasField('sample_text'):
          supports_lang_with_sample_text = True
          break
      if not supports_lang_with_sample_text:
        without_sample_text.append(family.name)
    for l in family.languages:
      if not languages[l].HasField('sample_text') and l not in supported_without_sample_text:
        supported_without_sample_text[l] = languages[l]

  for lang in supported_without_sample_text.values():
    rows.append([lang.id, lang.name, lang.language, lang.script, lang.population])

  path = os.path.join(out_dir, 'support.csv')
  _WriteCsv(path, rows)


def _SampleTextAudit(out_dir, languages, scripts, unused_scripts=[]):
  rows = [['id','language','script','has_sample_text','historical']]
  # sort by script|has_sample_text|historical|id
  entries = []

  min_sample_text_languages = 0
  by_script = {}
  for l in languages.values():
    if l.script not in by_script:
      by_script[l.script] = []
    by_script[l.script].append(l)
  for script in by_script:
    if script in unused_scripts:
      continue
    languages_with_sample_text = {l.id for l in by_script[script] if l.HasField('sample_text') and not l.sample_text.HasField('fallback_language')}
    non_historical_languages_without_sample_text = [l for l in by_script[script] if not l.historical and l.id not in languages_with_sample_text]
    if len(languages_with_sample_text) < 2:
      if len(languages_with_sample_text) == 1 and len(by_script[script]) > 1 and len(non_historical_languages_without_sample_text) > 1:
        min_sample_text_languages += 1
      elif len(languages_with_sample_text) == 0:
        if len(non_historical_languages_without_sample_text) > 1:
          min_sample_text_languages += 2
        else:
          min_sample_text_languages += 1

    if len(languages_with_sample_text) == 0 or (len(languages_with_sample_text) == 1 and len([l for l in by_script[script] if not l.historical]) > 1 ):
      for l in by_script[script]:
        entries.append({
          'id': l.id,
          'language': l.name,
          'script': scripts[l.script].name,
          'has_sample_text': l.id in languages_with_sample_text,
          'historical': l.historical,
        })

  print(min_sample_text_languages)

  last_script = None
  entries.sort(key = lambda x: (x['script'], not x['has_sample_text'], not x['historical'], x['id']))
  for e in entries:
    if last_script is not None and e['script'] != last_script:
      rows.append([])
    rows.append([e['id'], e['language'], e['script'], 'X' if e['has_sample_text'] else '', 'X' if e['historical'] else ''])
    last_script = e['script']

  path = os.path.join(out_dir, 'sample_text_audit.csv')
  _WriteCsv(path, rows)


def main(argv):
  languages = _LoadLanguages(os.path.join(FLAGS.lang, 'languages'))
  scripts = _LoadScripts(os.path.join(FLAGS.lang, 'scripts'))
  regions = _LoadRegions(os.path.join(FLAGS.lang, 'regions'))

  if FLAGS.report:
    assert len(argv) > 1, 'No METADATA.pb files specified'
    assert FLAGS.out is not None, 'No output dir specified (--out)'
    print('Writing insights report...')
    _WriteReport(argv[1:], FLAGS.out, languages)
  elif FLAGS.sample_text_audit:
    assert FLAGS.out is not None, 'No output dir specified (--out)'
    print('Auditing sample text')
    seen_scripts = set()
    unused_scripts = set()
    for path in argv[1:]:
      family = _ReadProto(fonts_public_pb2.FamilyProto(), path)
      for l in family.languages:
        seen_scripts.add(languages[l].script)
    for s in scripts:
      if s not in seen_scripts:
        unused_scripts.add(s)
    _SampleTextAudit(FLAGS.out, languages, scripts, unused_scripts)
  else:
    assert len(argv) > 1, 'No METADATA.pb files specified'
    line_to_lang_name = {}
    for l in languages:
      line = 'languages: "{code}"'.format(code=languages[l].id)
      line_to_lang_name[line] = languages[l].name
    for path in argv[1:]:
      _AddLanguageSupportMetadata(path, languages, scripts, line_to_lang_name)


if __name__ == '__main__':
  app.run(main)
