#!/usr/bin/env python3
# Copyright 2016 The Fontbakery Authors
# Copyright 2017 The Google Fonts Tools Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from os.path import basename
from argparse import ArgumentParser
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable


description = "Manipulate a collection of fonts' cmap tables."


def convert_cmap_subtables_to_v4(font):
  """Converts all cmap subtables to format 4.

  Returns a list of tuples (format, platformID, platEncID) of the tables
  which needed conversion."""
  cmap = font['cmap']
  outtables = []
  converted = []
  for table in cmap.tables:
    if table.format != 4:
      converted.append((table.format, table.platformID, table.platEncID))
    newtable = CmapSubtable.newSubtable(4)
    newtable.platformID = table.platformID
    newtable.platEncID = table.platEncID
    newtable.language = table.language
    newtable.cmap = table.cmap
    outtables.append(newtable)
  font['cmap'].tables = outtables
  return converted


def partition_cmap(font, test, report=True):
  """Drops all cmap tables from the font which do not pass the supplied test.

  Arguments:
    font: A ``TTFont`` instance
    test: A function which takes a cmap table and returns True if it should
      be kept or False if it should be removed from the font.
    report: Reports to stdout which tables were dropped and which were kept.

  Returns two lists: a list of `fontTools.ttLib.tables._c_m_a_p.*` objects
  which were kept in the font, and a list of those which were removed."""
  keep = []
  drop = []

  for index, table in enumerate(font['cmap'].tables):
    if test(table):
      keep.append(table)
    else:
      drop.append(table)

  if report:
    for table in keep:
        print(("Keeping format {} cmap subtable with Platform ID = {}"
               " and Encoding ID = {}").format(table.format,
                                               table.platformID,
                                               table.platEncID))
    for table in drop:
        print(("--- Removed format {} cmap subtable with Platform ID = {}"
             " and Encoding ID = {} ---").format(table.format,
                                                 table.platformID,
                                                 table.platEncID))

  font['cmap'].tables = keep
  return keep, drop


def drop_nonpid0_cmap(font, report=True):
  keep, drop = partition_cmap(font, lambda table: table.platformID == 0, report)
  return drop

def drop_mac_cmap(font, report=True):
  keep, drop = partition_cmap(font, lambda table: table.platformID != 1 or table.platEncID != 0, report)
  return drop

def main():
  parser = ArgumentParser(description=description)
  parser.add_argument('fonts', nargs='+')
  parser.add_argument('--format-4-subtables', '-f4', default=False,
                      action='store_true',
                      help="Convert cmap subtables to format 4")
  parser.add_argument('--drop-mac-subtable', '-dm', default=False,
                      action='store_true',
                      help='Drop Mac cmap subtables')
  parser.add_argument('--keep-only-pid-0', '-k0', default=False,
                      action='store_true',
                      help=('Keep only cmap subtables with pid=0'
                            ' and drop the rest.'))
  args = parser.parse_args()

  for path in args.fonts:
    font = TTFont(path)
    font_filename = basename(path)
    fixit = False

    if args.format_4_subtables:
      print('\nConverting Cmap subtables to format 4...')
      converted = convert_cmap_subtables_to_v4(font)
      for c in converted:
        print(('Converted format {} cmap subtable'
         ' with Platform ID = {} and Encoding ID = {}'
         ' to format 4.').format(c))
      fixit = fixit or converted

    if args.keep_only_pid_0:
      print('\nDropping all Cmap subtables,'
            ' except the ones with PlatformId = 0...')
      dropped = drop_nonpid0_cmap(font)
      fixit = fixit or dropped
    elif args.drop_mac_subtable:
      print('\nDropping any Cmap Mac subtable...')
      dropped = drop_mac_cmap(font)
      fixit = fixit or dropped

    if fixit:
      print('\n\nSaving %s to %s.fix' % (font_filename, path))
      font.save(path + '.fix')
    else:
      print('\n\nThere were no changes needed on the font file!')


if __name__ == '__main__':
  main()
