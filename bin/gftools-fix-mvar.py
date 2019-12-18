#!/usr/bin/env python3

# Copyright 2019 The Google Font Tools Authors
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
import os
import sys

from fontTools.ttLib import TTFont


def main():
    description = "Removes MVAR table from one or more font files"
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument("FONTPATH", nargs="+", help="One or more font files")

    args = parser.parse_args()

    for fontpath in args.FONTPATH:
        # validate file
        if not os.path.exists(fontpath):
            sys.stderr.write(
                "The file path '{}' does not appear to be valid.".format(fontpath)
            )
            sys.exit(1)

        try:
            tt = TTFont(fontpath)
            if "MVAR" in tt:
                del tt["MVAR"]
                tt.save(fontpath)
                tt_edited = TTFont(fontpath)
                assert "MVAR" not in tt_edited
                print("MVAR table removed from '{}'".format(fontpath))
            else:
                print("MVAR table was not found in '{}'".format(fontpath))
        except Exception as e:
            sys.stderr.write("Error during execution: {}".format(str(e)))
            sys.exit(1)


if __name__ == "__main__":
    main()
