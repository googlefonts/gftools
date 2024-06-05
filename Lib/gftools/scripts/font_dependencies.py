#!/usr/bin/env python3
"""
gftools font-dependencies

Write the dependencies used to generate a font to its Debg table or
read a font's dependencies in order to make a pip requirements file.

Usage:

Write font dependencies:
gftools font-dependencies write font.ttf -o font-deps.ttf
gftools font-dependencies write font.ttf --inplace

Read font dependencies:
gftools font-dependencies read font.ttf
gftools font-dependencies read font.ttf -o requirements.txt
"""
from argparse import ArgumentParser
from gftools.builder.dependencies import write_font_requirements, read_font_requirements
from fontTools.ttLib import TTFont
from fontTools.misc.cliTools import makeOutputFileName


def main(args=None):
    parser = ArgumentParser(description=__doc__)
    universal_options_parser = ArgumentParser(add_help=False)
    universal_options_parser.add_argument("font", help="Path to font", type=str)

    subparsers = parser.add_subparsers(
        dest="command", required=True, metavar='"read" or "write"'
    )

    build_parser = subparsers.add_parser(
        "write",
        parents=[universal_options_parser],
        help="Add a debg table to a font which contains the build's dependencies",
    )
    out_group = build_parser.add_mutually_exclusive_group()
    out_group.add_argument("--inplace", help="Overwrite font", action="store_true")
    out_group.add_argument("-o", "--out", help="Output path for new font")

    dump_parser = subparsers.add_parser(
        "read", parents=[universal_options_parser], help="Dump a font's dependencies"
    )
    dump_parser.add_argument(
        "-o", "--out", help="output a requirements file to specified path"
    )
    args = parser.parse_args(args)

    ttfont = TTFont(args.font)

    if args.command == "write":
        write_font_requirements(ttfont, "gftools")
        if args.inplace:
            ttfont.save(ttfont.reader.file.name)
        elif args.out:
            ttfont.save(args.out)
        else:
            out = makeOutputFileName(ttfont.reader.file.name)
            ttfont.save(out)
    elif args.command == "read":
        try:
            requirements = read_font_requirements(ttfont)
        except KeyError:
            parser.error("Font doesn't contain dependencies")
        if args.out:
            with open(args.out, "w") as doc:
                doc.write(requirements)
        else:
            print(requirements)


if __name__ == "__main__":
    main()
