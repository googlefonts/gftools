#!/usr/bin/env python3
"""
gftools fix-font

Update a font so it conforms to the Google Fonts specification
https://github.com/googlefonts/gf-docs/tree/main/Spec

Usage:

gftools fix-font font.ttf

# Fix font issues that should be fixed in the source files
gftools fix-font font.ttf --include-source-fixes
"""
import argparse
import logging
from fontTools.ttLib import TTFont
from gftools.fix import *
from gftools.utils import parse_axis_dflts


logging.basicConfig(level=logging.INFO)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("font", help="Path to font")
    parser.add_argument("-o", "--out", help="Output path for fixed font")
    parser.add_argument(
        "--include-source-fixes",
        action="store_true",
        help="Fix font issues that should be fixed in the source files.",
    )
    parser.add_argument("--rename-family", help="Change the family's name")
    parser.add_argument(
        "--fvar-instance-axis-dflts",
        help=(
            "Set the fvar instance default values for non-wght axes. e.g "
            "wdth=100 opsz=36"
        ),
    )
    args = parser.parse_args(args)

    font = TTFont(args.font)

    if args.fvar_instance_axis_dflts:
        axis_dflts = parse_axis_dflts(args.fvar_instance_axis_dflts)
    else:
        axis_dflts = None
    font = fix_font(font, args.include_source_fixes, args.rename_family, axis_dflts)

    if args.out:
        font.save(args.out)
    else:
        font.save(font.reader.file.name + ".fix")


if __name__ == "__main__":
    main()
