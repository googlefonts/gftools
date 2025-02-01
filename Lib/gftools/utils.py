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
from __future__ import annotations
from typing import Union
import requests
from io import BytesIO
from zipfile import ZipFile
import sys
import os
import shutil
import ufoLib2
import unicodedata
from unidecode import unidecode
from collections import namedtuple
from gflanguages import LoadLanguages
from github import Github
from pkg_resources import resource_filename
from google.protobuf import text_format
import json
from PIL import Image
import re
import shlex
import subprocess
from fontTools import unicodedata as ftunicodedata
from fontTools.ttLib import TTFont
from ufo2ft.util import classifyGlyphs
from collections import Counter
from collections import defaultdict
from pathlib import Path

if sys.version_info[0] == 3:
    from configparser import ConfigParser
else:
    from ConfigParser import ConfigParser
from bs4 import BeautifulSoup

# =====================================
# HELPER FUNCTIONS

PROD_FAMILY_DOWNLOAD = "https://fonts.google.com/download?family={}"


def download_family_from_Google_Fonts(
    family, dst=None, dl_url=PROD_FAMILY_DOWNLOAD, ignore_static=True
):
    """Download a font family from Google Fonts"""
    # TODO (M Foley) update all dl_urls in .ini files.
    dl_url = dl_url.replace("download?family=", "download/list?family=")
    url = dl_url.format(family.replace(" ", "%20"))
    data = json.loads(requests.get(url).text[5:])
    res = []
    for item in data["manifest"]["fileRefs"]:
        filename = item["filename"]
        dl_url = item["url"]
        if "static" in filename and ignore_static:
            continue
        if not filename.endswith(("otf", "ttf")):
            continue
        if dst:
            target = os.path.join(dst, filename)
            download_file(dl_url, target)
            res.append(target)
        else:
            res.append(download_file(dl_url))
    return res


def Google_Fonts_has_family(name):
    """Check if Google Fonts has the specified font family"""
    # This endpoint is private and may change at some point
    # TODO (MF) if another function needs this data, refactor it into a
    # function and use a lru cache
    data = requests.get("https://fonts.google.com/metadata/fonts").json()
    family_names = set(i["family"] for i in data["familyMetadataList"])
    return name in family_names


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
            if ignore_static_dir and "/static" in d:
                continue
            url = os.path.join(
                pull.head.repo.html_url, "tree", pull.head.ref, d  # head branch
            )
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


def download_files_in_github_dir(orig_url, dst, filter_files=[], overwrite=True):
    """Download files in a github dir e.g
    https://github.com/google/fonts/tree/main/ofl/abhayalibre

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
    url = parse_github_dir_url(orig_url)
    repo_slug = "{}/{}".format(url.user, url.repo)
    repo = gh.get_repo(repo_slug)
    try:
        files = [
            f for f in repo.get_contents(url.dir, ref=url.branch) if f.type == "file"
        ]
    except Exception as e:
        raise ValueError(
            f"Could not download from {orig_url}:\n{e}\n(Did the content get deleted?)"
        ) from e

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


def download_files_from_archive(url, dst):
    zip_io = download_file(url)
    with ZipFile(zip_io) as zip_file:
        return fonts_from_zip(zip_file, dst)


def download_file(url, dst_path=None):
    """Download a file from a url. If no dst_path is specified, store the file
    as a BytesIO object"""
    if os.environ.get("GH_TOKEN") and re.match(r"^https://(\w+\.)?github.com", url):
        headers = {"Authorization": f"token {os.environ['GH_TOKEN']}"}
    else:
        headers = {}

    request = requests.get(url, stream=True, headers=headers)
    request.raise_for_status()
    if not dst_path:
        return BytesIO(request.content)
    with open(dst_path, "wb") as downloaded_file:
        downloaded_file.write(request.content)


def fonts_from_zip(zipfile, dst=None, ignore_static=True):
    """Unzip fonts. If not dst is given unzip as BytesIO objects"""
    res = []
    for filename in zipfile.namelist():
        if ignore_static and filename.startswith("static"):
            continue
        if not filename.endswith(("otf", "ttf")):
            continue
        if dst:
            target = os.path.join(dst, filename)
            zipfile.extract(filename, dst)
            res.append(target)
        else:
            res.append(BytesIO(zipfile.read(filename)))
    return res


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


def _html_custom_formatter(string):
    whitespace = " "
    # Remove new lines
    string = string.replace("\n", " ")
    # Remove extra spaces
    string = " ".join(string.split())
    # Break sentences into new lines
    string = string.replace(". ", f".\n{whitespace}")
    string = string.replace("! ", f"!\n{whitespace}")
    string = string.replace("? ", f"?\n{whitespace}")
    # Read into list
    strings = string.split("\n")
    # Cycle through list to find abbreviations
    for i in range(1, len(strings)):
        this_line = strings[i - 1]
        next_line = strings[i]
        if this_line == "":
            continue
        if (
            re.search(r"i\.?e\.$", this_line)  # ie.
            or re.search(r"e\.?g\.$", this_line)  # eg.
            or (
                re.search(r"etc[\.|\?|!]$", this_line)
                and next_line[1] == next_line[1].lower()
            )  # etc.
            or (
                re.search(r"\W\w{1,2}[\.|\?|!]$", this_line)
                and this_line[-2] == this_line[-2].upper()
                and next_line[1] == next_line[1].lower()
            )  # H.R. Giger
        ):
            strings[i - 1] = strings[i - 1] + strings[i]
            strings[i] = ""
    # Join back together
    string = "\n".join(strings)
    # Remove double lines
    string = string.replace("\n\n", "\n")
    return string


def format_html(html):
    return BeautifulSoup(html, "html.parser").prettify(formatter=_html_custom_formatter)


## Font-related utility functions


def font_stylename(ttFont):
    """Get a font's stylename using the name table. Since our fonts use the
    RIBBI naming model, use the Typographic SubFamily Name (NAmeID 17) if it
    exists, otherwise use the SubFamily Name (NameID 2).

    Args:
        ttFont: a TTFont instance
    """
    return get_name_record(ttFont, 17, fallbackID=2)


def font_familyname(ttFont):
    """Get a font's familyname using the name table. since our fonts use the
    RIBBI naming model, use the Typographic Family Name (NameID 16) if it
    exists, otherwise use the Family Name (Name ID 1).

    Args:
        ttFont: a TTFont instance
    """
    return get_name_record(ttFont, 16, fallbackID=1)


def get_name_record(ttFont, nameID, fallbackID=None, platform=(3, 1, 0x409)):
    """Return a name table record which has the specified nameID.

    Args:
        ttFont: a TTFont instance
        nameID: nameID of name record to return,
        fallbackID: if nameID doesn't exist, use this nameID instead
        platform: Platform of name record. Default is Win US English

    Returns:
        str
    """
    name = ttFont["name"]
    record = name.getName(nameID, 3, 1, 0x409)
    if not record and fallbackID:
        record = name.getName(fallbackID, 3, 1, 0x409)
    if not record:
        raise ValueError(f"Cannot find record with nameID {nameID}")
    return record.toUnicode()


def family_bounding_box(ttFonts):
    y_min = min(f["head"].yMin for f in ttFonts)
    y_max = max(f["head"].yMax for f in ttFonts)
    return y_min, y_max


def typo_metrics_enabled(ttFont):
    return True if ttFont["OS/2"].fsSelection & (1 << 7) else False


def family_is_vf(ttFonts):
    has_fvar = ["fvar" in ttFont for ttFont in ttFonts]
    if any(has_fvar):
        if all(has_fvar):
            return True
        raise ValueError("Families cannot contain both static and variable fonts")
    return False


def validate_family(ttFonts):
    family_is_vf(ttFonts)
    family_names = set(font_familyname(f) for f in ttFonts)
    if len(family_names) != 1:
        raise ValueError(f"Multiple families found {family_names}")
    return True


def unique_name(ttFont, nameids):
    font_version = _font_version(ttFont)
    vendor = ttFont["OS/2"].achVendID.strip()
    ps_name = nameids[6]
    return f"{font_version};{vendor};{ps_name}"


def _font_version(font, platEncLang=(3, 1, 0x409)):
    nameRecord = font["name"].getName(5, *platEncLang)
    if nameRecord is None:
        return f'{font["head"].fontRevision:.3f}'
    # "Version 1.101; ttfautohint (v1.8.1.43-b0c9)" --> "1.101"
    # Also works fine with inputs "Version 1.101" or "1.101" etc
    versionNumber = nameRecord.toUnicode().split(";")[0]
    return versionNumber.lstrip("Version ").strip()


def partition_cmap(font, test, report=True):
    """Drops all cmap tables from the font which do not pass the supplied test.

    Arguments:
      font: A ``TTFont`` instance
      test: A function which takes a cmap table and returns True if it should
        be kept or False if it should be removed from the font.
      report: Reports to stdout which tables were dropped and which were kept.

    Returns two lists: a list of `fontTools.ttLib.tables._c_m_a_p.*` objects
    which were kept in the font, and a list of those which were removed."""
    keep = []
    drop = []

    for index, table in enumerate(font["cmap"].tables):
        if test(table):
            keep.append(table)
        else:
            drop.append(table)

    if report:
        for table in keep:
            print(
                (
                    "Keeping format {} cmap subtable with Platform ID = {}"
                    " and Encoding ID = {}"
                ).format(table.format, table.platformID, table.platEncID)
            )
        for table in drop:
            print(
                (
                    "--- Removed format {} cmap subtable with Platform ID = {}"
                    " and Encoding ID = {} ---"
                ).format(table.format, table.platformID, table.platEncID)
            )

    font["cmap"].tables = keep
    return keep, drop


def _unicode_marks(string):
    unicodemap = [("©", "(c)"), ("®", "(r)"), ("™", "(tm)")]
    return filter(lambda char: char[0] in string, unicodemap)


def normalize_unicode_marks(string):
    """Converts special characters like copyright,
    trademark signs to ascii name"""
    # print("input: '{}'".format(string))
    input_string = string
    for mark, ascii_repl in _unicode_marks(string):
        string = string.replace(mark, ascii_repl)

    rv = []
    #    for c in unicodedata.normalize('NFKC', smart_text(string)):
    for c in unicodedata.normalize("NFKC", string):
        # cat = unicodedata.category(c)[0]
        # if cat in 'LN' or c in ok:
        rv.append(c)

    new = "".join(rv).strip()
    result = unidecode(new)
    if result != input_string:
        print("Fixed string: '{}'".format(result))
    return result


def get_fsSelection_byte2(ttfont):
    return ttfont["OS/2"].fsSelection >> 8


def get_fsSelection_byte1(ttfont):
    return ttfont["OS/2"].fsSelection & 255


def get_encoded_glyphs(ttFont):
    """Collect all encoded glyphs"""
    return list(map(chr, ttFont.getBestCmap().keys()))


def get_unencoded_glyphs(font):
    """Check if font has unencoded glyphs"""
    cmap = font["cmap"]

    new_cmap = cmap.getcmap(3, 10)
    if not new_cmap:
        for ucs2cmapid in ((3, 1), (0, 3), (3, 0)):
            new_cmap = cmap.getcmap(ucs2cmapid[0], ucs2cmapid[1])
            if new_cmap:
                break

    if not new_cmap:
        return []

    diff = list(set(font.getGlyphOrder()) - set(new_cmap.cmap.values()) - {".notdef"})
    return [g for g in diff[:] if g != ".notdef"]


def has_mac_names(ttfont):
    """Check if a font has Mac names. Mac names have the following
    field values:
    platformID: 1, encodingID: 0, LanguageID: 0"""
    return any(
        namerecord.platformID == 1
        and namerecord.platEncID == 0
        and namerecord.langID == 0
        for namerecord in ttfont["name"].names
    )


def font_is_italic(ttfont):
    """Check if the font has the word "Italic" in its stylename."""
    stylename = ttfont["name"].getName(2, 3, 1, 0x409).toUnicode()
    return True if "Italic" in stylename else False


def font_sample_text(ttFont):
    """Collect words which exist in the Universal Declaration of Human Rights
    that can be formed using the ttFont instance.

    UDHR has been chosen due to the many languages it covers"""
    with open(resource_filename("gftools", "udhr_all.txt"), encoding="utf-8") as doc:
        uhdr = doc.read()

    cmap = set(ttFont.getBestCmap())
    words = []
    seen_chars = set()

    def _add_words(words, text, seen_chars):
        for word in text.split():
            chars = set(ord(l) for l in word)
            if not chars.issubset(cmap):
                continue
            if chars & seen_chars == chars:
                continue
            seen_chars |= chars
            words.append(word)

    _add_words(words, uhdr, seen_chars)

    if len(seen_chars) < len(cmap):
        languages = LoadLanguages()
        for file, proto in languages.items():
            if hasattr(proto, "sample_text"):
                for key, text in proto.sample_text.ListFields():
                    _add_words(words, text, seen_chars)

    return words


def partition(items, size):
    """partition([1,2,3,4,5,6], 2) --> [[1,2],[3,4],[5,6]]"""
    return [items[i : i + size] for i in range(0, len(items), size)]


def read_proto(fp, schema):
    with open(fp, "rb") as f:
        data = text_format.Parse(f.read(), schema)
    return data


def parse_axis_dflts(string):
    axes = string.split()
    res = {}
    for axis in axes:
        k, v = axis.split("=")
        res[k] = float(v)
    return res


def remove_url_prefix(url):
    """https://www.google.com --> google.com"""
    pattern = r"(https?://)?(www\.)?"
    cleaned_url = re.sub(pattern, "", url)
    return cleaned_url


def primary_script(ttFont, ignore_latin=True):
    g = classifyGlyphs(
        lambda uv: list(ftunicodedata.script_extension(chr(uv))),
        ttFont.getBestCmap(),
        gsub=ttFont.get("GSUB"),
    )
    badkeys = ["Zinh", "Zyyy", "Zzzz"]
    if ignore_latin:
        badkeys.append("Latn")
    for badkey in badkeys:
        if badkey in g:
            del g[badkey]
    script_count = Counter({k: len(v) for k, v in g.items()})

    # If there isn't a clear winner, give up
    if (
        len(script_count) > 2
        and script_count.most_common(2)[0][1] < 2 * script_count.most_common(2)[1][1]
    ):
        return
    most_common = script_count.most_common(1)
    if most_common:
        return most_common[0][0]


def autovivification(items):
    if items == None:
        return None
    if isinstance(items, (list, tuple)):
        return [autovivification(v) for v in items]
    if isinstance(items, (float, int, str, bool)):
        return items
    d = defaultdict(lambda: defaultdict(defaultdict))
    d.update({k: autovivification(v) for k, v in items.items()})
    return d


def font_version(font: TTFont):
    version_id = font["name"].getName(5, 3, 1, 0x409)
    if not version_id:
        version = str(font["head"].fontRevision)
    else:
        version = version_id.toUnicode()
    return version


def is_google_fonts_repo(fp: "Path | str"):
    if isinstance(fp, str):
        fp = Path(fp)
    sub_dirs = fp.glob("*/")
    if "ofl" not in [d.name for d in sub_dirs]:
        return False
    return True


def open_ufo(path):
    if os.path.isdir(path):
        return ufoLib2.Font.open(path)
    elif path.endswith(".json"):
        return ufoLib2.Font.json_load(open(path, "rb"))
    else:  # Maybe a .ufoz
        return ufoLib2.Font.open(path)
    return False


# https://github.com/googlefonts/nanoemoji/blob/fb4b0b3e10f7197e7fe33c4ae6949841e4440397/src/nanoemoji/util.py#L167-L176
def shell_quote(s: Union[str, Path]) -> str:
    """Quote a string or pathlib.Path for use in a shell command."""
    s = str(s)
    # shlex.quote() is POSIX-only, for Windows we use subprocess.list2cmdline()
    # which converts a list of args to a command line string following the
    # the MS C runtime rules.
    if sys.platform.startswith("win"):
        return subprocess.list2cmdline([s])
    else:
        return shlex.quote(s)


def github_user_repo(github_url):
    if github_url.endswith(".git"):
        github_url = github_url[:-4]
    pattern = r"https?://w?w?w?\.?github\.com/(?P<user>[^/]+)/(?P<repo>[^/]+)"
    match = re.search(pattern, github_url)
    if not match:
        raise ValueError(
            f"Cannot extract github user and repo name from url '{github_url}'."
        )
    return match.group("user"), match.group("repo")


def has_gh_token():
    if "GH_TOKEN" in os.environ:
        return True
    return False


def parse_codepoint(codepoint: str) -> int:
    # https://github.com/googlefonts/ufomerge/blob/2257a1d3807a4eec9b515aa98e059383f7814d9a/Lib/ufomerge/cli.py#L118-L126
    if codepoint.startswith(("U+", "u+", "0x", "0X")):
        return int(codepoint[2:], 16)
    else:
        return int(codepoint)
