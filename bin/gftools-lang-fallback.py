#!/usr/bin/env python3
"""
gftools lang

Generates Language/Region metadata.

CLDR info is supplemented with Hyperglot
(https://github.com/rosettatype/hyperglot), which pulls from other data sources
and consequently has a more complete set of language metadata.

Usage:

# Standard usage. Update languages in lang metadata pkg with fallbacks where possible.
gftools lang-fallback -l ./lang/

"""

from absl import app
from absl import flags
from gftools import fonts_public_pb2
from google.protobuf import text_format
import glob
import os

FLAGS = flags.FLAGS
flags.DEFINE_string('lang', None, 'Path to lang metadata package', short_name='l')
flags.mark_flag_as_required('lang')
flags.DEFINE_string('preview', None, 'Preview changes only', short_name='p')


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
    language = _ReadProto(fonts_public_pb2.LanguageProto(), textproto_file)
    languages[language.id] = language
  return languages


def main(argv):
  languages = _LoadLanguages(os.path.join(FLAGS.lang, 'languages'))

  for lang in languages.values():
    if not lang.HasField('sample_text'):
      for l in languages.values():
        if lang.id == l.id:
          continue
        if l.script == lang.script and l.HasField('sample_text') and not l.sample_text.HasField('fallback_language'):
          sample_text = fonts_public_pb2.SampleTextProto()
          sample_text.fallback_language = l.id
          lang.sample_text.MergeFrom(sample_text)
          if FLAGS.preview:
            print(lang.id + ' => ' + l.id)
          else:
            _WriteProto(lang, os.path.join(FLAGS.lang, 'languages', lang.id + '.textproto'))
          break

if __name__ == '__main__':
  app.run(main)
