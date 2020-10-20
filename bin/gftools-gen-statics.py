#!/usr/bin/env python3
"""
gftools gen-statics

Generate static fonts from a variable font using its STAT table.

Usage:

# All possible combinations in a variable font
gftools gen-statics varfont.ttf

# Only generate combinations using user supplied axis values
gftools gen-statics varfont.ttf --axis-values wght=300,400 wdth=75,100

# keep glyph overlaps
gftools gen-statics varfont.ttf --keep-overlaps

# Keep nametable
gftools gen-statics varfont.ttf --keep-nametable
"""
import argparse
import sys
from glob import glob
import shutil
import os
import re
from gftools.util.google_fonts import _KNOWN_WEIGHTS
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont, OverlapMode
from fontTools.ttLib import TTFont
from copy import copy
import logging


log = logging.getLogger(__name__)


# TODO import these constants from the fix module once it is merged
# https://github.com/googlefonts/gftools/pull/262
del _KNOWN_WEIGHTS["Hairline"]
GF_STYLES = list(_KNOWN_WEIGHTS.keys()) + [f"{s} Italic" for s in _KNOWN_WEIGHTS.keys()]
GF_STYLES += ["Italic"]


def update_gf_nametable_v1(nametable):
    # TODO Remove names
    family_name = nametable.getName(1, 3, 1, 0x409)
    typo_family_name = nametable.getName(16, 3, 1, 0x409)

    style_name = nametable.getName(2, 3, 1, 0x409)
    typo_style_name = nametable.getName(17, 3, 1, 0x409)

    ps_name = nametable.getName(6, 3, 1, 0x409)
    uniqueid_name = nametable.getName(3, 3, 1, 0x409)
    if not typo_family_name or not typo_style_name:
        # Since the subFamilyName is RIBBI, we don't need to do anything
        return

    name_ids = {}
    style_tokens = typo_style_name.toUnicode().split()
    sibling_family_name_tokens = " ".join(
        [t for t in style_tokens if t not in GF_STYLES]
    )
    style_name_tokens = (
        " ".join([t for t in style_tokens if t in GF_STYLES]) or "Regular"
    )
    new_typo_family_name = f"{typo_family_name} {sibling_family_name_tokens}".strip()
    new_typo_style_name = style_name_tokens.strip() or "Regular"

    name_ids[4] = f"{new_typo_family_name} {new_typo_style_name}"
    name_ids[
        6
    ] = f"{new_typo_family_name.replace(' ', '')}-{new_typo_style_name.replace(' ', '')}"
    name_ids[
        3
    ] = f"{uniqueid_name.toUnicode().replace(ps_name.toUnicode(), name_ids[6])}"

    # Remove existing typo names
    for i in (16, 17):
        nametable.removeNames(nameID=i)
    # only add new typo names if the typo family name isn't the same as
    # the family name
    if new_typo_family_name != family_name.toUnicode():
        name_ids[16] = new_typo_family_name
        name_ids[17] = new_typo_style_name

    for name_id, string in name_ids.items():
        nametable.setName(string, name_id, 3, 1, 0x409)


def update_fs_selection(ttfont):
    stylename = font_stylename(ttfont)
    fs_selection = ttfont["OS/2"].fsSelection

    # turn off all bits except for bit 7 (USE_TYPO_METRICS)
    fs_selection &= 0b10000000

    if "Italic" in stylename:
        fs_selection |= 0b1
    if stylename in ["Bold", "Bold Italic"]:
        fs_selection |= 0b100000
    # enable Regular bit for all other styles
    if stylename not in ["Bold", "Bold Italic"] and "Italic" not in stylename:
        fs_selection |= 0b1000000
    ttfont["OS/2"].fsSelection = fs_selection


def update_mac_style(ttfont):
    stylename = font_stylename(ttfont)
    mac_style = 0b0
    if "Italic" in stylename:
        mac_style |= 0b10
    if stylename in ["Bold", "Bold Italic"]:
        mac_style |= 0b1
    ttfont["head"].macStyle = mac_style


def font_stylename(ttfont):
    name = ttfont["name"]
    style_record = name.getName(2, 3, 1, 0x409) or name.getName(17, 3, 1, 0x409)
    if not style_record:
        raise ValueError(
            "Cannot find stylename since NameID 2 and NameID 16 are missing"
        )
    return style_record.toUnicode()


def get_font_axis_values(stat, fvar):
    axisRecords = stat.table.DesignAxisRecord.Axis
    axisOrder = {a.AxisTag: a.AxisOrdering for a in axisRecords}
    if not stat.table.AxisValueArray:
        raise ValueError("STAT table is missing Axis Value Tables")
    axisValues = stat.table.AxisValueArray.AxisValue
    axisTag = {a.AxisOrdering: a.AxisTag for a in axisRecords}
    res = {}
    fvarAxes = set(a.axisTag for a in fvar.axes)
    for axisValue in axisValues:

        if axisValue.Format == 4:
            for rec in axisValue.AxisValueRecord:
                axis_tag = axisTag[rec.AxisIndex]
                if axis_tag not in fvarAxes:
                    continue
                if axis_tag not in res:
                    res[axis_tag] = []
                res[axis_tag].append(rec.Value)
            continue

        axis_tag = axisTag[axisValue.AxisIndex]
        if axis_tag not in fvarAxes:
            continue

        if axisValue.Format in (1, 3):
            if axis_tag not in res:
                res[axis_tag] = []
            res[axis_tag].append(axisValue.Value)

        elif axisValue.Format == 2:
            if axis_tag not in res:
                res[axis_tag] = []
            res[axis_tag].append(axisValue.NominalValue)
    return res


def get_axis_combinations(axis_values, s=0, p={}, res=[]):
    # {"wght": [300, 400], "wdth": [75, 100]} -->
    # [{"wght": 300, "wdth": 75}, {"wght": 400, "wdth": 75} ...]
    # Instead of backtracking, using itertools may be better
    if s == len(axis_values):
        if p not in res:
            res.append(copy(p))
        return
    axes = list(axis_values.keys())
    axis = axes[s]
    for val in axis_values[axis]:
        p[axis] = val
        get_axis_combinations(axis_values, s + 1, p=p, res=res)
        if val in p:
            del p[val]
    return res


def populate_default_axis_values(fvar, axis_values):
    axis_defaults = {a.axisTag: a.defaultValue for a in fvar.axes}
    font_axes = set([a.axisTag for a in fvar.axes])
    missing_axes = set(font_axes) - set(axis_values)

    for axis in missing_axes:
        axis_values[axis] = [axis_defaults[axis]]
    return axis_values


def gen_statics(
    varfont, dst, axis_values=None, keep_overlaps=False, keep_nametable=True
):
    """Generate static fonts from a variable font using its STAT table."""
    if "STAT" not in varfont:
        raise ValueError("Cannot instantiate static fonts since there is no STAT table")
    if "fvar" not in varfont:
        raise ValueError("Font is not a variable font!")

    stat = varfont["STAT"]
    fvar = varfont["fvar"]

    if not axis_values:
        axis_values = get_font_axis_values(stat, fvar)
    axis_values = populate_default_axis_values(fvar, axis_values)
    axis_combinations = get_axis_combinations(axis_values)

    if not keep_overlaps:
        keep_overlaps = OverlapMode.REMOVE

    if len(axis_combinations) >= 25:
        log.warning(
            f"Warning: Generating {len(axis_combinations)} fonts. "
            "To generate less, use the --axis-values command."
        )
    for axis_combo in axis_combinations:
        static_font = instantiateVariableFont(
            varfont, axis_combo, overlap=keep_overlaps, updateFontNames=True
        )
        if not keep_nametable:
            update_gf_nametable_v1(static_font["name"])
        update_fs_selection(static_font)
        update_mac_style(static_font)
        filename = static_font["name"].getName(6, 3, 1, 0x409).toUnicode() + ".ttf"
        out = os.path.join(dst, filename)
        log.info(f"Saving {out}")
        static_font.save(out)


def parse_axis_values(string):
    # "wght=300,400 wdth=75,100" --> {"wght": [300, 400], "wdth": [75, 100]}
    res = {}
    for axis in string:
        try:
            k, v = axis.split("=")
            v = [int(i) for i in v.split(",")]
            res[k] = v
        except ValueError:
            raise ValueError(
                "Incorrect --axis-values input. Requires 'AXIS=val,val ...' "
                "e.g wght=300,400 wdth=75,100"
            )
    return res


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate static fonts from a variable font, "
            "using the variable font's STAT table."
        )
    )
    parser.add_argument("varfont", help="A variable font")
    parser.add_argument(
        "--axis-values",
        nargs="*",
        help=(
            "Axis values to generate e,g 'wght=300,400 wdth=75,100'. "
            "If this arg isn't included, all possible combinations "
            "within the font will be generated"
        ),
    )
    parser.add_argument(
        "--keep-overlaps",
        action="store_true",
        default=False,
        help="Do not remove glyph overlaps",
    )
    parser.add_argument(
        "--keep-nametable",
        action="store_true",
        default=False,
        help=("Do not update static font nametables. TODO explain"),
    )
    parser.add_argument("-o", "--out", default="out", help="output dir")
    args = parser.parse_args()

    varfont = TTFont(args.varfont)
    if not os.path.isdir(args.out):
        os.mkdir(args.out)
    axis_values = parse_axis_values(args.axis_values) if args.axis_values else None
    gen_statics(varfont, args.out, axis_values, args.keep_overlaps, args.keep_nametable)


if __name__ == "__main__":
    main()
