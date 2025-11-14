#!/usr/bin/env python3
"""
gftools gen-spac

Add a Spacing axis (SPAC) to a variable font.
https://fonts.google.com/variablefonts#axis-definitions

Usage:
gftools gen-spac font.ttf --amount 100 --inplace
"""
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib import TTFont
from fontTools.varLib.hvar import add_HVAR
from fontTools.misc.cliTools import makeOutputFileName
from fontTools.ttLib.tables import otTables
import argparse


def add_spacing_axis(font, min_amount, max_amount):
    assert "fvar" in font, "Font must have an 'fvar' table"
    gvar = font["gvar"]
    for glyph_name in font.getGlyphOrder():
        glyph = font["glyf"][glyph_name]
        if not hasattr(glyph, "coordinates"):
            continue
        glyph_variations = gvar.variations.get(glyph_name)
        if not glyph_variations:
            continue
        min_coords = [None] * len(glyph_variations[0].coordinates)
        min_coords[-3] = (min_amount, 0)
        min_coords[-4] = (-min_amount, 0)
        min_tp = TupleVariation({"SPAC": (-1.0, -1.0, 0.0)}, min_coords)
        gvar.variations[glyph_name].append(min_tp)

        max_coords = [None] * len(glyph_variations[0].coordinates)
        max_coords[-3] = (max_amount, 0)
        max_coords[-4] = (-max_amount, 0)
        max_tp = TupleVariation({"SPAC": (0.0, 1.0, 1.0)}, max_coords)
        gvar.variations[glyph_name].append(max_tp)

    name_table = font["name"]

    axis = Axis()
    axis.axisTag = "SPAC"
    axis.axisNameID = name_table.addMultilingualName({"en": "Spacing"})
    axis.minValue = min_amount
    axis.defaultValue = 0.0
    axis.maxValue = max_amount

    fvar = font["fvar"]
    fvar.axes.append(axis)
    for inst in fvar.instances:
        inst.coordinates["SPAC"] = 0.0
    add_HVAR(font)

    print("Update various VarStores")
    stores = []
    for table in ("MVAR", "HVAR", "BASE", "VVAR", "COLR", "GDEF"):
        if table in font and hasattr(font[table].table, "VarStore"):
            stores.append(font[table].table.VarStore)
    spacRegion = otTables.VarRegionAxis()
    spacRegion.StartCoord = -1
    spacRegion.PeakCoord = 0
    spacRegion.EndCoord = 1
    for store in stores:
        store.VarRegionList.RegionAxisCount = len(fvar.axes)
        for region in store.VarRegionList.Region:
            while len(region.VarRegionAxis) < len(fvar.axes):
                region.VarRegionAxis.append(spacRegion)


def main(args=None):
    parser = argparse.ArgumentParser(description="Add a SPAC axis to a variable font.")
    parser.add_argument(
        "font", type=TTFont, help="Path to the variable font file to modify."
    )
    parser.add_argument(
        "min",
        type=int,
        help="Min amount of spacing to add",
    )
    parser.add_argument(
        "max",
        type=int,
        help="Max amount of spacing to add",
    )
    out_group = parser.add_mutually_exclusive_group(required=False)
    out_group.add_argument("--out", "-o", help="Output dir for fonts")
    out_group.add_argument(
        "--inplace", action="store_true", default=False, help="Overwrite input files"
    )
    args = parser.parse_args(args)

    add_spacing_axis(args.font, args.min, args.max)
    if args.inplace:
        output_path = args.font.reader.file.name
    elif args.out:
        output_path = args.out
    else:
        output_path = makeOutputFileName(args.font.reader.file.name)
    args.font.save(output_path)


if __name__ == "__main__":
    main()
