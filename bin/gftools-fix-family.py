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


log = logging.getLogger(__name__)


def new_filename(font, font_renamed=None):
    if font_renamed:
        return fix_filename(font)
    return os.path.basename(font.reader.file.name)


def main():
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
    parser.add_argument(
        "--rename-family",
        help="Change the family's name"
    )
    args = parser.parse_args()

    fonts = [TTFont(f) for f in args.fonts]
    fix_family(fonts, args.include_source_fixes, args.rename_family)

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
