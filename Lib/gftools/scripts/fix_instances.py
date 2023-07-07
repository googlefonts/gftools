#!/usr/bin/env python3
from fontTools.ttLib import TTFont
from gftools.fix import fix_fvar_instances
from gftools.utils import parse_axis_dflts
import argparse


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("font", help="font file to fix")
    parser.add_argument(
        "-a", "--axis-defaults", default=None, help="Default values for non-wght axes"
    )
    parser.add_argument(
        "-i",
        "--inplace",
        default=False,
        action="store_true",
        help="overwrite existing font",
    )
    parser.add_argument("-o", "--out", default=None, help="output path")
    args = parser.parse_args(args)

    if args.axis_defaults:
        args.axis_defaults = parse_axis_dflts(args.axis_defaults)
    font = TTFont(args.font)
    fix_fvar_instances(font, axis_dflts=args.axis_defaults)
    if args.inplace:
        font.save(font.reader.file.name)
        return
    if args.out:
        font.save(args.out)
    else:
        font.save(font.reader.file.name + ".fix")


if __name__ == "__main__":
    main()
