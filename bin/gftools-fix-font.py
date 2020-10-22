#!/usr/bin/env python3
"""
gftools fix-font

Update a font so it conforms to the Google Fonts specification
https://github.com/googlefonts/gf-docs/tree/master/Spec
"""
import argparse
from fontTools.ttLib import TTFont
from gftools.fix import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("font", help="Path to font")
    parser.add_argument("-o", "--out", help="Output path for fixed font")
    args = parser.parse_args()

    font = TTFont(args.font)

    if "DSIG" not in font:
        add_dummy_dsig(font)

    if "fpgm" in font:
        fix_hinted_font(font)
    else:
        fix_unhinted_font(font)

    # TODO (Marc F) fsSelection, macStyle, usWeightClass, VF instances...

    if args.out:
        font.save(args.out)
    else:
        font.save(font.reader.file.name + ".fix")


if __name__ == "__main__":
    main()
