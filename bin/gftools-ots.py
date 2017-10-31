#!/usr/bin/env python2
# coding: utf-8
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
import subprocess
import sys
import os

def main(gf_path):
    results = []
    for p, i, files in os.walk(gf_path):
        for f in files:
            if f.endswith('.ttf'):
                try:
                    result = subprocess.check_output(["ots-sanitize", os.path.join(p,f)])
                    results.append('%s\t%s' % (f, result))
                except subprocess.CalledProcessError as e:
                    result = '%s\t%s' % (f, e.output)
                    results.append(result)

                print '%s\t%s' % (f, result)
    with open('ots_gf_results.txt', 'w') as doc:
        doc.write(''.join(results))
    print 'done!'


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'ERROR: Include path to OFL dir'
    else:
        main(sys.argv[-1])
