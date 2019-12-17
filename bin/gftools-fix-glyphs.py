#!/usr/bin/env python3
# Copyright 2016 The Font Bakery Authors
# Copyright 2017 The Google Fonts Tools Authors.
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
from __future__ import unicode_literals
import argparse
from glyphsLib import GSFont

parser = argparse.ArgumentParser(description='Report issues'
                                             ' on .glyphs font files')
parser.add_argument('font', nargs="+")
#parser.add_argument('--autofix', default=False,
#                    action='store_true', help='Apply autofix')

def customparam(font, name):
  for param in font.customParameters:
      if param.name == name:
          return param.value


def main():
  args = parser.parse_args()

  for font_path in args.font:
      font = GSFont(font_path)
      print('Copyright: "{}"'.format(font.copyright))
      print('VendorID: "{}"'.format(customparam(font, "vendorID")))
      print('fsType: {}'.format(customparam(font, "fsType")))
      print('license: "{}"'.format(customparam(font, "license")))
      print('licenseURL: "{}"'.format(customparam(font, "licenseURL")))
  # TODO: handle these other fields:
  #
  # for master/instance in masters-or-instances:
  #   print: 8 Vertical Metrics
  #
  # Instance ExtraLight weightClass set to 275
  # Instances italicAngle set to 0, if the master/instance slant value is not 0
  # Instance named Regular (400) for families with a single instance
  # Instance Bold style linking set for families with a 400 and 700 instance

if __name__ == '__main__':
  main()

