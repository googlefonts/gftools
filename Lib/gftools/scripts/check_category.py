#!/usr/bin/env python3
#
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
from __future__ import print_function

import argparse
import os
import sys
import requests
from gftools.fonts_public_pb2 import FamilyProto
from google.protobuf import text_format

description = (
    "Comparison of category fields of local METADATA.pb files"
    " with data corresponding metadata on the Google Fonts Developer API.\n\n"
    " In order to use it you need to provide an API key."
)
parser = argparse.ArgumentParser(description=description)
parser.add_argument("key", help="Key from Google Fonts Developer API")
parser.add_argument(
    "repo", help=("Directory tree that contains" " directories with METADATA.pb files.")
)
parser.add_argument(
    "--verbose", help="Print additional information", action="store_true"
)


API_URL = "https://www.googleapis.com/webfonts/v1/webfonts?key={}"


def main(args=None):
    args = parser.parse_args(args)
    response = requests.get(API_URL.format(args.key))
    try:
        webfontList = response.json()["items"]
        webfontListFamilyNames = [item["family"] for item in webfontList]
    except (ValueError, KeyError):
        sys.exit(
            "Unable to load and parse" " list of families from Google Web Fonts API."
        )

    for dirpath, dirnames, filenames in os.walk(args.repo):
        metadata_path = os.path.join(dirpath, "METADATA.pb")
        if not os.path.exists(metadata_path):
            continue

        metadata = FamilyProto()
        text_data = open(metadata_path, "rb").read()
        text_format.Merge(text_data, metadata)
        try:
            family = metadata.name
        except KeyError:
            print(
                ('ERROR: "{}" does not contain' " familyname info.").format(
                    metadata_path
                ),
                file=sys.stderr,
            )
            continue

        try:
            index = webfontListFamilyNames.index(family)
            webfontsItem = webfontList[index]
        except ValueError:
            if args.verbose:
                print(
                    (
                        'ERROR: Family "{}" could not be found'
                        " in Google Web Fonts API."
                    ).format(family)
                )
            continue

        if metadata.category == "SANS_SERIF":  # That's fine :-)
            category = "sans-serif"
        else:
            category = metadata.category.lower()

        if category != webfontsItem["category"]:
            print(
                (
                    'ERROR: "{}" category "{}" in git'
                    ' does not match category "{}"'
                    " in API."
                ).format(family, metadata.category, webfontsItem["category"])
            )
        else:
            if args.verbose:
                print(
                    ('OK: "{}" ' 'category "{}" in sync.').format(
                        family, metadata.category
                    )
                )


if __name__ == "__main__":
    main()
