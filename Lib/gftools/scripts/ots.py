#!/usr/bin/env python3
# Copyright 2017 The Font Bakery Authors.
# Copyright 2017 The Google Font Tools Authors
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
from __future__ import print_function
import ots
import sys
import os

def main(gf_path):
    results = []
    for p, i, files in os.walk(gf_path):
        for f in files:
            if f.endswith('.ttf'):
                try:
                    font = os.path.join(p, f)
                    process = ots.sanitize(font, check=True, capture_output=True)
                    result = '%s\t%s' % (font, process.stdout)
                except ots.CalledProcessError as e:
                    result = '%s\t%s' % (font, e.output)

                results.append(result)
                print('%s\t%s' % (f, result))

    with open('ots_gf_results.txt', 'w') as doc:
        doc.write(''.join(results))
    print('done!')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('ERROR: Include path to OFL dir')
    else:
        main(sys.argv[-1])
