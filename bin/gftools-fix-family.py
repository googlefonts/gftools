#!/usr/bin/env python3
"""
gftools fix-family

Update a family so it conforms to the Google Fonts specification
https://github.com/googlefonts/gf-docs/tree/master/Spec

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
    args = parser.parse_args()

    fonts = [TTFont(f) for f in args.fonts]
    fix_family(fonts, args.include_source_fixes)

    if args.inplace:
        for font in fonts:
            font.save(font.reader.file.name)
    elif args.out:
        if not os.path.isdir(args.out):
            os.mkdir(args.out)
        for font in fonts:
            out_path = os.path.join(
                args.out, os.path.basename(font.reader.file.name)
            )
            font.save(out_path)
    else:
        for font in fonts:
            font.save(font.reader.file.name + ".fix")


if __name__ == "__main__":
    main()
