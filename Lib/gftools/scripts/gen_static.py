#!/usr/bin/env python3
"""Generate a static font from a variable font.

The family name and style name are used to build a new name table which
complies with Microsoft's RIBBI naming convention. The style name must
match a named fvar instance in the variable font, unless axis positions
are provided with --coordinates.

Usage:

gftools gen-static font[wght].ttf "My Family" "SemiBold" -o font-SemiBold.ttf

gftools gen-static font[wght].ttf "My Family" "Regular" --coordinates wght=450
"""

import argparse
import os

from fontTools.ttLib import TTFont

from gftools.instancer import gen_static_font


def parse_coordinates(coordinates):
    res = {}
    for coord in coordinates:
        try:
            axis, value = coord.split("=")
            res[axis] = float(value)
        except ValueError:
            raise ValueError(
                f"Cannot parse coordinate '{coord}'. Coordinates must "
                "have the format AXIS=VALUE e.g wght=400"
            )
    return res


def instance_coordinates(font, style_name):
    nametable = font["name"]
    instances = {
        nametable.getDebugName(inst.subfamilyNameID): inst.coordinates
        for inst in font["fvar"].instances
    }
    if style_name not in instances:
        raise ValueError(
            f"Font has no fvar instance named '{style_name}'. Available "
            f"instances: {', '.join(instances)}. Alternatively, provide "
            "axis positions with --coordinates."
        )
    return dict(instances[style_name])


def main(args=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("font", help="path to variable font")
    parser.add_argument("family_name", help="static font family name")
    parser.add_argument("style_name", help="static font style name")
    parser.add_argument(
        "-o",
        "--out",
        help="output path. Defaults to FamilyName-StyleName.ttf",
    )
    parser.add_argument(
        "--coordinates",
        nargs="+",
        metavar="AXIS=VALUE",
        help="axis positions for the instance. If not provided, the "
        "coordinates are taken from the fvar instance which matches "
        "the style name",
    )
    parser.add_argument(
        "--keep-overlaps", action="store_true", help="do not remove glyph overlaps"
    )
    args = parser.parse_args(args)

    font = TTFont(args.font)
    if "fvar" not in font:
        raise ValueError(f"'{args.font}' is not a variable font")

    if args.coordinates:
        coordinates = parse_coordinates(args.coordinates)
    else:
        coordinates = instance_coordinates(font, args.style_name)

    out = args.out or "{}-{}.ttf".format(
        args.family_name.replace(" ", ""), args.style_name.replace(" ", "")
    )
    out_dir = os.path.dirname(out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    gen_static_font(
        font,
        coordinates,
        family_name=args.family_name,
        style_name=args.style_name,
        keep_overlaps=args.keep_overlaps,
        dst=out,
    )
    print(f"Saved static font '{out}'")


if __name__ == "__main__":
    main()
