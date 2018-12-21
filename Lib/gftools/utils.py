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
import requests
from io import BytesIO
from zipfile import ZipFile

# =====================================
# HELPER FUNCTIONS

def download_family_from_Google_Fonts(family_name):
    """Return a zipfile containing a font family hosted on fonts.google.com"""
    url_prefix = 'https://fonts.google.com/download?family='
    url = '%s%s' % (url_prefix, family_name.replace(' ', '+'))
    return ZipFile(download_file(url))


def download_file(url):
    request = requests.get(url, stream=True)
    return BytesIO(request.content)


def fonts_from_zip(zipfile):
  '''return a list of fontTools TTFonts'''
  fonts = []
  for file_name in zipfile.namelist():
    if file_name.endswith(".ttf"):
      fonts.append([file_name, ttLib.TTFont(zipfile.open(file_name))])
  return fonts


def cmp(x, y):
    """
    Replacement for built-in function cmp that was removed in Python 3

    Compare the two objects x and y and return an integer according to
    the outcome. The return value is negative if x < y, zero if x == y
    and strictly positive if x > y.
    """

    return (x > y) - (x < y)

