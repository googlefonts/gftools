#!/usr/bin/env python3
"""
gftools gen-stat

Generate a STAT table for each font in a variable font family
using the GF axis registry.

Usage:

gftools gen-stat [fonts.ttf] --axis-order wdth wght

# Overwrite existing fonts
gftools gen-stat [fonts.ttf] --axis-order wdth wght --inplace

# Overide which axis values are elided
gftools gen-stat [fonts.ttf] --elided-values wght=400
"""
from fontTools.ttLib import TTFont
from gftools.fix import gen_stat_tables
from gftools.axisreg import axis_registry
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
    parser.add_argument(
        "--axis-order", "-ao", nargs="+", required=True, choices=axis_registry.keys(),
        help="Stat table axis order"
    )
    parser.add_argument("--elided-values", nargs="+", default=None)
    parser.add_argument(
        "--inplace", action="store_true", default=False, help="Overwrite input files"
    )
    args = parser.parse_args()

    fonts = [TTFont(f) for f in args.fonts]
    elided_values = (
        parse_elided_values(args.elided_values) if args.elided_values else None
    )
    gen_stat_tables(fonts, args.axis_order, elided_values)

    for font in fonts:
        print(f"Updated STAT for {font.reader.file.name}")
        dst = font.reader.file.name if args.inplace else font.reader.file.name + ".fix"
        font.save(dst)


if __name__ == "__main__":
    main()
