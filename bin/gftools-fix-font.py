#!/usr/bin/env python3
"""
gftools fix-font

Update a font so it conforms to the Google Fonts specification
https://github.com/googlefonts/gf-docs/tree/master/Spec

Usage:

gftools fix-font font.ttf

# Fix font issues that should be fixed in the source files
gftools fix-font font.ttf --include-source-fixes
"""
import argparse
import logging
from fontTools.ttLib import TTFont
from gftools.fix import *


log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("font", help="Path to font")
    parser.add_argument("-o", "--out", help="Output path for fixed font")
    parser.add_argument(
        "--include-source-fixes",
        action="store_true",
        help="Fix font issues that should be fixed in the source files."
    )
    args = parser.parse_args()

    font = TTFont(args.font)

    if "DSIG" not in font:
        add_dummy_dsig(font)

    if "fpgm" in font:
        fix_hinted_font(font)
    else:
        fix_unhinted_font(font)

    if "fvar" in font:
        remove_tables(font, ["MVAR"])

    if args.include_source_fixes:
        log.warning(
            "include-source-fixes is enabled. Please consider fixing the "
            "source files instead."
        )
        remove_tables(font)
        fix_nametable(font)
        fix_fs_type(font)
        fix_fs_selection(font)
        fix_mac_style(font)
        fix_weight_class(font)
        # TODO inherit vertical metrics if font exists on Google Fonts

        if "fvar" in font:
            fix_fvar_instances(font)
            # TODO (Marc F) add gen-stat once merged 
            # https://github.com/googlefonts/gftools/pull/263

    if args.out:
        font.save(args.out)
    else:
        font.save(font.reader.file.name + ".fix")


if __name__ == "__main__":
    main()
