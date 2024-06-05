#!/usr/bin/env python3
# Copyright 2017 The Google Font Tools Authors
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
from __future__ import print_function
import itertools
import os
import sys
from absl import flags, app
from gftools.util import google_fonts as fonts
from gfsubsets import CodepointsInFont, CodepointsInSubset

FLAGS = flags.FLAGS
flags.DEFINE_integer(
    "max_diff_cps",
    5,
    "Maximum difference in number of codepoints allowed for"
    " a particular subset before which it is flagged.",
)


def main(argv):
    if len(argv) != 2 or not os.path.isdir(argv[1]):
        sys.exit("Must have one argument, a directory containing font files.")

    sys.stderr = open(os.devnull, "w")
    dirpath = argv[1]
    result = True
    files = []
    for font in fonts.Metadata(dirpath).fonts:
        files.append(os.path.join(dirpath, font.filename))
    for subset in fonts.Metadata(dirpath).subsets:
        if subset == "menu":
            continue
        (file1, file2, diff_size) = _LeastSimilarCoverage(files, subset)
        if diff_size > FLAGS.max_diff_cps:
            print("%s coverage for %s failed" % (dirpath, subset))
            print(
                "Difference of codepoints between %s & %s is %d"
                % (file1, file2, diff_size)
            )
            result = False

    if result:
        print("%s passed subset coverage" % (dirpath))


def _LeastSimilarCoverage(files, subset):
    """Returns pair of fonts having inconsistent coverage for a subset.

    Args:
      files: List of font files
      subset: Name of subset
    Returns:
      3 tuple of (file1, file2, number of codepoints difference)
    """
    worst = (None, None, 0)
    subsetcps = CodepointsInSubset(subset, True)
    for pair in itertools.combinations(files, 2):
        inconsistency = _InconsistentSubsetSupport(pair[0], pair[1], subsetcps)
        if inconsistency > worst[2]:
            worst = (pair[0], pair[1], inconsistency)
    return worst


def _InconsistentSubsetSupport(file1, file2, subsetcps):
    """Returns difference in number of codepoints supported.

    Args:
      file1: Name of font file
      file2: Name of font file
      subsetcps: Complete set of codepoints to be supported
    Returns:
      Difference in number of codepoints between file1 and file2.
    """
    supportcps1 = len(subsetcps.intersection(CodepointsInFont(file1)))
    supportcps2 = len(subsetcps.intersection(CodepointsInFont(file2)))
    return abs(supportcps1 - supportcps2)


if __name__ == "__main__":
    app.run(main)
