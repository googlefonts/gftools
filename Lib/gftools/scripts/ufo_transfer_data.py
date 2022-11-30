#!/usr/bin/env python3
"""Transfer data from one set of ufos to another

Usage:
# Transfer anchors from one set of ufos to another
gftools ufo-transfer-data --src font1.ufo font2.ufo --dst font3.ufo font4.ufo

# Same as above but match fonts by glyph a
gftools ufo-transfer-data --src font1.ufo font2.ufo --dst font3.ufo font4.ufo --match-by-glyph a

# Transfer kerning and anchors
gftools ufo-transfer-data --src font1.ufo --dst font2.ufo --anchors --kerning
"""
from defcon import Font
import os
from copy import deepcopy
import argparse


def glyph_point_hash(font, glyph_name):
    t = 0
    for cont in font[glyph_name]:
        for pt in cont:
            t += pt.x + pt.y
    return t


def match_fonts_by_glyph(src_fonts, dst_fonts, glyph):
    assert len(src_fonts) == len(dst_fonts)
    before, after = [], []

    for src_font in src_fonts:
        h = glyph_point_hash(src_font, glyph)
        before.append((h, src_font))

    for dst_font in dst_fonts:
        h = glyph_point_hash(dst_font, glyph)
        after.append((h, dst_font))

    before.sort(key=lambda k: k[0])
    after.sort(key=lambda k: k[0])

    return zip([i[1] for i in before], [i[1] for i in after])


def transfer_anchors(src_font, dst_font):
    for glyph in dst_font:
        glyph.clearAnchors()
        if glyph.name not in src_font:
            continue
        if not src_font[glyph.name].anchors:
            continue
        for idx, anchor in enumerate(src_font[glyph.name].anchors):
            dst_font[glyph.name].insertAnchor(idx, deepcopy(anchor))


def transfer_metrics(src_font, dst_font):
    for glyph in dst_font:
        if glyph.name not in src_font:
            continue
        dst_glyph = dst_font[glyph.name]
        glyph.leftMargin = dst_glyph.leftMargin
        glyph.width = dst_glyph.width


def transfer_kerning(src_font, dst_font):
    to_delete = set(dst_font.kerning.keys())
    for k in to_delete:
        dst_font.kerning.pop(k)

    has_glyphs = set(g.name for g in dst_font)
    for k, v in src_font.kerning.items():
        if k[0] in has_glyphs and k[1] in has_glyphs:
            dst_font.kerning[k] = v


def main(args=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--src", required=True, nargs="+", help="Source Fonts")
    parser.add_argument("--dst", required=True, nargs="+", help="Destination Fonts")
    parser.add_argument("--match-by-glyph", help="Match fonts by hashing a glyph")
    parser.add_argument("--anchors", action="store_true", help="Transfer anchor data")
    parser.add_argument("--metrics", action="store_true", help="Transfer glyph metrics")
    parser.add_argument("--kerning", action="store_true", help="Transfer kerning")
    args = parser.parse_args(args)

    if not any([args.anchors, args.metrics, args.kerning]):
        raise ValueError("Nothing chosen to transfer!")

    src_fonts = [Font(f) for f in args.src]
    dst_fonts = [Font(f) for f in args.dst]

    if args.match_by_glyph:
        matched_fonts = match_fonts_by_glyph(src_fonts, dst_fonts, args.match_by_glyph)
    else:
        matched_fonts = zip(src_fonts, dst_fonts)

    modified = False
    for src_font, dst_font in matched_fonts:
        print(
            f"Transferring {os.path.basename(src_font.path)} --> {os.path.basename(dst_font.path)}"
        )
        if args.anchors:
            modified = True
            transfer_anchors(src_font, dst_font)

        if args.metrics:
            modified = True
            transfer_metrics(src_font, dst_font)

        if args.kerning:
            modified = True
            transfer_kerning(src_font, dst_font)

        if modified:
            dst_font.save()


if __name__ == "__main__":
    main()
