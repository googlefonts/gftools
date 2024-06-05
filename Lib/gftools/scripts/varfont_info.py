#!/usr/bin/env python3
#
# Copyright 2017 Google Inc. All Rights Reserved.
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
"""Utility to dump variation font info.

Lists which variable font axes and named-instances are declared in the 'fvar'
table of a given TTF file.

"""
from __future__ import print_function
import argparse
import contextlib
import sys
from fontTools import ttLib


def _ResolveName(ttf, name_id):
    if name_id == 0xFFFF:
        return "[anonymous]"
    names = [n for n in ttf["name"].names if n.nameID == name_id]
    if not names:
        return "[?nameID=%d?]" % name_id
    unicode_names = [n for n in names if n.isUnicode()]
    if unicode_names:
        return unicode_names[0].toUnicode()
    return names[0].toUnicode()


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fonts", metavar="TTF", nargs="+", help="Fonts in OpenType (TTF/OTF) format"
    )

    args = parser.parse_args(args)
    for filename in args.fonts:
        with contextlib.closing(ttLib.TTFont(filename)) as ttf:
            print(filename)
            if "fvar" not in ttf:
                print("This font file lacks an 'fvar' table.")
            else:
                fvar = ttf["fvar"]
                print(" axes")
                axes = [
                    (a.axisTag, a.minValue, a.defaultValue, a.maxValue)
                    for a in fvar.axes
                ]
                for tag, minv, defv, maxv in axes:
                    print("  '%s' %d-%d, default %d" % (tag, minv, maxv, defv))

                if fvar.instances:
                    print(" named-instances")
                    for inst in fvar.instances:
                        print(
                            "   %s %s"
                            % (
                                _ResolveName(ttf, inst.postscriptNameID),
                                inst.coordinates,
                            )
                        )


if __name__ == "__main__":
    main()
