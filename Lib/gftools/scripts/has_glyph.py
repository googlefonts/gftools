#!/usr/bin/env python3
import os
import argparse
from fontTools.ttLib import TTFont


def check_glyph_in_font(font_path, char):
    """Return True if the Unicode char exists in the given font file."""
    try:
        font = TTFont(font_path)
        cmap = font.getBestCmap()  # maps Unicode codepoints -> glyph names
        codepoint = ord(char)
        return codepoint in cmap
    except Exception as e:
        print(f"[ERROR] Could not open {font_path}: {e}")
        return False


def scan_directory(root_dir, char):
    """Walk through directories and check each .ttf file for the character."""
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith(".ttf"):
                font_path = os.path.join(dirpath, filename)
                if check_glyph_in_font(font_path, char):
                    print(f"[FOUND] '{char}' (U+{ord(char):04X}) in {font_path}")


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Check if TTF fonts in a directory contain a specific Unicode glyph."
    )
    parser.add_argument("directory", help="Root directory to scan for TTF files")
    parser.add_argument(
        "glyph", help="The actual character to search for (e.g., 'A', '€', '你')"
    )
    args = parser.parse_args(args)

    if len(args.glyph) != 1:
        parser.error("Please provide exactly one character as the glyph argument.")

    scan_directory(args.directory, args.glyph)


if __name__ == "__main__":
    main()
