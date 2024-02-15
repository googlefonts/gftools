#!/usr/bin/env python3
# Copyright 2013 The Font Bakery Authors.
# Copyright 2017 The Google Font Tools Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# See AUTHORS.txt for the list of Authors and LICENSE.txt for the License.
#
import argparse
from gftools.utils import format_html

description = "Format HTML files according to Google Fonts specs"
parser = argparse.ArgumentParser(description=description)
parser.add_argument("html_file", nargs="+", help="HTML files to format")


def main(args=None):
    args = parser.parse_args(args)
    for path in args.html_file:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        formatted = format_html(content)
        with open(path, "w", encoding="utf-8") as f:
            f.write(formatted)


if __name__ == "__main__":
    main()
