"""
Rename glyph names in font_1 with font_2.

Usage:
gftools rename-glyphs font_1.ttf font_2.ttf out font_1-renamed.ttf
"""
from fontTools.ttLib import TTFont
from ufo2ft.postProcessor import PostProcessor, _reloadFont
from argparse import ArgumentParser


def main(args=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("font_1")
    parser.add_argument("font_2")
    parser.add_argument("-o", "--out", default="out-renamed.ttf")
    args = parser.parse_args(args)

    font1 = TTFont(args.font_1)
    font2 = TTFont(args.font_2)
    
    name_map = dict(zip(font1.getGlyphOrder(), font2.getGlyphOrder()))

    font1 = _reloadFont(font1)
    PostProcessor.rename_glyphs(font1, name_map)
    font1.save(args.out)


if __name__ == "__main__":
    main()
