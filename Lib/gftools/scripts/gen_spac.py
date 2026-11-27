#!/usr/bin/env python3
"""
gftools gen-spac

Add a Spacing axis (SPAC) to a variable font.
https://fonts.google.com/variablefonts#axis-definitions

Usage:
gftools gen-spac font.ttf --amount 100 --inplace
"""

import argparse

from fontTools.misc.cliTools import makeOutputFileName
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.varLib.hvar import add_HVAR

ELIDABLE_AXIS_VALUE_NAME = 0x0002


def add_spacing_axis(
    font: TTFont,
    min_amount: int,
    max_amount: int,
    *,
    min_user: int | None = None,
    max_user: int | None = None,
) -> None:
    assert "fvar" in font, "Font must have an 'fvar' table"
    gvar = font["gvar"]
    glyf = font["glyf"]
    for glyph_name in font.getGlyphOrder():
        glyph = glyf[glyph_name]
        # Every glyph gets spacing, including empty glyphs such as space and
        # composites such as Aacute. Neither has outline coordinates, and an
        # empty glyph may have no gvar tuples at all, so size the tuple from
        # the glyph itself: one entry per point or component, plus the four
        # phantom points.
        if glyph.isComposite():
            num_points = len(glyph.components)
        elif glyph.numberOfContours > 0:
            num_points = len(glyph.coordinates)
        else:
            num_points = 0
        num_points += 4
        glyph_variations = gvar.variations.setdefault(glyph_name, [])

        # The last four entries are the phantom points. Moving the left one
        # (-4) outward and the right one (-3) outward adds the amount to each
        # side bearing.
        min_coords: list[tuple[int, int] | None] = [None] * num_points
        min_coords[-3] = (min_amount, 0)
        min_coords[-4] = (-min_amount, 0)
        glyph_variations.append(TupleVariation({"SPAC": (-1.0, -1.0, 0.0)}, min_coords))

        max_coords: list[tuple[int, int] | None] = [None] * num_points
        max_coords[-3] = (max_amount, 0)
        max_coords[-4] = (-max_amount, 0)
        glyph_variations.append(TupleVariation({"SPAC": (0.0, 1.0, 1.0)}, max_coords))

    name_table = font["name"]

    axis = Axis()
    axis.axisTag = "SPAC"
    axis.axisNameID = name_table.addMultilingualName({"en": "Spacing"})
    axis.minValue = min_user if min_user is not None else min_amount
    axis.defaultValue = 0.0
    axis.maxValue = max_user if max_user is not None else max_amount

    fvar = font["fvar"]
    fvar.axes.append(axis)
    for inst in fvar.instances:
        inst.coordinates["SPAC"] = 0.0
    add_HVAR(font)

    if "STAT" in font:
        add_spacing_axis_to_STAT(font, axis.axisNameID)
    else:
        print("Font has no STAT table, so SPAC was not added to it")

    if "avar" in font:
        # avar must list every fvar axis. CoreText rejects the whole variation
        # when the counts differ, so give SPAC an identity segment map.
        avar = font["avar"]
        avar.segments["SPAC"] = {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0}

    print("Update various VarStores")
    stores = []
    for table in ("MVAR", "HVAR", "BASE", "VVAR", "COLR", "GDEF"):
        if table in font and hasattr(font[table].table, "VarStore"):
            stores.append(font[table].table.VarStore)
    if "avar" in font and getattr(font["avar"].table, "VarStore", None):
        stores.append(font["avar"].table.VarStore)
    spacRegion = otTables.VarRegionAxis()
    spacRegion.StartCoord = -1
    spacRegion.PeakCoord = 0
    spacRegion.EndCoord = 1
    for store in stores:
        store.VarRegionList.RegionAxisCount = len(fvar.axes)
        for region in store.VarRegionList.Region:
            while len(region.VarRegionAxis) < len(fvar.axes):
                region.VarRegionAxis.append(spacRegion)


def add_spacing_axis_to_STAT(font: TTFont, axis_name_id: int) -> None:
    """Add a SPAC axis record to STAT with one axis value, "Default", at 0.0."""
    stat = font["STAT"].table
    name_table = font["name"]

    axis_record = otTables.AxisRecord()
    axis_record.AxisTag = "SPAC"
    axis_record.AxisNameID = axis_name_id
    axis_record.AxisOrdering = len(stat.DesignAxisRecord.Axis)
    stat.DesignAxisRecord.Axis.append(axis_record)
    stat.DesignAxisCount = len(stat.DesignAxisRecord.Axis)

    axis_value = otTables.AxisValue()
    axis_value.Format = 1
    axis_value.AxisIndex = axis_record.AxisOrdering
    # The default value is elidable, so it does not appear in style names.
    axis_value.Flags = ELIDABLE_AXIS_VALUE_NAME
    axis_value.ValueNameID = name_table.addMultilingualName({"en": "Default"})
    axis_value.Value = 0.0
    if stat.AxisValueArray is None:
        stat.AxisValueArray = otTables.AxisValueArray()
        stat.AxisValueArray.AxisValue = []
    stat.AxisValueArray.AxisValue.append(axis_value)
    stat.AxisValueCount = len(stat.AxisValueArray.AxisValue)


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
    parser.add_argument(
        "--user-min",
        type=int,
        help="The user-exposed axis minimum (default: same as min)",
    )
    parser.add_argument(
        "--user-max",
        type=int,
        help="The user-exposed axis maximum (default: same as max)",
    )
    out_group = parser.add_mutually_exclusive_group(required=False)
    out_group.add_argument("--out", "-o", help="Output dir for fonts")
    out_group.add_argument(
        "--inplace", action="store_true", default=False, help="Overwrite input files"
    )
    args = parser.parse_args(args)

    add_spacing_axis(
        args.font, args.min, args.max, min_user=args.user_min, max_user=args.user_max
    )
    if args.inplace:
        output_path = args.font.reader.file.name
    elif args.out:
        output_path = args.out
    else:
        output_path = makeOutputFileName(args.font.reader.file.name)
    args.font.save(output_path)


if __name__ == "__main__":
    main()
