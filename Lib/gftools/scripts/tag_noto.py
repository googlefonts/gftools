#!/usr/bin/env python3
"""
gftools lang

Updates METADATA.pb to add is_noto field to families detected as Noto.

Families are determined to be part of the Noto collection based on naive logic.
Results should be verified.

Usage:

# Standard usage.
gftools tag-noto ofl/**/METADATA.pb

"""

from absl import app
from absl import flags
from gftools import fonts_public_pb2
from google.protobuf import text_format
import re


NOTO_FAMILY_NAME = re.compile(r'^Noto .*')


FLAGS = flags.FLAGS
flags.DEFINE_bool('preview', False, 'Preview mode', short_name='p')


def _ReadProto(proto, path):
  with open(path, 'r', encoding='utf-8') as f:
    proto = text_format.Parse(f.read(), proto)
    return proto


def _WriteProto(proto, path):
  with open(path, 'w', newline='') as f:
    textproto = text_format.MessageToString(proto, as_utf8=True)
    f.write(textproto)


def main(argv):
  assert len(argv) > 1, 'No METADATA.pb files specified'

  if FLAGS.preview:
    print('Running in preview mode. No changes will be made.')
    print('The names of families detected as part of the Noto')
    print('collection will be printed below.')

  for path in argv[1:]:
    family = _ReadProto(fonts_public_pb2.FamilyProto(), path)
    if NOTO_FAMILY_NAME.search(family.name):
      if FLAGS.preview:
        print(family.name)
      else:
        family.is_noto = True
        _WriteProto(family, path)


if __name__ == '__main__':
  app.run(main)
