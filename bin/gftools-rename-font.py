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


FAMILY_NAME = (1, 3, 1, 1033)
TYPO_FAMILY_NAME = (16, 3, 1, 1033)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("font")
    parser.add_argument("new_name")
    parser.add_argument("-o", "--out")
    args = parser.parse_args()

    font = TTFont(args.font)
    nametable = font["name"]
    current_name = nametable.getName(*TYPO_FAMILY_NAME) or \
        nametable.getName(*FAMILY_NAME)
    if not current_name:
        raise Exception(
            "Name table does not contain nameID 1 or nameID 16. "
            "This tool does not work on webfonts."
        )
    current_name = current_name.toUnicode()
    print("Updating font name records")
    for record in nametable.names:
        record_string = record.toUnicode()

        no_space = current_name.replace(" ", "")
        hyphenated = current_name.replace(" ", "-")
        # name with no spaces
        if no_space in record_string:
            new_string = record_string.replace(no_space, args.new_name.replace(" ", ""))
        # name with hyphens instead of spaces
        elif hyphenated in record_string:
            new_string = record_string.replace(hyphenated, args.new_name.replace(" ", "-"))
        # name with spaces
        else:
            new_string = record_string.replace(current_name, args.new_name)

        if new_string is not record_string:
            record_info = (
                record.nameID,
                record.platformID,
                record.platEncID,
                record.langID
            )
            print(
                "Updating {}: '{}' to '{}'".format(
                    record_info,
                    record_string,
                    new_string,
                )
            )
            record.string = new_string
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
