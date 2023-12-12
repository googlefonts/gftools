import argparse
from vttLib.transfer import merge_from_file as merge_vtt_hinting
from vttLib import compile_instructions as compile_vtt_hinting
from fontTools.ttLib import TTFont, newTable


def compile_vtt(font, vtt_source):
    merge_vtt_hinting(font, vtt_source, keep_cvar=True)
    compile_vtt_hinting(font, ship=True)

    # Add a gasp table which is optimised for VTT hinting
    # https://googlefonts.github.io/how-to-hint-variable-fonts/
    gasp_tbl = newTable("gasp")
    gasp_tbl.gaspRange = {8: 10, 65535: 15}
    gasp_tbl.version = 1
    font["gasp"] = gasp_tbl


def main(args=None):
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument("-o", "--output", metavar="TTF", help="file to save on")
    parser.add_argument("font", metavar="TTF", help="font file")
    parser.add_argument("vtt", metavar="TTX", help="hints instruction file")
    args = parser.parse_args()

    font = TTFont(args.font)
    if not args.output:
        args.output = args.font

    compile_vtt(font, args.vtt)

    font.save(args.output)


if __name__ == "__main__":
    main()
