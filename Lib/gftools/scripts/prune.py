#!/usr/bin/env python3
"""
gftools prune

Remove unreachable glyphs/features from a font binary

usage: gftools [-h] [-o OUT] font

positional arguments:
  font               path to font

options:
  -h, --help         show this help message and exit
  -o OUT, --out OUT  output path for pruned font
"""

import argparse
import logging
import sys

from fontTools.subset import main as subset

logging.basicConfig(level=logging.INFO)


def main(args=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "font",
        help="path to font",
    )
    parser.add_argument(
        "-o",
        "--out",
        help="output path for pruned font",
    )

    args = parser.parse_args(args)
    try:
        subset(
            [
                args.font,
                "--unicodes=*",
                "--no-ignore-missing-glyphs",
                "--notdef-outline",
                "--layout-features=*",
                "--name-IDs=*",
                "--name-languages=*",
                "--glyph-names",
                "--no-prune-unicode-ranges",
                "--recalc-bounds",
                f"--output-file={args.out or args.font}",
            ]
        )
    except Exception as e:
        logging.error(
            "ERROR: subsetting error during attempt to subset %s: %s",
            args.font,
            str(e),
        )
        sys.exit(1)
