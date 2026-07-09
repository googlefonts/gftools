import argparse
from defcon import Font
from pathops import Path
from ufo2ft.filters.decomposeComponents import DecomposeComponentsFilter
from ufo2ft.preProcessor import TTFPreProcessor
import math
from fontTools.designspaceLib import DesignSpaceDocument


def set_overlap_bits(ufo):
    # Skip setting bits if ufo
    if any(g.lib.get("public.truetype.overlap") for g in ufo):
        return
    # Decompose components first because some component glyphs may have
    # components that overlap each other
    outline_glyphset = TTFPreProcessor(
        ufo, filters=[DecomposeComponentsFilter()]
    ).process()

    overlaps = set()
    for glyph in outline_glyphset.values():
        skia_path = Path()
        pen = skia_path.getPen()
        for contour in glyph:
            contour.draw(pen)
        area = skia_path.area
        # rm overlaps
        skia_path.simplify()
        simplified_area = skia_path.area
        if not math.isclose(area, simplified_area, abs_tol=0.1):
            ufo[glyph.name].lib["public.truetype.overlap"] = True
            overlaps.add(glyph.name)
    return overlaps


def main(args=None):
    parser = argparse.ArgumentParser(description="Set the overlap bits of a ufo/ds")
    parser.add_argument("input", help="Input UFO or Designspace file", nargs="+")
    args = parser.parse_args(args)

    ufos = []
    for fp in args.input:
        if fp.endswith(".ufo"):
            ufos.append(Font(fp))
        elif fp.endswith(".designspace"):
            ds = DesignSpaceDocument.fromfile(fp)
            for src in ds.sources:
                ufos.append(Font(src.path))
        else:
            raise NotImplementedError(f"Not supported file type: {fp}")

    for ufo in ufos:
        overlapping_glyphs = set_overlap_bits(ufo)
        if overlapping_glyphs:
            print(f"Overlap flags set for {len(overlapping_glyphs)} glyphs")
            ufo.save()


if __name__ == "__main__":
    main()
