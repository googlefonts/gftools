#!/usr/bin/python
#
# Copyright 2014 Google Inc. All rights reserved.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributors: Rod Sheeter (rsheeter google com)
#
# Converts a .nam file to a list of ranges.
import sys
import tokenize


def get_codepoints(cps):
    results = []
    for cp in cps:
        if not cp.type == tokenize.NUMBER:
            continue
        results.append(int(cp.string, 16))
    return results


def main():
  if len(sys.argv) != 2:
    sys.exit("Usage: rangify <nam file>")

  codepoints_data = list(tokenize.tokenize(open(sys.argv[1], 'rb').readline))
  codepoints = get_codepoints(codepoints_data)
  codepoints.sort()

  seqs = []
  seq = (None,)
  for cp in codepoints:
    if seq[0] is None:
      seq = (cp,cp)
    elif seq[1] == cp - 1:
      seq = (seq[0], cp)
    else:
      seqs.append(seq)
      seq = (None,)

  for seq in seqs:
    print(seq)

if __name__ == '__main__':
  main()
