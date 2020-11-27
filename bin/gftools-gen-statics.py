#!/usr/bin/env python3
"""
gftools gen-statics

Generate static fonts from a variable font.

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
import os
import logging
import csv
from gftools.fix import update_nametable, fix_fs_selection, fix_mac_style
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont, OverlapMode
from fontTools.ttLib import TTFont


log = logging.getLogger(__name__)


def _get_font_axis_values(stat, fvar):
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


def _get_axis_combinations(axis_values, s=0, p={}, res=[]):
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


def instances_from_cross_product(var_font):
    axis_values = _get_font_axis_values(var_font)
    return _get_axis_combinations(axis_values, 0, {}, [])


def gen_static_font(var_font, family_name, style_name, axes, keep_overlaps=True):
    if "fvar" not in var_font:
        raise ValueError("Font is not a variable font!")
    if not keep_overlaps:
        keep_overlaps = OverlapMode.REMOVE
    static_font = instantiateVariableFont(var_font, axes, overlap=keep_overlaps)
    update_nametable(static_font, family_name, style_name)
    fix_fs_selection(static_font)
    fix_mac_style(static_font)
    return static_font


def instances_from_csv(csv_doc):
    fieldnames = ["src", "familyname", "stylename"]
    if not set(fieldnames).issubset(set(csv_doc.fieldnames)):
        missing_fields = set(fieldnames) - set(csv_doc.fieldnames)
        raise ValueError(
            f"csv must have the following fieldnames {fieldnames}. Missing "
            f"from file {list(missing_fields)}"
        )
    results = []
    axes_fieldnames = [f for f in csv_doc.fieldnames if f not in fieldnames]
    for row in csv_doc:
        new_row = {f: row[f] for f in fieldnames}
        new_row["coordinates"] = {f: float(row[f]) for f in axes_fieldnames}
        results.append(new_row)
    return results


def parse_instances(path=None):
    if path.endswith(".csv"):
        with open(path) as csv_file:
            csv_doc = csv.DictReader(csv_file, delimiter=",")
            instances = instances_from_csv(csv_doc)
    elif path.endswith(".designspace"):
        raise NotImplementedError("Instances from designspace not implemented yet")
    #        instances = instances_from_designspace()
    elif path is not None:
        raise NotImplementedError(
            f"Cannot parse {path}. Instances input must be either a designspace "
            "file or a csv"
        )
    else:
        instances = instances_from_cross_product(varfont)
        if len(instances) >= 50:
            raise ValueError(
                f"There are {len(instances)} possible instances. We can only "
                "generate up to 50"
            )
    return instances


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate static fonts from a variable font, "
            "using the variable font's STAT table."
        )
    )
    parser.add_argument("varfonts", nargs="+", help="A variable font")
    parser.add_argument(
        "--keep-overlaps",
        action="store_true",
        default=False,
        help="Do not remove glyph overlaps",
    )
    parser.add_argument(
        "--instance-file", "-i", default=None, help="Instances source file"
    )
    parser.add_argument("-o", "--out", default="out", help="output dir")
    args = parser.parse_args()

    varfonts = {os.path.basename(f): TTFont(f) for f in args.varfonts}
    instances = parse_instances(args.instance_file)

    if not os.path.isdir(args.out):
        os.mkdir(args.out)

    for instance in instances:
        if instance["src"] not in varfonts:
            raise ValueError(
                f"csv specifies '{instance['src']}' which is not in the "
                "supplied fonts {args.varfonts}"
            )
        varfont = varfonts[instance["src"]]
        static_font = gen_static_font(
            varfont,
            instance["familyname"],
            instance["stylename"],
            instance["coordinates"],
            args.keep_overlaps,
        )
        filename = f"{instance['familyname']}-{instance['stylename']}.ttf".replace(
            " ", ""
        )
        print(f"Saving {filename}")
        static_font.save(os.path.join(args.out, filename))


if __name__ == "__main__":
    main()
