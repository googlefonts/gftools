#!/usr/bin/env python3
"""
gftools diffenator

fontdiffenator's successor
"""
from gftools.diffenator import DFont, DiffFonts, Reporter, match_fonts
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("old_font")
    parser.add_argument("new_font")
    parser.add_argument("--strings", help="File of strings to visually compare")
    parser.add_argument("--out", "-o", default="out.html", help="Output html path")
    args = parser.parse_args()

    old_font = DFont(args.old_font)
    new_font = DFont(args.new_font)
    old_font, new_font = match_fonts(old_font, new_font, rename_glyphs=False, scale_upm=False)

    strings = None
    if args.strings:
        with open(args.strings) as file:
            strings = [line.rstrip() for line in file]

    diff = DiffFonts(old_font, new_font, strings=strings)
    diff.build()

    report = Reporter(diff)
    import pdb
    pdb.set_trace()
    report.save(args.out, args.old_font, args.new_font)


if __name__ == "__main__":
    main()
