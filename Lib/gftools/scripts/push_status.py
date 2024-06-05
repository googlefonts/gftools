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
"""Check the status of families being pushed to Google Fonts.

Families are pushed to a sandbox server and inspected before
they are sent to the production server. The files "to_sandbox.txt" and
"to_production.txt" in the google/fonts repo list which families need
pushing to their respective servers.

This script will check whether the families listed in the text files
have been pushed. A lint command is also provided to ensure they list
valid directory paths.

Usage:
gftools push-status /path/to/google/fonts/repo
# Check server push files are valid
gftools push-status /path/to/google/fonts/repo --lint
"""
import argparse
from pathlib import Path
from gftools.push.trafficjam import PushItems, PushStatus
from gftools.push.servers import (
    gf_server_metadata,
    PRODUCTION_META_URL,
    SANDBOX_META_URL,
)
from gftools.push.items import Family
import os


PUSH_STATUS_TEMPLATE = """
***{} Status***
New families:
{}

Existing families, last pushed:
{}
"""


def lint_server_files(fp: Path):
    template = "{}: Following paths are not valid:\n{}\n\n"
    footnote = (
        "lang and axisregistry dir paths need to be transformed.\n"
        "See https://github.com/googlefonts/gftools/issues/603"
    )

    prod_path = fp / "to_production.txt"
    production_file = PushItems.from_server_file(prod_path, PushStatus.IN_SANDBOX)
    prod_missing = "\n".join(map(str, production_file.missing_paths()))
    prod_msg = template.format("to_production.txt", prod_missing)

    sandbox_path = fp / "to_sandbox.txt"
    sandbox_file = PushItems.from_server_file(sandbox_path, PushStatus.IN_DEV)
    sandbox_missing = "\n".join(map(str, sandbox_file.missing_paths()))
    sandbox_msg = template.format("to_sandbox.txt", sandbox_missing)

    if prod_missing and sandbox_missing:
        raise ValueError(prod_msg + sandbox_msg + footnote)
    elif prod_missing:
        raise ValueError(prod_msg + footnote)
    elif sandbox_missing:
        raise ValueError(sandbox_msg + footnote)
    else:
        print("Server files have valid paths")


def server_push_status(fp: Path, url: str):
    families = [
        i
        for i in PushItems.from_server_file(fp, None, None)
        if isinstance(i.item(), Family)
    ]
    family_names = [i.item().name for i in families]

    gf_meta = gf_server_metadata(url)

    new_families = [f for f in family_names if f not in gf_meta]
    existing_families = [f for f in family_names if f in gf_meta]

    gf_families = sorted(
        [gf_meta[f] for f in existing_families], key=lambda k: k["lastModified"]
    )
    existing_families = [f"{f['family']}: {f['lastModified']}" for f in gf_families]
    return new_families, existing_families


def server_push_report(name: str, fp: Path, server_url: str):
    new_families, existing_families = server_push_status(fp, server_url)
    new = "\n".join(new_families) if new_families else "N/A"
    existing = "\n".join(existing_families) if existing_families else "N/A"
    print(PUSH_STATUS_TEMPLATE.format(name, new, existing))


def push_report(fp: Path):
    prod_path = fp / "to_production.txt"
    server_push_report("Production", prod_path, PRODUCTION_META_URL)

    sandbox_path = fp / "to_sandbox.txt"
    server_push_report("Sandbox", sandbox_path, SANDBOX_META_URL)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Path to google/fonts repo")
    parser.add_argument(
        "--lint", action="store_true", help="Check server files have correct paths"
    )
    args = parser.parse_args(args)

    if "ofl" not in os.listdir("."):
        raise ValueError("tool must be run from a google/fonts dir")

    if args.lint:
        lint_server_files(args.path)
    else:
        push_report(args.path)


if __name__ == "__main__":
    main()
