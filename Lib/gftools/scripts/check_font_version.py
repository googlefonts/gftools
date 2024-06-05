#!/usr/bin/env python3
# Copyright 2017 The Fontbakery Authors
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
"""
Check the version number of a family hosted on fonts.google.com.
"""
from __future__ import print_function
from argparse import ArgumentParser
from fontTools.ttLib import TTFont
from ntpath import basename
from zipfile import ZipFile
from gftools.utils import (
    download_family_from_Google_Fonts,
    download_file,
    fonts_from_zip,
)


def parse_version_head(fonts):
    """Return a family's version number. Ideally, each font in the
    family should have the same version number. If not, return the highest
    version number."""
    versions = []
    if isinstance(fonts, list):
        for font in fonts:
            versions.append(float(font["head"].fontRevision))
    else:
        versions.append(float(fonts["head"].fontRevision))
    return max(versions)


def main(args=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("family", help="Name of font family")
    parser.add_argument(
        "-wc", "--web-compare", help="Compare against a web url .zip family"
    )
    parser.add_argument(
        "-lc", "--local-compare", nargs="+", help="Compare against a set of local ttfs"
    )
    args = parser.parse_args(args)

    google_family = download_family_from_Google_Fonts(args.family)
    google_family_fonts = [TTFont(f) for f in google_family]
    google_family_version = parse_version_head(google_family_fonts)

    if args.web_compare:
        if args.web_compare.endswith(".zip"):
            web_family_zip = ZipFile(download_file(args.web_compare))
            web_family = fonts_from_zip(web_family_zip)
            web_family_fonts = [
                TTFont(f) for f in web_family if f.name.endswith(".ttf")
            ]
            web_family_name = set(f.reader.file.name.split("-")[0] for f in web_family)
            web_family_version = parse_version_head(web_family_fonts)
        print(
            "Google Fonts Version of %s is v%s" % (args.family, google_family_version)
        )
        print(
            "Web Version of %s is v%s"
            % (", ".join(web_family_name), web_family_version)
        )

    elif args.local_compare:
        local_family = [TTFont(f) for f in args.local_compare]
        local_family_version = parse_version_head(local_family)
        local_fonts_name = set(basename(f.split("-")[0]) for f in args.local_compare)
        print(
            "Google Fonts Version of %s is v%s" % (args.family, google_family_version)
        )
        print(
            "Local Version of %s is v%s"
            % (",".join(local_fonts_name), local_family_version)
        )

    else:
        print(
            "Google Fonts Version of %s is v%s" % (args.family, google_family_version)
        )


if __name__ == "__main__":
    main()
