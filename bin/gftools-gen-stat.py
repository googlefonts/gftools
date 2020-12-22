#!/usr/bin/env python3
"""
gftools gen-stat

Generate a STAT table for each font in a variable font family
using the GF axis registry. Alternatively, users can generate
STAT tables from a yaml file which has the following structure:

```
Lora[wght].ttf:
- name: Weight
  tag: wght
  values:
  - name: Regular
    value: 400
    ...
- name: Width
  tag: wdth
  values:
  ...

Lora-Italic[wght].ttf
...
```

Usage:

# Standard usage. Fonts will have ".fix" appended to their filenames
gftools gen-stat font1.ttf --axis-order wdth wght

# Output fonts to a dir
gftools gen-stat font1.ttf font2.ttf --axis-order wdth wght --out ~/Desktop/out

# Overwrite input fonts
gftools gen-stat font1.ttf font2.ttf --axis-order wdth wght --inplace

# Overide which axis values are elided
gftools gen-stat font.ttf --elided-values wght=400 --axis-order wdth wght

# Generate stats from a file
gftools gen-stat font.ttf --src my_stat.yaml

"""
from fontTools.ttLib import TTFont
from gftools.stat import gen_stat_tables, gen_stat_tables_from_config
from gftools.axisreg import axis_registry
import argparse
import yaml
import os


def parse_elided_values(string):
    # "wght=300,400 wdth=75,100" --> {"wght": [300, 400], "wdth": [75, 100]}
    res = {}
    for axis in string:
        try:
            k, v = axis.split("=")
            v = [int(i) for i in v.split(",")]
            res[k] = v
        except ValueError:
            raise ValueError(
                "Incorrect --elided-values input. Requires 'AXIS=val,val ...' "
                "e.g 'wght=400 wdth=100'"
            )
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "fonts", nargs="+", help="Variable TTF files which make up a family"
    )
    parser.add_argument("--src", help="use yaml file to build STAT", default=None)
    parser.add_argument(
        "--axis-order",
        nargs="+",
        required=False,
        choices=axis_registry.keys(),
        help="List of space seperated axis tags used to set the STAT table "
        "axis order e.g --axis-order wdth wght ital",
    )
    parser.add_argument(
        "--elided-values",
        nargs="+",
        default=None,
        help="List of space seperated axis_values to elide. "
        "Input must be structed as axis_tag=int,int..."
        "e.g --elided-values wdth=100 wght=400",
    )
    parser.add_argument("--out", "-o", help="Output dir for fonts")
    parser.add_argument(
        "--inplace", action="store_true", default=False, help="Overwrite input files"
    )
    args = parser.parse_args()

    fonts = [TTFont(f) for f in args.fonts]

    if args.src:
        config = yaml.load(open(args.src), Loader=yaml.SafeLoader)
        gen_stat_tables_from_config(config, fonts)
    else:
        if not args.axis_order:
            raise ValueError("axis-order arg is missing")
        elided_values = (
            parse_elided_values(args.elided_values) if args.elided_values else None
        )
        gen_stat_tables(fonts, args.axis_order, elided_values)

    if args.out:
        if not os.path.isdir(args.out):
            os.mkdir(args.out)

    for font in fonts:
        if args.out:
            dst = os.path.join(args.out, os.path.basename(font.reader.file.name))
        elif args.inplace:
            dst = font.reader.file.name
        else:
            dst = font.reader.file.name + ".fix"
        if os.path.isfile(dst):
            os.remove(dst)
        print(f"Saving font to {dst}")
        font.save(dst)


if __name__ == "__main__":
    main()
