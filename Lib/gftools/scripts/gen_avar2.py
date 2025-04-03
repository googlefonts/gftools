"""
gftools gen-avar2

Generate an avar2 table for each font in a variable font family
from a yaml file.
```
MavenPro[wght].ttf:
- in:
    wght: 400.0
  out:
    wght: 400.0
- in:
    wght: 900.0
  out:
    wght: 900.0
```
"""

import argparse
import os
from collections import OrderedDict
from fontTools.ttLib import TTFont
from fontTools.varLib import _add_avar
from fontTools.designspaceLib import AxisMappingDescriptor, AxisDescriptor
import yaml
from fontTools.varLib.avar import _denormalize


def gen_avar2_mapping(font, mapping):
    axisTags = [axis.axisTag for axis in font["fvar"].axes]
    axis_tag_to_name = {}
    nametable = font["name"]
    axes = OrderedDict()
    for axis in font["fvar"].axes:
        axis_name = nametable.getName(axis.axisNameID, 3, 1, 0x409).toUnicode()
        axis_tag_to_name[axis.axisTag] = axis_name
        axis_map = [
            (_denormalize(k, axis), _denormalize(v, axis))
            for k, v in font["avar"].segments[axis.axisTag].items()
        ]
        axis_map = list(sorted(set(axis_map)))
        axes[axis_name] = AxisDescriptor(
            tag=axis.axisTag,
            name=axis_name,
            minimum=axis.minValue,
            maximum=axis.maxValue,
            default=axis.defaultValue,
            map=axis_map,
            axisOrdering=None,
            axisLabels=[],
        )

    mapping = [
        AxisMappingDescriptor(
            inputLocation={axis_tag_to_name[k]: v for k, v in m["in"].items()},
            outputLocation={axis_tag_to_name[k]: v for k, v in m["out"].items()},
        )
        for m in mapping
    ]

    if "avar" in font:
        del font["avar"]
    _add_avar(font, axes, mapping, axisTags)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "fonts", nargs="+", help="Variable TTF files which make up a family"
    )
    parser.add_argument("src", help="use yaml file to build STAT", default=None)
    out_group = parser.add_mutually_exclusive_group(required=True)
    out_group.add_argument("--out", "-o", help="Output dir for fonts")
    out_group.add_argument(
        "--inplace", action="store_true", default=False, help="Overwrite input files"
    )
    args = parser.parse_args()

    fonts = [TTFont(f) for f in args.fonts]
    config = yaml.load(open(args.src), Loader=yaml.SafeLoader)
    for font in fonts:
        filename = os.path.basename(font.reader.file.name)
        gen_avar2_mapping(font, config[filename])

    if args.inplace:
        for font in fonts:
            font.save(font.reader.file.name)
    elif args.out:
        if not os.path.isdir(args.out):
            os.mkdir(args.out)
        for font in fonts:
            font.save(os.path.join(args.out, os.path.basename(font.reader.file.name)))


if __name__ == "__main__":
    main()
