"""Give a compiled TrueType font another font's TrueType hinting.

Usage:

    gftools transfer-hints SRC DST [-o OUT]

SRC is the hinted font (a .ttf, or a .ttx dump of one); DST is the font to hint,
built from sources that draw the same glyphs (OUT defaults to DST).

The tables that hold the hinting are copied whole: fpgm, prep, cvt, gasp, the
TrueType limits in maxp, head flags 2, 3 and 4, and hdmx, LTSH and VDMX.

A glyph program addresses the glyph's points by index, so it only works on the
points it was written for. For each glyph SRC instructs, DST must draw the same
outline: the same contours, which may start at another point, may lack on-curve
points exactly halfway between two off-curves (compilers drop them as implied)
or a point repeating the one before it, may lack a contour of a single point
(which draws nothing), and may be shifted horizontally; a composite must have the same components. Every
glyph that does takes SRC's glyph -- its points, recorded box, side bearing and
program -- so each program meets its points, and a composite placing a glyph drawn
shifted takes SRC's offsets. An instructed glyph that does not is refused, with
its reason, and nothing is written.
"""

import argparse
import copy

from fontTools.ttLib import TTFont

TABLES = ("fpgm", "prep", "cvt ", "gasp", "hdmx", "LTSH", "VDMX")
MAXP = (
    "maxZones",
    "maxTwilightPoints",
    "maxStorage",
    "maxFunctionDefs",
    "maxInstructionDefs",
    "maxStackElements",
    "maxSizeOfInstructions",
)
HEAD_FLAGS = (
    0x04 | 0x08 | 0x10
)  # instructions depend on size, integer ppem, alter advance


def load(path):
    if path.lower().endswith(".ttx"):
        font = TTFont()
        font.importXML(path)
        return font
    return TTFont(path)


def has_program(glyph):
    program = getattr(glyph, "program", None)
    return program is not None and len(program.getBytecode()) > 0


def contours(glyph):
    """Each contour as a list of (x, y, on-curve) points."""
    if glyph.numberOfContours <= 0:
        return []
    out, start = [], 0
    for end in glyph.endPtsOfContours:
        out.append(
            [
                (x, y, glyph.flags[i] & 1)
                for i, (x, y) in enumerate(glyph.coordinates[start : end + 1], start)
            ]
        )
        start = end + 1
    return out


def without_implied(contour):
    """The contour without on-curve points exactly halfway between two off-curves, and
    without a point that repeats the one before it (a zero-length segment)."""
    contour = [
        p for i, p in enumerate(contour) if len(contour) == 1 or p != contour[i - 1]
    ]
    n = len(contour)
    keep = []
    for i, (x, y, on) in enumerate(contour):
        (px, py, pon), (nx, ny, non) = contour[i - 1], contour[(i + 1) % n]
        if on and not pon and not non and px + nx == 2 * x and py + ny == 2 * y:
            continue
        keep.append((x, y, on))
    return keep


def same_cycle(a, b):
    """Whether two closed contours are the same points from another start."""
    if len(a) != len(b):
        return False
    if not a:
        return True
    return any(b[i:] + b[:i] == a for i, p in enumerate(b) if p == a[0])


def same_outline(src, dst):
    """Whether two simple glyphs draw the same outline (see the module docstring)."""
    # a contour of fewer than two points draws nothing, and compilers drop it
    a = [c for c in (without_implied(c) for c in contours(src)) if len(c) > 1]
    b = [c for c in (without_implied(c) for c in contours(dst)) if len(c) > 1]
    if len(a) != len(b):
        return False
    xa = [x for c in a for x, _, _ in c]
    xb = [x for c in b for x, _, _ in c]
    if not xa or not xb:
        return not xa and not xb
    dx = min(xa) - min(xb)
    b = [[(x + dx, y, on) for x, y, on in c] for c in b]
    return all(same_cycle(ca, cb) for ca, cb in zip(a, b))


def name_map(src, dst):
    """SRC glyph name -> DST glyph name: by name, else by index when a release's
    names are not the build's (no names, duplicates) and both have as many glyphs."""
    so, do = src.getGlyphOrder(), dst.getGlyphOrder()
    names = set(do)
    by_index = len(so) == len(do)
    return {
        s: s if s in names else (do[i] if by_index else None) for i, s in enumerate(so)
    }


def transfer(src, dst):
    """Give DST the hinting of SRC; return the refused glyphs as {name: reason}.
    Open DST with recalcBBoxes=False so the recorded boxes taken from SRC are saved."""
    to_dst = name_map(src, dst)
    sg, dg = src["glyf"], dst["glyf"]
    refused, taken = {}, []
    for name in src.getGlyphOrder():
        glyph, target = sg[name], to_dst[name]
        if target is None:
            reason = "not in the font"
        elif src["hmtx"][name][0] != dst["hmtx"][target][0]:
            reason = "another advance"
        elif glyph.isComposite():
            built = dg[target]
            same = built.isComposite() and [
                to_dst[c.glyphName] for c in glyph.components
            ] == [c.glyphName for c in built.components]
            reason = None if same else "other components"
        else:
            built = dg[target]
            reason = (
                None
                if not built.isComposite() and same_outline(glyph, built)
                else "another outline"
            )
        if reason is None:
            # every glyph drawing the same outline takes SRC's points, so a composite
            # placing a glyph drawn shifted takes SRC's offsets too
            taken.append((name, target))
        elif has_program(glyph):
            refused[name] = reason
    if refused:
        return refused
    for name, target in taken:
        glyph = copy.deepcopy(sg[name])
        if glyph.isComposite():
            for component in glyph.components:
                component.glyphName = to_dst[component.glyphName]
        dg[target] = glyph
        dst["hmtx"][target] = src["hmtx"][name]
    for tag in TABLES:
        if tag in src:
            dst[tag] = copy.deepcopy(src[tag])
        elif tag in dst:
            del dst[tag]
    if "hdmx" in dst:
        dst["hdmx"].hdmx = {
            ppem: {to_dst[g]: w for g, w in widths.items()}
            for ppem, widths in dst["hdmx"].hdmx.items()
        }
    if "LTSH" in dst:
        dst["LTSH"].yPels = {to_dst[g]: v for g, v in dst["LTSH"].yPels.items()}
    for attr in MAXP:
        setattr(dst["maxp"], attr, getattr(src["maxp"], attr))
    dst["head"].flags = (dst["head"].flags & ~HEAD_FLAGS) | (
        src["head"].flags & HEAD_FLAGS
    )
    return {}


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("src", help="the hinted font (.ttf, or a .ttx dump of one)")
    parser.add_argument("dst", help="the font to hint")
    parser.add_argument("-o", "--output", help="the hinted font (default: DST)")
    args = parser.parse_args(args)
    # recorded boxes are kept: a taken glyph's may be stale, and a TrueType rasterizer
    # places the glyph by it
    src, dst = load(args.src), TTFont(args.dst, recalcBBoxes=False)
    refused = transfer(src, dst)
    if refused:
        lines = ["%s: %s" % kv for kv in sorted(refused.items())]
        parser.exit(
            1,
            "%d instructed glyph(s) refused, nothing written:\n  %s\n"
            % (len(refused), "\n  ".join(lines[:40])),
        )
    dst.save(args.output or args.dst)


if __name__ == "__main__":
    main()
