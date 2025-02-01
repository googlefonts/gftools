#!/usr/bin/env python3
"""Check a font family using Google Fonts QA tools.

Examples:
Check a local family against the same family hosted on Google Fonts:
`gftools qa -f [fonts.ttf] -gfb -a -o qa`

Check a local family against another local family and generate reports
for Font Diffenator only:
`gftools qa -f [fonts_a.ttf] -fb [fonts_b.ttf] --diffenator -o qa`


Compare a pull request against the same family hosted on Google Fonts:
`gftools qa -pr www.github.com/user/repo/pull/1 -gfb -a -o qa`

Compare a github folder of fonts against the same family hosted on Google
Fonts:
`gftools qa -gh www.github.com/user/repo/tree/fonts/ttf -gfb -a -o qa`
"""
from fontTools.ttLib import TTFont
import argparse
import os
import sys
import shutil
import logging
from gftools.utils import (
    download_family_from_Google_Fonts,
    download_files_in_github_pr,
    download_files_in_github_dir,
    download_files_from_archive,
    Google_Fonts_has_family,
    mkdir,
)
import re
from gftools.qa import FontQA
from diffenator2.font import DFont


__version__ = "3.1.0"
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def family_name_from_fonts(fonts):
    results = set(f.family_name for f in fonts)
    if len(results) > 1:
        raise Exception("Multiple family names found: [{}]".format(", ".join(results)))
    return list(results)[0]


def main(args=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )

    font_group = parser.add_argument_group(title="Fonts to qa")
    font_input_group = font_group.add_mutually_exclusive_group(required=True)
    font_input_group.add_argument("-f", "--fonts", nargs="+", help="Paths to fonts")
    font_input_group.add_argument(
        "-pr", "--pull-request", help="Get fonts from a Github pull request"
    )
    font_input_group.add_argument(
        "-gh", "--github-dir", help="Get fonts from a Github directory"
    )
    font_input_group.add_argument(
        "-gf", "--googlefonts", help="Get fonts from Google Fonts"
    )
    font_input_group.add_argument(
        "-ar", "--archive", help="Get fonts from a zip file URL"
    )

    font_before_group = parser.add_argument_group(title="Fonts before input")
    font_before_input_group = font_before_group.add_mutually_exclusive_group(
        required=False
    )
    font_before_input_group.add_argument(
        "-fb", "--fonts-before", nargs="+", help="Paths to previous fonts"
    )
    font_before_input_group.add_argument(
        "-prb",
        "--pull-request-before",
        help="Get previous fonts from a Github pull request",
    )
    font_before_input_group.add_argument(
        "-ghb", "--github-dir-before", help="Get previous fonts from a Github dir"
    )
    font_before_input_group.add_argument(
        "-arb", "--archive-before", help="Get previous fonts from a zip file URL"
    )
    font_before_input_group.add_argument(
        "-gfb",
        "--googlefonts-before",
        action="store_true",
        help="Get previous fonts from Google Fonts",
    )

    check_group = parser.add_argument_group(title="QA checks")
    check_group.add_argument(
        "-a",
        "--auto-qa",
        action="store_true",
        help="Check fonts against against the same fonts hosted on Google Fonts",
    )
    check_group.add_argument(
        "--diffenator", action="store_true", help="Run Fontdiffenator"
    )
    check_group.add_argument("--proof", action="store_true", help="Run HTML proofs")
    check_group.add_argument(
        "--render",
        action="store_true",
        help="Run diffbrowsers if fonts_before exist, otherwise run proof",
    )
    check_group.add_argument("--fontbakery", action="store_true", help="Run FontBakery")
    check_group.add_argument(
        "--diffbrowsers", action="store_true", help="Run Diffbrowsers"
    )
    check_group.add_argument(
        "--interpolations", action="store_true", help="Run interpolation checker"
    )
    parser.add_argument("-re", "--filter-fonts", help="Filter fonts by regex")
    parser.add_argument(
        "-o", "--out", default="out", help="Output path for check results"
    )
    parser.add_argument(
        "-ogh",
        "--out-github",
        action="store_true",
        help=(
            "Post report data to either the pull request as a comment "
            "open a new issue. This can only be used if fonts have been "
            "fetched from either a pull request or github dir."
        ),
    )
    parser.add_argument(
        "--out-url",
        help=(
            "Post report data to a github pr. This can be used with any font "
            "fetching method."
        ),
    )
    check_group.add_argument(
        "--extra-fontbakery-args",
        help="Additional arguments to FontBakery",
        action="append",
    )

    parser.add_argument("--imgs", action="store_true", help="Gen images using Selenium")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(args)
    if args.out_github and not any([args.pull_request, args.github_dir]):
        raise Exception(
            "Cannot upload results to a github issue or pr. "
            "Font input must either a github dir or a pull request"
        )
    if not any(
        [
            args.auto_qa,
            args.fontbakery,
            args.proof,
            args.diffbrowsers,
            args.diffenator,
            args.render,
            args.interpolations,
        ]
    ):
        raise Exception(
            "Terminating. No checks selected. Run gftools qa "
            "--help to see all possible commands."
        )

    # Retrieve fonts and store in out dir
    mkdir(args.out)
    fonts_dir = os.path.join(args.out, "fonts")
    mkdir(fonts_dir)
    if args.fonts:
        [shutil.copy(f, fonts_dir) for f in args.fonts]
        fonts = args.fonts
    elif args.pull_request:
        fonts = download_files_in_github_pr(
            args.pull_request,
            fonts_dir,
            ignore_static_dir=False,
        )
        if not fonts:
            logger.info("No fonts found in pull request. Skipping")
            return
    elif args.github_dir:
        fonts = download_files_in_github_dir(args.github_dir, fonts_dir)
        if not fonts:
            logger.info("No fonts found in github dir. Skipping")
            return
    elif args.archive:
        fonts = download_files_from_archive(args.archive, fonts_dir)
    elif args.googlefonts:
        fonts = download_family_from_Google_Fonts(args.googlefonts, fonts_dir)

    if args.filter_fonts:
        re_filter = re.compile(args.filter_fonts)
        fonts = [f for f in fonts if re_filter.search(f)]

    dfonts = [
        DFont(f) for f in fonts if f.endswith((".ttf", ".otf")) and "static" not in f
    ]
    family_name = family_name_from_fonts(dfonts)
    family_on_gf = Google_Fonts_has_family(family_name)

    # Retrieve fonts_before and store in out dir
    fonts_before = None
    if any(
        [
            args.fonts_before,
            args.pull_request_before,
            args.github_dir_before,
            args.archive_before,
        ]
    ) or (args.googlefonts_before and family_on_gf):
        fonts_before_dir = os.path.join(args.out, "fonts_before")
        mkdir(fonts_before_dir, overwrite=False)
    if args.fonts_before:
        [shutil.copy(f, fonts_before_dir) for f in args.fonts_before]
        fonts_before = args.fonts_before
    elif args.pull_request_before:
        fonts_before = download_files_in_github_pr(
            args.pull_request_before, fonts_before_dir, ignore_static_dir=False
        )
    elif args.github_dir_before:
        fonts_before = download_files_in_github_dir(
            args.github_dir_before, fonts_before_dir
        )
    elif args.archive_before:
        fonts_before = download_files_from_archive(
            args.archive_before, fonts_before_dir
        )
    elif args.googlefonts_before and family_on_gf:
        fonts_before = download_family_from_Google_Fonts(family_name, fonts_before_dir)

    url = None
    if args.out_url:
        url = args.out_url
    elif args.out_github and args.pull_request:
        url = args.pull_request
    elif args.out_github and args.github_dir:
        url = args.github_dir

    if fonts_before:
        dfonts_before = [
            DFont(f)
            for f in fonts_before
            if f.endswith((".ttf", ".otf")) and "static" not in f
        ]
        qa = FontQA(dfonts, dfonts_before, args.out, url=url)
    else:
        qa = FontQA(dfonts, out=args.out, url=url)

    if args.auto_qa and family_on_gf:
        qa.googlefonts_upgrade(args.imgs)
    elif args.auto_qa and not family_on_gf:
        qa.googlefonts_new(args.imgs)
    if args.render:
        qa.render(args.imgs)
    if args.fontbakery:
        qa.fontbakery(extra_args=args.extra_fontbakery_args)
    if args.diffenator:
        qa.diffenator()
    if args.diffbrowsers:
        qa.diffbrowsers(args.imgs)
    if args.proof:
        qa.proof()
    if args.interpolations:
        qa.interpolations()

    if qa.has_error:
        logger.fatal("Fontbakery has raised a fatal error. Please fix!")
        sys.exit(1)


if __name__ == "__main__":
    main()
