#!/usr/bin/env python3
"""
Set the glyph Order for a collection of ufos

Usage:

# Set glyph orders based on first ufo
gftools ufo-set-order font1.ufo font2.ufo font3.ufo

# Set glyph orders based on font1.ufo glyph order
gftools ufo-set-order font2.ufo font3.ufo --origin font1.ufo
"""
# TODO: we can probably order components and anchors as well!
# add these when needed
from defcon import Font
import argparse
import os


def set_glyph_order(origin, fonts):
    glyph_order = origin.glyphOrder
    for font in fonts:
        if font.glyphOrder != glyph_order:
            print(
                f"Updating {os.path.basename(font.path)} since glyph order is different"
            )
        font.glyphOrder = glyph_order


def main(args=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("fonts", nargs="+")
    parser.add_argument(
        "--origin", help="Source font to set glyph order for other fonts"
    )
    args = parser.parse_args(args)

    if len(args.fonts) <= 1:
        print("Single font. No need to set order")
        return

    if not args.origin:
        origin = args.fonts[0]
        fonts = args.fonts[1:]
    else:
        origin = args.origin

    fonts = [Font(fp) for fp in args.fonts]
    origin = Font(origin)

    set_glyph_order(origin, fonts)

    for font in fonts:
        font.save()


if __name__ == "__main__":
    main()
