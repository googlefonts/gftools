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


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("font")
    parser.add_argument("new_name", help="New family name")
    parser.add_argument("-o", "--out", help="Output path")
    parser.add_argument(
        "--just-family",
        action="store_true",
        help="Only change family name and names based off it, such as the "
        "PostScript name. (By default, the old family name is replaced "
        "by the new name in all name table entries, including copyright, "
        "description, etc.)",
    )
    args = parser.parse_args(args)

    font = TTFont(args.font)
    current_name = font_familyname(font)
    rename_font(font, args.new_name, aggressive=not args.just_family)

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
