#!/usr/bin/env python3
"""
Primitive ufo prepolator!

Fix ufo and designspace glyph incompatibilities. It can
currently fix:
- starting points
- contour order
- component order

Users will need to manually fix paths which have different node counts.

Warning mega destructive! TODO work on duplicates instead of overwriting.
Always use version control!

This may take a while for families which contain many masters.


Usage:

# fix ufos
gftools ufo-fix-mm font1.ufo font2.ufo

# fix designspaces
gftools ufo-fix-mm family.designspace
"""
from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.varLib.interpolatable import test
from ufoLib2 import Font
import os
from itertools import permutations
import argparse


def _fix_starting_points(glyphsets, base_font, font, glyph, names, idx):
    base_glyph = base_font[glyph]
    font_glyph = font[glyph]
    font.save()
    test_order = test(
        [glyphsets[0], font.reader.getGlyphSet()], glyphs=[glyph], names=names
    )
    test_compatibility = nodes_compatible(base_font, font, glyph)
    if len(test_order) == 0 and test_compatibility:
        print(f"{glyph}: Fixed starting points")
        return True
    if idx == len(font_glyph):
        return False

    for _ in range(len(font_glyph[idx])):
        # incrememt starting point by next node
        font_glyph[idx].append(font_glyph[idx].pop(0))
        # check that both paths have the same node types
        font_nodes = [n.type for n in font_glyph[idx]]
        base_nodes = [n.type for n in base_glyph[idx]]
        if font_nodes != base_nodes:
            continue

        if _fix_starting_points(glyphsets, base_font, font, glyph, names, idx + 1):
            return True
    return False


def fix_starting_points(glyphsets, base_font, font, glyph, names):
    fixed = _fix_starting_points(glyphsets, base_font, font, glyph, names, 0)
    if not fixed:
        print(f"{glyph}: Failed fixing starting points")
        return False
    return True


def nodes_compatible(base_font, font, glyph):
    base_font_nodes = []
    font_nodes = []

    for cont in base_font[glyph]:
        for pt in cont:
            base_font_nodes.append(pt.type)

    for cont in font[glyph]:
        for pt in cont:
            font_nodes.append(pt.type)
    return base_font_nodes == font_nodes


def components_compatible(base_font, font, glyph):
    base_font_components = [c.baseGlyph for c in base_font[glyph].components]
    font_components = [c.baseGlyph for c in font[glyph].components]
    return base_font_components == font_components


def fix_contour_order(glyphsets, font, glyph, names):
    contours = font[glyph].contours
    perms = permutations(contours)
    for perm in perms:
        font[glyph].clearContours()
        for contour in perm:
            font[glyph].appendContour(contour)
        font.save()
        res = test(
            [glyphsets[0], font.reader.getGlyphSet()], glyphs=[glyph], names=names
        )
        if len(res) == 0:
            print(f"{glyph}: Fixed contour order")
            return
    print(f"{glyph}: Failed fixing contour order")


def fix_component_order(base_font, font, glyph):
    components = font[glyph].components
    perms = permutations(components)
    for perm in perms:
        font[glyph].clearComponents()
        for comp in perm:
            font[glyph].components.append(comp)
        font.save()
        res = components_compatible(base_font, font, glyph)
        if res:
            print(f"{glyph}: Fixed component order")
            return
    print(f"{glyph}: Failed fixing component order")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "fonts", nargs="+", help="Source files. Either ufos of designspace."
    )
    args = parser.parse_args()

    sources = []
    for src in args.fonts:
        if src.endswith(".designspace"):
            ds = DesignSpaceDocument()
            ds.read(src)
            for s in ds.sources:
                if s in sources:
                    continue
                sources.append(s.path)
        else:
            sources.append(src)
    
    if len(sources) == 1:
        raise ValueError("Single source family! cannot check.")

    names = [os.path.basename(f) for f in sources[1:]]
    fonts = [Font.open(f) for f in sources[1:]]
    glyphsets = [f.reader.getGlyphSet() for f in fonts]
    base_font = fonts[0]
    fonts = fonts[1:]

    base_glyphset = glyphsets[0]
    glyphsets = glyphsets[1:]

    glyphs = base_font.reader.getGlyphSet().keys()
    for glyph in glyphs:
        # Check each font against the base font
        for idx, glyphset in enumerate(glyphsets):
            font = fonts[idx]
            res = test([base_glyphset, glyphset], glyphs=[glyph], names=names)
            points_compat = nodes_compatible(base_font, font, glyph)
            comps_compat = components_compatible(base_font, font, glyph)
            if all([not res, points_compat, comps_compat]):
                continue
            if not comps_compat:
                fix_component_order(base_font, font, glyph)
            if any(i["type"] == "contour_order" for i in res[glyph]):
                fix_contour_order([base_glyphset, glyphset], font, glyph, names)
            if not points_compat:
                fix_starting_points(
                    [base_glyphset, glyphset], base_font, font, glyph, names
                )
            if res:
                for issue in res[glyph]:
                    if issue["type"] in ["wrong_start_point", "node_incompatibility"]:
                        fix_starting_points(
                            [base_glyphset, glyphset], base_font, font, glyph, names
                        )
                    else:
                        print("Cannot fix")
                        print(issue)

    print("Done!")


if __name__ == "__main__":
    main()
