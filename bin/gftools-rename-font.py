#!/usr/bin/env python3
"""
Rename a font.

Changes font menu name and filename. User can also specify their
own output path.

Usage:
gftools rename-font font.ttf "New Family Name"
"""
import argparse
from fontTools.ttLib import TTFont
from gftools.utils import font_familyname
from gftools.fix import rename_font


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("font")
    parser.add_argument("new_name")
    parser.add_argument("-o", "--out")
    args = parser.parse_args()

    font = TTFont(args.font)
    current_name = font_familyname(font)
    rename_font(font, args.new_name)

    if args.out:
        out = args.out
    else:
        out = args.font.replace(
            current_name.replace(" ", ""), args.new_name.replace(" ", "")
        )
    print("Saving font: {}".format(out))
    font.save(out)


if __name__ == "__main__":
    main()
