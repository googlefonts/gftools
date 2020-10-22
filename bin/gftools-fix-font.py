#!/usr/bin/env python3
"""
gftools fix-font

Update a font so it conforms to the Google Fonts specification
https://github.com/googlefonts/gf-docs/tree/master/Spec
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
    parser.add_argument("--hotfix", action="store_true", help="Hotfix fonts.")
    args = parser.parse_args()

    font = TTFont(args.font)

    if "DSIG" not in font:
        log.info("Adding dummy dsig")
        add_dummy_dsig(font)

    if "fpgm" in font:
        log.info("Improving hinted render quality")
        fix_hinted_font(font)
    else:
        log.info("Improving unhinted render quality")
        fix_unhinted_font(font)

    if args.hotfix:
        log.warning("Hotfixing fonts. Please consider fixing the source files instead")
        log.info("Fixing fsSelection")
        fix_fs_selection(font)
        log.info("Fixing macStyle")
        fix_mac_style(font)
        # TODO usWeightClass, nametable...

        if "fvar" in font:
            fix_fvar_instances(font)

    if args.out:
        font.save(args.out)
    else:
        font.save(font.reader.file.name + ".fix")


if __name__ == "__main__":
    main()
