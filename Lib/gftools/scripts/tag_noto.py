#!/usr/bin/env python3
"""
Updates METADATA.pb to add is_noto field to families detected as Noto.

Families are determined to be part of the Noto collection based on naive logic.
Results should be verified.

Usage:

# Standard usage.
gftools tag-noto ofl/**/METADATA.pb

"""

import argparse
from gftools import fonts_public_pb2
from google.protobuf import text_format
import re


NOTO_FAMILY_NAME = re.compile(r'^Noto .*')


parser = argparse.ArgumentParser(description='Updates METADATA.pb to add is_noto field to families detected as Noto')
parser.add_argument('--preview', '-p', action='store_true',help='Preview mode')
parser.add_argument('metadata', metavar='METADATA', nargs="+",help='METADATA.pb files')


def _ReadProto(proto, path):
  with open(path, 'r', encoding='utf-8') as f:
    proto = text_format.Parse(f.read(), proto)
    return proto


def _WriteProto(proto, path):
  with open(path, 'w', newline='') as f:
    textproto = text_format.MessageToString(proto, as_utf8=True)
    f.write(textproto)


def main(args=None):
  args = parser.parse_args(args)

  if args.preview:
    print('Running in preview mode. No changes will be made.')
    print('The names of families detected as part of the Noto')
    print('collection will be printed below.')

  for path in args.metadata:
    family = _ReadProto(fonts_public_pb2.FamilyProto(), path)
    if NOTO_FAMILY_NAME.search(family.name):
      if args.preview:
        print(family.name)
      else:
        family.is_noto = True
        _WriteProto(family, path)


if __name__ == '__main__':
  main()
