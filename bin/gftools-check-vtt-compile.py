#!/usr/bin/env python3
"""Check if a font's VTT hinting can be compiled with vttLib"""
from vttLib import *
from fontTools.ttLib import TTFont
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("font_path")
    args = parser.parse_args()

    font = TTFont(args.font_path)
    if "TSI1" not in font:
        print("Font is not VTT hinted")
        return
    glyph_names = font.getGlyphOrder()

    incompatible_glyphs = []
    for gid, glyph_name in enumerate(glyph_names):
        data = get_glyph_assembly(font, glyph_name)
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

    
if __name__ == "__main__":
    main()

