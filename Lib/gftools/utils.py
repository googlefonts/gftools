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
import sys
import os
import shutil
if sys.version_info[0] == 3:
    from configparser import ConfigParser
else:
    from ConfigParser import ConfigParser

# =====================================
# HELPER FUNCTIONS

def download_family_from_Google_Fonts(family, dst=None):
    """Download a font family from Google Fonts"""
    url = 'https://fonts.google.com/download?family={}'.format(
        family.replace(' ', '%20')
    )
    fonts_zip = ZipFile(download_file(url))
    if dst:
        return fonts_from_zip(fonts_zip, dst)
    return fonts_from_zip(fonts_zip)


def Google_Fonts_has_family(family):
    """Check if Google Fonts has the specified font family"""
    gf_api_key = load_Google_Fonts_api_key() or os.environ.get("GF_API_KEY")
    if not gf_api_key:
        raise FileNotFoundError("~/.gf-api-key or env not found. See ReadMe to create one")
    api_url = 'https://www.googleapis.com/webfonts/v1/webfonts?key={}'.format(gf_api_key)
    r = requests.get(api_url)
    families_on_gf = [f['family'] for f in r.json()['items']]

    if family in families_on_gf:
        return True
    return False


def load_Google_Fonts_api_key():
    config = ConfigParser()
    config_filepath = os.path.expanduser("~/.gf-api-key")

    if os.path.isfile(config_filepath):
        config.read(config_filepath)
        credentials = config.items("Credentials")
        return credentials[0][1]
    return None


def download_file(url, dst_path=None):
    """Download a file from a url. If no dst_path is specified, store the file
    as a BytesIO object"""
    request = requests.get(url, stream=True)
    if not dst_path:
        return BytesIO(request.content)
    with open(dst_path, 'wb') as downloaded_file:
        shutil.copyfileobj(request.raw, downloaded_file)


def fonts_from_zip(zipfile, dst=None):
    """Unzip fonts. If not dst is given unzip as BytesIO objects"""
    fonts = []
    for filename in zipfile.namelist():
        if filename.endswith(".ttf"):
            if dst:
                target = os.path.join(dst, filename)
                zipfile.extract(filename, dst)
                fonts.append(target)
            else:
                fonts.append(BytesIO(zipfile.read(filename)))
    return fonts


def cmp(x, y):
    """
    Replacement for built-in function cmp that was removed in Python 3

    Compare the two objects x and y and return an integer according to
    the outcome. The return value is negative if x < y, zero if x == y
    and strictly positive if x > y.
    """

    return (x > y) - (x < y)

