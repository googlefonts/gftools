#!/usr/bin/env python3
"""
gftools gen-html aka diffbrowsers2.

Generate html proofing pages for a family or diff pages which compares
two families.

Examples:
# Generate test pages for a single font
gftools gen-html proof font1.ttf

# Generate test pages for a family of fonts
gftools gen-html proof font1.ttf font2.ttf font3.ttf

# Output test pages to a dir
gftools gen-html proof font1.ttf -o ~/Desktop/myFamily

# Generate test pages and output images using Browserstack
# (a subscription is required)
gftools gen-html proof font1.ttf --imgs

# Generate diff comparison (font stylenames/fvar instance names must match!)
gftools gen-html diff ./fonts_after/font1.ttf -fb ./fonts_before/font1.ttf
"""
from gftools.html import HtmlProof, HtmlDiff
from fontTools.ttLib import TTFont
from glob import glob
import os
import argparse
import shutil


def create_package(fonts, out="out"):
    if os.path.isdir(out):
        shutil.rmtree(out)

    fonts_dir = os.path.join(out, "fonts")

    [os.mkdir(d) for d in (out, fonts_dir)]
    [shutil.copy(f, fonts_dir) for f in fonts]

    return (glob(os.path.join(fonts_dir, "*.ttf")), out)


def create_diff_package(fonts_before, fonts_after, out="out"):
    if os.path.isdir(out):
        shutil.rmtree(out)

    fonts_before_dir = os.path.join(out, "fonts_before")
    fonts_after_dir = os.path.join(out, "fonts_after")

    [os.mkdir(d) for d in (out, fonts_after_dir, fonts_before_dir)]
    [shutil.copy(f, fonts_before_dir) for f in fonts_before]
    [shutil.copy(f, fonts_after_dir) for f in fonts_after]

    return (
        glob(os.path.join(fonts_before_dir, "*.ttf")),
        glob(os.path.join(fonts_after_dir, "*.ttf")),
        out,
    )


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="command", required=True, metavar='"proof" or "diff"'
    )

    # Optional args which can be used in all subparsers
    universal_options_parser = argparse.ArgumentParser(add_help=False)
    universal_options_parser.add_argument(
        "--views",
        nargs="+",
    )
    universal_options_parser.add_argument(
        "--pt-size", "-pt", help="pt size of text", default=14
    )
    universal_options_parser.add_argument(
        "--imgs",
        action="store_true",
        help="Output images using Browserstack.",
    )
    universal_options_parser.add_argument(
        "--out", "-o", help="Output dir", default="diffbrowsers"
    )

    proof_parser = subparsers.add_parser(
        "proof",
        parents=[universal_options_parser],
        help="produce html proofing pages for a single set of fonts",
    )
    proof_parser.add_argument("fonts", nargs="+")

    diff_parser = subparsers.add_parser(
        "diff",
        parents=[universal_options_parser],
        help="produce html diff pages which compare two sets of fonts. "
        "Fonts are matched by their css properties e.g font-weight, font-width",
    )
    diff_parser.add_argument("--fonts-before", "-fa", nargs="+", required=True)
    diff_parser.add_argument("--fonts-after", "-fb", nargs="+", required=True)

    args = parser.parse_args()

    if args.command == "proof":
        fonts, out = create_package(args.fonts, args.out)
        ttFonts = [TTFont(f) for f in fonts]
        html = HtmlProof(ttFonts, out)

    elif args.command == "diff":
        fonts_before, fonts_after, out = create_diff_package(
            args.fonts_before, args.fonts_after, args.out
        )
        ttFonts_before = [TTFont(f) for f in fonts_before]
        ttFonts_after = [TTFont(f) for f in fonts_after]
        html = HtmlDiff(ttFonts_before, ttFonts_after, out)

    html.build_pages(['waterfall.html', 'text.html'], pt_size=args.pt_size)

    if args.imgs:
        html.save_imgs()


if __name__ == "__main__":
    main()
