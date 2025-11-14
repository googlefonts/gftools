#!/usr/bin/env python3
"""
Convert a font with an avar2 table to avar1.
This tool was specifically written for Crispy. It will only generate masters
for the corners of the designspace, hence why we're only doing the cart
product of min/max axis values.

A yaml based mapping file can be provided to add avar1 mappings. It has the
following format:

`
wght:
  400: 380
  500: 520
  700: 700
wdth:
  ...
`

I don't think we're going to use this tool often so we'll extend its
functionality when we need it.

Usage:
# default
gftools to-avar1 path/to/variable-font.ttf

# with custom avar1 mapping and outpath
gftools to-avar1 path/to/variable-font.ttf --mapping path/to/mapping.yaml -o path/to/avar1-font.ttf
"""
from fontTools.misc.cliTools import makeOutputFileName
from fontTools.designspaceLib import (
    DesignSpaceDocument,
    SourceDescriptor,
    InstanceDescriptor,
    AxisDescriptor,
)
from fontTools.ttLib import TTFont
import itertools
from fontTools.varLib import instancer
from fontTools.varLib import main as gen_vf
import tempfile
import argparse
import yaml


def avar2_to_avar1(ttfont, avar_mapping, out):
    if "fvar" not in ttfont:
        raise ValueError("Not a variable font")

    fvar = ttfont["fvar"]
    name = ttfont["name"]
    axes = [(a.minValue, (a.minValue + a.maxValue) / 2, a.maxValue) for a in fvar.axes]
    axis_order = [a.axisTag for a in fvar.axes]
    axis_names = [
        name.getName(a.axisNameID, 3, 1, 0x409).toUnicode() for a in fvar.axes
    ]

    ds = DesignSpaceDocument()
    for axis, real_name, tag_name in zip(axes, axis_names, axis_order):
        ax = AxisDescriptor()
        ax.name = real_name
        ax.tag = tag_name
        ax.minimum = axis[0]
        ax.maximum = axis[2]
        ax.default = axis[0]
        if avar_mapping:
            ax.map = [(k, v) for k, v in avar_mapping.get(tag_name, {}).items()]
        ds.axes.append(ax)

    total = len(list(itertools.product(*axes)))
    print("Generating masters...", total)
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, combo in enumerate(itertools.product(*axes)):
            print(f"  Master {idx+1}/{total}")
            source = SourceDescriptor()
            source.name = "_".join(f"{axis_order[i]}-{v}" for i, v in enumerate(combo))
            source.familyName = ttfont["name"].getBestFamilyName()
            source.filename = f"{tmpdir}/{source.name}.ttf"
            source.location = {axis_names[i]: v for i, v in enumerate(combo)}
            ds.sources.append(source)
            coords = {axis_order[i]: v for i, v in enumerate(combo)}
            partial = instancer.instantiateVariableFont(ttfont, coords)
            partial.save(source.filename)

        for fvar_inst in ttfont["fvar"].instances:
            new_inst = InstanceDescriptor()
            new_inst.name = name.getName(
                fvar_inst.subfamilyNameID, 3, 1, 0x409
            ).toUnicode()
            new_inst.familyName = ttfont["name"].getBestFamilyName()
            new_inst.styleName = new_inst.name
            new_inst.location = {
                axis_names[i]: fvar_inst.coordinates[axis_order[i]]
                for i in range(len(axis_order))
            }
            ds.instances.append(new_inst)

        ds.write(tmpdir + "/out.designspace")
        gen_vf([tmpdir + "/out.designspace", "-o", out])


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Generate avar1.ttf from a variable font."
    )
    parser.add_argument("font_path", help="Path to the variable font file")
    parser.add_argument("-m", "--mapping", help="Path to avar1 yaml mapping")
    parser.add_argument("-o", "--out")
    parser.add_argument(
        "--test-output", help="output a html testing doc to compare fonts"
    )
    args = parser.parse_args(args)

    ttfont = TTFont(args.font_path)

    if args.mapping:
        with open(args.mapping, "r", encoding="utf-8") as f:
            avar_mapping = yaml.safe_load(f)
    else:
        avar_mapping = None

    out = None
    if args.out:
        out = args.out
    else:
        fp = makeOutputFileName(
            args.font_path, outputDir=None, extension=None, overWrite=False
        )
        out = fp.replace(".ttf", "_avar1.ttf")
    avar2_to_avar1(ttfont, avar_mapping, out)


if __name__ == "__main__":
    main()
