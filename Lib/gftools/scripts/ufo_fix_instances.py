#!/usr/bin/env python3
"""
Fix designspace instances so they are gf spec complaint:
https://github.com/googlefonts/gf-docs/tree/main/Spec#fvar-instances

Usage:

gftools ufo-fix-instances family.designspace
"""
from fontTools.designspaceLib import DesignSpaceDocument, InstanceDescriptor
from copy import deepcopy
from gftools.fix import WEIGHT_VALUES
from axisregistry import AxisRegistry
import sys

axis_reg = AxisRegistry()


def build_instances(ds):
    """Generate Designspace instances which are gf spec complaint"""
    instances = []
    axes = ds.axes
    wght_axis = next((a for a in axes if a.tag == "wght"), None)
    wght_vals = list(range(int(wght_axis.minimum), int(wght_axis.maximum + 100), 100))
    italic_axis = next((a for a in axes if a.tag in ["slnt", "ital"]), None)

    dflt_coords = {}
    for axis in axes:
        if axis.tag not in axis_reg or (
            axis_reg[axis.tag].default_value < axis.minimum
            or axis_reg[axis.tag].default_value > axis.maximum
        ):
            dflt_coords[axis.tag] = axis.map_forward(axis.default)
        else:
            dflt_coords[axis.tag] = axis.map_forward(axis_reg[axis.tag].default_value)

    for wght in wght_vals:
        inst = InstanceDescriptor()
        coords = deepcopy(dflt_coords)
        coords["wght"] = wght_axis.map_forward(wght)
        inst.location = coords
        inst.styleName = WEIGHT_VALUES[wght]
        instances.append(inst)

    if italic_axis:
        italics = deepcopy(instances)
        for inst in italics:
            inst.styleName = f"{inst.styleName} Italic".replace(
                "Regular Italic", "Italic"
            )
            inst.location[italic_axis.tag] = italic_axis.map_forward(
                italic_axis.minimum
            )
        instances += italics
    return instances


def main(args=None):
    if len(sys.argv) != 2:
        print(__doc__)
        return
    ds_path = sys.argv[1]
    ds = DesignSpaceDocument()
    ds.read(ds_path)
    instances = build_instances(ds)
    ds.instances = instances
    ds.write(ds_path)


if __name__ == "__main__":
    main()
