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
import re
import shutil
from diffbrowsers.utils import load_browserstack_credentials as bstack_creds
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


def load_browserstack_credentials():
    """Return the user's Browserstack credentials"""
    credentials = bstack_creds()
    if not credentials:
        username = os.environ.get("BSTACK_USERNAME")
        access_key = os.environ.get("BSTACK_ACCESS_KEY")
        if all([username, access_key]):
            return (username, access_key)
        return False
    return credentials


def download_fonts_in_pr(url, dst=None):
    """Download fonts in a Github pull request.""" 
    # TODO (M Foley) see if urlparse can improve this
    url_split = url.split("/")
    repo_slug = "{}/{}".format(url_split[3], url_split[4])
    repo_pull_id = url_split[-1]
    if not repo_pull_id.isdigit():
        raise Exception("Incorrect pr url: {}. Url must end with pull "
                        "request number.\ne.g https://github.com/google"
                        "/fonts/pull/2056".format(url))
    api_url = "https://api.github.com/repos/{}/pulls/{}/files?page={}&per_page=30"
    # Find last api page
    r = requests.get(
        api_url.format(repo_slug, str(repo_pull_id), "1"),
        headers={"Authorization": "token {}".format(os.environ["GH_TOKEN"])},
    )
    if "link" in r.headers:
        pages = re.search(
            r'(?<=page\=)[0-9]{1,5}(?<!\&per_page=50\>\; rel="last")', r.headers["link"]
        ).group(0)
    else:
        pages = 1

    font_paths = []
    for page in range(1, int(pages) + 2):
        r = requests.get(
            api_url.format(repo_slug, str(repo_pull_id), page),
            headers={"Authorization": "token {}".format(os.environ["GH_TOKEN"])},
        )
        for item in r.json():
            download_url = item["raw_url"]
            filename = item["filename"]
            if "static" in filename:
                continue
            if filename.endswith(".ttf") and item["status"] != "removed":
                if dst:
                    dl_filename = sanitize_github_filename(os.path.basename(filename))
                    font_dst = os.path.join(dst, os.path.basename(dl_filename))
                    download_file(download_url, font_dst)
                    font_paths.append(font_dst)
                else:
                    dl = download_file(download_url)
                    font_paths.append(dl)
    return font_paths


def download_fonts_in_github_dir(url, dst=None):
    """Downlaod fonts in a github repo folder e.g
    https://github.com/google/fonts/tree/master/ofl/acme"""
    # TODO (M Foley) see if urlparse can improve this
    url = url.replace("https://github.com/", "https://api.github.com/repos/")
    if "tree/master" in url:
        url = url.replace("tree/master", "contents")
    else:
        # if font is in parent dir e.g https://github.com/bluemix/vibes-typeface
        url = url + "/contents"
    if "//" in url[10:]:  # ignore http://www. | https://www
        url = url[:10] + url[10:].replace("//", "/")
    font_paths = []
    r = requests.get(
        url, headers={"Authorization": "token {}".format(os.environ["GH_TOKEN"])}
    )
    font_paths = []
    for item in r.json():
        if item["name"].endswith(".ttf"):
            f = item["download_url"]
            if dst:
                dl_filename = sanitize_github_filename(os.path.basename(f))
                font_dst = os.path.join(dst, dl_filename)
                download_file(f, font_dst)
                font_paths.append(font_dst)
            else:
                dl = download_file(f)
                font_paths.append(dl)
    return font_paths


def sanitize_github_filename(f):
    """stip token suffix from filenames downloaded from private repos.
    Oswald-Regular.ttf?token=123545 --> Oswald-Regular.ttf"""
    return re.sub(r"\?token=.*", "", os.path.basename(f))


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


def mkdir(path, overwrite=True):
    if os.path.isdir(path) and overwrite:
        shutil.rmtree(path)
    if not os.path.isdir(path):
        os.mkdir(path)

