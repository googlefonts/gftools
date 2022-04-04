import argparse
import sys
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables.otTables import ClassDef
from fontTools.misc.roundTools import otRound



SCALEABLE_ATTRIBS = {
    "XAdvance",
    "YAdvance",
    "XPlacement",
    "YPlacement",
    "XAdvance",
    "YAdvance",
    "variations",
    "OS/2",
    "xMin",
    "minRightSideBearing",
    "xMax",
    "loca",
    "GPOS",
    "minLeftSideBearing",
    "ascent",
    "yStrikeoutPosition",
    "ySuperscriptYOffset",
    "instances",
    "sCapHeight",
    "xMaxExtent",
    "ySubscriptXSize",
    "hhea",
    "usWinAscent",
    "unitsPerEm",
    "descent",
    "usWinDescent",
    "checkSumAdjustment",
    "GDEF",
    "modified",
    "gvar",
    "xAvgCharWidth",
    "name",
    "head",
    "panose",
    "hmtx",
    "sTypoDescender",
    "fvar",
    "sxHeight",
    "HVAR",
    "yMax",
    "names",
    "ySuperscriptXSize",
    "metrics",
    "ySubscriptYOffset",
    "glyf",
    "coordinates",
    "ySuperscriptYSize",
    "ySubscriptYSize",
    "font",
    "sTypoAscender",
    "locations",
    "glyphs",
    "advanceWidthMax",
    "yMin",
}


def scale_font(ttFont, ratio):
    glyph_names = set(ttFont.getGlyphNames())
    return _scale(ttFont, ratio, glyph_names)


def _scale(obj, inc, glyph_names=None, apply=False):
    if isinstance(obj, (int, float)):
        if apply:
            return otRound(obj * inc)
        return obj
    if isinstance(obj, str):
        return obj

    # Only scale necessary tables. TODO add mor
    if isinstance(obj, TTFont):
        for k in obj.keys():
            if k not in ["hmtx", "glyf", "OS/2", "hhea", "head", "gvar", "GPOS", "HVAR"]:
                continue
            obj[k] = _scale(obj[k], inc, glyph_names, apply)

    # process glyph and gvar objects manually since they are a pita
    elif isinstance(obj, Glyph):
        if hasattr(obj, "coordinates"):
            obj.coordinates.scale((inc, inc))
        if hasattr(obj, "components"):
            for comp in obj.components:
                comp.x *= inc
                comp.y *= inc
    elif isinstance(obj, TupleVariation):
        if hasattr(obj, "coordinates"):
#            obj.coordinates = [tuple(j * inc for j in i) for i in obj.coordinates if i]
            for i in range(len(obj.coordinates)):
                if not obj.coordinates[i]:
                    continue
                obj.coordinates[i] = tuple(int(j * inc) for j in obj.coordinates[i])

    # TODO work our why we can't just ignore this
    elif isinstance(obj, ClassDef):
        return obj

    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in SCALEABLE_ATTRIBS or k in glyph_names:
                apply = True
            obj[k] = _scale(v, inc, glyph_names, apply)
            if apply:
                apply = False
    elif isinstance(obj, list):
        for i in range(len(obj)):
            obj[i] = _scale(obj[i], inc, glyph_names, apply)
    elif isinstance(obj, tuple):
        obj = tuple(_scale(i, inc, glyph_names, apply) for i in obj)
    elif isinstance(obj, set):
        obj = set([_scale(i, inc, glyph_names, apply) for i in obj])

    # scale class attributes
    elif hasattr(obj, "__dict__"):
        for k in vars(obj):
            if k in SCALEABLE_ATTRIBS or k in glyph_names:
                apply = True
            o = getattr(obj, k)
            setattr(obj, k, _scale(o, inc, glyph_names, apply))
            if apply:
                apply = False
    return obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("font")
    parser.add_argument("ratio", type=int)
    parser.add_argument("out")
    args = parser.parse_args()

    ttfont = TTFont(args.font)
    for g in ttfont['glyf'].keys():
        ttfont['glyf'][g]
    
    scale_font(ttfont, args.ratio)
    ttfont.save(args.out)


if __name__ == "__main__":
    main()