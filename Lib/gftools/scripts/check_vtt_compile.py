#!/usr/bin/env python3
"""Check if a font's VTT hinting can be compiled with vttLib"""
from vttLib import *
from fontTools.ttLib import TTFont
import argparse


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("font_path")
    parser.add_argument("-f", "--remove-incompatible-hinting", action="store_true")
    args = parser.parse_args(args)

    font = TTFont(args.font_path)
    if "TSI1" not in font:
        print("Font is not VTT hinted")
        return
    glyph_names = font.getGlyphOrder()

    incompatible_glyphs = []
    for gid, glyph_name in enumerate(glyph_names):
        try:
            data = get_glyph_assembly(font, glyph_name)
        except KeyError:
            pass
        try:
            program, components = make_glyph_program(data, glyph_name)
        except:
            incompatible_glyphs.append((gid, glyph_name))

    if not incompatible_glyphs:
        print("All glyphs compile")
        return
    print("Following glyphs cannot compile using vttLib:")
    print("GlyphID GlyphName")
    for gid, glyph_name in incompatible_glyphs:
        print(gid, glyph_name)

    if not args.remove_incompatible_hinting:
        return
    if args.remove_incompatible_hinting:
        for _, glyph_name in incompatible_glyphs:
            font["TSI1"].glyphPrograms[glyph_name] = ""
            font["TSI3"].glyphPrograms[glyph_name] = ""
    font.save(args.font_path + ".fix")
    print("Incompatible glyph hints have been removed")


if __name__ == "__main__":
    main()
