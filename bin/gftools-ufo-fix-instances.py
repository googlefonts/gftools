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
import sys


def build_instances(ds):
    """Generate Designspace instances which are gf spec complaint"""
    instances = []
    axes = ds.axes
    wght_axis = next((a for a in axes if a.tag == "wght"), None)
    wght_vals = list(range(int(wght_axis.minimum), int(wght_axis.maximum + 100), 100))
    italic_axis = next((a for a in axes if a.tag in ["slnt", "ital"]), None)
    for wght in wght_vals:
        inst = InstanceDescriptor()
        coords = {a.tag: a.default for a in axes}
        coords["wght"] = float(wght)
        inst.location = coords
        inst.styleName = WEIGHT_VALUES[wght]
        instances.append(inst)

    if italic_axis:
        italics = deepcopy(instances)
        for inst in italics:
            inst.styleName = f"{inst.styleName} Italic".replace(
                "Regular Italic", "Italic"
            )
            inst.location[italic_axis.tag] = italic_axis.minimum
        instances += italics
    return instances


def main():
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
