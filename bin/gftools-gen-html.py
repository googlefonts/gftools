#!/usr/bin/env python3
"""
gftools gen-html aka diffbrowsers2.

Generate html documents to proof a font family, or generate documents to
diff two families.

Examples:
# Generate proofing documents for a single font
gftools gen-html proof font1.ttf

# Generate proofing documents for a family of fonts
gftools gen-html proof font1.ttf font2.ttf font3.ttf

# Output test pages to a dir
gftools gen-html proof font1.ttf -o ~/Desktop/myFamily

# Generate proofing documents and output images using Browserstack
# (a subscription is required)
gftools gen-html proof font1.ttf --imgs

# Generate diff documents
gftools gen-html diff -fb ./fonts_before/font1.ttf -fa ./fonts_after/font1.ttf
"""
from pkg_resources import resource_filename
from gftools.html import HtmlProof, HtmlDiff
from fontTools.ttLib import TTFont
from glob import glob
import os
import argparse
import shutil


def main():
    html_templates_dir = resource_filename("gftools", "templates")

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="command", required=True, metavar='"proof" or "diff"'
    )

    # Optional args which can be used in all subparsers
    universal_options_parser = argparse.ArgumentParser(add_help=False)
    universal_options_parser.add_argument(
        "--pages",
        nargs="+",
        help="Choose which templates to populate. By default, all templates "
        "are populated.",
    )
    universal_options_parser.add_argument(
        "--pt-size", "-pt", help="Change pt size of document text", default=14
    )
    universal_options_parser.add_argument(
        "--imgs",
        action="store_true",
        help="Output images using Browserstack.",
    )
    universal_options_parser.add_argument(
        "--out", "-o", help="Output dir", default="diffbrowsers"
    )
    universal_options_parser.add_argument(
        "--template-dir",
        "-td",
        help="HTML template directory. By default, gftools/templates is used.",
        default=resource_filename("gftools", "templates"),
    )

    proof_parser = subparsers.add_parser(
        "proof",
        parents=[universal_options_parser],
        help="Generate html proofing documents for a family",
    )
    proof_parser.add_argument("fonts", nargs="+")

    diff_parser = subparsers.add_parser(
        "diff",
        parents=[universal_options_parser],
        help="Generate html diff documents which compares two families. "
        "Variable fonts can be compared against static fonts because we "
        "match the fvar instances against the static fonts. To Match fonts "
        "we use the font's name table records. For static fonts, the fullname "
        "is used e.g 'Maven Pro Medium'. For variable fonts, the family name "
        "+ fvar instance subfamilyname is used e.g 'Maven Pro' + 'Medium'.",
    )
    diff_parser.add_argument("--fonts-before", "-fb", nargs="+", required=True)
    diff_parser.add_argument("--fonts-after", "-fa", nargs="+", required=True)

    args = parser.parse_args()

    if args.command == "proof":
        html = HtmlProof(args.fonts, args.out, template_dir=args.template_dir)

    elif args.command == "diff":
        html = HtmlDiff(
            args.fonts_before,
            args.fonts_after,
            args.out,
            template_dir=args.template_dir,
        )

    html.build_pages(args.pages, pt_size=args.pt_size)

    if args.imgs:
        html.save_imgs()


if __name__ == "__main__":
    main()
