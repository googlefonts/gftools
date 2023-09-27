#!/usr/bin/env python3
"""
Remap a font's encoded glyphs.

Changes font cmap table. User can also specify their
own output path.

Usage:

gftools remap-font -o font-remap.ttf font.ttf A=A.alt B=B.alt U+0175=wcircumflex.alt
gftools remap-font --map-file=remapping.txt -o font-remap.ttf font.ttf
"""
import argparse
import sys

from fontTools.ttLib import TTFont


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-file", metavar="TXT", help="Newline-separated mappings")
    parser.add_argument("--output", "-o", metavar="TTF", help="Output font binary")
    parser.add_argument("font", metavar="TTF", help="Input font binary")
    parser.add_argument("mapping", nargs="*", help="Codepoint-to-glyph mapping")

    args = parser.parse_args(args)

    if not args.mapping and not args.map_file:
        print("You must either specify a mapping or a map file")
        sys.exit(1)
    if args.mapping and args.map_file:
        print("You must specify either a mapping or a map file, not both")
        sys.exit(1)

    mapping = {}
    font = TTFont(args.font)

    if args.map_file:
        incoming_map = open(args.map_file).readlines()
    else:
        incoming_map = args.mapping

    for entry in incoming_map:
        entry = entry.strip()
        if not entry or entry.startswith("#"):
            continue
        codepoint, glyph = entry.split("=")
        if codepoint.startswith("U+") or codepoint.startswith("0x"):
            codepoint = int(codepoint[2:], 16)
        else:
            codepoint = ord(codepoint)
        mapping[codepoint] = glyph
        if glyph not in font.getGlyphOrder():
            print(f"Glyph {glyph} (to be mapped to {codepoint}) not found in font")
            sys.exit(1)

    cmap = font["cmap"]
    for table in cmap.tables:
        for codepoint, glyph in mapping.items():
            table.cmap[codepoint] = glyph

    if args.output:
        out = args.output
    else:
        out = args.font
    print(f"Saving font: {out}")
    font.save(out)


if __name__ == "__main__":
    main()
