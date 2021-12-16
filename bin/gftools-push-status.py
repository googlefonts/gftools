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
from gftools.push import lint_server_files, push_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Path to google/fonts repo")
    parser.add_argument(
        "--lint", action="store_true", help="Check server files have correct paths"
    )
    args = parser.parse_args()
    if args.lint:
        lint_server_files(args.path)
    else:
        push_report(args.path)


if __name__ == "__main__":
    main()
