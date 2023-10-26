"""
gftools gen-debg-deps
Add the dependencies used to generate the font to the font's Debg table

Usage:

gftools gen-debg-deps font.ttf -o font-deps.ttf
gftools gen-debg-deps font.ttf --inplace
"""
from argparse import ArgumentParser
from gftools.builder.dependencies import requirements_to_debg_table
from fontTools.ttLib import TTFont


def main(args=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("font", help="Path to font")
    parser.add_argument("--inplace", help="Overwrite font", action="store_true")
    parser.add_argument("-o", "--out", help="Output path for new font")
    args = parser.parse_args(args)

    ttfont = TTFont(args.font)
    requirements_to_debg_table(ttfont, "gftools")

    if args.inplace:
        ttfont.save(ttfont.reader.file.name)
    elif args.out:
        ttfont.save(args.out)
    else:
        ttfont.save(ttfont.reader.file.name + ".fix")


if __name__ == "__main__":
    main()
