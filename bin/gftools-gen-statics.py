#!/usr/bin/env python3
"""
gftools gen-statics

Generate static fonts from a variable font.

Usage:

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



def gen_static_font(var_font, family_name, style_name, axes, keep_overlaps=True):
    """Generate a GF compliant static font from a variable font. Name table,
    fsSelection and macStyle bits will also be updated.

    Args:
        var_font: a variable TTFont instance
        family_name: desired static font family name
        style_name: desired static font style name
        axes: dictionary containing axis positions e.g {"wdth": 100, "wght": 400}
        keep_overlaps: If true do not remove glyph overlaps

    Returns:
        A TTFont instance or a filepath if an out path has been provided
    
    Usage:
        | >>> gen_static_font(var_font, "Open Sans", "Regular", {"wght": 400})
    """
    if "fvar" not in var_font:
        raise ValueError("Font is not a variable font!")
    if not keep_overlaps:
        keep_overlaps = OverlapMode.REMOVE
    static_font = instantiateVariableFont(var_font, axes, overlap=keep_overlaps)
    update_nametable(static_font, family_name, style_name)
    fix_fs_selection(static_font)
    fix_mac_style(static_font)
    return static_font


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
