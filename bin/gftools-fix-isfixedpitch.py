"""Fix a collection of fonts isfixedpitch flag"""
from fontTools.ttLib import TTFont
import argparse


def fix_isFixedPitch(ttfont):

    same_width = set()
    glyph_metrics = ttfont['hmtx'].metrics
    for character in [chr(c) for c in range(65, 91)]:
        same_width.add(glyph_metrics[character][0])

    if len(same_width) == 1:
        if ttfont['post'].isFixedPitch == 1:
            print("Skipping isFixedPitch is set correctly")
        else:
            print("Font is monospace. Updating isFixedPitch to 0")
            ttfont['post'].isFixedPitch = 1
    else:
        ttfont['post'].isFixedPitch = 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", nargs="+", required=True)
    args = parser.parse_args()

    for font in args.fonts:
        ttfont = TTFont(font)
        fix_isFixedPitch(ttfont)

        new_font = font + ".fix"
        print("Saving font to {}".format(new_font))
        ttfont.save(new_font)


if __name__ == "__main__":
    main()

