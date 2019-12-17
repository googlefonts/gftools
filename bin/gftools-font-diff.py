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
"""Diff two fonts.

Attempts to highlight the variable(s) that differ table by table.

"""
from __future__ import print_function
import collections
import warnings

from fontTools import ttLib
from absl import app

DiffTuple = collections.namedtuple('DiffTuple', ['name', 'lhs', 'rhs'])


def _TryLoadTable(ttf, tag):
  try:
    # force parse, may kerplode
    ttf[tag]  # pylint: disable=pointless-statement
    return (True, None)
  except LookupError as e:
    return (False, str(e))


def _ShortDisplay(v):
  s = str(v)
  if len(s) > 32:
    s = s[:29] + '...'
  return s


def _KeyMatch(lh_keys, rh_keys):
  for k in sorted(set(lh_keys) | set(rh_keys)):
    if k not in lh_keys:
      yield (k, 'rhs')
    if k not in rh_keys:
      yield (k, 'lhs')
    yield (k, None)


def _DiffFont(lhs, rhs):
  """Compares two fonts.

  Inputs must be read from file and not modified as we assume if the raw table
  data was the same then the table is unchanged.

  Args:
    lhs: A TTFont, read from a file and not modified.
    rhs: A TTFont, read from a file and not modified.
  Returns:
    A list of (tag, one_side, diff_tuples, error) tuples. If error is set then
    the table couldn't be parsed. If one_side is not None it will be 'lhs' or
    'rhs', indicating only one side has the table. diff_tuples is a list of
    DiffTuple.
  """

  results = []
  for tag, one_side in _KeyMatch(lhs.reader.keys(), rhs.reader.keys()):
    diff_tuples = []
    results.append((tag, one_side, diff_tuples, None))

    if one_side or lhs.reader[tag] == rhs.reader[tag]:
      continue

    # table might not be parseable
    (l_table_ok, l_table_err) = _TryLoadTable(lhs, tag)
    (r_table_ok, r_table_err) = _TryLoadTable(rhs, tag)
    if not l_table_ok:
      results[-1] = (tag, 'lhs', diff_tuples,
                     'LHS load failed %s' % l_table_err)
    if not r_table_ok:
      results[-1] = (tag, 'lhs', diff_tuples,
                     'RHS load failed %s' % r_table_err)
    if not l_table_ok or not r_table_ok:
      continue

    lhs_vars = vars(lhs[tag])
    rhs_vars = vars(rhs[tag])
    for k, _ in _KeyMatch(lhs_vars.keys(), rhs_vars.keys()):
      if lhs_vars.get(k) != rhs_vars.get(k):
        diff_tuples.append(DiffTuple(k, lhs_vars.get(k), rhs_vars.get(k)))

  return results


def main(argv):
  print(argv)
  if len(argv) != 3:
    raise ValueError('Specify two files to diff')

  with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    with open(argv[1], 'rb') as f1, open(argv[2], 'rb') as f2:
      lhs = ttLib.TTFont(f1)
      rhs = ttLib.TTFont(f2)
      font_diff = _DiffFont(lhs, rhs)

  for tag, one_side, diff_tuples, error in font_diff:
    if error:
      print('%s %s' % (tag, error))
    elif one_side:
      print('Only %s has %s' % (one_side.upper(), str(tag)))
    elif not diff_tuples:
      print('%s identical' % tag)
    else:
      print('%s DIFF' % tag)

    for name, lhs, rhs in diff_tuples:
      print('  %s %s != %s' % (name, _ShortDisplay(lhs), _ShortDisplay(rhs)))


if __name__ == '__main__':
  app.run(main)
