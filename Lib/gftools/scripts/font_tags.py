"""
gftools font-tags

Export Font classification tags to csv, or check the spreadsheet
is still structured correctly.

Usage:
# Write tags csv file to google/fonts/tags/all/families.csv
gftools font-tags write path/to/google/fonts

# Check Google Sheet is still structured correctly
gftools font-tags lint path/to/google/fonts
"""
import os
from pathlib import Path
import sys
from gftools.tags import GFTags
from argparse import ArgumentParser
from gftools.utils import is_google_fonts_repo


def main(args=None):
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="command", required=True, metavar='"write" or "lint"'
    )
    universal_options_parser = ArgumentParser(add_help=False)
    universal_options_parser.add_argument("gf_path", type=Path)

    write_parser = subparsers.add_parser(
        "write",
        parents=[universal_options_parser],
        help="Write Google Sheet to google/fonts csv file",
    )
    lint_parser = subparsers.add_parser(
        "lint",
        parents=[universal_options_parser],
        help="Check Google Sheet is structured correctly",
    )
    args = parser.parse_args(args)

    if not is_google_fonts_repo(args.gf_path):
        raise ValueError(f"'{args.gf_path.absolute()}' is not a path to a valid google/fonts repo")

    gf_tags = GFTags()

    if args.command == "write":
        out_dir = args.gf_path / "tags" / "all"
        if not out_dir.exists():
            os.makedirs(out_dir)
        out = out_dir / "families.csv"
        gf_tags.to_csv(out)
    elif args.command == "lint":
        gf_tags.check_structure()


if __name__ == "__main__":
    main()
