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
from axisregistry import AxisRegistry
from fontTools.ttLib import TTFont
from gftools.stat import gen_stat_tables, gen_stat_tables_from_config
import argparse
import yaml
import os

axis_registry = AxisRegistry()


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "fonts", nargs="+", help="Variable TTF files which make up a family"
    )
    parser.add_argument("--src", help="use yaml file to build STAT", default=None)
    parser.add_argument("--out", "-o", help="Output dir for fonts")
    parser.add_argument(
        "--inplace", action="store_true", default=False, help="Overwrite input files"
    )
    args = parser.parse_args(args)

    fonts = [TTFont(f) for f in args.fonts]

    if args.src:
        config = yaml.load(open(args.src), Loader=yaml.SafeLoader)
        gen_stat_tables_from_config(config, fonts)
    else:
        gen_stat_tables(fonts)

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
