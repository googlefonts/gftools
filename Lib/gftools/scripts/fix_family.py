#!/usr/bin/env python3
"""
gftools fix-family

Update a family so it conforms to the Google Fonts specification
https://github.com/googlefonts/gf-docs/tree/main/Spec

Usage:

gftools fix-family fonts1.ttf fonts2.ttf

# Fix font issues that should be fixed in the source files
gftools fix-family fonts1.ttf --include-source-fixes
"""
import argparse
import logging
import os
from fontTools.ttLib import TTFont
from gftools.fix import *
from gftools.utils import parse_axis_dflts

logging.basicConfig(level=logging.INFO)


def new_filename(font, font_renamed=None):
    if font_renamed:
        return fix_filename(font)
    return os.path.basename(font.reader.file.name)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("fonts", nargs="+", help="Font family paths")
    parser.add_argument(
        "--inplace", action="store_true", default=False, help="Save fixed fonts inplace"
    )
    parser.add_argument("-o", "--out", help="Output dir for fixed fonts")
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

    fonts = [TTFont(f) for f in args.fonts]
    if args.fvar_instance_axis_dflts:
        axis_dflts = parse_axis_dflts(args.fvar_instance_axis_dflts)
    else:
        axis_dflts = None
    fonts = fix_family(fonts, args.include_source_fixes, args.rename_family, axis_dflts)

    if args.inplace:
        for font in fonts:
            font.save(font.reader.file.name)
    elif args.out:
        if not os.path.isdir(args.out):
            os.mkdir(args.out)
        for font in fonts:
            filename = new_filename(font, args.rename_family)
            out_path = os.path.join(args.out, filename)
            font.save(out_path)
    else:
        for font in fonts:
            dir_ = os.path.dirname(font.reader.file.name)
            filename = os.path.join(dir_, new_filename(font, args.rename_family))
            if filename == font.reader.file.name:
                font.save(filename + ".fix")
            else:
                font.save(filename)


if __name__ == "__main__":
    main()
