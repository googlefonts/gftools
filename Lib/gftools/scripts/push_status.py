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
from gftools.push import push_report
from gftools.push2 import PushItems


def lint_server_files(fp):
    template = "{}: Following paths are not valid:\n{}\n\n"
    footnote = (
        "lang and axisregistry dir paths need to be transformed.\n"
        "See https://github.com/googlefonts/gftools/issues/603"
    )

    prod_path = fp / "to_production.txt"
    production_file = PushItems.from_server_file(prod_path, "In Sandbox")
    prod_missing = "\n".join(production_file.missing_paths())
    prod_msg = template.format("to_production.txt", prod_missing)

    sandbox_path = fp / "to_sandbox.txt"
    sandbox_file = PushItems.from_server_file(sandbox_path, "In Dev / PR Merged")
    sandbox_missing = "\n".join(sandbox_file.missing_paths())
    sandbox_msg = template.format("to_sandbox.txt", sandbox_missing)

    if prod_missing and sandbox_missing:
        raise ValueError(prod_msg + sandbox_msg + footnote)
    elif prod_missing:
        raise ValueError(prod_msg + footnote)
    elif sandbox_missing:
        raise ValueError(sandbox_msg + footnote)
    else:
        print("Server files have valid paths")


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Path to google/fonts repo")
    parser.add_argument(
        "--lint", action="store_true", help="Check server files have correct paths"
    )
    args = parser.parse_args(args)
    if args.lint:
        lint_server_files(args.path)
    else:
        push_report(args.path)


if __name__ == "__main__":
    main()
