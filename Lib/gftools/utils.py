#!/usr/bin/env python2
# Copyright 2016 The Fontbakery Authors
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
from fontTools import ttLib
from StringIO import StringIO
from urllib import urlopen
from zipfile import ZipFile

# =====================================
# HELPER FUNCTIONS

def download_family_from_Google_Fonts(family_name):
    """Return a zipfile containing a font family hosted on fonts.google.com"""
    url_prefix = 'https://fonts.google.com/download?family='
    url = '%s%s' % (url_prefix, family_name.replace(' ', '+'))
    return ZipFile(download_file(url))


def download_file(url):
    request = urlopen(url)
    return StringIO(request.read())


def fonts_from_zip(zipfile):
  '''return a list of fontTools TTFonts'''
  fonts = []
  for file_name in zipfile.namelist():
    if file_name.endswith(".ttf"):
      fonts.append([file_name, ttLib.TTFont(zipfile.open(file_name))])
  return fonts
