#!/usr/bin/env python3
# Copyright 2020 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Check push status of families on Dev, Sandbox and Production servers.

This script will determine whether the families listed in
to_production.txt and to_sandbox.txt in the google/fonts dir have been
pushed to their respective servers from a specific date.

If the files are empty, you can always use git checkout to view past
states.


Usage:

Check push status for the past month:
gftools push-status path/to/google/fonts

Check push status for specified date:
gftools push-status path/to/google/fonts -pd 2020-07-01
"""
import argparse
from argparse import RawDescriptionHelpFormatter
import os
from pathlib import Path
import gftools.fonts_public_pb2 as fonts_pb2
from google.protobuf import text_format
from datetime import datetime, timedelta
import json
import requests


# If no push date is added we can assume that the push has probably
# happened in the past month
ONE_MONTH_AGO = datetime.now() - timedelta(days=31)


def get_family_metadata(url):
    """Get family json data from a Google Fonts metadata url"""
    # can't do requests.get("url").json() since request text starts with ")]}'"
    info = json.loads(requests.get(url).text[5:])
    return {i['family']: i for i in info["familyMetadataList"]}


def read_proto(fp, schema):
    with open(fp, "rb") as f:
        data = text_format.Parse(f.read(), schema)
    return data


def families_from_file(fp):
    """Convert to_sandbox.txt and to_production.txt files to a list of
    family names."""
    results = set()
    with open(fp) as doc:
        family_dirs = [p for p in doc.read().split() if p.startswith(("ofl", "ufl", "apache"))]
    metadata_files = [Path(fp).parent / d / 'METADATA.pb' for d in family_dirs]
    missing_files = [str(f) for f in metadata_files if not f.is_file()]
    if missing_files:
        raise FileNotFoundError(
            "Following METADATA.pbs files are missing:\n{}".format(
                "\n".join(missing_files)
            )
        )
    return [read_proto(f, fonts_pb2.FamilyProto()).name for f in metadata_files]


def families_status(info, push_date, filter_families=set()):
    """Determine which families have been pushed or not pushed from a
    specific date. If a filter_families set is provided, remove
    families from the results which are not included in this set."""
    results = {"pushed": set(), "not_pushed": set()}
    if filter_families:
        info = {k: v for k,v in info.items() if k in filter_families}
    for family in info:
        last_push = info[family]['lastModified']
        last_push = iso_8601_to_date(last_push)
        if last_push >= push_date:
            results['pushed'].add(family)
        if last_push < push_date:
            results["not_pushed"].add(family)
    return results


def status_reporter(server_name, status):
    """Produce a report for a server status dict"""
    report = []
    report.append(f"***{server_name}***")
    for k, v in status.items():
        report.append(f"{k}: {sorted(v)}")
    report.append("\n")
    return "\n".join(report)


def specimen_reporter(server_name, url_base, families):
    """Produce a report containing urls for a list of families"""
    report = []
    report.append(f"***{server_name} specimens to inspect***")
    for family in sorted(families):
        family_url = url_base.format(family.replace(" ", "+"))
        report.append(family_url)
    if len(report) == 1:
        report.append("No urls to inspect")
    report.append("\n")
    return "\n".join(report)


def iso_8601_to_date(string):
    """YYYY-MM-DD --> datetime"""
    if ":" in string or len(string.split("-")) != 3:
        raise ValueError(f"Date format should be 'YYYY-MM-DD' got '{string}'")
    return datetime.strptime(string, "%Y-%m-%d")


def gf_repo(path):
    """Check if path is a Google Fonts repo"""
    path = Path(path)
    if not path.is_dir() or list(path.glob("to_production`.txt")):
        raise OSError(f"{path} is not a Google/Fonts dir")
    return path


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument("gf_path", type=gf_repo, help="path to google/fonts dir")
    parser.add_argument(
        "--push_date", "-pd", type=iso_8601_to_date, default=ONE_MONTH_AGO,
        help="Date when last push occurred"
    )
    args = parser.parse_args()

    dev_meta = get_family_metadata("https://fonts-dev.sandbox.google.com/metadata/fonts")
    sandbox_meta = get_family_metadata(f"https://fonts.sandbox.google.com/metadata/fonts")
    prod_meta = get_family_metadata(f"https://fonts.google.com/metadata/fonts")

    dev_status = families_status(dev_meta, args.push_date)

    to_sandbox_file = Path(f"{args.gf_path}/to_sandbox.txt")
    requested_sandbox_families = families_from_file(to_sandbox_file)
    sandbox_status = families_status(sandbox_meta, args.push_date, requested_sandbox_families)

    to_production_file = Path(f"{args.gf_path}/to_production.txt")
    requested_prod_families = families_from_file(to_production_file)
    prod_status = families_status(prod_meta, args.push_date, requested_prod_families)

    specimen_url = "https://fonts-dev.sandbox.google.com/specimen/{}"
    print(specimen_reporter("Dev Server", specimen_url, dev_status["pushed"]))
    print(status_reporter("Sandbox Server", sandbox_status))
    print(status_reporter("Production Server", prod_status))


if __name__ == "__main__":
    main()

