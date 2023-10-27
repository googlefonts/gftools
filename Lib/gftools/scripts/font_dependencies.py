"""
gftools font-dependencies

Add the dependencies used to generate the font to the font's Debg table or
dump a font's dependencies in order to make a pip requirements file.

Usage:

Build font dependencies:
gftools font-dependencies build font.ttf -o font-deps.ttf
gftools font-dependencies build font.ttf --inplace

gftools font-dependencies dump font.ttf
gftools font-dependencies dump font.ttf -o requirements.txt
"""
from argparse import ArgumentParser
from gftools.builder.dependencies import build_font_requirements, dump_font_requirements
from fontTools.ttLib import TTFont


def main(args=None):
    parser = ArgumentParser(description=__doc__)
    universal_options_parser = ArgumentParser(add_help=False)
    universal_options_parser.add_argument("font", help="Path to font", type=str)

    subparsers = parser.add_subparsers(
        dest="command", required=True, metavar='"build" or "dump"'
    )

    build_parser = subparsers.add_parser(
        "build",
        parents=[universal_options_parser],
        help="Add a debg table to a font which contains the build's dependencies",
    )
    out_group = build_parser.add_mutually_exclusive_group()
    out_group.add_argument("--inplace", help="Overwrite font", action="store_true")
    out_group.add_argument("-o", "--out", help="Output path for new font")

    dump_parser = subparsers.add_parser(
        "dump", parents=[universal_options_parser], help="Dump a font's dependencies"
    )
    dump_parser.add_argument(
        "-o", "--out", help="output a requirements file to specified path"
    )
    args = parser.parse_args(args)

    ttfont = TTFont(args.font)

    if args.command == "build":
        build_font_requirements(ttfont, "gftools")
        if args.inplace:
            ttfont.save(ttfont.reader.file.name)
        elif args.out:
            ttfont.save(args.out)
        else:
            ttfont.save(ttfont.reader.file.name + ".fix")
    elif args.command == "dump":
        requirements = dump_font_requirements(ttfont)
        if args.out:
            with open(args.out, "w") as doc:
                doc.write(requirements)
        else:
            print(requirements)


if __name__ == "__main__":
    main()
