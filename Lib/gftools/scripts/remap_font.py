#!/usr/bin/env python3
"""
Remap a font's encoded glyphs.

Changes font cmap table. User can also specify their
own output path.

Usage:

gftools remap-font --deep -o font-remap.ttf font.ttf A=A.alt B=B.alt U+0175=wcircumflex.alt
gftools remap-font --map-file=remapping.txt -o font-remap.ttf font.ttf
"""
import argparse
import sys

from fontTools.ttLib import TTFont


def grovel_substitutions(font, lookup, glyphmap):
    if lookup.LookupType == 7:
        raise NotImplementedError
    gmap = lambda g: glyphmap.get(g, g)
    go = font.getGlyphOrder()

    def do_coverage(c):
        c.glyphs = list(sorted([gmap(g) for g in c.glyphs], key=lambda g: go.index(g)))
        return c

    for st in lookup.SubTable:
        if lookup.LookupType == 1:
            newmap = {}
            for inglyph, outglyph in st.mapping.items():
                newmap[gmap(inglyph)] = gmap(outglyph)
            st.mapping = newmap
        elif lookup.LookupType == 2:
            newmap = {}
            for inglyph, outglyphs in st.mapping.items():
                newmap[gmap(inglyph)] = [gmap(g) for g in outglyphs]
            st.mapping = newmap
        elif lookup.LookupType == 4:
            newligatures = {}
            for outglyph, inglyphs in st.ligatures.items():
                for ig in inglyphs:
                    ig.LigGlyph = gmap(ig.LigGlyph)
                    ig.Component = [gmap(c) for c in ig.Component]
                newligatures[gmap(outglyph)] = inglyphs
            st.ligatures = newligatures
        elif lookup.LookupType == 5:
            if st.Format == 1:
                do_coverage(st.Coverage)
                for srs in st.SubRuleSet:
                    for subrule in srs.SubRule:
                        subrule.Input = [gmap(c) for c in subrule.Input]
            elif st.Format == 2:
                do_coverage(st.Coverage)
                st.ClassDef.classDefs = {
                    gmap(k): v for k, v in st.ClassDef.classDefs.items()
                }
            else:
                st.Coverage = [do_coverage(c) for c in st.Coverage]
        elif lookup.LookupType == 6:
            if st.Format == 1:
                do_coverage(st.Coverage)
                for srs in st.ChainSubRuleSet:
                    for subrule in srs.ChainSubRule:
                        subrule.Backtrack = [gmap(c) for c in subrule.Backtrack]
                        subrule.Input = [gmap(c) for c in subrule.Input]
                        subrule.LookAhead = [gmap(c) for c in subrule.LookAhead]
            elif st.Format == 2:
                do_coverage(st.Coverage)
                st.BacktrackClassDef.classDefs = {
                    gmap(k): v for k, v in st.BacktrackClassDef.classDefs.items()
                }
                st.InputClassDef.classDefs = {
                    gmap(k): v for k, v in st.InputClassDef.classDefs.items()
                }
                st.LookAheadClassDef.classDefs = {
                    gmap(k): v for k, v in st.LookAheadClassDef.classDefs.items()
                }
            elif st.Format == 3:
                st.BacktrackCoverage = [do_coverage(c) for c in st.BacktrackCoverage]
                st.InputCoverage = [do_coverage(c) for c in st.InputCoverage]
                st.LookAheadCoverage = [do_coverage(c) for c in st.LookAheadCoverage]


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-file", metavar="TXT", help="Newline-separated mappings")
    parser.add_argument("--output", "-o", metavar="TTF", help="Output font binary")
    parser.add_argument(
        "--deep", action="store_true", help="Also remap inside GSUB table"
    )
    parser.add_argument("font", metavar="TTF", help="Input font binary")
    parser.add_argument("mapping", nargs="*", help="Codepoint-to-glyph mapping")

    args = parser.parse_args(args)

    if not args.mapping and not args.map_file:
        print("You must either specify a mapping or a map file")
        sys.exit(1)
    if args.mapping and args.map_file:
        print("You must specify either a mapping or a map file, not both")
        sys.exit(1)

    mapping = {}
    font = TTFont(args.font)

    if args.map_file:
        incoming_map = open(args.map_file).readlines()
    else:
        incoming_map = args.mapping

    glyph_mapping = {}  # Map glyphname->glyphname
    cmap = font.getBestCmap()

    for entry in incoming_map:
        entry = entry.strip()
        if not entry or entry.startswith("#"):
            continue
        codepoint, newglyph = entry.split("=")
        if codepoint.startswith("U+") or codepoint.startswith("0x"):
            codepoint = int(codepoint[2:], 16)
        else:
            codepoint = ord(codepoint)
        mapping[codepoint] = newglyph
        if newglyph not in font.getGlyphOrder():
            print(
                f"Glyph '{newglyph}' (to be mapped to U+{codepoint:04X}) not found in font"
            )
            sys.exit(1)
        if codepoint in cmap:
            glyph_mapping[cmap[codepoint]] = newglyph

    if args.deep:
        for lookup in font["GSUB"].table.LookupList.Lookup:
            grovel_substitutions(font, lookup, glyph_mapping)

    cmap = font["cmap"]
    for table in cmap.tables:
        for codepoint, glyph in mapping.items():
            table.cmap[codepoint] = glyph

    if args.output:
        out = args.output
    else:
        out = args.font
    print(f"Saving font: {out}")
    font.save(out)


if __name__ == "__main__":
    main()
