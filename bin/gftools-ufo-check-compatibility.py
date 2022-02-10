#!/usr/bin/env python3
"""
Check ufo sources are MM compatible. Very primitive.

Usage:

Basic:
gftools ufo-check-compatibility font1.ttf font2.ttf font3.ttf

Check everything against font1.ttf:
gftools ufo-check-compatibility font2.ttf font3.ttf --origin font1.ttf -a 

Check contours:
gftools ufo-check-compatibility font2.ttf font3.ttf --origin font1.ttf --contours 

"""
import os
from defcon import Font
import argparse


def check_glyphs(origin, fonts):
    origin_glyph_names = set(g.name for g in origin)

    for font in fonts[1:]:
        filename = os.path.basename(font.path)
        glyph_names = set(g.name for g in font)
        if glyph_names != origin_glyph_names:
            missing = origin_glyph_names - glyph_names
            additional = glyph_names - origin_glyph_names
            if missing:
                print(f"{filename}: missing glyphs {missing}")
            if additional:
                print(f"{filename}: additional glyphs {additional}")


def check_anchors(origin, fonts):
    origin_anchors = {}

    for glyph in origin:
        origin_anchors[glyph.name] = set(a.name for a in glyph.anchors)

    for font in fonts[1:]:
        filename = os.path.basename(font.path)
        for glyph in font:
            glyph_anchors = set(a.name for a in glyph.anchors)

            if glyph.name not in origin_anchors:
                continue

            if glyph_anchors != origin_anchors[glyph.name]:
                print(
                    f"{filename}: {glyph.name} has {glyph_anchors} want {origin_anchors[glyph.name]}"
                )


def check_contours(origin, fonts):
    origin_contours = {}
    for glyph in origin:
        contours = []
        for contour in glyph:
            for pt in contour:
                contours.append(pt.segmentType)
        origin_contours[glyph.name] = contours

    for font in fonts[1:]:
        filename = os.path.basename(font.path)
        for glyph in font:
            contours = []
            for contour in glyph:
                for pt in contour:
                    contours.append(pt.segmentType)

            if glyph.name not in origin_contours:
                continue

            if contours != origin_contours[glyph.name]:
                print(f"{filename} {glyph.name}: incompatible contours")


def check_components(origin, fonts):
    origin_components = {}
    for glyph in origin:
        origin_components[glyph.name] = [c.glyph.name for c in glyph.components]

    for font in fonts:
        filename = os.path.basename(font.path)
        for glyph in font:
            glyph_components = [c.glyph.name for c in glyph.components]

            if glyph.name not in origin_components:
                continue

            if origin_components[glyph.name] != glyph_components:
                print(
                    f"{filename} {glyph.name}: incompatible components. has {origin_components} want {origin_components[glyph.name]}"
                )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("fonts", nargs="+", help="UFOs to check")
    parser.add_argument("--origin", help="Origin font to check all other fonts against")
    parser.add_argument("-a", "--all", action="store_true", help="Check everything")
    parser.add_argument("--anchors", action="store_true", help="Check anchors")
    parser.add_argument("--glyphs", action="store_true", help="Check glyph sets")
    parser.add_argument("--contours", action="store_true", help="Check glyph contours")
    parser.add_argument(
        "--components", action="store_true", help="Check glyph components"
    )
    args = parser.parse_args()

    if len(args.fonts) <= 1:
        print("Single font. No need to check!")
        return

    fonts = [Font(fp) for fp in args.fonts]

    if not any([args.all, args.anchors, args.glyphs, args.contours, args.components]):
        args.all = True

    if not args.origin:
        origin = fonts[0]
        fonts = fonts[1:]
    else:
        origin = Font(args.origin)

    if args.all:
        check_anchors(origin, fonts)
        check_glyphs(origin, fonts)
        check_contours(origin, fonts)
        check_components(origin, fonts)
        return

    if args.anchors:
        check_anchors(origin, fonts)
    elif args.glyphs:
        check_glyphs(origin, fonts)
    if args.contours:
        check_contours(origin, fonts)
    if args.components:
        check_components(origin, fonts)


if __name__ == "__main__":
    main()
