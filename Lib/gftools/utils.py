#!/usr/bin/env python3
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
from collections import namedtuple
from github import Github
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
        fonts = fonts_from_zip(fonts_zip, dst)
        # Remove static fonts if the family is a variable font
        return [f for f in fonts if "static" not in f]
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


def parse_github_pr_url(url):
    if not "github.com" in url and "pull" not in url:
        raise ValueError("{} is not a github.com pr url".format(url))
    if not url[-1].isdigit():
        raise ValueError("{} should end with a pull request number".format(url))
    segments = url.split("/")
    GithubPR = namedtuple("GithubPR", "user repo pull")
    return GithubPR(segments[3], segments[4], int(segments[-1]))


def parse_github_dir_url(url):
    if not "github.com" in url:
        raise ValueError("{} is not a github.com dir url".format(url))
    segments = url.split("/")
    GithubDir = namedtuple("GithubDir", "user repo branch dir")
    return GithubDir(segments[3], segments[4], segments[6], "/".join(segments[7:]))


def download_files_in_github_pr(
    url,
    dst,
    filter_files=[],
    ignore_static_dir=True,
    overwrite=True,
):
    """Download files in a github pr e.g
    https://github.com/google/fonts/pull/2072

    Arguments
    ---------
    url: str, github pr url
    dst: str, path to output files
    filter_files: list, collection of files to include. None will keep all.
    ignore_static_dir: bool, If true, do not include files which reside in
    a /static dir. These dirs are used in family dirs on google/fonts
    e.g ofl/oswald.
    overwrite: bool, set True to overwrite existing contents in dst

    Returns
    -------
    list of paths to downloaded files
    """
    gh = Github(os.environ["GH_TOKEN"])
    url = parse_github_pr_url(url)
    repo_slug = "{}/{}".format(url.user, url.repo)
    repo = gh.get_repo(repo_slug)
    pull = repo.get_pull(url.pull)
    files = [f for f in pull.get_files()]

    mkdir(dst, overwrite=overwrite)
    # if the pr is from google/fonts or a fork of it, download all the
    # files inside the family dir as well. This way means we can qa
    # the whole family together as a whole unit. It will also download
    # the metadata, license and description files so all Fontbakery
    # checks will be executed.
    if pull.base.repo.name == "fonts":
        dirs = set([os.path.dirname(p.filename) for p in files])
        results = []
        for d in dirs:
            if ignore_static_dir and '/static' in d:
                continue
            url = os.path.join(
                pull.head.repo.html_url,
                "tree",
                pull.head.ref, # head branch
                d)
            results += download_files_in_github_dir(url, dst, overwrite=False)
        return results

    results = []
    for f in files:
        filename = os.path.join(dst, f.filename)
        if filter_files and not filename.endswith(tuple(filter_files)):
            continue
        if ignore_static_dir and "/static" in filename:
            continue
        if not overwrite and os.path.exists(filename):
            continue
        dst_ = os.path.dirname(filename)
        mkdir(dst_, overwrite=False)
        download_file(f.raw_url, filename)
        results.append(filename)
    return results


def download_files_in_github_dir(
    url,
    dst,
    filter_files=[],
    overwrite=True
):
    """Download files in a github dir e.g
    https://github.com/google/fonts/tree/master/ofl/abhayalibre

    Arguments
    ---------
    url: str, github dir url
    dst: str, path to output files
    filter_files: list, collection of files to include. None will keep all.
    overwrite: bool, set True to overwrite existing contents in dst

    Returns
    -------
    list of paths to downloaded files
    """
    gh = Github(os.environ["GH_TOKEN"])
    url = parse_github_dir_url(url)
    repo_slug = "{}/{}".format(url.user, url.repo)
    repo = gh.get_repo(repo_slug)
    files = [f for f in repo.get_contents(url.dir, ref=url.branch)
             if f.type == 'file']

    mkdir(dst, overwrite=overwrite)
    results = []
    for f in files:
        filename = os.path.join(dst, f.path)
        if filter_files and not filename.endswith(tuple(filter_files)):
            continue
        if not overwrite and os.path.exists(filename):
            continue
        dst_ = os.path.dirname(filename)
        mkdir(dst_, overwrite=False)
        download_file(f.download_url, filename)
        results.append(filename)
    return results


def download_file(url, dst_path=None):
    """Download a file from a url. If no dst_path is specified, store the file
    as a BytesIO object"""
    request = requests.get(url, stream=True)
    if not dst_path:
        return BytesIO(request.content)
    with open(dst_path, 'wb') as downloaded_file:
        downloaded_file.write(request.content)


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
        os.makedirs(path)
    return path

