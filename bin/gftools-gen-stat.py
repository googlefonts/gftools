#!/usr/bin/env python3
"""
gftools gen-stat

Generate a STAT table for each font in a variable font family
using the GF axis registry.

Usage:

gftools gen-stat [fonts.ttf] 

# Overwrite existing fonts
gftools gen-stat [fonts.ttf] --inplace
"""
from fontTools.ttLib import TTFont
import argparse
import os


def parse_elided_values(string):
    # "wght=300,400 wdth=75,100" --> {"wght": [300, 400], "wdth": [75, 100]}
    res = {}
    for axis in string:
        try:
            k, v = axis.split("=")
            v = [int(i) for i in v.split(",")]
            res[k] = v
        except ValueError:
            raise ValueError(
                "Incorrect --elided-values input. Requires 'AXIS=val,val ...' "
                "e.g 'wght=400 wdth=100'"
            )
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fonts", nargs="+")
    parser.add_argument("--elided-values", nargs="+", default=None)
    parser.add_argument(
        "--inplace", action="store_true", default=False, help="Overwrite input files"
    )
    args = parser.parse_args()

    fonts = [TTFont(f) for f in args.fonts]
    elided_values = (
        parse_elided_values(args.elided_values) if args.elided_values else None
    )
    gen_stat_tables(fonts, elided_values)

    for font in fonts:
        print(f"Updated STAT for {font.reader.file.name}")
        dst = font.reader.file.name if inplace else font.reader.file.name + ".fix"
        font.save(dst)


if __name__ == "__main__":
    main()
