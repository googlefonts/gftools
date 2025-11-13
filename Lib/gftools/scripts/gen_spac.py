#!/usr/bin/env python3
"""
gftools add-spac

Add a Spacing axis (SPAC) to a variable font.
https://fonts.google.com/variablefonts#axis-definitions

Usage:
gftools add-spac font.ttf --amount 100 --inplace
"""
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib import TTFont
from fontTools.varLib.hvar import add_HVAR
from fontTools.misc.cliTools import makeOutputFileName
import argparse


def add_space_axis(font, amount):
    # Current implementation can only add positive SPAC values
    assert "fvar" in font, "Font must have an 'fvar' table"
    gvar = font["gvar"]
    for glyph_name in font.getGlyphOrder():
        glyph = font["glyf"][glyph_name]
        if not hasattr(glyph, "coordinates"):
            continue
        glyph_variations = gvar.variations.get(glyph_name)
        if not glyph_variations:
            continue
        coords = [None] * len(glyph_variations[0].coordinates)
        coords[0] = (amount, 0)
        coords[-3] = (amount*2, 0)
        for idx in glyph.endPtsOfContours[:-1]:
            coords[idx + 1] = (amount, 0)
        tp = TupleVariation(
            {"SPAC": (0.0, 1.0, 1.0)},
            coords
        )
        gvar.variations[glyph_name].append(tp)

    name_table = font["name"]

    axis = Axis()
    axis.axisTag = "SPAC"
    axis.axisNameID = name_table.addMultilingualName({"en": "Spacing"})
    axis.minValue = 0.0
    axis.defaultValue = 0.0
    axis.maxValue = amount

    fvar = font["fvar"]
    fvar.axes.append(axis)
    for inst in fvar.instances:
        inst.coordinates["SPAC"] = 0.0
    add_HVAR(font)


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Add a SPAC axis to a variable font."
    )
    parser.add_argument(
        "font",
        type=TTFont,
        help="Path to the variable font file to modify."
    )
    parser.add_argument(
        "--amount",
        type=int,
        default=100,
        help="Amount of spacing to add (default: 100)."
    )
    out_group = parser.add_mutually_exclusive_group(required=False)
    out_group.add_argument("--out", "-o", help="Output dir for fonts")
    out_group.add_argument(
        "--inplace", action="store_true", default=False, help="Overwrite input files"
    )
    args = parser.parse_args(args)

    add_space_axis(args.font, args.amount)
    if args.inplace:
        output_path = args.font.reader.file.name
    elif args.out:
        output_path = args.out
    else:
        output_path = makeOutputFileName(
            args.font.reader.file.name
        )
    args.font.save(output_path)


if __name__ == "__main__":
    main()