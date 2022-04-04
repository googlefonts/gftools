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
    parser.add_argument("--out", "-o", default="out.html", help="Output html path")
    args = parser.parse_args()

    old_font = DFont(args.old_font)
    new_font = DFont(args.new_font)
    old_font, new_font = match_fonts(old_font, new_font)

    diff = DiffFonts(old_font, new_font)
    diff.build()

    report = Reporter(diff)
    report.save(args.out, args.old_font, args.new_font)


if __name__ == "__main__":
    main()
