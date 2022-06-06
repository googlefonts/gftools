"""
Primitive prepolator!

Warning mega destructive! TODO work on duplicates instead of overwriting

This may take a while to run so grab dinner
"""
from fontTools.varLib.interpolatable import test
from fontmake.compatibility import CompatibilityChecker
from ufoLib2 import Font
import sys
import os


def _fix_starting_points(glyphsets, base_font, font, glyph, names, idx):
    aa = base_font[glyph]
    gg = font[glyph]
    font.save()
    res = test([glyphsets[0], font.reader.getGlyphSet()], glyphs=[glyph], names=names)
    res2 = point_compat(base_font, font, glyph)
    if len(res) == 0 and res2:
        print(f"Fixed {glyph}")
        return True
    if idx == len(gg):
        return False
    
    for _ in range(len(gg[idx])):
        gg[idx].append(gg[idx].pop(0))
        gg_types = [n.type for n in gg[idx]]
        aa_types = [n.type for n in aa[idx]]
        if gg_types != aa_types:
            continue
        
        if _fix_starting_points(glyphsets, base_font, font, glyph, names, idx+1):
            return True
    return False


def fix_starting_points(glyphsets, base_font, font, glyph, names):
    fixed = _fix_starting_points(glyphsets, base_font, font, glyph, names, 0)
    if not fixed:
        raise ValueError("shit Curves")
    return True

def point_compat(base_font, font, glyph):
    base_points = []
    font_points = []

    for cont in base_font[glyph]:
        for pt in cont:
            base_points.append(pt.type)
    
    for cont in font[glyph]:
        for pt in cont:
            font_points.append(pt.type)
    return base_points == font_points


def main():
    names = [os.path.basename(f) for f in sys.argv[1:]]
    fonts = [Font.open(f) for f in sys.argv[1:]]
    glyphsets = [f.reader.getGlyphSet() for f in fonts]
    base_font = fonts[0]
    fonts = fonts[1:]

    base_glyphset = glyphsets[0]
    glyphsets = glyphsets[1:]

    glyphs = base_font.reader.getGlyphSet().keys()
    for glyph in glyphs:
        for idx, glyphset in enumerate(glyphsets):
            font = fonts[idx]
            res = test([base_glyphset, glyphset], glyphs=[glyph], names=names)
            points_compat = point_compat(base_font, font, glyph)
            if not res and points_compat:
                continue
            if not points_compat:
                fix_starting_points([base_glyphset, glyphset], base_font, font, glyph, names)
            else:
                for issue in res[glyph]:
                    if issue['type'] in ["wrong_start_point", "node_incompatibility"]:
                        fix_starting_points([base_glyphset, glyphset], base_font, font, glyph, names)

    print("Done!")


if __name__ == "__main__":
    main()